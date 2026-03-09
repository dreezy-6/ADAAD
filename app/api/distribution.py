# SPDX-License-Identifier: MIT
"""Distribution API Router — ADAAD Phase 10, M10-04.

FastAPI router for all Phase 10 distribution and growth surfaces:

  Referral endpoints:
    GET  /api/distribution/referral/code          — get your referral code
    POST /api/distribution/referral/register       — register incoming referral
    POST /api/distribution/referral/qualify        — record qualifying action
    GET  /api/distribution/referral/rewards        — org's pending rewards
    GET  /api/distribution/referral/leaderboard    — top referrers

  Marketplace endpoints:
    POST /api/distribution/marketplace/purchase    — handle marketplace webhook
    POST /api/distribution/marketplace/install     — handle app install webhook
    GET  /api/distribution/marketplace/stats       — install + conversion stats

  Deploy endpoints:
    GET  /api/distribution/deploy/railway          — download railway.json
    GET  /api/distribution/deploy/render           — download render.yaml
    GET  /api/distribution/deploy/dockerfile       — download Dockerfile
    GET  /api/distribution/deploy/compose          — download docker-compose.yml
    GET  /api/distribution/deploy/fly              — download fly.toml
    GET  /api/distribution/deploy/bundle           — all manifests as JSON

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hmac
import os
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Request
    from fastapi.responses import JSONResponse, PlainTextResponse
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

from runtime.distribution.referral_engine import (
    ReferralEngine,
    ReferralQualifyingAction,
    NudgeChannel,
)
from runtime.distribution.marketplace import (
    GitHubMarketplaceProcessor,
    parse_marketplace_event,
    parse_installation_event,
    verify_github_marketplace_signature,
)
from runtime.distribution.deploy_manifests import (
    DeployConfig,
    DeployPlatform,
    generate_all,
    generate_railway_json,
    generate_render_yaml,
    generate_dockerfile,
    generate_docker_compose,
    generate_fly_toml,
)

# ---------------------------------------------------------------------------
# Service singletons (injected by server.py)
# ---------------------------------------------------------------------------

_referral_engine: Optional[ReferralEngine] = None
_marketplace_processor: Optional[GitHubMarketplaceProcessor] = None


def init_distribution_services(
    referral_engine: ReferralEngine,
    marketplace_processor: GitHubMarketplaceProcessor,
) -> None:
    global _referral_engine, _marketplace_processor
    _referral_engine          = referral_engine
    _marketplace_processor    = marketplace_processor


def _require_admin(request: "Request") -> None:
    expected = os.environ.get("ADAAD_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Admin token not configured")
    provided = request.headers.get("X-Admin-Token", "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, "Invalid admin token")


def _get_org_id(request: "Request") -> str:
    """Extract org_id from Bearer token header (or fallback to query param)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        # First 2 chars of tier prefix + 6 chars org_id portion (simplified)
        # In production, parse from ApiKeyManager.validate()
        return token.split("_")[2] if token.count("_") >= 2 else "unknown"
    return request.query_params.get("org_id", "unknown")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    router = APIRouter(prefix="/api/distribution", tags=["distribution"])

    # ===================================================================
    # Referral endpoints
    # ===================================================================

    class ReferralRegisterRequest(BaseModel):
        org_id: str
        referral_code: str

    class ReferralQualifyRequest(BaseModel):
        referred_org_id: str
        action: str   # ReferralQualifyingAction value

    @router.get("/referral/code")
    async def get_referral_code(
        request: Request,
        org_id: str,
    ) -> Dict[str, Any]:
        """Get the stable referral code for an org."""
        if not _referral_engine:
            raise HTTPException(503, "Referral engine not initialised")
        code = _referral_engine.code_for_org(org_id)
        share_url = f"https://innovativeai.dev/?ref={code}"
        return {
            "org_id": org_id,
            "referral_code": code,
            "share_url": share_url,
            "rewards": {
                "first_epoch": "25 bonus epochs when your referral runs their first evolution",
                "pro_conversion": "$10 credit when your referral upgrades to Pro",
                "enterprise_conversion": "$50 credit when your referral goes Enterprise",
                "seven_day_active": "50 bonus epochs when your referral is active 7 days straight",
            },
        }

    @router.post("/referral/register")
    async def register_referral(
        payload: ReferralRegisterRequest,
    ) -> Dict[str, Any]:
        """Register an org as referred by a referral code."""
        if not _referral_engine:
            raise HTTPException(503, "Referral engine not initialised")
        ok, msg = _referral_engine.register_referral(
            referred_org_id=payload.org_id,
            referral_code=payload.referral_code,
        )
        if not ok:
            raise HTTPException(400, msg)
        return {"success": True, "message": msg}

    @router.post("/referral/qualify")
    async def qualify_referral(
        payload: ReferralQualifyRequest,
        request: Request,
        _: None = Depends(_require_admin),
    ) -> Dict[str, Any]:
        """Record a qualifying action for a referred org."""
        if not _referral_engine:
            raise HTTPException(503, "Referral engine not initialised")
        try:
            action = ReferralQualifyingAction(payload.action)
        except ValueError:
            raise HTTPException(400, f"Unknown action: {payload.action}")
        event = _referral_engine.qualify(payload.referred_org_id, action)
        if not event:
            return {"qualified": False, "reason": "org not referred or no referral chain"}
        return {
            "qualified": True,
            "event_id": event.event_id,
            "referrer": event.referrer_org_id,
            "reward_granted": event.reward_granted is not None,
            "reward": {
                "type": event.reward_granted.reward_type.value,
                "value": event.reward_granted.value,
                "description": event.reward_granted.description,
            } if event.reward_granted else None,
            "content_hash": event.content_hash,
        }

    @router.get("/referral/rewards")
    async def get_rewards(
        request: Request,
        org_id: str,
    ) -> Dict[str, Any]:
        """Return pending rewards for an org."""
        if not _referral_engine:
            raise HTTPException(503, "Referral engine not initialised")
        return {
            "org_id": org_id,
            "referral_count": _referral_engine.referral_count(org_id),
            "epoch_bonus_pending": _referral_engine.pending_epoch_bonus(org_id),
            "credit_usd_pending": round(_referral_engine.pending_credit_usd(org_id), 2),
            "viral_coefficient": round(_referral_engine.viral_coefficient(), 3),
        }

    @router.get("/referral/leaderboard")
    async def referral_leaderboard(
        request: Request,
        n: int = 10,
        _: None = Depends(_require_admin),
    ) -> Dict[str, Any]:
        """Top n referrers by referral count."""
        if not _referral_engine:
            raise HTTPException(503, "Referral engine not initialised")
        top = _referral_engine.top_referrers(n=n)
        return {
            "leaderboard": [{"org_id": o, "referrals": c} for o, c in top],
            "viral_coefficient": round(_referral_engine.viral_coefficient(), 3),
        }

    # ===================================================================
    # Marketplace endpoints
    # ===================================================================

    @router.post("/marketplace/purchase")
    async def marketplace_purchase(request: Request) -> Dict[str, Any]:
        """Handle GitHub Marketplace purchase/change/cancel webhook."""
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        body   = await request.body()
        sig    = request.headers.get("X-Hub-Signature-256", "")

        if secret and not verify_github_marketplace_signature(body, sig, secret):
            raise HTTPException(400, "Invalid webhook signature")

        import json
        payload = json.loads(body)
        event   = parse_marketplace_event(payload)
        if not event:
            raise HTTPException(400, "Not a valid marketplace event")

        if not _marketplace_processor:
            raise HTTPException(503, "Marketplace processor not initialised")

        result = _marketplace_processor.handle_marketplace(event)
        if not result.success:
            raise HTTPException(500, result.error or "Processing error")

        return {
            "success": True,
            "org_id": result.org_id,
            "action": result.action_taken,
            "tier_after": result.tier_after,
            "api_key_issued": result.api_key_issued is not None,
        }

    @router.post("/marketplace/install")
    async def marketplace_install(request: Request) -> Dict[str, Any]:
        """Handle GitHub App installation webhook."""
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        body   = await request.body()
        sig    = request.headers.get("X-Hub-Signature-256", "")

        if secret and not verify_github_marketplace_signature(body, sig, secret):
            raise HTTPException(400, "Invalid webhook signature")

        import json
        payload = json.loads(body)
        event   = parse_installation_event(payload)
        if not event:
            raise HTTPException(400, "Not a valid installation event")

        if not _marketplace_processor:
            raise HTTPException(503, "Marketplace processor not initialised")

        result = _marketplace_processor.handle_installation(event)
        return {
            "success": result.success,
            "org_id": result.org_id,
            "action": result.action_taken,
            "api_key_issued": result.api_key_issued is not None,
        }

    @router.get("/marketplace/stats")
    async def marketplace_stats(
        request: Request,
        _: None = Depends(_require_admin),
    ) -> Dict[str, Any]:
        """GitHub Marketplace install + conversion stats."""
        if not _marketplace_processor:
            raise HTTPException(503, "Marketplace processor not initialised")
        log = _marketplace_processor.process_log()
        return {
            "total_events_processed": len(log),
            "total_installs": _marketplace_processor.installs_count(),
            "recent_events": [
                {
                    "org_id": e.org_id,
                    "action": e.action_taken,
                    "tier_after": e.tier_after,
                }
                for e in log[-10:]
            ],
        }

    # ===================================================================
    # Deploy manifest endpoints
    # ===================================================================

    def _default_cfg() -> DeployConfig:
        return DeployConfig(platform=DeployPlatform.DOCKER)

    @router.get("/deploy/railway")
    async def deploy_railway() -> PlainTextResponse:
        return PlainTextResponse(
            generate_railway_json(_default_cfg()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=railway.json"},
        )

    @router.get("/deploy/render")
    async def deploy_render() -> PlainTextResponse:
        return PlainTextResponse(
            generate_render_yaml(_default_cfg()),
            media_type="text/yaml",
            headers={"Content-Disposition": "attachment; filename=render.yaml"},
        )

    @router.get("/deploy/dockerfile")
    async def deploy_dockerfile() -> PlainTextResponse:
        return PlainTextResponse(
            generate_dockerfile(_default_cfg()),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=Dockerfile"},
        )

    @router.get("/deploy/compose")
    async def deploy_compose() -> PlainTextResponse:
        return PlainTextResponse(
            generate_docker_compose(_default_cfg()),
            media_type="text/yaml",
            headers={"Content-Disposition": "attachment; filename=docker-compose.yml"},
        )

    @router.get("/deploy/fly")
    async def deploy_fly() -> PlainTextResponse:
        return PlainTextResponse(
            generate_fly_toml(_default_cfg()),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=fly.toml"},
        )

    @router.get("/deploy/bundle")
    async def deploy_bundle() -> Dict[str, Any]:
        """Return all deployment manifests as a single JSON bundle."""
        bundle = generate_all(_default_cfg())
        return {
            "generated_at": int(time.time()),
            "platform_files": bundle.files(),
            "readme_section": bundle.railway_readme_section,
        }

else:
    router = None  # type: ignore
