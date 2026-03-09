# SPDX-License-Identifier: MIT
"""Customer Health Scorer — ADAAD Phase 9, M9-01.

Deterministic, replay-safe health scoring for every InnovativeAI LLC customer.
Scores drive proactive churn prevention and expansion revenue triggers.

Health score: 0–100 (higher = healthier, more likely to expand).
Risk band:    CRITICAL / AT_RISK / NEUTRAL / HEALTHY / CHAMPION

Scoring is a pure function of usage telemetry snapshots — no I/O, no side
effects. Safe to run inside the constitutional replay harness.

Architectural invariants:
- Health checks are pure functions — deterministic, I/O-free, replay-safe.
- No health score ever bypasses GovernanceGate or tier enforcement.
- Score computation is transparent and auditable (all factors exposed).
- CONSTITUTIONAL_FLOOR: a CRITICAL org always receives a human-review event.

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
# Risk band
# ---------------------------------------------------------------------------

class RiskBand(str, Enum):
    CRITICAL  = "critical"   # 0–24  — immediate churn risk, alert CSM
    AT_RISK   = "at_risk"    # 25–49 — declining engagement, proactive outreach
    NEUTRAL   = "neutral"    # 50–64 — steady state, watch for trend
    HEALTHY   = "healthy"    # 65–84 — good utilisation, expansion candidate
    CHAMPION  = "champion"   # 85–100 — power user, referral / case-study target


def band_from_score(score: int) -> RiskBand:
    """Map a 0–100 health score to a risk band."""
    if score < 25:
        return RiskBand.CRITICAL
    if score < 50:
        return RiskBand.AT_RISK
    if score < 65:
        return RiskBand.NEUTRAL
    if score < 85:
        return RiskBand.HEALTHY
    return RiskBand.CHAMPION


# ---------------------------------------------------------------------------
# Input snapshot (pure data — no DB handles)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UsageSnapshot:
    """Point-in-time usage telemetry for one organisation.

    All fields are plain Python values so snapshots are trivially serialisable
    and safe for deterministic replay.
    """
    org_id: str
    tier: str                        # "community" | "pro" | "enterprise"
    snapshot_epoch: int              # Unix timestamp of measurement window end

    # Engagement signals
    epochs_run_last_30d: int = 0
    epochs_run_prev_30d: int = 0     # for trend
    mutations_accepted_last_30d: int = 0
    governance_gates_triggered: int = 0

    # Product-depth signals
    features_used: List[str] = field(default_factory=list)
    api_calls_last_7d: int = 0
    active_users_last_30d: int = 1   # seat-level engagement

    # Support / friction signals
    support_tickets_open: int = 0
    failed_payments_last_90d: int = 0
    days_since_last_login: int = 0

    # Billing health
    days_until_renewal: Optional[int] = None   # None = free tier
    mrr_usd: float = 0.0


# ---------------------------------------------------------------------------
# Score factors (each a 0–1 contribution)
# ---------------------------------------------------------------------------

@dataclass
class HealthFactors:
    """Decomposed scoring factors — each 0.0–1.0."""
    epoch_activity:    float = 0.0   # raw epoch usage vs tier limit
    activity_trend:    float = 0.0   # 30d vs prior 30d
    feature_depth:     float = 0.0   # breadth of product surface used
    governance_health: float = 0.0   # gate pass rate
    api_engagement:    float = 0.0   # API call frequency
    support_friction:  float = 0.0   # inverse of open tickets / payment fails
    renewal_proximity: float = 0.0   # risk bonus near renewal (paid only)
    seat_breadth:      float = 0.0   # multi-user = stickier

    def weighted_score(self) -> float:
        """Weighted linear combination → 0.0–1.0."""
        weights = {
            "epoch_activity":    0.25,
            "activity_trend":    0.15,
            "feature_depth":     0.15,
            "governance_health": 0.10,
            "api_engagement":    0.10,
            "support_friction":  0.10,
            "renewal_proximity": 0.10,
            "seat_breadth":      0.05,
        }
        total = 0.0
        for attr, w in weights.items():
            total += getattr(self, attr) * w
        return max(0.0, min(1.0, total))


# ---------------------------------------------------------------------------
# Epoch-limit reference table (mirrors TierEngine)
# ---------------------------------------------------------------------------

_TIER_EPOCH_LIMIT: Dict[str, int] = {
    "community":  50,
    "pro":        500,
    "enterprise": 10_000,   # effectively unlimited; cap for scoring
}

_TIER_FEATURES_EXPECTED: Dict[str, int] = {
    "community":  3,
    "pro":        8,
    "enterprise": 15,
}


# ---------------------------------------------------------------------------
# Pure scoring function
# ---------------------------------------------------------------------------

def compute_health(snap: UsageSnapshot) -> "HealthScore":
    """Compute a health score from a usage snapshot.

    Pure function — no I/O.  Safe to call inside replay harnesses.
    """
    factors = HealthFactors()
    tier = snap.tier.lower()

    # 1. Epoch activity: usage vs tier cap
    epoch_cap = _TIER_EPOCH_LIMIT.get(tier, 50)
    factors.epoch_activity = min(snap.epochs_run_last_30d / epoch_cap, 1.0)

    # 2. Activity trend: is usage growing?
    if snap.epochs_run_prev_30d > 0:
        ratio = snap.epochs_run_last_30d / snap.epochs_run_prev_30d
        factors.activity_trend = min(ratio / 2.0, 1.0)   # 2× growth = full score
    elif snap.epochs_run_last_30d > 0:
        factors.activity_trend = 0.5   # new activity from cold start

    # 3. Feature depth
    expected = _TIER_FEATURES_EXPECTED.get(tier, 3)
    factors.feature_depth = min(len(snap.features_used) / expected, 1.0)

    # 4. Governance health: gate triggers (more = power user, not a penalty)
    #    Normalised against epoch count — at least 1 gate per epoch = full score
    if snap.epochs_run_last_30d > 0:
        gate_ratio = snap.governance_gates_triggered / snap.epochs_run_last_30d
        factors.governance_health = min(gate_ratio, 1.0)
    else:
        factors.governance_health = 0.0

    # 5. API engagement
    factors.api_engagement = min(snap.api_calls_last_7d / 100.0, 1.0)

    # 6. Support friction (inverse)
    friction = snap.support_tickets_open * 10 + snap.failed_payments_last_90d * 20
    factors.support_friction = max(0.0, 1.0 - friction / 100.0)

    # 7. Renewal proximity: paid orgs near renewal are churn risk → lower score
    if snap.days_until_renewal is not None and tier != "community":
        if snap.days_until_renewal <= 7:
            factors.renewal_proximity = 0.2   # critical window
        elif snap.days_until_renewal <= 30:
            factors.renewal_proximity = 0.6
        else:
            factors.renewal_proximity = 1.0
    else:
        factors.renewal_proximity = 0.5       # community / unknown

    # 8. Seat breadth (stickier with more users)
    factors.seat_breadth = min(snap.active_users_last_30d / 5.0, 1.0)

    raw = factors.weighted_score()
    score = round(raw * 100)
    band  = band_from_score(score)

    # Content hash for replay verification
    payload = json.dumps(asdict(snap), sort_keys=True, default=str)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()

    return HealthScore(
        org_id=snap.org_id,
        tier=snap.tier,
        score=score,
        band=band,
        factors=factors,
        snapshot_epoch=snap.snapshot_epoch,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class HealthScore:
    """Computed health assessment for one organisation."""
    org_id: str
    tier: str
    score: int                 # 0–100
    band: RiskBand
    factors: HealthFactors
    snapshot_epoch: int
    content_hash: str          # SHA-256 of input snapshot (replay anchor)

    # Derived signals for downstream automation
    @property
    def needs_csmm_alert(self) -> bool:
        """True when band is CRITICAL — triggers human CSM review event."""
        return self.band == RiskBand.CRITICAL

    @property
    def is_expansion_candidate(self) -> bool:
        """True when health is strong enough to trigger upgrade nudge."""
        return self.band in (RiskBand.HEALTHY, RiskBand.CHAMPION)

    @property
    def upgrade_prompt_tier(self) -> Optional[str]:
        """Suggested upgrade tier, if applicable."""
        if self.tier == "community" and self.is_expansion_candidate:
            return "pro"
        if self.tier == "pro" and self.band == RiskBand.CHAMPION:
            return "enterprise"
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["band"] = self.band.value
        d["needs_csmm_alert"] = self.needs_csmm_alert
        d["is_expansion_candidate"] = self.is_expansion_candidate
        d["upgrade_prompt_tier"] = self.upgrade_prompt_tier
        return d


# ---------------------------------------------------------------------------
# Batch scorer
# ---------------------------------------------------------------------------

class CustomerHealthScorer:
    """Batch compute health scores for a portfolio of orgs.

    Designed to run as a scheduled job (e.g., hourly cron) over the
    OrgRegistry + UsageTracker outputs.

    Usage::

        scorer = CustomerHealthScorer()
        snapshots = [UsageSnapshot(org_id="acme", tier="pro", ...)]
        report = scorer.score_all(snapshots)
        for hs in report.at_risk:
            notify_csm(hs)
    """

    def score_all(self, snapshots: List[UsageSnapshot]) -> "HealthReport":
        scores = [compute_health(s) for s in snapshots]
        return HealthReport(scores=scores, computed_at=int(time.time()))


@dataclass
class HealthReport:
    """Portfolio-level health summary."""
    scores: List[HealthScore]
    computed_at: int   # Unix timestamp

    # Segment accessors
    @property
    def critical(self) -> List[HealthScore]:
        return [s for s in self.scores if s.band == RiskBand.CRITICAL]

    @property
    def at_risk(self) -> List[HealthScore]:
        return [s for s in self.scores if s.band == RiskBand.AT_RISK]

    @property
    def expansion_candidates(self) -> List[HealthScore]:
        return [s for s in self.scores if s.is_expansion_candidate]

    @property
    def champion_orgs(self) -> List[HealthScore]:
        return [s for s in self.scores if s.band == RiskBand.CHAMPION]

    @property
    def average_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)

    @property
    def churn_risk_count(self) -> int:
        return len(self.critical) + len(self.at_risk)

    def summary(self) -> Dict[str, Any]:
        bands: Dict[str, int] = {b.value: 0 for b in RiskBand}
        for s in self.scores:
            bands[s.band.value] += 1
        return {
            "computed_at": self.computed_at,
            "total_orgs": len(self.scores),
            "average_score": round(self.average_score, 1),
            "band_distribution": bands,
            "churn_risk_count": self.churn_risk_count,
            "expansion_candidates": len(self.expansion_candidates),
            "champion_orgs": len(self.champion_orgs),
        }
