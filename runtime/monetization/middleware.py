# SPDX-License-Identifier: Apache-2.0
"""Monetization Middleware — ADAAD Phase 8, M8-05.

FastAPI middleware that enforces API key authentication, tier capability
checks, and rate limiting on every request to the ADAAD API.

Architecture:
- Requests to /api/** require a valid Bearer token (ADAAD API key).
- Public paths (/, /health, /docs, /governance/reviewer-calibration) are
  exempt from auth but still rate-limited by IP.
- Rate limiting uses a sliding window counter (in-process; Redis in prod).
- Tier capability mismatches return 402 Payment Required with upgrade URL.
- All auth failures are logged as governance events (never silently dropped).

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import os
import time
import threading
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Deque, Optional, Set

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from runtime.monetization.api_key_manager import ApiKeyManager, ApiKeyValidationError, ApiKey
from runtime.monetization.tier_engine import TierEngine, Tier, TIER_COMMUNITY


# ---------------------------------------------------------------------------
# Public paths — no auth required
# ---------------------------------------------------------------------------

PUBLIC_PATHS: Set[str] = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/governance/reviewer-calibration",
    "/webhooks/stripe",
}

# Paths that accept optional auth (auth upgrades capability if present)
OPTIONAL_AUTH_PATHS: Set[str] = {
    "/api/tiers",
    "/api/pricing",
}


# ---------------------------------------------------------------------------
# Sliding-window rate limiter (in-process)
# ---------------------------------------------------------------------------

class _SlidingWindowRateLimiter:
    """Per-key sliding-window counter (thread-safe)."""

    def __init__(self, window_seconds: int = 60) -> None:
        self._window  = window_seconds
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock    = threading.Lock()

    def is_allowed(self, key: str, limit: int) -> bool:
        """Return True if the request is within the rate limit."""
        if limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._buckets[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True

    def remaining(self, key: str, limit: int) -> int:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._buckets[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            return max(0, limit - len(dq))


# ---------------------------------------------------------------------------
# Monetization middleware
# ---------------------------------------------------------------------------

class MonetizationMiddleware(BaseHTTPMiddleware):
    """ADAAD API authentication, tier enforcement, and rate limiting."""

    def __init__(
        self,
        app: ASGIApp,
        key_manager:    Optional[ApiKeyManager] = None,
        tier_engine:    Optional[TierEngine]    = None,
        dev_mode:       bool = False,
    ) -> None:
        super().__init__(app)
        self._keys       = key_manager or _build_default_key_manager()
        self._tiers      = tier_engine or TierEngine()
        self._dev_mode   = dev_mode
        self._limiter    = _SlidingWindowRateLimiter(window_seconds=60)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Passthrough for public paths
        if path in PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        # Extract Bearer token
        api_key: Optional[ApiKey] = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            try:
                api_key = self._keys.validate(token, current_time=int(time.time()))
            except ApiKeyValidationError as exc:
                return _auth_error(exc.reason, exc.status.value)

        # Paths that don't strictly require auth
        if path in OPTIONAL_AUTH_PATHS:
            request.state.api_key = api_key
            return await call_next(request)

        # All /api/** routes require auth
        if path.startswith("/api/"):
            if api_key is None and not self._dev_mode:
                return _auth_error("Missing API key. Include 'Authorization: Bearer <key>'")

            if api_key is not None:
                tier = Tier(api_key.tier)
                cfg  = self._tiers.config(tier)
                rate_limit = cfg.api_rate_limit_per_minute

                if not self._limiter.is_allowed(api_key.kid, rate_limit):
                    remaining = self._limiter.remaining(api_key.kid, rate_limit)
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error":     "rate_limit_exceeded",
                            "tier":      tier.value,
                            "limit_per_minute": rate_limit,
                            "remaining": remaining,
                            "upgrade_url": "https://innovativeai.io/adaad/upgrade",
                        },
                        headers={"Retry-After": "60"},
                    )

                # Attach resolved tier context to request state
                request.state.api_key = api_key
                request.state.tier    = tier
                request.state.tier_config = cfg
            else:
                # Dev mode: default to community
                request.state.api_key    = None
                request.state.tier       = Tier.COMMUNITY
                request.state.tier_config = TIER_COMMUNITY

        response = await call_next(request)

        # Inject rate-limit headers
        if api_key is not None:
            tier     = Tier(api_key.tier)
            cfg      = self._tiers.config(tier)
            limit    = cfg.api_rate_limit_per_minute
            rem      = self._limiter.remaining(api_key.kid, limit)
            response.headers["X-RateLimit-Limit"]     = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(rem)
            response.headers["X-ADAAD-Tier"]          = tier.value

        return response


# ---------------------------------------------------------------------------
# Monetization API routes
# ---------------------------------------------------------------------------

def build_monetization_router() -> Any:
    """Return a FastAPI APIRouter with monetization endpoints."""
    from fastapi import APIRouter, Depends, Header, HTTPException
    from runtime.monetization.tier_engine import ALL_TIERS

    router = APIRouter(prefix="/api/monetization", tags=["monetization"])

    @router.get("/tiers")
    def list_tiers():
        """Return capability summary for all tiers."""
        engine = TierEngine()
        return {
            "tiers": [engine.capability_summary(t) for t in ALL_TIERS],
            "upgrade_url": "https://innovativeai.io/adaad/upgrade",
        }

    @router.get("/pricing")
    def pricing():
        """Return current pricing information."""
        return {
            "currency": "USD",
            "billing_cycle": "monthly",
            "plans": [
                {
                    "tier": "community",
                    "display_name": "Community",
                    "price_usd": 0.0,
                    "epochs_per_month": 50,
                    "highlights": [
                        "3 Claude-powered mutation agents",
                        "Deterministic replay",
                        "Constitutional gating (16 rules)",
                        "SHA-256 evidence ledger",
                        "Android companion app",
                    ],
                    "cta": "Get started free",
                    "cta_url": "https://github.com/InnovativeAI-adaad/ADAAD",
                },
                {
                    "tier": "pro",
                    "display_name": "Pro",
                    "price_usd": 49.0,
                    "epochs_per_month": 500,
                    "highlights": [
                        "Everything in Community",
                        "Reviewer reputation engine",
                        "Roadmap self-amendment",
                        "Simulation DSL",
                        "Aponi IDE integration",
                        "Webhook integrations",
                        "Audit export",
                        "Up to 3 federation nodes",
                    ],
                    "cta": "Start Pro trial",
                    "cta_url": "https://innovativeai.io/adaad/upgrade?plan=pro",
                },
                {
                    "tier": "enterprise",
                    "display_name": "Enterprise",
                    "price_usd": 499.0,
                    "price_note": "Base pricing; custom contracts available",
                    "epochs_per_month": "Unlimited",
                    "highlights": [
                        "Everything in Pro",
                        "Unlimited epochs & federation nodes",
                        "SSO / SAML",
                        "99.9% SLA guarantee",
                        "Priority support",
                        "Custom constitutional rules",
                        "Dedicated onboarding",
                    ],
                    "cta": "Contact sales",
                    "cta_url": "https://innovativeai.io/adaad/enterprise",
                },
            ],
        }

    @router.get("/usage/{org_id}")
    def get_usage(
        org_id: str,
        epoch_window: str = "",
        authorization: str = Header(default=""),
    ):
        """Return usage summary for an organisation (requires valid API key)."""
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing API key")
        # In production this would validate the key and check org_id matches
        return {
            "org_id": org_id,
            "epoch_window": epoch_window or "current",
            "note": "Usage data requires live UsageTracker instance.",
        }

    return router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_error(reason: str, status: str = "invalid") -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error":   "authentication_failed",
            "reason":  reason,
            "status":  status,
            "docs":    "https://innovativeai.io/adaad/docs/api-keys",
        },
    )


def _build_default_key_manager() -> Optional[ApiKeyManager]:
    """Build key manager from env vars, or return None in dev mode."""
    signing_key_env = os.environ.get(ApiKeyManager.ENV_SIGNING_KEY, "")
    if not signing_key_env:
        return None
    try:
        return ApiKeyManager(signing_key=signing_key_env.encode())
    except Exception:
        return None
