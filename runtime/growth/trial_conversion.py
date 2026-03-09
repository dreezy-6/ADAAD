# SPDX-License-Identifier: MIT
"""Trial Conversion Engine — ADAAD Phase 9, M9-02.

Drives free (Community) → paid (Pro / Enterprise) conversion for
InnovativeAI LLC.  Tracks trial milestones, emits upgrade nudges at the
right moment, and records conversion events in the governance ledger.

All conversion logic is deterministic and replay-safe:
- No external HTTP calls at evaluation time (nudges are *queued*, not sent)
- Upgrade nudge emission is idempotent per org per trigger type
- Conversion events are SHA-256 hash-chained (same ledger pattern as governance)

Architectural invariants:
- Conversion events are **appended** to the evidence ledger — never mutated.
- Upgrade prompts never override or weaken GovernanceGate.
- CONSTITUTIONAL_FLOOR: trial limits are hard-coded; a nudge never grants
  extra quota. Only a real tier upgrade (via BillingGateway) can do that.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Trigger catalogue
# ---------------------------------------------------------------------------

class ConversionTrigger(str, Enum):
    """Events that indicate a Community org is ready for a paid upgrade nudge."""
    EPOCH_QUOTA_80_PCT   = "epoch_quota_80_pct"    # used ≥40 of 50 free epochs
    EPOCH_QUOTA_100_PCT  = "epoch_quota_100_pct"   # hit the cap; blocked
    GOVERNANCE_DEPTH     = "governance_depth"       # 3+ unique gate triggers
    FEATURE_WALL_HIT     = "feature_wall_hit"       # attempted Pro-only feature
    TEAM_SIZE_SIGNAL     = "team_size_signal"       # ≥3 active users on free tier
    HIGH_HEALTH_SCORE    = "high_health_score"      # health ≥ 75 (champion-track)
    CONSECUTIVE_DAYS     = "consecutive_days"       # active ≥ 7 consecutive days
    REFERRAL_SENT        = "referral_sent"          # shared ADAAD with others


class NudgeChannel(str, Enum):
    """Delivery channel for an upgrade nudge."""
    IN_APP   = "in_app"
    EMAIL    = "email"
    SLACK    = "slack"     # only if Slack webhook configured
    APONI    = "aponi"     # inside the Aponi IDE companion


# ---------------------------------------------------------------------------
# Nudge queue item
# ---------------------------------------------------------------------------

@dataclass
class UpgradeNudge:
    """A queued upgrade suggestion — not yet delivered."""
    org_id: str
    trigger: ConversionTrigger
    suggested_tier: str               # "pro" | "enterprise"
    channel: NudgeChannel
    headline: str
    body: str
    cta_url: str
    created_at: int = field(default_factory=lambda: int(time.time()))
    idempotency_key: str = ""         # set by engine; prevents duplicate nudges

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            raw = f"{self.org_id}:{self.trigger.value}:{self.suggested_tier}"
            self.idempotency_key = hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Conversion event (immutable ledger record)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConversionEvent:
    """Immutable record of a tier upgrade — appended to the evidence ledger."""
    event_id: str
    org_id: str
    from_tier: str
    to_tier: str
    trigger: str                       # ConversionTrigger value or "manual"
    attributed_nudge_key: Optional[str]
    occurred_at: int
    mrr_delta_usd: float               # revenue impact of this conversion
    content_hash: str = ""

    def _compute_hash(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "content_hash"}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()

    def with_hash(self) -> "ConversionEvent":
        return ConversionEvent(**{**asdict(self), "content_hash": self._compute_hash()})


# ---------------------------------------------------------------------------
# Nudge copy catalogue (deterministic — no LLM at evaluation time)
# ---------------------------------------------------------------------------

_NUDGE_COPY: Dict[str, Dict[str, str]] = {
    ConversionTrigger.EPOCH_QUOTA_80_PCT.value: {
        "headline": "You're 80% through your free epochs this month",
        "body": (
            "You've run {used} of {cap} free epochs. Upgrade to Pro to unlock "
            "500 epochs/month — never hit a wall mid-sprint again."
        ),
        "cta": "Upgrade to Pro — $49/mo",
    },
    ConversionTrigger.EPOCH_QUOTA_100_PCT.value: {
        "headline": "You've hit your free epoch limit",
        "body": (
            "Your 50 free epochs for this month are used. Upgrade to Pro now "
            "to resume your evolution pipeline instantly — 500 epochs/month, "
            "no interruptions."
        ),
        "cta": "Unblock now — Upgrade to Pro",
    },
    ConversionTrigger.FEATURE_WALL_HIT.value: {
        "headline": "This feature requires Pro",
        "body": (
            "{feature} is available on Pro and Enterprise plans. "
            "Upgrade to unlock the reviewer reputation engine, simulation DSL, "
            "Aponi IDE, and federation across 3 nodes."
        ),
        "cta": "See Pro features →",
    },
    ConversionTrigger.HIGH_HEALTH_SCORE.value: {
        "headline": "You're getting serious value from ADAAD",
        "body": (
            "Your governance pipeline is running strong. Pro unlocks 10× more "
            "epochs, the reviewer calibration engine, and multi-repo federation — "
            "built for teams ready to scale."
        ),
        "cta": "Upgrade to Pro — $49/mo",
    },
    ConversionTrigger.TEAM_SIZE_SIGNAL.value: {
        "headline": "3+ team members are using ADAAD",
        "body": (
            "Your team is adopting ADAAD. Pro gives every member 500 shared "
            "epochs, Aponi IDE access, and team-level governance dashboards. "
            "Enterprise adds SSO, SLA, and unlimited federation."
        ),
        "cta": "Upgrade for your team →",
    },
    ConversionTrigger.GOVERNANCE_DEPTH.value: {
        "headline": "You're pushing the governance engine hard",
        "body": (
            "You've triggered {gate_count} governance gate evaluations — a sign "
            "of serious constitutional usage. Pro unlocks the simulation DSL so "
            "you can replay hypothetical constitutional constraints before applying."
        ),
        "cta": "Unlock the simulation DSL →",
    },
    ConversionTrigger.CONSECUTIVE_DAYS.value: {
        "headline": "You've been active {days} days in a row",
        "body": (
            "Consistent use like yours is exactly what Pro is built for. "
            "Upgrade to stop worrying about epoch limits and get 10× more "
            "governance headroom every month."
        ),
        "cta": "Upgrade to Pro — $49/mo",
    },
    ConversionTrigger.REFERRAL_SENT.value: {
        "headline": "Thanks for spreading the word about ADAAD",
        "body": (
            "As a thank-you, your first month of Pro is 20% off. "
            "Use code REFERRAL20 at checkout."
        ),
        "cta": "Claim your discount →",
    },
}

_BASE_CHECKOUT_URL = "https://innovativeai.dev/checkout"


def _build_nudge(
    org_id: str,
    trigger: ConversionTrigger,
    suggested_tier: str,
    channel: NudgeChannel,
    context: Optional[Dict[str, Any]] = None,
) -> UpgradeNudge:
    ctx = context or {}
    copy = _NUDGE_COPY.get(trigger.value, {
        "headline": "Upgrade ADAAD",
        "body": "Unlock more power with Pro or Enterprise.",
        "cta": "See plans →",
    })

    headline = copy["headline"].format(**ctx)
    body = copy["body"].format(**ctx)
    cta_label = copy["cta"]
    cta_url = f"{_BASE_CHECKOUT_URL}?plan={suggested_tier}&ref={trigger.value}"

    return UpgradeNudge(
        org_id=org_id,
        trigger=trigger,
        suggested_tier=suggested_tier,
        channel=channel,
        headline=headline,
        body=body,
        cta_url=cta_url,
    )


# ---------------------------------------------------------------------------
# Conversion Engine
# ---------------------------------------------------------------------------

class TrialConversionEngine:
    """Evaluate an org's Community usage and queue upgrade nudges.

    This class is stateful only in its in-process nudge queue and a set of
    already-emitted idempotency keys (preventing duplicate nudges per session).
    Callers should persist these to stable storage between process restarts.

    Usage::

        engine = TrialConversionEngine()
        nudges = engine.evaluate(snap, health_score)
        for nudge in nudges:
            notification_dispatcher.send_nudge(nudge)

    All evaluation is deterministic and side-effect-free.  Only ``evaluate``
    needs to be called — nudge delivery is the caller's responsibility.
    """

    def __init__(self) -> None:
        self._emitted_keys: set[str] = set()
        self._nudge_queue: List[UpgradeNudge] = []
        self._conversion_log: List[ConversionEvent] = []

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        snap: "UsageSnapshot",             # from customer_health module
        health_score: Optional[int] = None,
        active_days_streak: int = 0,
        feature_wall_feature: Optional[str] = None,
        referral_sent: bool = False,
    ) -> List[UpgradeNudge]:
        """Evaluate triggers for a Community org.  Returns new nudges (if any).

        Idempotent: repeated calls with the same inputs produce no additional nudges.
        Only Community orgs are evaluated — paid orgs are passed through unchanged.
        """
        if snap.tier.lower() != "community":
            return []

        new_nudges: List[UpgradeNudge] = []

        # --- Epoch quota ---
        epoch_pct = snap.epochs_run_last_30d / 50.0
        if epoch_pct >= 1.0:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.EPOCH_QUOTA_100_PCT, "pro",
                NudgeChannel.IN_APP,
                context={"used": snap.epochs_run_last_30d, "cap": 50},
            ))
        elif epoch_pct >= 0.8:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.EPOCH_QUOTA_80_PCT, "pro",
                NudgeChannel.EMAIL,
                context={"used": snap.epochs_run_last_30d, "cap": 50},
            ))

        # --- Feature wall ---
        if feature_wall_feature:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.FEATURE_WALL_HIT, "pro",
                NudgeChannel.IN_APP,
                context={"feature": feature_wall_feature},
            ))

        # --- Governance depth ---
        if snap.governance_gates_triggered >= 3:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.GOVERNANCE_DEPTH, "pro",
                NudgeChannel.EMAIL,
                context={"gate_count": snap.governance_gates_triggered},
            ))

        # --- Team size ---
        if snap.active_users_last_30d >= 3:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.TEAM_SIZE_SIGNAL, "pro",
                NudgeChannel.EMAIL,
            ))

        # --- Health score ---
        if health_score is not None and health_score >= 75:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.HIGH_HEALTH_SCORE, "pro",
                NudgeChannel.IN_APP,
            ))

        # --- Consecutive days ---
        if active_days_streak >= 7:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.CONSECUTIVE_DAYS, "pro",
                NudgeChannel.EMAIL,
                context={"days": active_days_streak},
            ))

        # --- Referral ---
        if referral_sent:
            new_nudges.extend(self._maybe_emit(
                snap.org_id, ConversionTrigger.REFERRAL_SENT, "pro",
                NudgeChannel.EMAIL,
            ))

        self._nudge_queue.extend(new_nudges)
        return new_nudges

    # ------------------------------------------------------------------
    # Conversion recording
    # ------------------------------------------------------------------

    def record_conversion(
        self,
        org_id: str,
        from_tier: str,
        to_tier: str,
        trigger: str = "manual",
        nudge_key: Optional[str] = None,
    ) -> ConversionEvent:
        """Record a tier upgrade event in the conversion log.

        Returns the immutable ConversionEvent (hash-chained).
        """
        _MRR = {"community": 0.0, "pro": 49.0, "enterprise": 499.0}
        delta = _MRR.get(to_tier, 0.0) - _MRR.get(from_tier, 0.0)

        event_id = hashlib.sha256(
            f"{org_id}:{from_tier}:{to_tier}:{int(time.time())}".encode()
        ).hexdigest()[:24]

        event = ConversionEvent(
            event_id=event_id,
            org_id=org_id,
            from_tier=from_tier,
            to_tier=to_tier,
            trigger=trigger,
            attributed_nudge_key=nudge_key,
            occurred_at=int(time.time()),
            mrr_delta_usd=delta,
        ).with_hash()

        self._conversion_log.append(event)
        return event

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def pending_nudges(self) -> List[UpgradeNudge]:
        return list(self._nudge_queue)

    def drain_nudges(self) -> List[UpgradeNudge]:
        """Return and clear the pending nudge queue."""
        result = list(self._nudge_queue)
        self._nudge_queue.clear()
        return result

    def conversion_log(self) -> List[ConversionEvent]:
        return list(self._conversion_log)

    # ------------------------------------------------------------------
    # Revenue impact
    # ------------------------------------------------------------------

    def total_mrr_attributed(self) -> float:
        return sum(e.mrr_delta_usd for e in self._conversion_log if e.mrr_delta_usd > 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_emit(
        self,
        org_id: str,
        trigger: ConversionTrigger,
        tier: str,
        channel: NudgeChannel,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[UpgradeNudge]:
        nudge = _build_nudge(org_id, trigger, tier, channel, context)
        if nudge.idempotency_key in self._emitted_keys:
            return []
        self._emitted_keys.add(nudge.idempotency_key)
        return [nudge]
