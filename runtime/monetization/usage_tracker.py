# SPDX-License-Identifier: Apache-2.0
"""Usage Tracker — ADAAD Phase 8, M8-03.

Append-only, in-memory usage metering for epoch consumption and API calls.
Callers flush to persistent storage (Redis, Postgres, or append-only file)
— this module is the authoritative in-process accumulator.

Architectural invariants:
- Append-only: events are never removed or modified after recording.
- Deterministic: quota checks depend only on the event sequence, not time.
- Thread-safe: all mutation is guarded by a reentrant lock.
- Quota enforcement is fail-closed: ambiguous state → reject.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

EVENT_EPOCH_RUN      = "epoch_run"
EVENT_API_CALL       = "api_call"
EVENT_MUTATION_APPLY = "mutation_apply"
EVENT_AUDIT_EXPORT   = "audit_export"
EVENT_FEDERATION_OP  = "federation_op"

ALL_EVENT_TYPES = frozenset({
    EVENT_EPOCH_RUN,
    EVENT_API_CALL,
    EVENT_MUTATION_APPLY,
    EVENT_AUDIT_EXPORT,
    EVENT_FEDERATION_OP,
})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class QuotaExceededError(Exception):
    """Raised when a usage request would exceed the tier quota."""
    def __init__(self, org_id: str, event_type: str, used: int, limit: int):
        self.org_id     = org_id
        self.event_type = event_type
        self.used       = used
        self.limit      = limit
        super().__init__(
            f"[ADAAD-QUOTA] {org_id} has reached the {event_type} quota "
            f"({used}/{limit}). Upgrade at https://innovativeai.io/adaad/upgrade"
        )


# ---------------------------------------------------------------------------
# Usage event
# ---------------------------------------------------------------------------

@dataclass
class UsageEvent:
    """Immutable record of a single metered operation."""
    org_id:        str
    kid:           str          # API key ID that triggered the event
    event_type:    str          # One of ALL_EVENT_TYPES
    epoch_window:  str          # Billing window key e.g. "2026-03"
    count:         int = 1      # Units consumed (e.g. 1 epoch, N API calls)
    metadata:      Dict[str, Any] = field(default_factory=dict)
    entry_hash:    str = field(default="", init=False)

    def __post_init__(self) -> None:
        if self.event_type not in ALL_EVENT_TYPES:
            raise ValueError(f"Unknown event_type: {self.event_type!r}")
        if self.count < 1:
            raise ValueError("count must be >= 1")
        # Compute deterministic content hash
        payload = json.dumps(
            {k: v for k, v in asdict(self).items() if k != "entry_hash"},
            sort_keys=True,
            separators=(",", ":"),
        )
        self.entry_hash = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Usage Tracker
# ---------------------------------------------------------------------------

class UsageTracker:
    """Thread-safe, append-only usage accumulator.

    Designed to be instantiated once per process and shared across request
    handlers. Periodic flushing to persistent storage is the caller's
    responsibility.
    """

    def __init__(
        self,
        epoch_limit_by_tier: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Args:
            epoch_limit_by_tier: Overrides tier epoch limits. Defaults to
                canonical tier configuration if not provided.
        """
        self._lock   = threading.RLock()
        self._events: List[UsageEvent] = []

        # Per-org, per-window, per-event-type counters
        # key: (org_id, epoch_window, event_type) → total_count
        self._counters: Dict[tuple, int] = {}

        # Default epoch limits per tier (matches TierConfig)
        self._epoch_limits: Dict[str, int] = epoch_limit_by_tier or {
            "community":  50,
            "pro":        500,
            "enterprise": -1,   # unlimited
        }

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        org_id:       str,
        kid:          str,
        tier:         str,
        event_type:   str,
        epoch_window: str,
        count:        int = 1,
        metadata:     Optional[Dict[str, Any]] = None,
        enforce_quota: bool = True,
    ) -> UsageEvent:
        """Record a usage event, optionally enforcing quota.

        Args:
            org_id:        Organisation ID.
            kid:           API key ID.
            tier:          Tier name ("community" | "pro" | "enterprise").
            event_type:    One of ALL_EVENT_TYPES.
            epoch_window:  Billing period key, e.g. "2026-03".
            count:         Units consumed.
            metadata:      Optional extra context (stored but not quota-counted).
            enforce_quota: If True and quota is exceeded, raises QuotaExceededError
                           and the event is NOT recorded.

        Returns:
            The recorded UsageEvent.
        """
        with self._lock:
            if enforce_quota and event_type == EVENT_EPOCH_RUN:
                self._check_epoch_quota(org_id, tier, epoch_window, count)

            event = UsageEvent(
                org_id       = org_id,
                kid          = kid,
                event_type   = event_type,
                epoch_window = epoch_window,
                count        = count,
                metadata     = metadata or {},
            )
            self._events.append(event)
            key = (org_id, epoch_window, event_type)
            self._counters[key] = self._counters.get(key, 0) + count
            return event

    # ------------------------------------------------------------------
    # Quota checks
    # ------------------------------------------------------------------

    def _check_epoch_quota(
        self,
        org_id:       str,
        tier:         str,
        epoch_window: str,
        delta:        int,
    ) -> None:
        """Raise QuotaExceededError if recording *delta* would exceed the limit."""
        limit = self._epoch_limits.get(tier, 0)
        if limit == -1:
            return  # unlimited
        key  = (org_id, epoch_window, EVENT_EPOCH_RUN)
        used = self._counters.get(key, 0)
        if used + delta > limit:
            raise QuotaExceededError(org_id, EVENT_EPOCH_RUN, used, limit)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def usage_summary(self, org_id: str, epoch_window: str) -> Dict[str, Any]:
        """Return a JSON-serialisable usage summary for *org_id* in *epoch_window*."""
        with self._lock:
            result: Dict[str, int] = {}
            for etype in ALL_EVENT_TYPES:
                key = (org_id, epoch_window, etype)
                result[etype] = self._counters.get(key, 0)
            return {
                "org_id":       org_id,
                "epoch_window": epoch_window,
                "usage":        result,
            }

    def all_events(self) -> Sequence[UsageEvent]:
        """Return a snapshot of all recorded events (immutable view)."""
        with self._lock:
            return list(self._events)

    def flush_events(self) -> List[Dict[str, Any]]:
        """Return all events as dicts and clear the internal buffer.

        Callers should persist the returned list before calling flush_events
        again — events are non-recoverable once flushed without persistence.
        """
        with self._lock:
            dicts = [e.to_dict() for e in self._events]
            self._events.clear()
            return dicts

    def event_count(self, org_id: Optional[str] = None, event_type: Optional[str] = None) -> int:
        """Return count of events matching optional filters."""
        with self._lock:
            return sum(
                1 for e in self._events
                if (org_id is None or e.org_id == org_id)
                and (event_type is None or e.event_type == event_type)
            )
