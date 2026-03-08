# SPDX-License-Identifier: Apache-2.0
"""ADAAD Phase 8 — Enterprise SaaS Monetization Layer.

This package governs API access tiers, usage metering, license validation,
and billing integration for InnovativeAI LLC's commercial ADAAD offering.

Architectural invariants:
- All monetization gates are fail-closed: unauthenticated or over-quota
  requests are rejected before reaching the governance pipeline.
- Tier limits are deterministic and replay-safe (no wall-clock in core logic).
- The constitutional governance pipeline is NEVER bypassed for any tier.
- Enterprise licenses are validated via HMAC-signed tokens, not database lookups.
- Usage events are append-only and hash-chained (mirrors ledger architecture).

Tier hierarchy (ascending capability):
  COMMUNITY → PRO → ENTERPRISE

Founder: Dustin L. Reid · InnovativeAI LLC · Blackwell, Oklahoma
"""

from __future__ import annotations

from runtime.monetization.tier_engine import (
    Tier,
    TierConfig,
    TIER_COMMUNITY,
    TIER_PRO,
    TIER_ENTERPRISE,
    TierEngine,
    TierLimitExceeded,
    TierResolutionError,
)
from runtime.monetization.api_key_manager import (
    ApiKey,
    ApiKeyManager,
    ApiKeyValidationError,
    KeyStatus,
)
from runtime.monetization.usage_tracker import (
    UsageEvent,
    UsageTracker,
    QuotaExceededError,
)

__all__ = [
    # Tiers
    "Tier",
    "TierConfig",
    "TIER_COMMUNITY",
    "TIER_PRO",
    "TIER_ENTERPRISE",
    "TierEngine",
    "TierLimitExceeded",
    "TierResolutionError",
    # API Keys
    "ApiKey",
    "ApiKeyManager",
    "ApiKeyValidationError",
    "KeyStatus",
    # Usage
    "UsageEvent",
    "UsageTracker",
    "QuotaExceededError",
]
