# SPDX-License-Identifier: MIT
"""Revenue Analytics Engine — ADAAD Phase 9, M9-03.

Real-time MRR / ARR tracking, cohort analysis, and growth metrics for
InnovativeAI LLC.  All computations are pure functions over immutable
event streams — replay-safe and deterministic.

Provides:
  - MRR / ARR snapshots (current + trended)
  - New MRR, Expansion MRR, Churned MRR (waterfall decomposition)
  - Quick-ratio (growth quality indicator: >4 = exceptional)
  - Cohort retention curves
  - LTV estimates per tier
  - Payback-period calculation (CAC payback)

Architectural invariants:
- Analytics computations are pure functions — no I/O, no side-effects.
- Revenue figures are computed from the ConversionEvent log — single source of truth.
- No analytics metric ever modifies OrgRegistry or overrides governance state.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Tier MRR reference values
# ---------------------------------------------------------------------------

TIER_MRR_USD: Dict[str, float] = {
    "community":  0.0,
    "pro":        49.0,
    "enterprise": 499.0,
}

TIER_ARR_USD: Dict[str, float] = {
    k: v * 12 for k, v in TIER_MRR_USD.items()
}

# Estimated CAC per acquisition channel (for payback calc)
CHANNEL_CAC_USD: Dict[str, float] = {
    "organic":      15.0,
    "github":       25.0,
    "marketplace":  40.0,
    "paid_search": 120.0,
    "referral":     10.0,
    "default":      50.0,
}


# ---------------------------------------------------------------------------
# Input: org billing record (snapshot from OrgRegistry / BillingGateway)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrgBillingRecord:
    """Billing snapshot for a single organisation."""
    org_id: str
    tier: str
    status: str                    # "active" | "grace_period" | "suspended"
    created_at: int                # Unix timestamp of org creation
    converted_at: Optional[int]    # When they first upgraded from Community
    last_payment_at: Optional[int]
    churn_at: Optional[int]        # Non-null if org has churned
    acquisition_channel: str = "default"


# ---------------------------------------------------------------------------
# MRR waterfall
# ---------------------------------------------------------------------------

@dataclass
class MRRWaterfall:
    """MRR movement decomposition for a billing period."""
    period_start: int
    period_end: int

    new_mrr: float        = 0.0    # Community → Paid conversions
    expansion_mrr: float  = 0.0    # Pro → Enterprise upgrades
    contraction_mrr: float = 0.0   # Enterprise → Pro downgrades
    churned_mrr: float    = 0.0    # Paid → Community / cancelled
    reactivation_mrr: float = 0.0  # Churned org returned to paid

    starting_mrr: float   = 0.0

    @property
    def net_new_mrr(self) -> float:
        return self.new_mrr + self.expansion_mrr - self.contraction_mrr - self.churned_mrr + self.reactivation_mrr

    @property
    def ending_mrr(self) -> float:
        return self.starting_mrr + self.net_new_mrr

    @property
    def quick_ratio(self) -> float:
        """Growth quality metric.  > 4.0 = exceptional, > 1.0 = growing."""
        denominator = self.contraction_mrr + self.churned_mrr
        if denominator == 0:
            return float("inf") if (self.new_mrr + self.expansion_mrr) > 0 else 1.0
        return (self.new_mrr + self.expansion_mrr + self.reactivation_mrr) / denominator

    @property
    def net_revenue_retention(self) -> float:
        """NRR: how much of last period's revenue we kept and grew. > 1.0 = expanding."""
        if self.starting_mrr == 0:
            return 1.0
        return (self.starting_mrr + self.expansion_mrr - self.contraction_mrr - self.churned_mrr) / self.starting_mrr


# ---------------------------------------------------------------------------
# Cohort retention
# ---------------------------------------------------------------------------

@dataclass
class CohortRetention:
    """Retention curve for a monthly acquisition cohort."""
    cohort_month: str          # "2026-01"
    initial_size: int
    active_by_month: List[int] = field(default_factory=list)   # index 0 = month 1

    def retention_rate(self, months_after: int) -> float:
        if months_after <= 0 or months_after > len(self.active_by_month):
            return 1.0 if months_after == 0 else 0.0
        if self.initial_size == 0:
            return 0.0
        return self.active_by_month[months_after - 1] / self.initial_size

    def ltv_estimate(self, tier: str, avg_months: float = 24.0) -> float:
        """Simple LTV estimate: avg MRR × average contract months × avg retention."""
        mrr = TIER_MRR_USD.get(tier, 0.0)
        avg_retention = (
            sum(self.retention_rate(m) for m in range(1, int(avg_months) + 1))
            / avg_months
        )
        return mrr * avg_months * avg_retention


# ---------------------------------------------------------------------------
# Revenue snapshot
# ---------------------------------------------------------------------------

@dataclass
class RevenueSnapshot:
    """Point-in-time revenue dashboard."""
    snapshot_at: int

    total_orgs: int          = 0
    paying_orgs: int         = 0
    community_orgs: int      = 0
    pro_orgs: int            = 0
    enterprise_orgs: int     = 0

    mrr_usd: float           = 0.0
    arr_usd: float           = 0.0

    pro_mrr: float           = 0.0
    enterprise_mrr: float    = 0.0

    avg_revenue_per_user: float = 0.0    # ARPU (paid only)
    conversion_rate: float       = 0.0   # Community → paid (lifetime)

    @property
    def monthly_growth_rate_7d(self) -> Optional[float]:
        """Placeholder — populated by compare_snapshots()."""
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_at": self.snapshot_at,
            "orgs": {
                "total": self.total_orgs,
                "paying": self.paying_orgs,
                "community": self.community_orgs,
                "pro": self.pro_orgs,
                "enterprise": self.enterprise_orgs,
            },
            "revenue": {
                "mrr_usd": round(self.mrr_usd, 2),
                "arr_usd": round(self.arr_usd, 2),
                "pro_mrr": round(self.pro_mrr, 2),
                "enterprise_mrr": round(self.enterprise_mrr, 2),
                "arpu_usd": round(self.avg_revenue_per_user, 2),
            },
            "conversion_rate": round(self.conversion_rate, 4),
        }


# ---------------------------------------------------------------------------
# Pure analytics functions
# ---------------------------------------------------------------------------

def compute_snapshot(orgs: List[OrgBillingRecord]) -> RevenueSnapshot:
    """Compute a revenue snapshot from org billing records.

    Pure function — no I/O.
    """
    snap = RevenueSnapshot(snapshot_at=int(time.time()))
    snap.total_orgs = len(orgs)

    for org in orgs:
        if org.status not in ("active", "grace_period"):
            continue
        tier = org.tier.lower()
        mrr  = TIER_MRR_USD.get(tier, 0.0)
        snap.mrr_usd += mrr

        if tier == "community":
            snap.community_orgs += 1
        elif tier == "pro":
            snap.pro_orgs += 1
            snap.pro_mrr += mrr
            snap.paying_orgs += 1
        elif tier == "enterprise":
            snap.enterprise_orgs += 1
            snap.enterprise_mrr += mrr
            snap.paying_orgs += 1

    snap.arr_usd = snap.mrr_usd * 12
    snap.avg_revenue_per_user = (
        snap.mrr_usd / snap.paying_orgs if snap.paying_orgs > 0 else 0.0
    )
    snap.conversion_rate = (
        snap.paying_orgs / snap.total_orgs if snap.total_orgs > 0 else 0.0
    )
    return snap


def compute_payback_period(
    tier: str,
    channel: str = "default",
    gross_margin: float = 0.85,
) -> Optional[float]:
    """Months to pay back CAC for a given tier + acquisition channel.

    Returns None for Community (no revenue).
    """
    mrr = TIER_MRR_USD.get(tier.lower(), 0.0)
    if mrr == 0:
        return None
    cac = CHANNEL_CAC_USD.get(channel, CHANNEL_CAC_USD["default"])
    return cac / (mrr * gross_margin)


def growth_rate(prev_mrr: float, curr_mrr: float) -> float:
    """Month-over-month MRR growth rate."""
    if prev_mrr == 0:
        return 1.0 if curr_mrr > 0 else 0.0
    return (curr_mrr - prev_mrr) / prev_mrr


def build_waterfall(
    orgs_start: List[OrgBillingRecord],
    orgs_end: List[OrgBillingRecord],
    period_start: int,
    period_end: int,
) -> MRRWaterfall:
    """Compute MRR waterfall by comparing two org billing snapshots.

    Pure function — no I/O.
    """
    start_map = {o.org_id: o for o in orgs_start}
    end_map   = {o.org_id: o for o in orgs_end}

    wf = MRRWaterfall(period_start=period_start, period_end=period_end)
    wf.starting_mrr = sum(
        TIER_MRR_USD.get(o.tier.lower(), 0.0)
        for o in orgs_start
        if o.status == "active"
    )

    for org_id, end_org in end_map.items():
        if end_org.status not in ("active", "grace_period"):
            continue
        end_mrr = TIER_MRR_USD.get(end_org.tier.lower(), 0.0)
        if org_id not in start_map:
            # Brand-new org
            if end_mrr > 0:
                wf.new_mrr += end_mrr
        else:
            start_org  = start_map[org_id]
            start_mrr  = TIER_MRR_USD.get(start_org.tier.lower(), 0.0)
            delta      = end_mrr - start_mrr
            if start_mrr == 0 and end_mrr > 0:
                wf.new_mrr += end_mrr        # Community → paid
            elif delta > 0:
                wf.expansion_mrr += delta    # upgrade
            elif delta < 0:
                wf.contraction_mrr += abs(delta)   # downgrade

    for org_id, start_org in start_map.items():
        start_mrr = TIER_MRR_USD.get(start_org.tier.lower(), 0.0)
        if start_mrr == 0:
            continue
        if org_id not in end_map:
            wf.churned_mrr += start_mrr      # deleted org
        else:
            end_org = end_map[org_id]
            if end_org.status not in ("active", "grace_period"):
                wf.churned_mrr += start_mrr  # suspended / churned

    return wf


# ---------------------------------------------------------------------------
# Revenue Analytics Service (thin stateful wrapper)
# ---------------------------------------------------------------------------

class RevenueAnalyticsService:
    """Thin service wrapper — stores snapshots and provides trend queries.

    In production, snapshots should be persisted to Postgres or Redis.
    This class is the in-process accumulator; safe for replay.

    Usage::

        svc = RevenueAnalyticsService()
        svc.record_snapshot(orgs)
        dashboard = svc.dashboard()
    """

    def __init__(self) -> None:
        self._snapshots: List[Tuple[int, RevenueSnapshot]] = []   # (ts, snap)

    def record_snapshot(self, orgs: List[OrgBillingRecord]) -> RevenueSnapshot:
        snap = compute_snapshot(orgs)
        self._snapshots.append((snap.snapshot_at, snap))
        return snap

    def latest_snapshot(self) -> Optional[RevenueSnapshot]:
        if not self._snapshots:
            return None
        return self._snapshots[-1][1]

    def mrr_trend(self, n: int = 12) -> List[Dict[str, Any]]:
        """Last *n* recorded MRR values."""
        recent = self._snapshots[-n:]
        return [
            {"snapshot_at": ts, "mrr_usd": snap.mrr_usd, "arr_usd": snap.arr_usd}
            for ts, snap in recent
        ]

    def mom_growth(self) -> Optional[float]:
        """Month-over-month MRR growth rate from last two snapshots."""
        if len(self._snapshots) < 2:
            return None
        prev = self._snapshots[-2][1].mrr_usd
        curr = self._snapshots[-1][1].mrr_usd
        return growth_rate(prev, curr)

    def dashboard(self) -> Dict[str, Any]:
        snap = self.latest_snapshot()
        if not snap:
            return {"error": "no_snapshots_recorded"}
        result = snap.to_dict()
        result["mom_growth"] = self.mom_growth()
        result["mrr_trend"] = self.mrr_trend()
        return result
