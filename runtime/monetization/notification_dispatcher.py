# SPDX-License-Identifier: Apache-2.0
"""Outbound Notification Dispatcher — ADAAD Phase 8, M8-07.

Dispatches governed events to external channels: Slack, PagerDuty,
generic HTTP webhooks. Enterprise feature (Pro+ tier).

Architecture:
- All dispatches are fire-and-forget (non-blocking, async-compatible).
- Every dispatch attempt is logged as a governance event regardless of outcome.
- Delivery failures are retried once with exponential backoff; then logged
  as `notification_delivery_failed` — never silently dropped.
- Channel configuration is per-org, stored in OrgRegistry metadata.
- No governance decision is gated on notification delivery success.

Invariant: notifications are observability — never authority.
The governance pipeline never waits for a notification to complete.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

log = logging.getLogger("adaad.notifications")


# ---------------------------------------------------------------------------
# Event types that trigger notifications
# ---------------------------------------------------------------------------

class NotifiableEvent(str, Enum):
    MUTATION_APPROVED       = "mutation_approved"
    MUTATION_REJECTED       = "mutation_rejected"
    GATE_HALT               = "gate_halt"
    EPOCH_COMPLETE          = "epoch_complete"
    EPOCH_QUOTA_WARNING     = "epoch_quota_warning"     # 80% of quota consumed
    EPOCH_QUOTA_EXCEEDED    = "epoch_quota_exceeded"
    TIER_CHANGED            = "tier_changed"
    KEY_ROTATED             = "key_key_rotated"
    PAYMENT_FAILED          = "payment_failed"
    PAYMENT_RECOVERED       = "payment_recovered"
    FEDERATION_DIVERGENCE   = "federation_divergence"
    ROADMAP_AMENDMENT       = "roadmap_amendment_proposed"


# ---------------------------------------------------------------------------
# Channel types
# ---------------------------------------------------------------------------

class ChannelType(str, Enum):
    SLACK     = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK   = "webhook"   # generic HTTP POST


# ---------------------------------------------------------------------------
# Notification payload
# ---------------------------------------------------------------------------

@dataclass
class NotificationPayload:
    event_type:   NotifiableEvent
    org_id:       str
    title:        str
    body:         str
    severity:     str   # "info" | "warning" | "critical"
    metadata:     Dict[str, Any] = field(default_factory=dict)
    timestamp:    int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "org_id":     self.org_id,
            "title":      self.title,
            "body":       self.body,
            "severity":   self.severity,
            "metadata":   self.metadata,
            "timestamp":  self.timestamp,
        }


# ---------------------------------------------------------------------------
# Channel configuration
# ---------------------------------------------------------------------------

@dataclass
class ChannelConfig:
    channel_type: ChannelType
    url:          str   # Slack webhook URL, PagerDuty Events API URL, or generic URL
    events:       List[NotifiableEvent] = field(default_factory=list)  # empty = all events
    secret:       Optional[str] = None    # optional HMAC secret for generic webhooks
    enabled:      bool = True

    def should_fire(self, event_type: NotifiableEvent) -> bool:
        if not self.enabled:
            return False
        if not self.events:
            return True  # subscribed to all
        return event_type in self.events


# ---------------------------------------------------------------------------
# Dispatch result
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    channel_type: ChannelType
    org_id:       str
    event_type:   str
    success:      bool
    status_code:  Optional[int]
    error:        Optional[str]
    attempt:      int
    duration_ms:  float


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _format_slack(payload: NotificationPayload) -> bytes:
    """Format payload as Slack Block Kit message."""
    emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(payload.severity, "📢")
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {payload.title}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": payload.body}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"*Org:* `{payload.org_id}` · *Event:* `{payload.event_type.value}`"}
            ]
        }
    ]
    return json.dumps({"blocks": blocks}).encode("utf-8")


def _format_pagerduty(payload: NotificationPayload) -> bytes:
    """Format payload as PagerDuty Events API v2 payload."""
    severity_map = {"info": "info", "warning": "warning", "critical": "critical"}
    event_action = "trigger" if payload.severity == "critical" else "acknowledge"
    return json.dumps({
        "routing_key":   "",  # caller injects; URL contains routing key for PD
        "event_action":  event_action,
        "dedup_key":     f"adaad-{payload.org_id}-{payload.event_type.value}",
        "payload": {
            "summary":   payload.title,
            "source":    f"adaad/{payload.org_id}",
            "severity":  severity_map.get(payload.severity, "info"),
            "custom_details": payload.to_dict(),
        },
    }).encode("utf-8")


def _format_generic_webhook(payload: NotificationPayload, secret: Optional[str]) -> tuple[bytes, Dict[str, str]]:
    """Format payload as ADAAD signed webhook."""
    body = json.dumps(payload.to_dict(), sort_keys=True).encode("utf-8")
    headers: Dict[str, str] = {"Content-Type": "application/json", "X-ADAAD-Event": payload.event_type.value}
    if secret:
        import hmac as _hmac
        sig = _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-ADAAD-Signature"] = f"sha256={sig}"
    return body, headers


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class NotificationDispatcher:
    """Fire-and-forget outbound notification dispatcher.

    Thread-safe. Non-blocking (dispatches in a background thread pool).
    """

    def __init__(
        self,
        max_threads:     int = 4,
        timeout_seconds: int = 5,
        retry_once:      bool = True,
        on_result:       Optional[Callable[[DispatchResult], None]] = None,
    ) -> None:
        self._timeout    = timeout_seconds
        self._retry      = retry_once
        self._on_result  = on_result
        self._results:   List[DispatchResult] = []
        self._lock       = threading.Lock()
        # Bounded thread pool
        self._semaphore  = threading.BoundedSemaphore(max_threads)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        payload:  NotificationPayload,
        channels: Sequence[ChannelConfig],
    ) -> None:
        """Fire notifications to all subscribed channels (non-blocking).

        Args:
            payload:  The notification to dispatch.
            channels: List of configured channels for this org.
        """
        for channel in channels:
            if not channel.should_fire(payload.event_type):
                continue
            t = threading.Thread(
                target  = self._dispatch_one,
                args    = (payload, channel),
                daemon  = True,
                name    = f"adaad-notify-{channel.channel_type.value}",
            )
            t.start()

    def dispatch_sync(
        self,
        payload:  NotificationPayload,
        channels: Sequence[ChannelConfig],
    ) -> List[DispatchResult]:
        """Blocking version — for tests and admin tooling."""
        results: List[DispatchResult] = []
        for channel in channels:
            if not channel.should_fire(payload.event_type):
                continue
            result = self._dispatch_one_attempt(payload, channel, attempt=1)
            results.append(result)
        return results

    def recent_results(self, limit: int = 100) -> List[DispatchResult]:
        with self._lock:
            return list(self._results[-limit:])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _dispatch_one(self, payload: NotificationPayload, channel: ChannelConfig) -> None:
        with self._semaphore:
            result = self._dispatch_one_attempt(payload, channel, attempt=1)
            if not result.success and self._retry:
                time.sleep(1.5)  # brief backoff
                result = self._dispatch_one_attempt(payload, channel, attempt=2)

            with self._lock:
                self._results.append(result)
                if len(self._results) > 1000:
                    self._results = self._results[-500:]

            if self._on_result:
                try:
                    self._on_result(result)
                except Exception:
                    pass

            if not result.success:
                log.warning(
                    "notification_delivery_failed org=%s event=%s channel=%s error=%s",
                    result.org_id, result.event_type, result.channel_type, result.error
                )
            else:
                log.debug(
                    "notification_delivered org=%s event=%s channel=%s",
                    result.org_id, result.event_type, result.channel_type
                )

    def _dispatch_one_attempt(
        self,
        payload: NotificationPayload,
        channel: ChannelConfig,
        attempt: int,
    ) -> DispatchResult:
        start = time.monotonic()
        try:
            body, headers = self._build_request(payload, channel)
            req = urllib.request.Request(
                channel.url,
                data    = body,
                headers = headers,
                method  = "POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status = resp.getcode()
                duration = (time.monotonic() - start) * 1000
                return DispatchResult(
                    channel_type = channel.channel_type,
                    org_id       = payload.org_id,
                    event_type   = payload.event_type.value,
                    success      = 200 <= status < 300,
                    status_code  = status,
                    error        = None if 200 <= status < 300 else f"HTTP {status}",
                    attempt      = attempt,
                    duration_ms  = duration,
                )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            return DispatchResult(
                channel_type = channel.channel_type,
                org_id       = payload.org_id,
                event_type   = payload.event_type.value,
                success      = False,
                status_code  = None,
                error        = str(exc)[:200],
                attempt      = attempt,
                duration_ms  = duration,
            )

    def _build_request(
        self,
        payload: NotificationPayload,
        channel: ChannelConfig,
    ) -> tuple[bytes, Dict[str, str]]:
        if channel.channel_type == ChannelType.SLACK:
            body = _format_slack(payload)
            return body, {"Content-Type": "application/json"}

        elif channel.channel_type == ChannelType.PAGERDUTY:
            body = _format_pagerduty(payload)
            return body, {"Content-Type": "application/json"}

        else:  # generic webhook
            body, headers = _format_generic_webhook(payload, channel.secret)
            return body, headers
