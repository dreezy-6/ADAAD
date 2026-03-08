# SPDX-License-Identifier: Apache-2.0
"""Onboarding Service — ADAAD Phase 8, M8-08.

Self-serve organisation onboarding: creates the org in OrgRegistry,
generates an API key, and returns everything needed to start using ADAAD
in a single governed transaction.

This is the commercial critical path — the flow that converts a Stripe
subscription into a working ADAAD API key.

Architectural invariants:
- Onboarding is atomic: if key generation fails, the org is not created.
- Every onboarding event is emitted to the governance ledger.
- Org IDs are caller-supplied slugs (stable, URL-safe, alphanumeric + hyphens).
- The returned API key is shown exactly once and never stored server-side.
  Callers must store it securely.
- Replay-safe: caller supplies `now` for deterministic audit.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from runtime.monetization.org_registry import OrgRegistry, Organisation, OrgAlreadyExists
from runtime.monetization.api_key_manager import ApiKeyManager


# ---------------------------------------------------------------------------
# Org ID validation
# ---------------------------------------------------------------------------

_ORG_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")


def validate_org_id(org_id: str) -> None:
    """Raise ValueError if org_id is not a valid slug."""
    if not _ORG_ID_RE.match(org_id):
        raise ValueError(
            f"Invalid org_id {org_id!r}. Must be 3-63 chars, lowercase alphanumeric + hyphens, "
            "no leading/trailing hyphens."
        )


# ---------------------------------------------------------------------------
# Onboarding result
# ---------------------------------------------------------------------------

@dataclass
class OnboardingResult:
    """Result of a successful org onboarding."""
    org:         Organisation
    api_key:     str       # ⚠ shown once — must be stored by caller
    kid:         str
    tier:        str
    is_new_org:  bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org":        self.org.to_public_dict(),
            "api_key":    self.api_key,
            "kid":        self.kid,
            "tier":       self.tier,
            "is_new_org": self.is_new_org,
            "warning":    "Store your API key securely — it cannot be retrieved after this response.",
        }


# ---------------------------------------------------------------------------
# Onboarding Service
# ---------------------------------------------------------------------------

class OnboardingService:
    """Governs the complete self-serve org creation and key provisioning flow.

    Designed to be called from:
    - Stripe webhook handler (on subscription.created)
    - Admin CLI (manual org provisioning)
    - Self-serve API endpoint (POST /api/orgs)
    """

    def __init__(
        self,
        org_registry: OrgRegistry,
        key_manager:  ApiKeyManager,
    ) -> None:
        self._orgs = org_registry
        self._keys = key_manager

    def onboard(
        self,
        org_id:             str,
        display_name:       str,
        tier:               str = "community",
        stripe_customer_id: Optional[str] = None,
        expires_at:         Optional[int] = None,
        metadata:           Optional[Dict[str, Any]] = None,
        now:                Optional[int] = None,
    ) -> OnboardingResult:
        """Create an org and provision its first API key.

        Args:
            org_id:             Unique slug (lowercase alphanumeric + hyphens).
            display_name:       Human-readable org name.
            tier:               Initial tier ("community" | "pro" | "enterprise").
            stripe_customer_id: Stripe customer ID (for billing webhook correlation).
            expires_at:         Optional key expiry (Unix timestamp). None = never.
            metadata:           Additional org metadata.
            now:                Unix timestamp for replay safety. Defaults to time.time().

        Returns:
            OnboardingResult with the org and its API key.

        Raises:
            ValueError:       If org_id is invalid.
            OrgAlreadyExists: If org_id is already registered.
        """
        validate_org_id(org_id)
        ts = now or int(time.time())

        # Generate key FIRST (atomic: if this fails, org is not created)
        api_key_token = self._keys.generate(
            tier       = tier,
            org_id     = org_id,
            issued_at  = ts,
            expires_at = expires_at,
        )
        # Parse to get the kid
        parsed = self._keys.validate(api_key_token, current_time=None)

        # Create org with the key's kid
        org = self._orgs.create(
            org_id             = org_id,
            display_name       = display_name,
            tier               = tier,
            stripe_customer_id = stripe_customer_id,
            active_kid         = parsed.kid,
            metadata           = metadata or {},
            now                = ts,
        )

        return OnboardingResult(
            org        = org,
            api_key    = api_key_token,
            kid        = parsed.kid,
            tier       = tier,
            is_new_org = True,
        )

    def rotate_key(
        self,
        org_id:     str,
        expires_at: Optional[int] = None,
        now:        Optional[int] = None,
    ) -> OnboardingResult:
        """Issue a new API key for an existing org and record the rotation.

        The old key continues to work until explicitly revoked.

        Returns:
            OnboardingResult with the new key. is_new_org = False.
        """
        ts  = now or int(time.time())
        org = self._orgs.get(org_id)

        new_token = self._keys.generate(
            tier       = org.tier,
            org_id     = org_id,
            issued_at  = ts,
            expires_at = expires_at,
        )
        parsed = self._keys.validate(new_token, current_time=None)
        self._orgs.rotate_key(org_id, new_kid=parsed.kid, now=ts)

        return OnboardingResult(
            org        = org,
            api_key    = new_token,
            kid        = parsed.kid,
            tier       = org.tier,
            is_new_org = False,
        )
