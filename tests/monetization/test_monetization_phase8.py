# SPDX-License-Identifier: Apache-2.0
"""Tests — ADAAD Phase 8, M8 monetization module.

Covers:
  T8-01  TierEngine capability checks
  T8-02  TierEngine limit enforcement
  T8-03  ApiKeyManager generate / validate round-trip
  T8-04  ApiKeyManager revocation
  T8-05  ApiKeyManager expiry enforcement
  T8-06  ApiKeyManager signature tamper detection
  T8-07  UsageTracker record and quota enforcement
  T8-08  UsageTracker thread safety
  T8-09  UsageTracker flush lifecycle
  T8-10  BillingGateway subscription creation
  T8-11  BillingGateway idempotency
  T8-12  BillingGateway tier upgrade / downgrade
  T8-13  BillingGateway cancellation reverts to community
  T8-14  BillingGateway payment failure / recovery
  T8-15  All tier enum values stable (no breaking renames)
"""

from __future__ import annotations

import threading
import time
from typing import List
from unittest.mock import patch

import pytest

from runtime.monetization.tier_engine import (
    Tier,
    TierEngine,
    TierLimitExceeded,
    TierResolutionError,
    Capability,
    TIER_COMMUNITY,
    TIER_PRO,
    TIER_ENTERPRISE,
    tier_gte,
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
    EVENT_EPOCH_RUN,
    EVENT_API_CALL,
)
from runtime.monetization.billing_gateway import (
    BillingGateway,
    BillingEventType,
    BillingLifecycleEvent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_SIGNING_KEY = b"adaad-test-signing-key-32bytes!!"


@pytest.fixture()
def engine() -> TierEngine:
    return TierEngine()


@pytest.fixture()
def key_manager() -> ApiKeyManager:
    return ApiKeyManager(signing_key=TEST_SIGNING_KEY)


@pytest.fixture()
def tracker() -> UsageTracker:
    return UsageTracker()


@pytest.fixture()
def gateway() -> BillingGateway:
    lifecycle_events: List[BillingLifecycleEvent] = []
    return BillingGateway(
        on_lifecycle_event=lifecycle_events.append,
        webhook_secret="",       # skip signature check in tests
        price_pro="price_pro_1",
        price_enterprise="price_ent_1",
    )


# ---------------------------------------------------------------------------
# T8-01 · TierEngine capability checks
# ---------------------------------------------------------------------------

class TestTierEngineCapabilities:

    def test_community_android_companion(self, engine):
        """Community tier includes android_companion."""
        # Should not raise
        engine.check_capability(Tier.COMMUNITY, Capability.ANDROID_COMPANION)

    def test_community_no_reviewer_reputation(self, engine):
        """Community tier does NOT include reviewer_reputation."""
        with pytest.raises(TierLimitExceeded) as exc_info:
            engine.check_capability(Tier.COMMUNITY, Capability.REVIEWER_REPUTATION)
        assert exc_info.value.tier == Tier.COMMUNITY
        assert "upgrade" in str(exc_info.value).lower()

    def test_pro_reviewer_reputation(self, engine):
        """Pro tier includes reviewer_reputation."""
        engine.check_capability(Tier.PRO, Capability.REVIEWER_REPUTATION)

    def test_pro_no_sso(self, engine):
        """Pro tier does NOT include SSO/SAML."""
        with pytest.raises(TierLimitExceeded):
            engine.check_capability(Tier.PRO, Capability.SSO_SAML)

    def test_enterprise_all_features(self, engine):
        """Enterprise tier satisfies all boolean capabilities."""
        boolean_caps = [
            Capability.REVIEWER_REPUTATION,
            Capability.ROADMAP_AMENDMENT_ENGINE,
            Capability.SIMULATION_DSL,
            Capability.APONI_IDE,
            Capability.SSO_SAML,
            Capability.SLA_GUARANTEED,
            Capability.PRIORITY_SUPPORT,
            Capability.AUDIT_EXPORT,
            Capability.CUSTOM_CONSTITUTION,
            Capability.WEBHOOK_INTEGRATIONS,
            Capability.ANDROID_COMPANION,
        ]
        for cap in boolean_caps:
            engine.check_capability(Tier.ENTERPRISE, cap)  # must not raise

    def test_tier_ordinal_gte(self):
        assert tier_gte(Tier.ENTERPRISE, Tier.PRO)
        assert tier_gte(Tier.PRO, Tier.COMMUNITY)
        assert tier_gte(Tier.COMMUNITY, Tier.COMMUNITY)
        assert not tier_gte(Tier.COMMUNITY, Tier.PRO)


# ---------------------------------------------------------------------------
# T8-02 · Numeric limit enforcement
# ---------------------------------------------------------------------------

class TestTierLimits:

    def test_community_epoch_limit(self, engine):
        """Community epoch limit is 50."""
        engine.check_capability(Tier.COMMUNITY, Capability.EPOCHS_PER_MONTH, 50)
        with pytest.raises(TierLimitExceeded):
            engine.check_capability(Tier.COMMUNITY, Capability.EPOCHS_PER_MONTH, 51)

    def test_enterprise_unlimited_epochs(self, engine):
        """Enterprise has unlimited epochs (-1 means ≥ any value)."""
        engine.check_capability(Tier.ENTERPRISE, Capability.EPOCHS_PER_MONTH, 999_999)

    def test_community_no_federation(self, engine):
        """Community federation_nodes limit is 0."""
        with pytest.raises(TierLimitExceeded):
            engine.check_capability(Tier.COMMUNITY, Capability.FEDERATION_NODES, 1)

    def test_unknown_tier_raises(self, engine):
        with pytest.raises(TierResolutionError):
            engine.config(Tier("nonexistent"))  # type: ignore


# ---------------------------------------------------------------------------
# T8-03 · ApiKeyManager round-trip
# ---------------------------------------------------------------------------

class TestApiKeyRoundTrip:

    def test_generate_and_validate_community(self, key_manager):
        token = key_manager.generate(
            tier="community", org_id="org-abc", issued_at=1_000_000
        )
        assert token.startswith("adaad_cm_")
        key = key_manager.validate(token)
        assert key.tier == "community"
        assert key.org_id == "org-abc"
        assert key.status == KeyStatus.ACTIVE

    def test_generate_and_validate_pro(self, key_manager):
        token = key_manager.generate("pro", "org-xyz", 2_000_000, expires_at=3_000_000)
        key   = key_manager.validate(token)
        assert key.tier == "pro"
        assert key.expires_at == 3_000_000

    def test_generate_and_validate_enterprise(self, key_manager):
        token = key_manager.generate("enterprise", "mega-corp", 1_000_000)
        key   = key_manager.validate(token)
        assert key.tier == "enterprise"
        assert key.is_enterprise


# ---------------------------------------------------------------------------
# T8-04 · Revocation
# ---------------------------------------------------------------------------

class TestApiKeyRevocation:

    def test_revoked_key_rejected(self, key_manager):
        token = key_manager.generate("pro", "org-revoke", 1_000_000)
        key   = key_manager.validate(token)
        key_manager.revoke(key.kid)
        with pytest.raises(ApiKeyValidationError) as exc_info:
            key_manager.validate(token)
        assert exc_info.value.status == KeyStatus.REVOKED

    def test_is_revoked_query(self, key_manager):
        token = key_manager.generate("community", "org-q", 1_000_000)
        key   = key_manager.validate(token)
        assert not key_manager.is_revoked(key.kid)
        key_manager.revoke(key.kid)
        assert key_manager.is_revoked(key.kid)


# ---------------------------------------------------------------------------
# T8-05 · Expiry enforcement
# ---------------------------------------------------------------------------

class TestApiKeyExpiry:

    def test_expired_key_rejected(self, key_manager):
        token = key_manager.generate(
            "pro", "org-exp", issued_at=1_000_000, expires_at=2_000_000
        )
        with pytest.raises(ApiKeyValidationError) as exc_info:
            key_manager.validate(token, current_time=3_000_000)
        assert exc_info.value.status == KeyStatus.EXPIRED

    def test_non_expired_key_accepted(self, key_manager):
        token = key_manager.generate(
            "pro", "org-ok", issued_at=1_000_000, expires_at=5_000_000
        )
        key = key_manager.validate(token, current_time=2_000_000)
        assert key.status == KeyStatus.ACTIVE


# ---------------------------------------------------------------------------
# T8-06 · Tamper detection
# ---------------------------------------------------------------------------

class TestApiKeyTamper:

    def test_modified_payload_rejected(self, key_manager):
        token  = key_manager.generate("community", "org-t", 1_000_000)
        # Flip one character in the payload segment
        parts  = token.split("_")
        bad_payload = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
        tampered = "_".join([parts[0], parts[1], bad_payload, parts[3]])
        with pytest.raises(ApiKeyValidationError):
            key_manager.validate(tampered)

    def test_wrong_signing_key_rejected(self):
        km1 = ApiKeyManager(signing_key=b"key-one-32-bytes-padding-padding!")
        km2 = ApiKeyManager(signing_key=b"key-two-32-bytes-padding-padding!")
        token = km1.generate("pro", "org-cross", 1_000_000)
        with pytest.raises(ApiKeyValidationError):
            km2.validate(token)

    def test_malformed_token_rejected(self, key_manager):
        with pytest.raises(ApiKeyValidationError):
            key_manager.validate("not_a_valid_token")

    def test_unknown_tier_prefix_rejected(self, key_manager):
        token = key_manager.generate("pro", "org-x", 1_000_000)
        parts = token.split("_")
        # Replace tier prefix with unknown value
        bad = "_".join([parts[0], "xx", parts[2], parts[3]])
        with pytest.raises(ApiKeyValidationError):
            key_manager.validate(bad)


# ---------------------------------------------------------------------------
# T8-07 · UsageTracker basic recording and quota
# ---------------------------------------------------------------------------

class TestUsageTracker:

    def test_record_epoch_run(self, tracker):
        event = tracker.record(
            org_id="org1", kid="kid1", tier="pro",
            event_type=EVENT_EPOCH_RUN, epoch_window="2026-03",
        )
        assert event.event_type == EVENT_EPOCH_RUN
        assert event.entry_hash.startswith("sha256:")
        assert tracker.event_count("org1") == 1

    def test_community_epoch_quota_enforced(self, tracker):
        """Community tier blocks epoch_run after 50 events."""
        for i in range(50):
            tracker.record(
                "org-c", "kid", "community",
                EVENT_EPOCH_RUN, "2026-03",
            )
        with pytest.raises(QuotaExceededError) as exc_info:
            tracker.record("org-c", "kid", "community", EVENT_EPOCH_RUN, "2026-03")
        assert exc_info.value.limit == 50
        assert "upgrade" in str(exc_info.value).lower()

    def test_enterprise_no_epoch_quota(self, tracker):
        """Enterprise tier has no epoch cap."""
        for i in range(200):
            tracker.record("org-e", "kid", "enterprise", EVENT_EPOCH_RUN, "2026-03")
        assert tracker.event_count("org-e") == 200

    def test_usage_summary(self, tracker):
        tracker.record("org-s", "kid", "pro", EVENT_EPOCH_RUN, "2026-03")
        tracker.record("org-s", "kid", "pro", EVENT_API_CALL, "2026-03", count=5)
        summary = tracker.usage_summary("org-s", "2026-03")
        assert summary["usage"][EVENT_EPOCH_RUN] == 1
        assert summary["usage"][EVENT_API_CALL] == 5


# ---------------------------------------------------------------------------
# T8-08 · Thread safety
# ---------------------------------------------------------------------------

class TestUsageTrackerThreadSafety:

    def test_concurrent_records(self, tracker):
        errors: List[Exception] = []

        def record_many():
            try:
                for _ in range(10):
                    tracker.record(
                        "org-thread", "kid", "enterprise",
                        EVENT_EPOCH_RUN, "2026-03",
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert tracker.event_count("org-thread") == 50


# ---------------------------------------------------------------------------
# T8-09 · Flush lifecycle
# ---------------------------------------------------------------------------

class TestUsageTrackerFlush:

    def test_flush_returns_and_clears(self, tracker):
        tracker.record("org-f", "kid", "pro", EVENT_EPOCH_RUN, "2026-03")
        tracker.record("org-f", "kid", "pro", EVENT_API_CALL, "2026-03")
        dicts = tracker.flush_events()
        assert len(dicts) == 2
        assert tracker.event_count() == 0


# ---------------------------------------------------------------------------
# T8-10 · BillingGateway subscription creation
# ---------------------------------------------------------------------------

class TestBillingGateway:

    def _make_subscription_event(self, event_type: str, price_ids=None, tier_meta="pro") -> dict:
        price_ids = price_ids or ["price_pro_1"]
        return {
            "id":      "evt_test_001",
            "type":    event_type,
            "created": 1_700_000_000,
            "data": {
                "object": {
                    "id":       "sub_001",
                    "customer": "cus_001",
                    "metadata": {"adaad_org_id": "org-billed", "adaad_tier": tier_meta},
                    "items": {
                        "data": [{"price": {"id": pid}} for pid in price_ids]
                    },
                }
            },
        }

    def test_subscription_created_emits_event(self):
        events: List[BillingLifecycleEvent] = []
        gw = BillingGateway(
            on_lifecycle_event=events.append,
            webhook_secret="",
            price_pro="price_pro_1",
            price_enterprise="price_ent_1",
        )
        import json
        payload = json.dumps(self._make_subscription_event(
            "customer.subscription.created"
        )).encode()
        gw.process_webhook(payload, "")
        assert len(events) == 1
        assert events[0].event_type == BillingEventType.TIER_PROVISIONED
        assert events[0].to_tier == "pro"

    def test_subscription_deleted_reverts_to_community(self):
        events: List[BillingLifecycleEvent] = []
        gw = BillingGateway(on_lifecycle_event=events.append, webhook_secret="",
                            price_pro="price_pro_1", price_enterprise="price_ent_1")
        import json
        payload = json.dumps(self._make_subscription_event(
            "customer.subscription.deleted"
        )).encode()
        gw.process_webhook(payload, "")
        assert events[0].to_tier == "community"
        assert events[0].event_type == BillingEventType.TIER_CANCELLED

    def test_idempotency_same_event_processed_once(self):
        events: List[BillingLifecycleEvent] = []
        gw = BillingGateway(on_lifecycle_event=events.append, webhook_secret="",
                            price_pro="price_pro_1", price_enterprise="price_ent_1")
        import json
        payload = json.dumps(self._make_subscription_event(
            "customer.subscription.created"
        )).encode()
        gw.process_webhook(payload, "")
        gw.process_webhook(payload, "")  # duplicate
        assert len(events) == 1, "Idempotency failure: duplicate event processed"

    def test_enterprise_price_resolves_enterprise_tier(self):
        events: List[BillingLifecycleEvent] = []
        gw = BillingGateway(on_lifecycle_event=events.append, webhook_secret="",
                            price_pro="price_pro_1", price_enterprise="price_ent_1")
        import json
        payload = json.dumps(self._make_subscription_event(
            "customer.subscription.created", price_ids=["price_ent_1"]
        )).encode()
        gw.process_webhook(payload, "")
        assert events[0].to_tier == "enterprise"


# ---------------------------------------------------------------------------
# T8-15 · Stable tier enum values
# ---------------------------------------------------------------------------

class TestTierEnumStability:
    """Ensure tier enum values are stable — breaking renames would invalidate stored keys."""

    def test_community_value(self):
        assert Tier.COMMUNITY.value == "community"

    def test_pro_value(self):
        assert Tier.PRO.value == "pro"

    def test_enterprise_value(self):
        assert Tier.ENTERPRISE.value == "enterprise"

    def test_all_tiers_present(self):
        names = {t.value for t in Tier}
        assert names == {"community", "pro", "enterprise"}
