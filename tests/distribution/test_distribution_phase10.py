# SPDX-License-Identifier: MIT
"""Tests — ADAAD Phase 10 Distribution Engine.

T10-01  generate_referral_code — deterministic (same input → same code)
T10-02  generate_referral_code — different orgs → different codes
T10-03  ReferralEngine.register_referral — success
T10-04  ReferralEngine.register_referral — self-referral blocked
T10-05  ReferralEngine.register_referral — unknown code rejected
T10-06  ReferralEngine.register_referral — duplicate blocked
T10-07  ReferralEngine.qualify — first_epoch reward granted
T10-08  ReferralEngine.qualify — idempotent (no double reward)
T10-09  ReferralEngine.qualify — non-referred org returns None
T10-10  ReferralEngine.qualify — pro_conversion grants $10 credit
T10-11  ReferralEngine.pending_epoch_bonus — sum of active bonuses
T10-12  ReferralEngine.pending_credit_usd — sum of active credits
T10-13  ReferralEngine.viral_coefficient — correct k-factor
T10-14  ReferralEngine.top_referrers — sorted descending
T10-15  ReferralEvent.content_hash — changes when input changes
T10-16  parse_marketplace_event — purchased action parsed correctly
T10-17  parse_marketplace_event — plan → tier mapping (pro)
T10-18  parse_marketplace_event — unknown plan → community tier
T10-19  parse_marketplace_event — invalid payload → None
T10-20  parse_installation_event — created action parsed
T10-21  verify_github_marketplace_signature — valid sig passes
T10-22  verify_github_marketplace_signature — tampered sig fails
T10-23  generate_railway_json — valid JSON, contains startCommand
T10-24  generate_dockerfile — contains HEALTHCHECK and non-root USER
T10-25  generate_docker_compose — contains service name
T10-26  generate_fly_toml — contains app name and health check
T10-27  generate_all — returns bundle with all 5 files
T10-28  GITHUB_PLAN_TO_TIER — all known plan names map correctly

Author: Dustin L. Reid · InnovativeAI LLC
"""

import hashlib
import hmac
import json
import time

import pytest

from runtime.distribution.referral_engine import (
    ReferralEngine,
    ReferralQualifyingAction,
    RewardType,
    generate_referral_code,
    ReferralEvent,
)
from runtime.distribution.marketplace import (
    parse_marketplace_event,
    parse_installation_event,
    verify_github_marketplace_signature,
    GITHUB_PLAN_TO_TIER,
    InstallationAction,
)
from runtime.distribution.deploy_manifests import (
    DeployConfig,
    DeployPlatform,
    generate_railway_json,
    generate_dockerfile,
    generate_docker_compose,
    generate_fly_toml,
    generate_all,
)


# ---------------------------------------------------------------------------
# Referral code generation
# ---------------------------------------------------------------------------

def test_t1001_referral_code_deterministic():
    code1 = generate_referral_code("acme-inc", "secret")
    code2 = generate_referral_code("acme-inc", "secret")
    assert code1 == code2
    assert code1.startswith("ADAAD-")


def test_t1002_different_orgs_different_codes():
    c1 = generate_referral_code("acme-inc", "secret")
    c2 = generate_referral_code("globex-corp", "secret")
    assert c1 != c2


# ---------------------------------------------------------------------------
# ReferralEngine — registration
# ---------------------------------------------------------------------------

def _engine() -> ReferralEngine:
    e = ReferralEngine(secret="test-secret")
    e.register_code("referrer-org")
    return e


def _engine_with_referral() -> ReferralEngine:
    e = _engine()
    code = e.code_for_org("referrer-org")
    e.register_referral("new-org", code)
    return e


def test_t1003_register_referral_success():
    e    = _engine()
    code = e.code_for_org("referrer-org")
    ok, msg = e.register_referral("new-org", code)
    assert ok is True
    assert "referrer-org" in msg


def test_t1004_self_referral_blocked():
    e    = _engine()
    code = e.code_for_org("referrer-org")
    ok, msg = e.register_referral("referrer-org", code)
    assert ok is False
    assert "self-referral" in msg.lower()


def test_t1005_unknown_code_rejected():
    e = _engine()
    ok, msg = e.register_referral("new-org", "ADAAD-XXXXXXXX")
    assert ok is False
    assert "unknown" in msg.lower()


def test_t1006_duplicate_referral_blocked():
    e    = _engine()
    code = e.code_for_org("referrer-org")
    e.register_referral("new-org", code)
    ok2, msg2 = e.register_referral("new-org", code)
    assert ok2 is False
    assert "already referred" in msg2.lower()


# ---------------------------------------------------------------------------
# ReferralEngine — qualifying actions
# ---------------------------------------------------------------------------

def test_t1007_qualify_first_epoch_reward():
    e     = _engine_with_referral()
    event = e.qualify("new-org", ReferralQualifyingAction.FIRST_EPOCH)
    assert event is not None
    assert event.referrer_org_id == "referrer-org"
    assert event.referred_org_id == "new-org"
    assert event.reward_granted is not None
    assert event.reward_granted.reward_type == RewardType.EPOCH_BONUS
    assert event.reward_granted.value == 25.0


def test_t1008_qualify_idempotent():
    e = _engine_with_referral()
    e1 = e.qualify("new-org", ReferralQualifyingAction.FIRST_EPOCH)
    e2 = e.qualify("new-org", ReferralQualifyingAction.FIRST_EPOCH)
    # Second call: event exists but no new reward
    assert e1 is not None
    assert e2 is not None
    assert e2.reward_granted is None


def test_t1009_non_referred_org_returns_none():
    e = _engine()
    result = e.qualify("ghost-org", ReferralQualifyingAction.FIRST_EPOCH)
    assert result is None


def test_t1010_pro_conversion_credit():
    e     = _engine_with_referral()
    event = e.qualify("new-org", ReferralQualifyingAction.PRO_CONVERSION)
    assert event.reward_granted.reward_type == RewardType.PRO_CREDIT_USD
    assert event.reward_granted.value == 10.0


# ---------------------------------------------------------------------------
# ReferralEngine — reward queries
# ---------------------------------------------------------------------------

def test_t1011_epoch_bonus_sum():
    e = _engine_with_referral()
    e.qualify("new-org", ReferralQualifyingAction.FIRST_EPOCH)
    e.qualify("new-org", ReferralQualifyingAction.SEVEN_DAY_ACTIVE)
    bonus = e.pending_epoch_bonus("referrer-org")
    assert bonus == 75   # 25 + 50


def test_t1012_credit_usd_sum():
    e = _engine_with_referral()
    e.qualify("new-org", ReferralQualifyingAction.PRO_CONVERSION)
    e.qualify("new-org", ReferralQualifyingAction.ENTERPRISE_CONV)
    credit = e.pending_credit_usd("referrer-org")
    assert credit == pytest.approx(60.0)   # $10 + $50


# ---------------------------------------------------------------------------
# ReferralEngine — analytics
# ---------------------------------------------------------------------------

def test_t1013_viral_coefficient():
    e = ReferralEngine(secret="test-secret")
    e.register_code("r1")
    e.register_code("r2")
    c1 = e.code_for_org("r1")
    c2 = e.code_for_org("r2")
    e.register_referral("a", c1)
    e.register_referral("b", c1)
    e.register_referral("c", c2)
    # 3 referred / 2 referrers = 1.5
    assert e.viral_coefficient() == pytest.approx(1.5)


def test_t1014_top_referrers():
    e = ReferralEngine(secret="test-secret")
    e.register_code("big-referrer")
    e.register_code("small-referrer")
    code_big   = e.code_for_org("big-referrer")
    code_small = e.code_for_org("small-referrer")
    for i in range(5):
        e.register_referral(f"org-{i}", code_big)
    e.register_referral("org-x", code_small)
    top = e.top_referrers(n=2)
    assert top[0][0] == "big-referrer"
    assert top[0][1] == 5
    assert top[1][0] == "small-referrer"


# ---------------------------------------------------------------------------
# ReferralEvent content hash
# ---------------------------------------------------------------------------

def test_t1015_content_hash_changes():
    e = _engine_with_referral()
    ev1 = e.qualify("new-org", ReferralQualifyingAction.FIRST_EPOCH)
    assert ev1.content_hash != ""
    # Second engine with different referrer
    e2 = ReferralEngine(secret="other-secret")
    e2.register_code("other-referrer")
    code2 = e2.code_for_org("other-referrer")
    e2.register_referral("new-org", code2)
    ev2 = e2.qualify("new-org", ReferralQualifyingAction.FIRST_EPOCH)
    assert ev2.content_hash != ev1.content_hash


# ---------------------------------------------------------------------------
# Marketplace event parsing
# ---------------------------------------------------------------------------

def _marketplace_payload(action="purchased", plan="pro") -> dict:
    return {
        "action": action,
        "sender": {"login": "dusty", "id": 12345},
        "marketplace_purchase": {
            "account": {"login": "acme-corp", "id": 99, "type": "Organization"},
            "plan": {
                "name": plan,
                "monthly_price_in_cents": 4900,
            },
            "next_billing_date": "2026-04-01",
        },
    }


def test_t1016_parse_marketplace_purchased():
    event = parse_marketplace_event(_marketplace_payload("purchased", "pro"))
    assert event is not None
    assert event.action == "purchased"
    assert event.account_login == "acme-corp"
    assert event.org_id == "gh-acme-corp"


def test_t1017_plan_to_tier_pro():
    event = parse_marketplace_event(_marketplace_payload("purchased", "pro"))
    assert event.adaad_tier == "pro"


def test_t1018_unknown_plan_defaults_community():
    payload = _marketplace_payload("purchased", "legacy-plan")
    event   = parse_marketplace_event(payload)
    assert event.adaad_tier == "community"


def test_t1019_invalid_payload_returns_none():
    result = parse_marketplace_event({"action": "star_created"})
    assert result is None


# ---------------------------------------------------------------------------
# Installation event parsing
# ---------------------------------------------------------------------------

def _install_payload(action="created") -> dict:
    return {
        "action": action,
        "installation": {
            "id": 777,
            "account": {"login": "acme-corp", "type": "Organization"},
        },
        "sender": {"login": "dusty"},
        "repositories": [
            {"full_name": "acme-corp/backend"},
            {"full_name": "acme-corp/frontend"},
        ],
    }


def test_t1020_parse_installation_created():
    event = parse_installation_event(_install_payload("created"))
    assert event is not None
    assert event.action == "created"
    assert event.org_id == "gh-acme-corp"
    assert "acme-corp/backend" in event.repositories


# ---------------------------------------------------------------------------
# HMAC signature verification
# ---------------------------------------------------------------------------

def test_t1021_valid_signature_passes():
    secret  = "my-webhook-secret"
    payload = b'{"action":"purchased"}'
    sig     = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_github_marketplace_signature(payload, sig, secret) is True


def test_t1022_tampered_signature_fails():
    secret  = "my-webhook-secret"
    payload = b'{"action":"purchased"}'
    sig     = "sha256=deadbeef0000"
    assert verify_github_marketplace_signature(payload, sig, secret) is False


# ---------------------------------------------------------------------------
# Deploy manifest generation
# ---------------------------------------------------------------------------

def _cfg() -> DeployConfig:
    return DeployConfig(platform=DeployPlatform.DOCKER)


def test_t1023_railway_json_valid():
    out = generate_railway_json(_cfg())
    data = json.loads(out)
    assert "deploy" in data
    assert "startCommand" in data["deploy"]
    assert "uvicorn" in data["deploy"]["startCommand"]


def test_t1024_dockerfile_healthcheck_nonroot():
    out = generate_dockerfile(_cfg())
    assert "HEALTHCHECK" in out
    assert "USER adaad" in out
    # Confirm FROM does not use root by checking no sudo/root USER after USER adaad
    assert out.count("USER root") == 0


def test_t1025_docker_compose_service_name():
    cfg = DeployConfig(platform=DeployPlatform.DOCKER, service_name="my-adaad")
    out = generate_docker_compose(cfg)
    assert "my-adaad" in out


def test_t1026_fly_toml_health_check():
    out = generate_fly_toml(_cfg())
    assert "[checks.health]" in out
    assert "/health" in out


def test_t1027_generate_all_bundle():
    bundle = generate_all(_cfg())
    files  = bundle.files()
    assert "railway.json"        in files
    assert "render.yaml"         in files
    assert "Dockerfile"          in files
    assert "docker-compose.yml"  in files
    assert "fly.toml"            in files
    # All non-empty
    for name, content in files.items():
        assert len(content) > 100, f"{name} appears empty"


# ---------------------------------------------------------------------------
# Tier mapping completeness
# ---------------------------------------------------------------------------

def test_t1028_github_plan_tier_mapping():
    assert GITHUB_PLAN_TO_TIER["free"]       == "community"
    assert GITHUB_PLAN_TO_TIER["pro"]        == "pro"
    assert GITHUB_PLAN_TO_TIER["enterprise"] == "enterprise"
    # All values are valid tiers
    for plan, tier in GITHUB_PLAN_TO_TIER.items():
        assert tier in ("community", "pro", "enterprise"), f"Bad tier for plan {plan!r}"
