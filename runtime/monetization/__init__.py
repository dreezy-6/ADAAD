# SPDX-License-Identifier: Apache-2.0
"""ADAAD Monetization Package — Phase 8.

Exports the complete commercial layer:
  M8-01 · TierEngine           — three-tier capability enforcement
  M8-02 · ApiKeyManager        — HMAC-signed bearer tokens
  M8-03 · UsageTracker         — append-only epoch metering
  M8-04 · BillingGateway       — Stripe webhook processor
  M8-05 · MonetizationMiddleware — FastAPI middleware + API routes
  M8-06 · OrgRegistry          — event-sourced org store
  M8-07 · NotificationDispatcher — Slack/PagerDuty/webhook outbound
  M8-08 · OnboardingService    — self-serve org creation + key provisioning
"""

from runtime.monetization.tier_engine import (
    Tier,
    Capability,
    TierConfig,
    TierEngine,
    TierLimitExceeded,
    TIER_COMMUNITY,
    TIER_PRO,
    TIER_ENTERPRISE,
    ALL_TIERS,
    tier_gte,
)
from runtime.monetization.api_key_manager import ApiKeyManager, ApiKey
from runtime.monetization.usage_tracker import UsageTracker, UsageEvent, QuotaExceededError
from runtime.monetization.billing_gateway import BillingGateway, BillingLifecycleEvent, BillingEventType
from runtime.monetization.middleware import build_monetization_router
from runtime.monetization.org_registry import (
    OrgRegistry,
    Organisation,
    OrgStatus,
    OrgLifecycleEvent,
    OrgNotFound,
    OrgAlreadyExists,
)
from runtime.monetization.notification_dispatcher import (
    NotificationDispatcher,
    NotificationPayload,
    NotifiableEvent,
    ChannelConfig,
    ChannelType,
)
from runtime.monetization.onboarding_service import OnboardingService, OnboardingResult

__all__ = [
    # Tiers
    "Tier", "Capability", "TierConfig", "TierEngine", "TierLimitExceeded",
    "TIER_COMMUNITY", "TIER_PRO", "TIER_ENTERPRISE", "ALL_TIERS", "tier_gte",
    # Keys
    "ApiKeyManager", "ApiKey",
    # Usage
    "UsageTracker", "UsageEvent", "QuotaExceededError",
    # Billing
    "BillingGateway", "BillingLifecycleEvent", "BillingEventType",
    # Middleware
    "build_monetization_router",
    # Orgs
    "OrgRegistry", "Organisation", "OrgStatus", "OrgLifecycleEvent",
    "OrgNotFound", "OrgAlreadyExists",
    # Notifications
    "NotificationDispatcher", "NotificationPayload", "NotifiableEvent",
    "ChannelConfig", "ChannelType",
    # Onboarding
    "OnboardingService", "OnboardingResult",
]
