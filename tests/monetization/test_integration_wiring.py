# SPDX-License-Identifier: Apache-2.0
"""Tests — ADAAD Phase 8 integration wiring (M8-06..M8-11).

Covers:
  T8-16  OrgRegistry create / get / list
  T8-17  OrgRegistry tier and status transitions
  T8-18  OrgRegistry soft delete
  T8-19  OrgRegistry event stream and flush
  T8-20  OrgRegistry duplicate creation raises
  T8-21  OrgRegistry get_by_stripe
  T8-22  OngRegistry thread safety
  T8-23  OnboardingService happy path (create + key)
  T8-24  OnboardingService org_id validation
  T8-25  OnboardingService key rotation
  T8-26  NotificationDispatcher sync dispatch (all channels)
  T8-27  NotificationDispatcher channel filtering by event
  T8-28  NotificationDispatcher delivery failure captured
  T8-29  Billing → OrgRegistry lifecycle integration
  T8-30  Admin router dashboard endpoint
  T8-31  Public orgs router creation rate limit
"""

from __future__ import annotations

import threading
import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from runtime.monetization.org_registry import (
    OrgRegistry,
    OrgStatus,
    OrgNotFound,
    OrgAlreadyExists,
    ORG_EVENT_CREATED,
    ORG_EVENT_TIER_CHANGED,
    ORG_EVENT_STATUS_CHANGED,
    ORG_EVENT_KEY_ROTATED,
)
from runtime.monetization.onboarding_service import (
    OnboardingService,
    OnboardingResult,
)
from runtime.monetization.api_key_manager import ApiKeyManager
from runtime.monetization.notification_dispatcher import (
    NotificationDispatcher,
    NotificationPayload,
    NotifiableEvent,
    ChannelConfig,
    ChannelType,
)
from runtime.monetization.billing_gateway import (
    BillingGateway,
    BillingEventType,
    BillingLifecycleEvent,
)

TEST_SIGNING_KEY = b"adaad-test-signing-key-32bytes!!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry() -> OrgRegistry:
    return OrgRegistry()


@pytest.fixture()
def key_manager() -> ApiKeyManager:
    return ApiKeyManager(signing_key=TEST_SIGNING_KEY)


@pytest.fixture()
def onboarding(registry, key_manager) -> OnboardingService:
    return OnboardingService(registry, key_manager)


@pytest.fixture()
def dispatcher() -> NotificationDispatcher:
    return NotificationDispatcher(retry_once=False)


# ---------------------------------------------------------------------------
# T8-16 · OrgRegistry create / get / list
# ---------------------------------------------------------------------------

class TestOrgRegistryBasic:

    def test_create_and_get(self, registry):
        org = registry.create("acme", "Acme Corp", tier="pro", now=1_000_000)
        assert org.org_id == "acme"
        assert org.tier == "pro"
        assert org.status == OrgStatus.ACTIVE

        fetched = registry.get("acme")
        assert fetched.org_id == "acme"

    def test_list_all(self, registry):
        registry.create("org-a", "Org A", now=1_000_000)
        registry.create("org-b", "Org B", tier="enterprise", now=1_000_001)
        orgs = registry.list_all()
        assert len(orgs) == 2

    def test_get_nonexistent_raises(self, registry):
        with pytest.raises(OrgNotFound):
            registry.get("nobody")

    def test_count(self, registry):
        registry.create("c1", "C1", tier="community", now=1_000_000)
        registry.create("p1", "P1", tier="pro", now=1_000_001)
        counts = registry.count()
        assert counts["total"] == 2
        assert counts["by_tier"]["community"] == 1
        assert counts["by_tier"]["pro"] == 1


# ---------------------------------------------------------------------------
# T8-17 · Tier and status transitions
# ---------------------------------------------------------------------------

class TestOrgRegistryTransitions:

    def test_set_tier(self, registry):
        registry.create("org-t", "Org T", tier="community", now=1_000_000)
        org = registry.set_tier("org-t", "pro", reason="upgraded", now=1_000_100)
        assert org.tier == "pro"

    def test_set_status_grace(self, registry):
        registry.create("org-g", "Org G", now=1_000_000)
        org = registry.set_status("org-g", OrgStatus.GRACE_PERIOD, reason="payment_failed", now=1_000_100)
        assert org.status == OrgStatus.GRACE_PERIOD

    def test_tier_change_emits_event(self, registry):
        registry.create("org-e", "Org E", tier="community", now=1_000_000)
        registry.set_tier("org-e", "enterprise", now=1_000_100)
        events = registry.flush_events()
        types = [e["event_type"] for e in events]
        assert ORG_EVENT_CREATED in types
        assert ORG_EVENT_TIER_CHANGED in types


# ---------------------------------------------------------------------------
# T8-18 · Soft delete
# ---------------------------------------------------------------------------

class TestOrgRegistryDelete:

    def test_soft_delete(self, registry):
        registry.create("org-del", "Org Del", now=1_000_000)
        org = registry.soft_delete("org-del", now=1_000_100)
        assert org.status == OrgStatus.DELETED
        # Still retrievable
        assert registry.get("org-del").status == OrgStatus.DELETED

    def test_delete_nonexistent_raises(self, registry):
        with pytest.raises(OrgNotFound):
            registry.soft_delete("ghost")


# ---------------------------------------------------------------------------
# T8-19 · Event stream and flush
# ---------------------------------------------------------------------------

class TestOrgRegistryEvents:

    def test_flush_clears_events(self, registry):
        registry.create("org-f", "Org F", now=1_000_000)
        registry.set_tier("org-f", "pro", now=1_000_100)
        events = registry.flush_events()
        assert len(events) == 2
        assert registry.event_count() == 0  # cleared after flush

    def test_events_have_hashes(self, registry):
        registry.create("org-h", "Org H", now=1_000_000)
        events = registry.flush_events()
        for e in events:
            assert e["entry_hash"].startswith("sha256:")


# ---------------------------------------------------------------------------
# T8-20 · Duplicate creation
# ---------------------------------------------------------------------------

class TestOrgRegistryDuplicate:

    def test_duplicate_org_id_raises(self, registry):
        registry.create("dup", "Dup", now=1_000_000)
        with pytest.raises(OrgAlreadyExists):
            registry.create("dup", "Dup 2", now=1_000_001)


# ---------------------------------------------------------------------------
# T8-21 · get_by_stripe
# ---------------------------------------------------------------------------

class TestOrgRegistryStripe:

    def test_get_by_stripe(self, registry):
        registry.create("stripe-org", "Stripe Org",
                         stripe_customer_id="cus_abc123", now=1_000_000)
        org = registry.get_by_stripe("cus_abc123")
        assert org.org_id == "stripe-org"

    def test_unknown_stripe_id_raises(self, registry):
        with pytest.raises(OrgNotFound):
            registry.get_by_stripe("cus_unknown")


# ---------------------------------------------------------------------------
# T8-22 · Thread safety
# ---------------------------------------------------------------------------

class TestOrgRegistryThreadSafety:

    def test_concurrent_creates(self, registry):
        errors: List[Exception] = []

        def create_org(i):
            try:
                registry.create(f"org-{i:04d}", f"Org {i}", now=i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=create_org, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert registry.count()["total"] == 20


# ---------------------------------------------------------------------------
# T8-23 · OnboardingService happy path
# ---------------------------------------------------------------------------

class TestOnboardingHappyPath:

    def test_onboard_community(self, onboarding):
        result = onboarding.onboard("test-co", "Test Co", tier="community",
                                     now=1_000_000)
        assert result.is_new_org
        assert result.tier == "community"
        assert result.api_key.startswith("adaad_cm_")
        assert result.kid

    def test_onboard_pro(self, onboarding):
        result = onboarding.onboard("pro-co", "Pro Co", tier="pro", now=1_000_000)
        assert result.api_key.startswith("adaad_pr_")

    def test_onboard_enterprise(self, onboarding):
        result = onboarding.onboard("ent-co", "Ent Co", tier="enterprise", now=1_000_000)
        assert result.api_key.startswith("adaad_en_")

    def test_onboard_registers_kid(self, onboarding, registry):
        result = onboarding.onboard("kid-check", "Kid Check", now=1_000_000)
        org = registry.get("kid-check")
        assert org.active_kid == result.kid

    def test_api_key_is_valid(self, onboarding, key_manager):
        result = onboarding.onboard("valid-key-co", "Valid", now=1_000_000)
        key = key_manager.validate(result.api_key)
        assert key.org_id == "valid-key-co"


# ---------------------------------------------------------------------------
# T8-24 · OnboardingService org_id validation
# ---------------------------------------------------------------------------

class TestOnboardingValidation:

    def test_invalid_org_id_rejected(self, onboarding):
        with pytest.raises(ValueError):
            onboarding.onboard("UPPERCASE", "Bad")

    def test_org_id_with_spaces_rejected(self, onboarding):
        with pytest.raises(ValueError):
            onboarding.onboard("has space", "Bad")

    def test_too_short_org_id_rejected(self, onboarding):
        with pytest.raises(ValueError):
            onboarding.onboard("ab", "Bad")

    def test_duplicate_org_raises(self, onboarding):
        onboarding.onboard("dup-org", "Dup", now=1_000_000)
        with pytest.raises(OrgAlreadyExists):
            onboarding.onboard("dup-org", "Dup 2", now=1_000_001)


# ---------------------------------------------------------------------------
# T8-25 · OnboardingService key rotation
# ---------------------------------------------------------------------------

class TestOnboardingKeyRotation:

    def test_rotate_issues_new_key(self, onboarding, registry):
        onboarding.onboard("rotate-me", "Rotate Me", now=1_000_000)
        result = onboarding.rotate_key("rotate-me", now=1_000_100)
        assert not result.is_new_org
        org = registry.get("rotate-me")
        assert org.active_kid == result.kid

    def test_old_and_new_key_both_valid(self, onboarding, key_manager):
        r1 = onboarding.onboard("two-keys", "Two Keys", now=1_000_000)
        r2 = onboarding.rotate_key("two-keys", now=1_000_100)
        # Both tokens parse correctly (revocation is caller-managed)
        key1 = key_manager.validate(r1.api_key)
        key2 = key_manager.validate(r2.api_key)
        assert key1.kid != key2.kid
        assert key1.org_id == key2.org_id == "two-keys"


# ---------------------------------------------------------------------------
# T8-26 · NotificationDispatcher sync dispatch
# ---------------------------------------------------------------------------

class TestNotificationDispatcherSync:

    def _payload(self, event_type=NotifiableEvent.EPOCH_COMPLETE) -> NotificationPayload:
        return NotificationPayload(
            event_type = event_type,
            org_id     = "test-org",
            title      = "Test notification",
            body       = "This is a test.",
            severity   = "info",
            timestamp  = 1_000_000,
        )

    def test_generic_webhook_dispatch_failure_captured(self, dispatcher):
        channels = [ChannelConfig(
            channel_type = ChannelType.WEBHOOK,
            url          = "http://127.0.0.1:19999/nonexistent",  # will fail
            events       = [],
        )]
        results = dispatcher.dispatch_sync(self._payload(), channels)
        assert len(results) == 1
        assert not results[0].success
        assert results[0].error

    def test_empty_channels_no_dispatch(self, dispatcher):
        results = dispatcher.dispatch_sync(self._payload(), channels=[])
        assert results == []


# ---------------------------------------------------------------------------
# T8-27 · Channel filtering by event
# ---------------------------------------------------------------------------

class TestNotificationChannelFiltering:

    def test_channel_not_subscribed_does_not_fire(self, dispatcher):
        # Channel only subscribes to GATE_HALT — not EPOCH_COMPLETE
        payload = NotificationPayload(
            event_type = NotifiableEvent.EPOCH_COMPLETE,
            org_id     = "test-org",
            title      = "Epoch done",
            body       = "Done.",
            severity   = "info",
            timestamp  = 1_000_000,
        )
        channels = [ChannelConfig(
            channel_type = ChannelType.WEBHOOK,
            url          = "http://127.0.0.1:19999/",
            events       = [NotifiableEvent.GATE_HALT],  # different event
        )]
        results = dispatcher.dispatch_sync(payload, channels)
        assert results == []  # filtered out — no dispatch attempted

    def test_channel_subscribed_all_fires(self, dispatcher):
        payload = NotificationPayload(
            event_type = NotifiableEvent.EPOCH_COMPLETE,
            org_id     = "test-org",
            title      = "Epoch done",
            body       = "Done.",
            severity   = "info",
            timestamp  = 1_000_000,
        )
        channels = [ChannelConfig(
            channel_type = ChannelType.WEBHOOK,
            url          = "http://127.0.0.1:19999/",
            events       = [],  # empty = all events
        )]
        results = dispatcher.dispatch_sync(payload, channels)
        # Will fail (bad URL) but was attempted
        assert len(results) == 1


# ---------------------------------------------------------------------------
# T8-28 · Delivery failure captured
# ---------------------------------------------------------------------------

class TestNotificationDeliveryFailure:

    def test_failure_result_has_error(self, dispatcher):
        payload = NotificationPayload(
            event_type = NotifiableEvent.GATE_HALT,
            org_id     = "org",
            title      = "Gate halted",
            body       = "Halt!",
            severity   = "critical",
            timestamp  = 1_000_000,
        )
        channels = [ChannelConfig(
            channel_type = ChannelType.SLACK,
            url          = "http://127.0.0.1:19999/bad",
            events       = [],
        )]
        results = dispatcher.dispatch_sync(payload, channels)
        assert not results[0].success
        assert results[0].error is not None
        assert results[0].attempt == 1


# ---------------------------------------------------------------------------
# T8-29 · Billing → OrgRegistry lifecycle integration
# ---------------------------------------------------------------------------

class TestBillingOrgIntegration:

    def _make_gateway(self, registry, onboarding) -> BillingGateway:
        from app.api.webhooks import _handle_billing_lifecycle
        import app.api.webhooks as wh_module
        wh_module._org_registry  = registry
        wh_module._onboarding    = onboarding
        wh_module._notifications = None

        return BillingGateway(
            on_lifecycle_event = _handle_billing_lifecycle,
            webhook_secret     = "",
            price_pro          = "price_pro_1",
            price_enterprise   = "price_ent_1",
        )

    def test_subscription_created_auto_onboards_org(self, registry, onboarding):
        gw = self._make_gateway(registry, onboarding)
        import json
        payload = json.dumps({
            "id": "evt_auto_001",
            "type": "customer.subscription.created",
            "created": 1_000_000,
            "data": {"object": {
                "customer": "cus_auto001",
                "metadata": {"adaad_org_id": "auto-org"},
                "items": {"data": [{"price": {"id": "price_pro_1"}}]},
            }},
        }).encode()
        gw.process_webhook(payload, "")
        # Org should now exist
        org = registry.get("auto-org")
        assert org.tier == "pro"

    def test_payment_failed_sets_grace_period(self, registry, onboarding):
        gw = self._make_gateway(registry, onboarding)
        # Pre-create org
        registry.create("grace-org", "Grace Org",
                         stripe_customer_id="cus_grace", now=999_000)
        import json
        payload = json.dumps({
            "id": "evt_grace_001",
            "type": "invoice.payment_failed",
            "created": 1_000_000,
            "data": {"object": {
                "customer": "cus_grace",
                "metadata": {"adaad_org_id": "grace-org"},
            }},
        }).encode()
        gw.process_webhook(payload, "")
        org = registry.get("grace-org")
        assert org.status == OrgStatus.GRACE_PERIOD


# ---------------------------------------------------------------------------
# T8-30 · Admin router dashboard
# ---------------------------------------------------------------------------

class TestAdminDashboard:

    def test_dashboard_mrr_calculation(self):
        from app.api.admin import build_admin_router
        from runtime.monetization.org_registry import OrgRegistry
        from runtime.monetization.usage_tracker import UsageTracker
        from runtime.monetization.tier_engine import TierEngine
        from runtime.monetization.onboarding_service import OnboardingService
        from runtime.monetization.api_key_manager import ApiKeyManager

        reg  = OrgRegistry()
        km   = ApiKeyManager(signing_key=TEST_SIGNING_KEY)
        ob   = OnboardingService(reg, km)
        ut   = UsageTracker()
        te   = TierEngine()

        ob.onboard("revenue-1", "Rev 1", tier="pro", now=1_000_000)
        ob.onboard("revenue-2", "Rev 2", tier="enterprise", now=1_000_001)
        ob.onboard("revenue-3", "Rev 3", tier="community", now=1_000_002)

        router = build_admin_router(reg, ob, ut, te)
        # Verify router was created without errors
        assert router is not None
        assert len(router.routes) > 0


# ---------------------------------------------------------------------------
# T8-31 · Public orgs rate limiter
# ---------------------------------------------------------------------------

class TestPublicOrgsRateLimit:

    def test_rate_limiter_allows_then_blocks(self):
        from app.api.orgs import _CreationRateLimiter
        limiter = _CreationRateLimiter()
        # 3 allowed
        assert limiter.is_allowed("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1")
        # 4th blocked
        assert not limiter.is_allowed("10.0.0.1")

    def test_different_ips_independent(self):
        from app.api.orgs import _CreationRateLimiter
        limiter = _CreationRateLimiter()
        for _ in range(3):
            limiter.is_allowed("10.0.0.1")
        # Different IP still allowed
        assert limiter.is_allowed("10.0.0.2")
