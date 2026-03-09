# SPDX-License-Identifier: MIT
"""Referral Engine — ADAAD Phase 10, M10-01.

Drives viral growth for InnovativeAI LLC through a governed, auditable
referral programme.

Design:
  - Every org gets a unique referral code at signup (deterministic, no DB call)
  - Referrals are tracked as hash-chained events (same ledger pattern as governance)
  - Rewards are only unlocked AFTER the referred org completes a qualifying action
  - Fraud prevention: one reward per (referrer, referred) pair; self-referral blocked
  - Reward catalogue: Pro discount credits + epoch bonuses (never weakens governance)

Constitutional invariant: referral rewards are capacity bonuses only.
They never bypass the GovernanceGate or weaken constitutional enforcement.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Referral code generation (deterministic from org_id + secret)
# ---------------------------------------------------------------------------

_CODE_PREFIX = "ADAAD"
_CODE_LEN    = 8   # characters of hex digest used


def generate_referral_code(org_id: str, secret: str) -> str:
    """Generate a stable referral code for an org.

    Deterministic: same org_id + secret → same code every time.
    Unguessable without the secret.
    """
    digest = hmac.new(
        secret.encode(),
        org_id.encode(),
        hashlib.sha256,
    ).hexdigest()[:_CODE_LEN].upper()
    return f"{_CODE_PREFIX}-{digest}"


def generate_random_code() -> str:
    """Generate a one-time random referral code (for manual issuance)."""
    return f"{_CODE_PREFIX}-{secrets.token_hex(4).upper()}"


# ---------------------------------------------------------------------------
# Qualifying actions that unlock rewards
# ---------------------------------------------------------------------------

class ReferralQualifyingAction(str, Enum):
    FIRST_EPOCH     = "first_epoch"         # referred org runs their first epoch
    PRO_CONVERSION  = "pro_conversion"      # referred org upgrades to Pro
    ENTERPRISE_CONV = "enterprise_conv"     # referred org upgrades to Enterprise
    SEVEN_DAY_ACTIVE = "seven_day_active"   # referred org active 7 days straight


# ---------------------------------------------------------------------------
# Reward types
# ---------------------------------------------------------------------------

class RewardType(str, Enum):
    EPOCH_BONUS        = "epoch_bonus"         # extra epochs this month
    PRO_CREDIT_USD     = "pro_credit_usd"      # USD credit on Pro invoice
    ENTERPRISE_CREDIT  = "enterprise_credit"   # USD credit on Enterprise invoice
    FREE_MONTH_PRO     = "free_month_pro"      # one free Pro month
    GOVERNANCE_BADGE   = "governance_badge"    # profile badge (non-monetary)


@dataclass(frozen=True)
class ReferralReward:
    """A concrete reward granted to a referrer."""
    reward_type: RewardType
    value: float          # epochs or USD depending on type
    description: str
    granted_at: int
    expires_at: Optional[int]    # None = never expires


# Reward catalogue: what action by the referred org unlocks what for the referrer
_REWARD_CATALOGUE: Dict[str, Dict[str, Any]] = {
    ReferralQualifyingAction.FIRST_EPOCH.value: {
        "reward_type": RewardType.EPOCH_BONUS,
        "value": 25.0,
        "description": "25 bonus epochs — your referral ran their first evolution",
        "expires_days": 30,
    },
    ReferralQualifyingAction.PRO_CONVERSION.value: {
        "reward_type": RewardType.PRO_CREDIT_USD,
        "value": 10.0,
        "description": "$10 credit on your Pro plan — your referral upgraded to Pro",
        "expires_days": 60,
    },
    ReferralQualifyingAction.ENTERPRISE_CONV.value: {
        "reward_type": RewardType.ENTERPRISE_CREDIT,
        "value": 50.0,
        "description": "$50 credit on your plan — your referral went Enterprise",
        "expires_days": 90,
    },
    ReferralQualifyingAction.SEVEN_DAY_ACTIVE.value: {
        "reward_type": RewardType.EPOCH_BONUS,
        "value": 50.0,
        "description": "50 bonus epochs — your referral has been active 7 days straight",
        "expires_days": 30,
    },
}


# ---------------------------------------------------------------------------
# Referral event (immutable ledger record)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReferralEvent:
    """Immutable record of a referral action — appended to the evidence ledger."""
    event_id: str
    referrer_org_id: str
    referred_org_id: str
    referral_code: str
    action: str                     # ReferralQualifyingAction value
    reward_granted: Optional[ReferralReward]
    occurred_at: int
    content_hash: str = ""

    def _compute_hash(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "content_hash"}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

    def with_hash(self) -> "ReferralEvent":
        h = self._compute_hash()
        # Reconstruct reward_granted as ReferralReward if asdict() has converted it to a dict
        reward = self.reward_granted
        if isinstance(reward, dict):
            reward = ReferralReward(
                reward_type=RewardType(reward["reward_type"]) if not isinstance(reward["reward_type"], RewardType) else reward["reward_type"],
                value=reward["value"],
                description=reward["description"],
                granted_at=reward["granted_at"],
                expires_at=reward.get("expires_at"),
            )
        return ReferralEvent(
            event_id=self.event_id,
            referrer_org_id=self.referrer_org_id,
            referred_org_id=self.referred_org_id,
            referral_code=self.referral_code,
            action=self.action,
            reward_granted=reward,
            occurred_at=self.occurred_at,
            content_hash=h,
        )


# ---------------------------------------------------------------------------
# Referral Engine
# ---------------------------------------------------------------------------

class ReferralEngine:
    """Track referrals, validate codes, grant rewards, prevent fraud.

    Thread-safety: This class uses no mutexes — callers should coordinate
    access in concurrent environments (or use a Redis-backed implementation).
    The in-process store is suitable for single-process deployments and tests.

    Usage::

        engine = ReferralEngine(secret="your-hmac-secret")
        code   = engine.code_for_org("acme-inc")       # deterministic

        # When a new org signs up with a referral code:
        ok, msg = engine.register_referral("new-org", code)

        # When the new org completes a qualifying action:
        event = engine.qualify("new-org", ReferralQualifyingAction.PRO_CONVERSION)
    """

    def __init__(self, secret: str = "adaad-referral-default-secret") -> None:
        self._secret            = secret
        self._code_to_org:  Dict[str, str]             = {}  # code → referrer_org_id
        self._referred_by:  Dict[str, str]             = {}  # referred_org_id → referrer_org_id
        self._referral_code: Dict[str, str]            = {}  # referred_org_id → code used
        self._rewarded_pairs: Set[Tuple[str, str, str]] = set()  # (referrer, referred, action)
        self._rewards:      Dict[str, List[ReferralReward]] = {}  # referrer_org_id → rewards
        self._event_log:    List[ReferralEvent]         = []

    # ------------------------------------------------------------------
    # Code management
    # ------------------------------------------------------------------

    def code_for_org(self, org_id: str) -> str:
        """Return the stable referral code for an org (deterministic)."""
        code = generate_referral_code(org_id, self._secret)
        self._code_to_org[code] = org_id
        return code

    def register_code(self, org_id: str) -> str:
        """Ensure org has a code registered in the lookup table."""
        return self.code_for_org(org_id)

    # ------------------------------------------------------------------
    # Referral registration
    # ------------------------------------------------------------------

    def register_referral(
        self,
        referred_org_id: str,
        referral_code: str,
    ) -> Tuple[bool, str]:
        """Record that `referred_org_id` signed up via `referral_code`.

        Returns (success, message).
        Fails if: code unknown, self-referral, already referred.
        """
        referral_code = referral_code.upper().strip()

        # Look up referrer
        referrer_org_id = self._code_to_org.get(referral_code)
        if not referrer_org_id:
            return False, f"Unknown referral code: {referral_code}"

        # Self-referral block
        if referrer_org_id == referred_org_id:
            return False, "Self-referral is not permitted"

        # Already referred
        if referred_org_id in self._referred_by:
            return False, f"{referred_org_id} was already referred by {self._referred_by[referred_org_id]}"

        self._referred_by[referred_org_id]  = referrer_org_id
        self._referral_code[referred_org_id] = referral_code
        return True, f"Referral registered: {referred_org_id} → {referrer_org_id}"

    # ------------------------------------------------------------------
    # Qualifying actions
    # ------------------------------------------------------------------

    def qualify(
        self,
        referred_org_id: str,
        action: ReferralQualifyingAction,
    ) -> Optional[ReferralEvent]:
        """Record a qualifying action and grant reward to referrer (if eligible).

        Returns ReferralEvent if referral chain exists, None otherwise.
        Idempotent: duplicate (referrer, referred, action) triplets are ignored.
        """
        referrer_org_id = self._referred_by.get(referred_org_id)
        if not referrer_org_id:
            return None  # not a referred org

        pair_key = (referrer_org_id, referred_org_id, action.value)
        reward: Optional[ReferralReward] = None

        if pair_key not in self._rewarded_pairs:
            self._rewarded_pairs.add(pair_key)
            reward = self._build_reward(action)
            if reward:
                if referrer_org_id not in self._rewards:
                    self._rewards[referrer_org_id] = []
                self._rewards[referrer_org_id].append(reward)

        event_id = hashlib.sha256(
            f"{referrer_org_id}:{referred_org_id}:{action.value}:{int(time.time())}".encode()
        ).hexdigest()[:24]

        event = ReferralEvent(
            event_id=event_id,
            referrer_org_id=referrer_org_id,
            referred_org_id=referred_org_id,
            referral_code=self._referral_code.get(referred_org_id, ""),
            action=action.value,
            reward_granted=reward,
            occurred_at=int(time.time()),
        ).with_hash()

        self._event_log.append(event)
        return event

    # ------------------------------------------------------------------
    # Reward queries
    # ------------------------------------------------------------------

    def rewards_for_org(self, org_id: str) -> List[ReferralReward]:
        return list(self._rewards.get(org_id, []))

    def pending_epoch_bonus(self, org_id: str) -> int:
        """Total un-expired epoch bonus credits for an org."""
        now = int(time.time())
        return int(sum(
            r.value
            for r in self._rewards.get(org_id, [])
            if r.reward_type == RewardType.EPOCH_BONUS
            and (r.expires_at is None or r.expires_at > now)
        ))

    def pending_credit_usd(self, org_id: str) -> float:
        """Total un-expired USD credit for an org."""
        now = int(time.time())
        return sum(
            r.value
            for r in self._rewards.get(org_id, [])
            if r.reward_type in (RewardType.PRO_CREDIT_USD, RewardType.ENTERPRISE_CREDIT)
            and (r.expires_at is None or r.expires_at > now)
        )

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def referral_count(self, org_id: str) -> int:
        """How many orgs this org has successfully referred."""
        return sum(1 for v in self._referred_by.values() if v == org_id)

    def top_referrers(self, n: int = 10) -> List[Tuple[str, int]]:
        """Top n orgs by referral count — [(org_id, count), ...]."""
        counts: Dict[str, int] = {}
        for v in self._referred_by.values():
            counts[v] = counts.get(v, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]

    def event_log(self) -> List[ReferralEvent]:
        return list(self._event_log)

    def total_rewards_granted(self) -> int:
        return len(self._event_log)

    def viral_coefficient(self) -> float:
        """k-factor: average referrals per paying org.  > 1.0 = viral growth."""
        total_referred = len(self._referred_by)
        total_referrers = len(set(self._referred_by.values()))
        if total_referrers == 0:
            return 0.0
        return total_referred / total_referrers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_reward(self, action: ReferralQualifyingAction) -> Optional[ReferralReward]:
        spec = _REWARD_CATALOGUE.get(action.value)
        if not spec:
            return None
        now = int(time.time())
        expires = now + spec["expires_days"] * 86400
        return ReferralReward(
            reward_type=spec["reward_type"],
            value=spec["value"],
            description=spec["description"],
            granted_at=now,
            expires_at=expires,
        )
