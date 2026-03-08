# SPDX-License-Identifier: Apache-2.0
"""Admin API Router — ADAAD Phase 8, M8-10.

Internal administration endpoints for InnovativeAI LLC operations:
  - Organisation CRUD
  - API key provisioning and rotation
  - Usage dashboards
  - Org tier management
  - Notification channel management

⚠ These endpoints are gated behind ADAAD_ADMIN_TOKEN (env var).
   Never expose the admin router without this token set.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from runtime.monetization.org_registry import (
    OrgRegistry,
    Organisation,
    OrgStatus,
    OrgNotFound,
    OrgAlreadyExists,
)
from runtime.monetization.onboarding_service import OnboardingService, validate_org_id
from runtime.monetization.usage_tracker import UsageTracker
from runtime.monetization.tier_engine import TierEngine, Tier, ALL_TIERS


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _admin_auth(authorization: Optional[str] = Header(default=None)) -> str:
    """Validate admin bearer token. Fail-closed if token not set."""
    expected = os.environ.get("ADAAD_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin API disabled: ADAAD_ADMIN_TOKEN not set",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = authorization[7:].strip()
    import hmac
    # Constant-time comparison
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return token


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateOrgRequest(BaseModel):
    org_id:             str
    display_name:       str
    tier:               str = "community"
    stripe_customer_id: Optional[str] = None
    expires_at:         Optional[int] = None
    metadata:           Dict[str, Any] = {}


class SetTierRequest(BaseModel):
    tier:   str
    reason: str = ""


class SetStatusRequest(BaseModel):
    status: str
    reason: str = ""


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_admin_router(
    org_registry:   OrgRegistry,
    onboarding:     OnboardingService,
    usage_tracker:  UsageTracker,
    tier_engine:    TierEngine,
) -> APIRouter:
    """Build the admin APIRouter with injected dependencies."""
    router = APIRouter(
        prefix="/api/admin",
        tags=["admin"],
        dependencies=[Depends(_admin_auth)],
    )

    # ---------------------------------------------------------------
    # Dashboard
    # ---------------------------------------------------------------

    @router.get("/dashboard")
    def admin_dashboard():
        """InnovativeAI LLC operations dashboard — org counts, revenue summary."""
        counts = org_registry.count()
        orgs   = org_registry.list_all()

        # Revenue estimate (MRR based on active paid orgs)
        prices = {t.value: ALL_TIERS[t].monthly_price_usd for t in Tier}
        mrr = sum(
            prices.get(o.tier, 0.0)
            for o in orgs
            if o.status == OrgStatus.ACTIVE and o.tier != "community"
        )

        return {
            "org_counts":      counts,
            "estimated_mrr":   round(mrr, 2),
            "currency":        "USD",
            "active_orgs":     sum(1 for o in orgs if o.status == OrgStatus.ACTIVE),
            "grace_period_orgs": sum(1 for o in orgs if o.status == OrgStatus.GRACE_PERIOD),
            "platform_version": _read_version(),
        }

    # ---------------------------------------------------------------
    # Org management
    # ---------------------------------------------------------------

    @router.get("/orgs")
    def list_orgs(tier: Optional[str] = None, status: Optional[str] = None):
        """List all organisations with optional tier/status filter."""
        orgs = org_registry.list_all()
        if tier:
            orgs = [o for o in orgs if o.tier == tier]
        if status:
            orgs = [o for o in orgs if o.status.value == status]
        return {
            "count": len(orgs),
            "orgs":  [o.to_public_dict() for o in orgs],
        }

    @router.get("/orgs/{org_id}")
    def get_org(org_id: str):
        """Get full org details."""
        try:
            org = org_registry.get(org_id)
        except OrgNotFound:
            raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
        return org.to_dict()

    @router.post("/orgs")
    def create_org(body: CreateOrgRequest):
        """Provision a new organisation and generate its first API key."""
        try:
            validate_org_id(body.org_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        try:
            result = onboarding.onboard(
                org_id             = body.org_id,
                display_name       = body.display_name,
                tier               = body.tier,
                stripe_customer_id = body.stripe_customer_id,
                expires_at         = body.expires_at,
                metadata           = body.metadata,
            )
        except OrgAlreadyExists:
            raise HTTPException(status_code=409, detail=f"Org already exists: {body.org_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        return {
            "created":  True,
            "result":   result.to_dict(),
            "warning":  "API key shown once — store securely.",
        }

    @router.put("/orgs/{org_id}/tier")
    def set_org_tier(org_id: str, body: SetTierRequest):
        """Change an org's tier."""
        if body.tier not in {"community", "pro", "enterprise"}:
            raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier}")
        try:
            org = org_registry.set_tier(org_id, body.tier, reason=body.reason)
        except OrgNotFound:
            raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
        return {"updated": True, "org_id": org_id, "new_tier": org.tier}

    @router.put("/orgs/{org_id}/status")
    def set_org_status(org_id: str, body: SetStatusRequest):
        """Change an org's status (active/grace_period/suspended/deleted)."""
        try:
            new_status = OrgStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown status: {body.status}")
        try:
            org = org_registry.set_status(org_id, new_status, reason=body.reason)
        except OrgNotFound:
            raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
        return {"updated": True, "org_id": org_id, "new_status": org.status.value}

    @router.delete("/orgs/{org_id}")
    def delete_org(org_id: str):
        """Soft-delete an org (status → deleted)."""
        try:
            org = org_registry.soft_delete(org_id)
        except OrgNotFound:
            raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
        return {"deleted": True, "org_id": org_id, "status": org.status.value}

    # ---------------------------------------------------------------
    # Key management
    # ---------------------------------------------------------------

    @router.post("/orgs/{org_id}/keys/rotate")
    def rotate_key(org_id: str, expires_at: Optional[int] = None):
        """Issue a new API key for an org. Old key stays valid until revoked."""
        try:
            result = onboarding.rotate_key(org_id, expires_at=expires_at)
        except OrgNotFound:
            raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return {
            "rotated": True,
            "result":  result.to_dict(),
            "warning": "New API key shown once — store securely.",
        }

    # ---------------------------------------------------------------
    # Usage
    # ---------------------------------------------------------------

    @router.get("/usage/{org_id}")
    def org_usage(org_id: str, epoch_window: str = ""):
        """Return usage summary for an org in a billing window."""
        window = epoch_window or _current_window()
        return usage_tracker.usage_summary(org_id, window)

    @router.get("/usage")
    def global_usage(epoch_window: str = ""):
        """Return aggregate usage across all orgs."""
        window  = epoch_window or _current_window()
        orgs    = org_registry.list_all()
        summaries = [
            usage_tracker.usage_summary(o.org_id, window)
            for o in orgs
        ]
        return {
            "epoch_window": window,
            "org_count":    len(summaries),
            "summaries":    summaries,
        }

    # ---------------------------------------------------------------
    # Revenue
    # ---------------------------------------------------------------

    @router.get("/revenue")
    def revenue_summary():
        """Monthly Recurring Revenue breakdown by tier."""
        orgs   = org_registry.list_all()
        prices = {t.value: ALL_TIERS[t].monthly_price_usd for t in Tier}
        breakdown: Dict[str, Any] = {"community": 0, "pro": 0, "enterprise": 0}

        for org in orgs:
            if org.status == OrgStatus.ACTIVE:
                breakdown[org.tier] = breakdown.get(org.tier, 0) + 1

        mrr = sum(
            count * prices.get(tier, 0.0)
            for tier, count in breakdown.items()
        )

        return {
            "currency":        "USD",
            "estimated_mrr":   round(mrr, 2),
            "estimated_arr":   round(mrr * 12, 2),
            "active_orgs_by_tier": breakdown,
            "pricing":         {t: prices[t] for t in prices},
            "note":            "MRR based on active paid orgs at base plan price. Enterprise custom contracts not reflected.",
        }

    return router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_window() -> str:
    """Return current billing window key (YYYY-MM)."""
    import datetime
    return datetime.date.today().strftime("%Y-%m")


def _read_version() -> str:
    """Read VERSION file."""
    try:
        from pathlib import Path
        return Path("VERSION").read_text().strip()
    except Exception:
        return "unknown"
