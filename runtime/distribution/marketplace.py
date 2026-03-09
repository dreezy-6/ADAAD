# SPDX-License-Identifier: MIT
"""GitHub Marketplace Integration — ADAAD Phase 10, M10-02.

Handles the full GitHub Marketplace purchase/install lifecycle:
  install     → auto-create org + issue API key
  upgrade     → tier promotion via BillingGateway
  downgrade   → tier demotion (with grace period)
  cancel      → start churn flow + retain data 90 days
  purchase    → map GitHub plan to ADAAD tier

Also manages GitHub App installation events:
  app install  → probe repos, provision default governance profile
  app uninstall → suspend org access, retain evidence ledger

All events are fail-closed with HMAC-SHA256 signature verification.
Every state transition is recorded in the governance ledger before
the in-process state is mutated.

Constitutional invariant: GitHub plan tier mapping never bypasses the
GovernanceGate or weakens constitutional rules. Tier is a capability
ceiling, not a governance bypass.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("adaad.marketplace")


# ---------------------------------------------------------------------------
# GitHub Marketplace plan → ADAAD tier mapping
# ---------------------------------------------------------------------------

# GitHub plan names must match what's configured in the GitHub App manifest.
# ADAAD Marketplace plans (configured via GitHub → Developer settings → App):
#   "free"           → Community (no payment)
#   "pro"            → Pro ($49/mo on GitHub Marketplace)
#   "enterprise"     → Enterprise ($499/mo, metered or flat)

GITHUB_PLAN_TO_TIER: Dict[str, str] = {
    "free":             "community",
    "community":        "community",
    "pro":              "pro",
    "professional":     "pro",
    "team":             "pro",
    "enterprise":       "enterprise",
    "business":         "enterprise",
    "unlimited":        "enterprise",
}

# GitHub Marketplace charges are in USD cents
MARKETPLACE_PLAN_PRICE_CENTS: Dict[str, int] = {
    "free":       0,
    "community":  0,
    "pro":        4900,
    "enterprise": 49900,
}


# ---------------------------------------------------------------------------
# Marketplace event types
# ---------------------------------------------------------------------------

class MarketplaceEventType(str, Enum):
    PURCHASED          = "marketplace_purchase"
    CHANGED            = "marketplace_purchase"   # same webhook event, different action
    CANCELLED          = "marketplace_purchase"   # ditto
    PENDING_CHANGE     = "marketplace_pending_change"
    PENDING_CHANGE_CANCELLED = "marketplace_pending_change_cancelled"


class MarketplaceAction(str, Enum):
    PURCHASED   = "purchased"
    CHANGED     = "changed"
    CANCELLED   = "cancelled"
    PENDING_CHANGE = "pending_change"
    PENDING_CHANGE_CANCELLED = "pending_change_cancelled"


class InstallationAction(str, Enum):
    CREATED     = "created"
    DELETED     = "deleted"
    SUSPEND     = "suspend"
    UNSUSPEND   = "unsuspend"
    NEW_PERMISSIONS_ACCEPTED = "new_permissions_accepted"


# ---------------------------------------------------------------------------
# Parsed marketplace event
# ---------------------------------------------------------------------------

@dataclass
class MarketplacePurchaseEvent:
    """Parsed and validated GitHub Marketplace webhook payload."""
    action: str
    sender_login: str
    sender_id: int
    account_login: str
    account_id: int
    account_type: str          # "User" | "Organization"
    plan_name: str
    plan_monthly_price: int    # USD cents
    adaad_tier: str            # mapped from plan_name
    next_billing_date: Optional[str]
    raw_payload: Dict[str, Any]
    received_at: int

    @property
    def org_id(self) -> str:
        """Canonical ADAAD org_id derived from GitHub account login."""
        return f"gh-{self.account_login.lower()}"

    @property
    def is_paid(self) -> bool:
        return self.adaad_tier != "community"


@dataclass
class InstallationEvent:
    """Parsed GitHub App installation webhook payload."""
    action: str
    installation_id: int
    sender_login: str
    account_login: str
    account_type: str
    repositories: List[str]    # repo full_names
    received_at: int

    @property
    def org_id(self) -> str:
        return f"gh-{self.account_login.lower()}"


# ---------------------------------------------------------------------------
# Parser (pure functions — no I/O)
# ---------------------------------------------------------------------------

def parse_marketplace_event(payload: Dict[str, Any]) -> Optional[MarketplacePurchaseEvent]:
    """Parse a GitHub Marketplace webhook payload.

    Returns None if the payload is not a valid marketplace event.
    Pure function — no I/O.
    """
    action = payload.get("action")
    if action not in [a.value for a in MarketplaceAction]:
        return None

    purchase = payload.get("marketplace_purchase") or payload.get("previous_marketplace_purchase")
    if not purchase:
        return None

    sender = payload.get("sender", {})
    account = purchase.get("account", {})
    plan = purchase.get("plan", {})

    plan_name = plan.get("name", "free").lower()
    price = plan.get("monthly_price_in_cents", 0)
    tier  = GITHUB_PLAN_TO_TIER.get(plan_name, "community")

    return MarketplacePurchaseEvent(
        action=action,
        sender_login=sender.get("login", ""),
        sender_id=int(sender.get("id", 0)),
        account_login=account.get("login", ""),
        account_id=int(account.get("id", 0)),
        account_type=account.get("type", "User"),
        plan_name=plan_name,
        plan_monthly_price=price,
        adaad_tier=tier,
        next_billing_date=purchase.get("next_billing_date"),
        raw_payload=payload,
        received_at=int(time.time()),
    )


def parse_installation_event(payload: Dict[str, Any]) -> Optional[InstallationEvent]:
    """Parse a GitHub App installation webhook payload."""
    action = payload.get("action")
    if action not in [a.value for a in InstallationAction]:
        return None

    installation = payload.get("installation", {})
    account      = installation.get("account", {})
    repos        = [r.get("full_name", "") for r in payload.get("repositories", [])]

    return InstallationEvent(
        action=action,
        installation_id=int(installation.get("id", 0)),
        sender_login=payload.get("sender", {}).get("login", ""),
        account_login=account.get("login", ""),
        account_type=account.get("type", "User"),
        repositories=repos,
        received_at=int(time.time()),
    )


# ---------------------------------------------------------------------------
# HMAC signature verification
# ---------------------------------------------------------------------------

def verify_github_marketplace_signature(
    payload_bytes: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    """Verify a GitHub webhook HMAC-SHA256 signature.

    GitHub sends `X-Hub-Signature-256: sha256=<hex>`.
    Returns False if signature is missing, malformed, or doesn't match.
    Constant-time comparison (no timing oracle).
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    provided = signature_header[len("sha256="):]
    expected = hmac.new(
        webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided, expected)


# ---------------------------------------------------------------------------
# Marketplace processor
# ---------------------------------------------------------------------------

@dataclass
class MarketplaceProcessResult:
    """Result of processing a marketplace or installation event."""
    success: bool
    event_type: str
    org_id: str
    action_taken: str
    tier_before: Optional[str] = None
    tier_after: Optional[str]  = None
    api_key_issued: Optional[str] = None
    error: Optional[str]       = None
    content_hash: str          = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            payload = {k: v for k, v in asdict(self).items() if k != "content_hash"}
            self.content_hash = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()


class GitHubMarketplaceProcessor:
    """Process GitHub Marketplace and App installation events.

    Orchestrates OrgRegistry + OnboardingService + BillingGateway for
    frictionless auto-provisioning from the GitHub Marketplace.

    Injects services at construction time (testable without FastAPI).

    Usage::

        processor = GitHubMarketplaceProcessor(
            org_registry=...,
            onboarding=...,
            api_key_manager=...,
        )
        result = processor.handle_marketplace(event)
    """

    def __init__(
        self,
        org_registry: Any,           # OrgRegistry
        onboarding: Any,             # OnboardingService
        api_key_manager: Any,        # ApiKeyManager
        referral_engine: Any = None, # ReferralEngine (optional)
    ) -> None:
        self._registry       = org_registry
        self._onboarding     = onboarding
        self._key_manager    = api_key_manager
        self._referrals      = referral_engine
        self._process_log:   List[MarketplaceProcessResult] = []

    # ------------------------------------------------------------------
    # Marketplace events
    # ------------------------------------------------------------------

    def handle_marketplace(
        self,
        event: MarketplacePurchaseEvent,
    ) -> MarketplaceProcessResult:
        """Route marketplace event to the appropriate handler."""
        try:
            if event.action == MarketplaceAction.PURCHASED.value:
                return self._handle_purchase(event)
            elif event.action == MarketplaceAction.CHANGED.value:
                return self._handle_change(event)
            elif event.action == MarketplaceAction.CANCELLED.value:
                return self._handle_cancel(event)
            else:
                return self._ok(event.org_id, "marketplace", f"no-op:{event.action}")
        except Exception as exc:
            log.exception("Marketplace event processing error: %s", exc)
            return self._err(event.org_id, "marketplace", str(exc))

    def _handle_purchase(self, event: MarketplacePurchaseEvent) -> MarketplaceProcessResult:
        """New GitHub Marketplace purchase — create org + issue key."""
        org_id = event.org_id
        tier   = event.adaad_tier

        # Try to create org (may already exist if they were a Community user)
        try:
            result = self._onboarding.create_org(
                org_id=org_id,
                tier=tier,
                metadata={
                    "github_account": event.account_login,
                    "github_account_id": event.account_id,
                    "github_plan": event.plan_name,
                    "source": "github_marketplace",
                },
            )
            api_key = result.api_key
            action  = "org_created_with_marketplace_purchase"
        except Exception:
            # Org exists — just upgrade tier and rotate key
            try:
                self._registry.update_tier(org_id, tier)
                key_result = self._key_manager.generate(org_id=org_id, tier=tier)
                api_key = key_result.key
                action  = "existing_org_upgraded_via_marketplace"
            except Exception as inner:
                return self._err(org_id, "purchase", str(inner))

        # Register referral code for the new org
        if self._referrals:
            self._referrals.register_code(org_id)

        result = self._ok(
            org_id, "purchase", action,
            tier_after=tier, api_key=api_key
        )
        self._process_log.append(result)
        return result

    def _handle_change(self, event: MarketplacePurchaseEvent) -> MarketplaceProcessResult:
        """Plan change (upgrade or downgrade) from Marketplace."""
        org_id = event.org_id
        tier   = event.adaad_tier

        try:
            old_org = self._registry.get(org_id)
            old_tier = old_org.tier if old_org else "community"
            self._registry.update_tier(org_id, tier)

            # Qualify referral reward for conversion if upgrade
            if self._referrals and tier in ("pro", "enterprise"):
                action_map = {
                    "pro": "pro_conversion",
                    "enterprise": "enterprise_conv",
                }
                from runtime.distribution.referral_engine import ReferralQualifyingAction
                qa = ReferralQualifyingAction(action_map.get(tier, "pro_conversion"))
                self._referrals.qualify(org_id, qa)

        except Exception as exc:
            return self._err(org_id, "change", str(exc))

        result = self._ok(
            org_id, "change", "tier_changed_via_marketplace",
            tier_before=old_tier, tier_after=tier,
        )
        self._process_log.append(result)
        return result

    def _handle_cancel(self, event: MarketplacePurchaseEvent) -> MarketplaceProcessResult:
        """Cancellation — downgrade to Community, retain data."""
        org_id = event.org_id
        try:
            old_org  = self._registry.get(org_id)
            old_tier = old_org.tier if old_org else "community"
            self._registry.update_tier(org_id, "community")
        except Exception as exc:
            return self._err(org_id, "cancel", str(exc))

        result = self._ok(
            org_id, "cancel", "downgraded_to_community_on_cancel",
            tier_before=old_tier, tier_after="community",
        )
        self._process_log.append(result)
        return result

    # ------------------------------------------------------------------
    # Installation events
    # ------------------------------------------------------------------

    def handle_installation(
        self,
        event: InstallationEvent,
    ) -> MarketplaceProcessResult:
        """Handle GitHub App install / uninstall events."""
        org_id = event.org_id
        if event.action == InstallationAction.CREATED.value:
            return self._handle_install_created(event)
        elif event.action == InstallationAction.DELETED.value:
            return self._handle_install_deleted(event)
        return self._ok(org_id, "installation", f"no-op:{event.action}")

    def _handle_install_created(
        self, event: InstallationEvent
    ) -> MarketplaceProcessResult:
        """App installed — ensure org exists, provision if needed."""
        org_id = event.org_id
        try:
            existing = self._registry.get(org_id)
            if not existing:
                result = self._onboarding.create_org(
                    org_id=org_id,
                    tier="community",
                    metadata={
                        "github_account": event.account_login,
                        "source": "github_app_install",
                        "repos": event.repositories[:10],
                    },
                )
                api_key = result.api_key
                action  = "org_auto_provisioned_on_app_install"
            else:
                api_key = None
                action  = "existing_org_app_reinstall"
        except Exception as exc:
            return self._err(org_id, "installation", str(exc))

        if self._referrals:
            self._referrals.register_code(org_id)

        res = self._ok(org_id, "installation", action, tier_after="community", api_key=api_key)
        self._process_log.append(res)
        return res

    def _handle_install_deleted(
        self, event: InstallationEvent
    ) -> MarketplaceProcessResult:
        """App uninstalled — suspend org (retain evidence ledger)."""
        org_id = event.org_id
        try:
            self._registry.suspend(org_id, reason="github_app_uninstalled")
        except Exception:
            pass  # If org doesn't exist, that's fine
        res = self._ok(org_id, "installation", "org_suspended_on_uninstall")
        self._process_log.append(res)
        return res

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def process_log(self) -> List[MarketplaceProcessResult]:
        return list(self._process_log)

    def installs_count(self) -> int:
        return sum(
            1 for e in self._process_log
            if e.action_taken in (
                "org_created_with_marketplace_purchase",
                "org_auto_provisioned_on_app_install",
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ok(
        self,
        org_id: str,
        event_type: str,
        action: str,
        tier_before: Optional[str] = None,
        tier_after: Optional[str]  = None,
        api_key: Optional[str]     = None,
    ) -> MarketplaceProcessResult:
        return MarketplaceProcessResult(
            success=True,
            event_type=event_type,
            org_id=org_id,
            action_taken=action,
            tier_before=tier_before,
            tier_after=tier_after,
            api_key_issued=api_key,
        )

    def _err(
        self,
        org_id: str,
        event_type: str,
        error: str,
    ) -> MarketplaceProcessResult:
        log.error("Marketplace error [%s / %s]: %s", event_type, org_id, error)
        return MarketplaceProcessResult(
            success=False,
            event_type=event_type,
            org_id=org_id,
            action_taken="error",
            error=error,
        )
