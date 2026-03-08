# SPDX-License-Identifier: Apache-2.0
"""Tier Engine — ADAAD Phase 8, M8-01.

Defines and enforces the three-tier SaaS access model:

  COMMUNITY  →  Free, open-source users (capped epochs, no federation)
  PRO        →  Individual / small team ($49/mo), full governance suite
  ENTERPRISE →  Organizations ($499/mo+), multi-node federation, SLA, SSO

Tier enforcement is fail-closed: any ambiguity or missing tier information
resolves to the lowest permitted capability set.

Architectural invariants:
- Tier checks are pure functions — no I/O, no side-effects, deterministic.
- Capability gates never bypass GovernanceGate or constitutional rules.
- Enterprise tier gates are enforced via HMAC-validated license tokens only.
- No tier ever removes the constitutional human-review requirement.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

class Tier(str, Enum):
    """SaaS access tier."""
    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Tier ordinal for comparison (higher = more capable)
_TIER_ORDINAL: Dict[Tier, int] = {
    Tier.COMMUNITY: 0,
    Tier.PRO: 1,
    Tier.ENTERPRISE: 2,
}


def tier_gte(a: Tier, b: Tier) -> bool:
    """Return True if tier *a* has at least the capabilities of tier *b*."""
    return _TIER_ORDINAL[a] >= _TIER_ORDINAL[b]


# ---------------------------------------------------------------------------
# Capability catalogue
# ---------------------------------------------------------------------------

class Capability(str, Enum):
    """Feature flags governed by tier."""
    EPOCHS_PER_MONTH          = "epochs_per_month"
    FEDERATION_NODES          = "federation_nodes"
    MUTATION_CANDIDATES       = "mutation_candidates_per_epoch"
    REVIEWER_REPUTATION       = "reviewer_reputation"
    ROADMAP_AMENDMENT_ENGINE  = "roadmap_amendment_engine"
    SIMULATION_DSL            = "simulation_dsl"
    APONI_IDE                 = "aponi_ide"
    SSO_SAML                  = "sso_saml"
    SLA_GUARANTEED            = "sla_guaranteed"
    PRIORITY_SUPPORT          = "priority_support"
    AUDIT_EXPORT              = "audit_export"
    CUSTOM_CONSTITUTION       = "custom_constitution"
    WEBHOOK_INTEGRATIONS      = "webhook_integrations"
    ANDROID_COMPANION         = "android_companion"
    API_RATE_LIMIT_PER_MIN    = "api_rate_limit_per_minute"


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierConfig:
    """Immutable capability spec for a given tier."""

    tier: Tier
    display_name: str
    monthly_price_usd: float  # 0.0 = free

    # Numeric limits (-1 = unlimited)
    epochs_per_month: int
    federation_nodes: int
    mutation_candidates_per_epoch: int
    api_rate_limit_per_minute: int

    # Feature flags
    reviewer_reputation: bool
    roadmap_amendment_engine: bool
    simulation_dsl: bool
    aponi_ide: bool
    sso_saml: bool
    sla_guaranteed: bool
    priority_support: bool
    audit_export: bool
    custom_constitution: bool
    webhook_integrations: bool
    android_companion: bool

    def capability_value(self, cap: Capability) -> Any:
        """Return the value for a given capability."""
        return getattr(self, cap.value, None)

    def satisfies(self, cap: Capability, required_value: Any = True) -> bool:
        """Return True if this tier satisfies the required capability value."""
        val = self.capability_value(cap)
        if val is None:
            return False
        if isinstance(required_value, bool):
            return bool(val) == required_value
        if isinstance(val, int) and isinstance(required_value, int):
            return val == -1 or val >= required_value
        return val == required_value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Canonical tier configurations — single source of truth
TIER_COMMUNITY = TierConfig(
    tier=Tier.COMMUNITY,
    display_name="Community",
    monthly_price_usd=0.0,
    epochs_per_month=50,
    federation_nodes=0,
    mutation_candidates_per_epoch=3,
    api_rate_limit_per_minute=10,
    reviewer_reputation=False,
    roadmap_amendment_engine=False,
    simulation_dsl=False,
    aponi_ide=False,
    sso_saml=False,
    sla_guaranteed=False,
    priority_support=False,
    audit_export=False,
    custom_constitution=False,
    webhook_integrations=False,
    android_companion=True,
)

TIER_PRO = TierConfig(
    tier=Tier.PRO,
    display_name="Pro",
    monthly_price_usd=49.0,
    epochs_per_month=500,
    federation_nodes=3,
    mutation_candidates_per_epoch=10,
    api_rate_limit_per_minute=60,
    reviewer_reputation=True,
    roadmap_amendment_engine=True,
    simulation_dsl=True,
    aponi_ide=True,
    sso_saml=False,
    sla_guaranteed=False,
    priority_support=False,
    audit_export=True,
    custom_constitution=False,
    webhook_integrations=True,
    android_companion=True,
)

TIER_ENTERPRISE = TierConfig(
    tier=Tier.ENTERPRISE,
    display_name="Enterprise",
    monthly_price_usd=499.0,   # base; custom pricing for large orgs
    epochs_per_month=-1,        # unlimited
    federation_nodes=-1,        # unlimited
    mutation_candidates_per_epoch=-1,
    api_rate_limit_per_minute=600,
    reviewer_reputation=True,
    roadmap_amendment_engine=True,
    simulation_dsl=True,
    aponi_ide=True,
    sso_saml=True,
    sla_guaranteed=True,
    priority_support=True,
    audit_export=True,
    custom_constitution=True,
    webhook_integrations=True,
    android_companion=True,
)

# Ordered registry for iteration / lookup
ALL_TIERS: Dict[Tier, TierConfig] = {
    Tier.COMMUNITY: TIER_COMMUNITY,
    Tier.PRO: TIER_PRO,
    Tier.ENTERPRISE: TIER_ENTERPRISE,
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TierLimitExceeded(Exception):
    """Raised when a request exceeds the capability limit for its tier."""
    def __init__(self, tier: Tier, capability: Capability, requested: Any, limit: Any):
        self.tier = tier
        self.capability = capability
        self.requested = requested
        self.limit = limit
        super().__init__(
            f"[ADAAD-TIER] Capability '{capability.value}' limit exceeded for tier "
            f"'{tier.value}': requested={requested}, limit={limit}. "
            f"Upgrade at https://innovativeai.io/adaad/upgrade"
        )


class TierResolutionError(Exception):
    """Raised when a tier cannot be resolved from an API key."""


# ---------------------------------------------------------------------------
# Tier Engine
# ---------------------------------------------------------------------------

class TierEngine:
    """Stateless tier capability enforcement engine.

    All methods are pure/deterministic — safe for replay harnesses.
    """

    def __init__(self, tier_registry: Optional[Dict[Tier, TierConfig]] = None) -> None:
        self._registry = tier_registry or ALL_TIERS

    def config(self, tier: Tier) -> TierConfig:
        """Return the TierConfig for a given tier."""
        try:
            return self._registry[tier]
        except KeyError:
            raise TierResolutionError(f"Unknown tier: {tier!r}")

    def check_capability(
        self,
        tier: Tier,
        capability: Capability,
        requested_value: Any = True,
    ) -> None:
        """Assert that *tier* satisfies *capability* at *requested_value*.

        Raises TierLimitExceeded if the tier does not meet the requirement.
        This is the primary enforcement surface for feature gating.
        """
        cfg = self.config(tier)
        if not cfg.satisfies(capability, requested_value):
            limit = cfg.capability_value(capability)
            raise TierLimitExceeded(tier, capability, requested_value, limit)

    def capability_summary(self, tier: Tier) -> Dict[str, Any]:
        """Return a JSON-serialisable capability summary for *tier*."""
        cfg = self.config(tier)
        return {
            "tier": tier.value,
            "display_name": cfg.display_name,
            "monthly_price_usd": cfg.monthly_price_usd,
            "limits": {
                "epochs_per_month": cfg.epochs_per_month,
                "federation_nodes": cfg.federation_nodes,
                "mutation_candidates_per_epoch": cfg.mutation_candidates_per_epoch,
                "api_rate_limit_per_minute": cfg.api_rate_limit_per_minute,
            },
            "features": {
                "reviewer_reputation": cfg.reviewer_reputation,
                "roadmap_amendment_engine": cfg.roadmap_amendment_engine,
                "simulation_dsl": cfg.simulation_dsl,
                "aponi_ide": cfg.aponi_ide,
                "sso_saml": cfg.sso_saml,
                "sla_guaranteed": cfg.sla_guaranteed,
                "priority_support": cfg.priority_support,
                "audit_export": cfg.audit_export,
                "custom_constitution": cfg.custom_constitution,
                "webhook_integrations": cfg.webhook_integrations,
                "android_companion": cfg.android_companion,
            },
        }

    def upgrade_path(self, current: Tier, required: Tier) -> Optional[str]:
        """Return upgrade URL if *current* is below *required*, else None."""
        if tier_gte(current, required):
            return None
        return (
            f"https://innovativeai.io/adaad/upgrade"
            f"?from={current.value}&to={required.value}"
        )

    def compare_tiers(self, a: Tier, b: Tier) -> int:
        """Return -1, 0, or 1 like cmp(a, b) by tier ordinal."""
        oa, ob = _TIER_ORDINAL[a], _TIER_ORDINAL[b]
        return (oa > ob) - (oa < ob)
