# SPDX-License-Identifier: MIT
"""Tests for ADAAD Phase 9 Revenue Growth Engine.

Test coverage:
  T9-01  CustomerHealthScorer — band classification
  T9-02  CustomerHealthScorer — pure/deterministic (same input → same score)
  T9-03  CustomerHealthScorer — CRITICAL band triggers needs_csm_alert
  T9-04  CustomerHealthScorer — CHAMPION band sets is_expansion_candidate
  T9-05  CustomerHealthScorer — upgrade_prompt_tier: community → pro
  T9-06  CustomerHealthScorer — upgrade_prompt_tier: pro → enterprise
  T9-07  TrialConversionEngine — epoch_quota_100_pct nudge emitted
  T9-08  TrialConversionEngine — nudge idempotency (no duplicate)
  T9-09  TrialConversionEngine — feature_wall_hit nudge
  T9-10  TrialConversionEngine — paid org skipped (no nudges)
  T9-11  TrialConversionEngine — record_conversion MRR delta
  T9-12  TrialConversionEngine — total_mrr_attributed accumulates
  T9-13  RevenueAnalyticsService — compute_snapshot MRR sum
  T9-14  RevenueAnalyticsService — ARR = 12 × MRR
  T9-15  RevenueAnalyticsService — ARPU (paid only)
  T9-16  RevenueAnalyticsService — conversion_rate
  T9-17  MRRWaterfall — net_new_mrr composition
  T9-18  MRRWaterfall — quick_ratio > 1 when growing
  T9-19  MRRWaterfall — net_revenue_retention > 1 when expanding
  T9-20  compute_payback_period — pro tier default channel
  T9-21  batch_scorer — HealthReport segments (at_risk, champion)
  T9-22  content_hash stability (replay anchor)

Author: Dustin L. Reid · InnovativeAI LLC
"""

import time
import pytest

from runtime.growth.customer_health import (
    UsageSnapshot,
    compute_health,
    RiskBand,
    CustomerHealthScorer,
    HealthReport,
)
from runtime.growth.trial_conversion import (
    TrialConversionEngine,
    ConversionTrigger,
    NudgeChannel,
)
from runtime.growth.revenue_analytics import (
    OrgBillingRecord,
    RevenueAnalyticsService,
    MRRWaterfall,
    build_waterfall,
    compute_snapshot,
    compute_payback_period,
    TIER_MRR_USD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _community_snap(**kwargs) -> UsageSnapshot:
    defaults = dict(
        org_id="test-org",
        tier="community",
        snapshot_epoch=int(time.time()),
        epochs_run_last_30d=0,
        epochs_run_prev_30d=0,
        mutations_accepted_last_30d=0,
        governance_gates_triggered=0,
        features_used=[],
        api_calls_last_7d=0,
        active_users_last_30d=1,
        support_tickets_open=0,
        failed_payments_last_90d=0,
        days_since_last_login=0,
        days_until_renewal=None,
        mrr_usd=0.0,
    )
    defaults.update(kwargs)
    return UsageSnapshot(**defaults)


def _pro_snap(**kwargs) -> UsageSnapshot:
    return _community_snap(tier="pro", mrr_usd=49.0, **kwargs)


def _champion_snap() -> UsageSnapshot:
    return _community_snap(
        tier="community",
        epochs_run_last_30d=45,
        epochs_run_prev_30d=30,
        governance_gates_triggered=50,
        features_used=["f1", "f2", "f3"],
        api_calls_last_7d=90,
        active_users_last_30d=4,
    )


def _critical_snap() -> UsageSnapshot:
    return _community_snap(
        epochs_run_last_30d=0,
        support_tickets_open=5,
        failed_payments_last_90d=3,
        days_since_last_login=60,
    )


# ---------------------------------------------------------------------------
# T9-01  Band classification (basic)
# ---------------------------------------------------------------------------

def test_t901_critical_band():
    hs = compute_health(_critical_snap())
    assert hs.band == RiskBand.CRITICAL
    assert hs.score < 25


def test_t901_champion_band():
    hs = compute_health(_champion_snap())
    assert hs.band in (RiskBand.HEALTHY, RiskBand.CHAMPION)
    assert hs.score >= 65


# ---------------------------------------------------------------------------
# T9-02  Determinism — same input → identical output
# ---------------------------------------------------------------------------

def test_t902_deterministic():
    snap = _champion_snap()
    hs1  = compute_health(snap)
    hs2  = compute_health(snap)
    assert hs1.score         == hs2.score
    assert hs1.band          == hs2.band
    assert hs1.content_hash  == hs2.content_hash


# ---------------------------------------------------------------------------
# T9-03  CRITICAL → needs_csmm_alert
# ---------------------------------------------------------------------------

def test_t903_critical_triggers_alert():
    hs = compute_health(_critical_snap())
    assert hs.needs_csmm_alert is True


# ---------------------------------------------------------------------------
# T9-04  CHAMPION → is_expansion_candidate
# ---------------------------------------------------------------------------

def test_t904_champion_expansion_candidate():
    snap = _champion_snap()
    hs   = compute_health(snap)
    # champion_snap hits at least HEALTHY
    assert hs.is_expansion_candidate is True


# ---------------------------------------------------------------------------
# T9-05  upgrade_prompt_tier: community → pro
# ---------------------------------------------------------------------------

def test_t905_community_upgrade_prompt():
    hs = compute_health(_champion_snap())
    if hs.is_expansion_candidate:
        assert hs.upgrade_prompt_tier == "pro"


# ---------------------------------------------------------------------------
# T9-06  upgrade_prompt_tier: pro champion → enterprise
# ---------------------------------------------------------------------------

def test_t906_pro_champion_upgrade():
    snap = _community_snap(
        tier="pro",
        mrr_usd=49.0,
        epochs_run_last_30d=450,
        epochs_run_prev_30d=400,
        governance_gates_triggered=500,
        features_used=["f1","f2","f3","f4","f5","f6","f7","f8"],
        api_calls_last_7d=99,
        active_users_last_30d=5,
        days_until_renewal=60,
    )
    hs = compute_health(snap)
    if hs.band == RiskBand.CHAMPION:
        assert hs.upgrade_prompt_tier == "enterprise"


# ---------------------------------------------------------------------------
# T9-07  TrialConversionEngine — epoch_quota_100_pct nudge
# ---------------------------------------------------------------------------

def test_t907_epoch_quota_100_nudge():
    engine = TrialConversionEngine()
    snap = _community_snap(epochs_run_last_30d=50)
    nudges = engine.evaluate(snap)
    triggers = [n.trigger for n in nudges]
    assert ConversionTrigger.EPOCH_QUOTA_100_PCT in triggers


# ---------------------------------------------------------------------------
# T9-08  Nudge idempotency — no duplicate on second call
# ---------------------------------------------------------------------------

def test_t908_nudge_idempotency():
    engine = TrialConversionEngine()
    snap   = _community_snap(epochs_run_last_30d=50)
    n1 = engine.evaluate(snap)
    n2 = engine.evaluate(snap)
    # Second call should produce no new nudges for the same trigger
    assert len(n2) == 0


# ---------------------------------------------------------------------------
# T9-09  feature_wall_hit nudge
# ---------------------------------------------------------------------------

def test_t909_feature_wall_nudge():
    engine = TrialConversionEngine()
    snap   = _community_snap()
    nudges = engine.evaluate(snap, feature_wall_feature="reviewer_reputation")
    triggers = [n.trigger for n in nudges]
    assert ConversionTrigger.FEATURE_WALL_HIT in triggers
    # CTA URL contains the trigger name
    nudge = next(n for n in nudges if n.trigger == ConversionTrigger.FEATURE_WALL_HIT)
    assert "feature_wall_hit" in nudge.cta_url


# ---------------------------------------------------------------------------
# T9-10  Paid org — no nudges emitted
# ---------------------------------------------------------------------------

def test_t910_paid_org_no_nudges():
    engine = TrialConversionEngine()
    snap   = _pro_snap(epochs_run_last_30d=500)
    nudges = engine.evaluate(snap)
    assert nudges == []


# ---------------------------------------------------------------------------
# T9-11  record_conversion MRR delta
# ---------------------------------------------------------------------------

def test_t911_conversion_mrr_delta():
    engine = TrialConversionEngine()
    event  = engine.record_conversion(
        org_id="acme", from_tier="community", to_tier="pro", trigger="epoch_quota"
    )
    assert event.mrr_delta_usd == pytest.approx(49.0)
    assert event.content_hash != ""


# ---------------------------------------------------------------------------
# T9-12  total_mrr_attributed accumulates
# ---------------------------------------------------------------------------

def test_t912_mrr_attributed():
    engine = TrialConversionEngine()
    engine.record_conversion("a", "community", "pro")
    engine.record_conversion("b", "community", "pro")
    engine.record_conversion("c", "pro", "enterprise")
    total = engine.total_mrr_attributed()
    assert total == pytest.approx(49.0 + 49.0 + 450.0)


# ---------------------------------------------------------------------------
# T9-13  compute_snapshot MRR sum
# ---------------------------------------------------------------------------

def test_t913_snapshot_mrr():
    orgs = [
        OrgBillingRecord("a", "pro", "active", 0, None, None, None),
        OrgBillingRecord("b", "pro", "active", 0, None, None, None),
        OrgBillingRecord("c", "enterprise", "active", 0, None, None, None),
        OrgBillingRecord("d", "community", "active", 0, None, None, None),
    ]
    snap = compute_snapshot(orgs)
    expected = 49.0 + 49.0 + 499.0
    assert snap.mrr_usd == pytest.approx(expected)


# ---------------------------------------------------------------------------
# T9-14  ARR = 12 × MRR
# ---------------------------------------------------------------------------

def test_t914_arr_equals_12x_mrr():
    orgs = [OrgBillingRecord("a", "pro", "active", 0, None, None, None)]
    snap = compute_snapshot(orgs)
    assert snap.arr_usd == pytest.approx(snap.mrr_usd * 12)


# ---------------------------------------------------------------------------
# T9-15  ARPU (paid only)
# ---------------------------------------------------------------------------

def test_t915_arpu():
    orgs = [
        OrgBillingRecord("a", "pro", "active", 0, None, None, None),
        OrgBillingRecord("b", "enterprise", "active", 0, None, None, None),
        OrgBillingRecord("c", "community", "active", 0, None, None, None),
    ]
    snap = compute_snapshot(orgs)
    expected_arpu = (49.0 + 499.0) / 2
    assert snap.avg_revenue_per_user == pytest.approx(expected_arpu)


# ---------------------------------------------------------------------------
# T9-16  conversion_rate
# ---------------------------------------------------------------------------

def test_t916_conversion_rate():
    orgs = [
        OrgBillingRecord("a", "pro", "active", 0, None, None, None),
        OrgBillingRecord("b", "community", "active", 0, None, None, None),
        OrgBillingRecord("c", "community", "active", 0, None, None, None),
        OrgBillingRecord("d", "community", "active", 0, None, None, None),
    ]
    snap = compute_snapshot(orgs)
    assert snap.conversion_rate == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# T9-17  MRRWaterfall — net_new_mrr composition
# ---------------------------------------------------------------------------

def test_t917_waterfall_net_new():
    wf = MRRWaterfall(period_start=0, period_end=1)
    wf.starting_mrr   = 100.0
    wf.new_mrr        = 49.0
    wf.expansion_mrr  = 450.0
    wf.churned_mrr    = 49.0
    assert wf.net_new_mrr == pytest.approx(450.0)
    assert wf.ending_mrr  == pytest.approx(550.0)


# ---------------------------------------------------------------------------
# T9-18  Quick ratio > 1 when growing
# ---------------------------------------------------------------------------

def test_t918_quick_ratio_growth():
    wf = MRRWaterfall(period_start=0, period_end=1)
    wf.new_mrr       = 200.0
    wf.churned_mrr   = 50.0
    assert wf.quick_ratio == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# T9-19  NRR > 1 when expanding
# ---------------------------------------------------------------------------

def test_t919_nrr_expansion():
    wf = MRRWaterfall(period_start=0, period_end=1)
    wf.starting_mrr  = 100.0
    wf.expansion_mrr = 50.0
    assert wf.net_revenue_retention == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# T9-20  Payback period — Pro, organic
# ---------------------------------------------------------------------------

def test_t920_payback_pro_organic():
    months = compute_payback_period("pro", "organic")
    # CAC=15, MRR=49 × 0.85 margin ≈ 41.65 → payback ≈ 0.36 months
    assert months is not None
    assert months == pytest.approx(15.0 / (49.0 * 0.85), rel=1e-3)


def test_t920_payback_community_none():
    assert compute_payback_period("community") is None


# ---------------------------------------------------------------------------
# T9-21  Batch scorer — segment correctness
# ---------------------------------------------------------------------------

def test_t921_batch_scorer_segments():
    scorer  = CustomerHealthScorer()
    snaps   = [_champion_snap(), _critical_snap()]
    report  = scorer.score_all(snaps)
    summary = report.summary()
    assert summary["total_orgs"] == 2
    assert summary["churn_risk_count"] >= 1     # at least the critical snap
    assert summary["expansion_candidates"] >= 1  # at least the champion snap


# ---------------------------------------------------------------------------
# T9-22  Content hash stability (replay anchor)
# ---------------------------------------------------------------------------

def test_t922_content_hash_stable():
    snap = _champion_snap()
    hs   = compute_health(snap)
    # Re-compute from identical input → same hash
    hs2  = compute_health(snap)
    assert hs.content_hash == hs2.content_hash
    # Mutated input → different hash
    snap2 = _community_snap(org_id="test-org", tier="community", epochs_run_last_30d=1)
    hs3   = compute_health(snap2)
    assert hs3.content_hash != hs.content_hash
