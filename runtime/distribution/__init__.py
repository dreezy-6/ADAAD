# SPDX-License-Identifier: MIT
"""ADAAD Phase 10 — Distribution Engine.

Modules:
  referral_engine    — viral referral tracking, fraud prevention, reward management
  marketplace        — GitHub Marketplace purchase/install event processing
  deploy_manifests   — one-click deploy manifest generation (Railway, Render, Docker, Fly)
"""

from runtime.distribution.referral_engine import (
    ReferralEngine,
    ReferralEvent,
    ReferralQualifyingAction,
    ReferralReward,
    RewardType,
    generate_referral_code,
)
from runtime.distribution.marketplace import (
    GitHubMarketplaceProcessor,
    MarketplacePurchaseEvent,
    InstallationEvent,
    MarketplaceProcessResult,
    parse_marketplace_event,
    parse_installation_event,
    verify_github_marketplace_signature,
    GITHUB_PLAN_TO_TIER,
)
from runtime.distribution.deploy_manifests import (
    DeployBundle,
    DeployConfig,
    DeployPlatform,
    generate_all,
)

__all__ = [
    # referral
    "ReferralEngine",
    "ReferralEvent",
    "ReferralQualifyingAction",
    "ReferralReward",
    "RewardType",
    "generate_referral_code",
    # marketplace
    "GitHubMarketplaceProcessor",
    "MarketplacePurchaseEvent",
    "InstallationEvent",
    "MarketplaceProcessResult",
    "parse_marketplace_event",
    "parse_installation_event",
    "verify_github_marketplace_signature",
    "GITHUB_PLAN_TO_TIER",
    # deploy
    "DeployBundle",
    "DeployConfig",
    "DeployPlatform",
    "generate_all",
]
