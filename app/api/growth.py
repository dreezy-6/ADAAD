# SPDX-License-Identifier: MIT
"""Growth API Router — ADAAD Phase 9, M9-04.

FastAPI router exposing customer health, trial conversion, and revenue
analytics to the Aponi dashboard and the Admin CLI.

Endpoints
---------
GET  /api/growth/health                — portfolio-level health report
GET  /api/growth/health/{org_id}       — single-org health score
GET  /api/growth/revenue               — MRR/ARR dashboard snapshot
GET  /api/growth/revenue/trend         — MRR trend (last 30 snapshots)
GET  /api/growth/conversion            — conversion funnel summary
POST /api/growth/conversion/evaluate   — evaluate nudge triggers for an org
GET  /api/growth/churn/at-risk         — orgs in CRITICAL or AT_RISK band

All endpoints require ADAAD_ADMIN_TOKEN (same guard as /api/admin/*).

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hmac
import os
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

from runtime.growth.customer_health import (
    CustomerHealthScorer,
    UsageSnapshot,
    compute_health,
    HealthReport,
)
from runtime.growth.trial_conversion import TrialConversionEngine
from runtime.growth.revenue_analytics import (
    OrgBillingRecord,
    RevenueAnalyticsService,
    compute_payback_period,
)

# ---------------------------------------------------------------------------
# Service singletons (injected by server.py at startup)
# ---------------------------------------------------------------------------

_health_scorer: Optional[CustomerHealthScorer] = None
_conversion_engine: Optional[TrialConversionEngine] = None
_revenue_service: Optional[RevenueAnalyticsService] = None


def init_growth_services(
    health_scorer: CustomerHealthScorer,
    conversion_engine: TrialConversionEngine,
    revenue_service: RevenueAnalyticsService,
) -> None:
    """Called by server.py at startup to inject shared service instances."""
    global _health_scorer, _conversion_engine, _revenue_service
    _health_scorer       = health_scorer
    _conversion_engine   = conversion_engine
    _revenue_service     = revenue_service


def _require_admin_token(request: "Request") -> None:
    """Dependency: validate ADAAD_ADMIN_TOKEN header."""
    expected = os.environ.get("ADAAD_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Admin token not configured")
    provided = request.headers.get("X-Admin-Token", "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    class UsageSnapshotRequest(BaseModel):
        org_id: str
        tier: str
        epochs_run_last_30d: int = 0
        epochs_run_prev_30d: int = 0
        mutations_accepted_last_30d: int = 0
        governance_gates_triggered: int = 0
        features_used: List[str] = []
        api_calls_last_7d: int = 0
        active_users_last_30d: int = 1
        support_tickets_open: int = 0
        failed_payments_last_90d: int = 0
        days_since_last_login: int = 0
        days_until_renewal: Optional[int] = None
        mrr_usd: float = 0.0
        active_days_streak: int = 0
        feature_wall_feature: Optional[str] = None
        referral_sent: bool = False

    class OrgBillingRequest(BaseModel):
        org_id: str
        tier: str
        status: str = "active"
        created_at: int = 0
        converted_at: Optional[int] = None
        last_payment_at: Optional[int] = None
        churn_at: Optional[int] = None
        acquisition_channel: str = "default"

    class RevenueSnapshotRequest(BaseModel):
        orgs: List[OrgBillingRequest]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    router = APIRouter(prefix="/api/growth", tags=["growth"])

    # --- Health endpoints ---------------------------------------------------

    @router.get("/health")
    async def portfolio_health(
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Return a portfolio-level health summary (requires snapshot data)."""
        return {
            "status": "ok",
            "message": "POST /api/growth/conversion/evaluate per org to compute health scores",
            "timestamp": int(time.time()),
        }

    @router.post("/health/score")
    async def compute_org_health(
        payload: "UsageSnapshotRequest",
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Compute a health score for a single org from a usage snapshot."""
        snap = UsageSnapshot(
            org_id=payload.org_id,
            tier=payload.tier,
            snapshot_epoch=int(time.time()),
            epochs_run_last_30d=payload.epochs_run_last_30d,
            epochs_run_prev_30d=payload.epochs_run_prev_30d,
            mutations_accepted_last_30d=payload.mutations_accepted_last_30d,
            governance_gates_triggered=payload.governance_gates_triggered,
            features_used=payload.features_used,
            api_calls_last_7d=payload.api_calls_last_7d,
            active_users_last_30d=payload.active_users_last_30d,
            support_tickets_open=payload.support_tickets_open,
            failed_payments_last_90d=payload.failed_payments_last_90d,
            days_since_last_login=payload.days_since_last_login,
            days_until_renewal=payload.days_until_renewal,
            mrr_usd=payload.mrr_usd,
        )
        hs = compute_health(snap)
        return hs.to_dict()

    # --- Revenue endpoints --------------------------------------------------

    @router.post("/revenue/snapshot")
    async def record_revenue_snapshot(
        payload: "RevenueSnapshotRequest",
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Record an MRR snapshot and return the computed dashboard."""
        if _revenue_service is None:
            raise HTTPException(status_code=503, detail="Revenue service not initialised")
        orgs = [
            OrgBillingRecord(
                org_id=o.org_id,
                tier=o.tier,
                status=o.status,
                created_at=o.created_at or int(time.time()),
                converted_at=o.converted_at,
                last_payment_at=o.last_payment_at,
                churn_at=o.churn_at,
                acquisition_channel=o.acquisition_channel,
            )
            for o in payload.orgs
        ]
        snap = _revenue_service.record_snapshot(orgs)
        return snap.to_dict()

    @router.get("/revenue")
    async def revenue_dashboard(
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Current MRR/ARR dashboard snapshot."""
        if _revenue_service is None:
            raise HTTPException(status_code=503, detail="Revenue service not initialised")
        return _revenue_service.dashboard()

    @router.get("/revenue/trend")
    async def revenue_trend(
        request: Request,
        n: int = 30,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """MRR trend for the last *n* snapshots."""
        if _revenue_service is None:
            raise HTTPException(status_code=503, detail="Revenue service not initialised")
        return {"trend": _revenue_service.mrr_trend(n=n)}

    @router.get("/revenue/payback")
    async def payback_period(
        request: Request,
        tier: str = "pro",
        channel: str = "default",
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """CAC payback period estimate for a tier + acquisition channel."""
        months = compute_payback_period(tier, channel)
        return {
            "tier": tier,
            "channel": channel,
            "payback_months": months,
            "note": "Assumes 85% gross margin",
        }

    # --- Conversion endpoints -----------------------------------------------

    @router.post("/conversion/evaluate")
    async def evaluate_conversion(
        payload: "UsageSnapshotRequest",
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Evaluate upgrade nudge triggers for a Community org."""
        if _conversion_engine is None:
            raise HTTPException(status_code=503, detail="Conversion engine not initialised")
        snap = UsageSnapshot(
            org_id=payload.org_id,
            tier=payload.tier,
            snapshot_epoch=int(time.time()),
            epochs_run_last_30d=payload.epochs_run_last_30d,
            epochs_run_prev_30d=payload.epochs_run_prev_30d,
            mutations_accepted_last_30d=payload.mutations_accepted_last_30d,
            governance_gates_triggered=payload.governance_gates_triggered,
            features_used=payload.features_used,
            api_calls_last_7d=payload.api_calls_last_7d,
            active_users_last_30d=payload.active_users_last_30d,
            support_tickets_open=payload.support_tickets_open,
            failed_payments_last_90d=payload.failed_payments_last_90d,
            days_since_last_login=payload.days_since_last_login,
            days_until_renewal=payload.days_until_renewal,
            mrr_usd=payload.mrr_usd,
        )
        hs = compute_health(snap)
        nudges = _conversion_engine.evaluate(
            snap=snap,
            health_score=hs.score,
            active_days_streak=payload.active_days_streak,
            feature_wall_feature=payload.feature_wall_feature,
            referral_sent=payload.referral_sent,
        )
        return {
            "org_id": snap.org_id,
            "health_score": hs.score,
            "risk_band": hs.band.value,
            "nudges_queued": len(nudges),
            "nudges": [
                {
                    "trigger": n.trigger.value,
                    "channel": n.channel.value,
                    "headline": n.headline,
                    "cta_url": n.cta_url,
                    "idempotency_key": n.idempotency_key,
                }
                for n in nudges
            ],
        }

    @router.get("/conversion/summary")
    async def conversion_summary(
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Conversion funnel summary (pending nudges + conversion log)."""
        if _conversion_engine is None:
            raise HTTPException(status_code=503, detail="Conversion engine not initialised")
        return {
            "total_nudges_pending": len(_conversion_engine.pending_nudges()),
            "total_conversions": len(_conversion_engine.conversion_log()),
            "mrr_attributed_usd": round(_conversion_engine.total_mrr_attributed(), 2),
        }

    # --- Churn at-risk endpoint ---------------------------------------------

    @router.post("/churn/at-risk")
    async def churn_at_risk(
        snapshots: List["UsageSnapshotRequest"],
        request: Request,
        _: None = Depends(_require_admin_token),
    ) -> Dict[str, Any]:
        """Return orgs in CRITICAL or AT_RISK health band from a batch of snapshots."""
        results = []
        for payload in snapshots:
            snap = UsageSnapshot(
                org_id=payload.org_id,
                tier=payload.tier,
                snapshot_epoch=int(time.time()),
                epochs_run_last_30d=payload.epochs_run_last_30d,
                epochs_run_prev_30d=payload.epochs_run_prev_30d,
                mutations_accepted_last_30d=payload.mutations_accepted_last_30d,
                governance_gates_triggered=payload.governance_gates_triggered,
                features_used=payload.features_used,
                api_calls_last_7d=payload.api_calls_last_7d,
                active_users_last_30d=payload.active_users_last_30d,
                support_tickets_open=payload.support_tickets_open,
                failed_payments_last_90d=payload.failed_payments_last_90d,
                days_since_last_login=payload.days_since_last_login,
                days_until_renewal=payload.days_until_renewal,
                mrr_usd=payload.mrr_usd,
            )
            hs = compute_health(snap)
            if hs.needs_csmm_alert or hs.band.value == "at_risk":
                results.append(hs.to_dict())

        return {
            "at_risk_count": len(results),
            "orgs": results,
        }

else:
    # Fallback for environments without FastAPI
    router = None  # type: ignore
