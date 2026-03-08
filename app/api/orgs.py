# SPDX-License-Identifier: Apache-2.0
"""Public Orgs API — ADAAD Phase 8, M8-11.

Self-serve organisation creation endpoint. Called by:
  - The ADAAD sign-up flow (after Stripe checkout completes)
  - CLI users provisioning a Community org

POST /api/orgs   — create org + get first API key
GET  /api/orgs/{org_id}/capabilities — tier capability summary

Rate-limited to 3 requests / 5 minutes per IP (creation is expensive).

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from runtime.monetization.onboarding_service import OnboardingService, validate_org_id
from runtime.monetization.org_registry import OrgRegistry, OrgNotFound, OrgAlreadyExists
from runtime.monetization.tier_engine import TierEngine, Tier


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateOrgPublicRequest(BaseModel):
    org_id:       str
    display_name: str
    tier:         str = "community"
    # Stripe checkout session ID or subscription ID supplied after payment
    stripe_session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Simple creation-rate limiter (per IP, separate from API key rate limiter)
# ---------------------------------------------------------------------------

class _CreationRateLimiter:
    MAX_CREATES_PER_WINDOW = 3
    WINDOW_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now    = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS
        with self._lock:
            dq = self._buckets[ip]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.MAX_CREATES_PER_WINDOW:
                return False
            dq.append(now)
            return True


_creation_limiter = _CreationRateLimiter()


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_orgs_router(
    org_registry: OrgRegistry,
    onboarding:   OnboardingService,
    tier_engine:  TierEngine,
) -> APIRouter:
    """Build the public orgs APIRouter with injected dependencies."""
    router = APIRouter(prefix="/api/orgs", tags=["orgs"])

    @router.post("")
    def create_org(body: CreateOrgPublicRequest, request: Request):
        """Self-serve org creation.

        Creates a Community org with a free API key, or a paid org if a
        Stripe session ID is provided. Returns the API key exactly once.
        """
        # IP-based creation rate limit
        client_ip = (request.client.host if request.client else "unknown")
        if not _creation_limiter.is_allowed(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Too many org creation requests. Try again in 5 minutes.",
            )

        # Validate tier
        if body.tier not in {"community", "pro", "enterprise"}:
            raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier!r}")

        # Paid orgs via public endpoint require a Stripe session (prevent free tier abuse)
        if body.tier != "community" and not body.stripe_session_id:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Tier '{body.tier}' requires a completed Stripe checkout. "
                    "Complete payment at https://innovativeai.io/adaad/upgrade "
                    "and retry with your stripe_session_id."
                ),
            )

        try:
            validate_org_id(body.org_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        try:
            result = onboarding.onboard(
                org_id       = body.org_id,
                display_name = body.display_name,
                tier         = body.tier,
                metadata     = {"stripe_session_id": body.stripe_session_id},
            )
        except OrgAlreadyExists:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Organisation '{body.org_id}' already exists. "
                    "Choose a different org_id or contact support@innovativeai.io."
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Org creation failed")

        return {
            "created":     True,
            "org_id":      result.org.org_id,
            "display_name": result.org.display_name,
            "tier":        result.tier,
            "api_key":     result.api_key,
            "kid":         result.kid,
            "warning":     "⚠️  Store your API key securely — it cannot be retrieved after this response.",
            "docs":        "https://innovativeai.io/adaad/docs/quickstart",
            "next_steps": [
                "Set ADAAD_API_KEY=<your_api_key> in your environment",
                "Run: python onboard.py",
                "Start your first epoch: python -m app.main --verbose",
            ],
        }

    @router.get("/{org_id}/capabilities")
    def org_capabilities(org_id: str):
        """Return the capability summary for an org's current tier."""
        try:
            org = org_registry.get(org_id)
        except OrgNotFound:
            raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")

        try:
            tier = Tier(org.tier)
        except ValueError:
            tier = Tier.COMMUNITY

        summary = tier_engine.capability_summary(tier)
        upgrade_url = tier_engine.upgrade_path(tier, Tier.PRO) if tier == Tier.COMMUNITY else None

        return {
            "org_id":      org_id,
            "capabilities": summary,
            "upgrade_url":  upgrade_url,
        }

    return router
