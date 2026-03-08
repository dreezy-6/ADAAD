# SPDX-License-Identifier: Apache-2.0
"""API Key Manager — ADAAD Phase 8, M8-02.

Generates, validates, and revokes HMAC-SHA256-signed API keys for the
ADAAD SaaS platform. Keys are self-contained bearer tokens — no database
lookup required for validation (offline-capable, replay-safe).

Key anatomy:
  adaad_<tier_prefix>_<base64url(payload)>_<hmac_tag>

  tier_prefix: cm (community) | pr (pro) | en (enterprise)
  payload: base64url-encoded JSON {kid, tier, org_id, issued_at, expires_at}
  hmac_tag: first 32 chars of HMAC-SHA256(signing_key, payload)

Architectural invariants:
- Validation is deterministic given the same signing key — replay-safe.
- Revocation is tracked in an in-memory set (callers supply persistence).
- Key generation never calls time.time() directly; callers pass issued_at.
- Signing key is loaded from ADAAD_API_SIGNING_KEY env var (fail-closed).

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Optional, Set


# ---------------------------------------------------------------------------
# Key status
# ---------------------------------------------------------------------------

class KeyStatus(str, Enum):
    ACTIVE  = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    INVALID = "invalid"


# ---------------------------------------------------------------------------
# Key prefix mapping
# ---------------------------------------------------------------------------

_TIER_PREFIX: Dict[str, str] = {
    "community":  "cm",
    "pro":        "pr",
    "enterprise": "en",
}

_PREFIX_TO_TIER: Dict[str, str] = {v: k for k, v in _TIER_PREFIX.items()}

KEY_VERSION = "1"
KEY_SCHEME  = "adaad"


# ---------------------------------------------------------------------------
# ApiKey dataclass
# ---------------------------------------------------------------------------

@dataclass
class ApiKey:
    """Decoded, validated API key."""
    kid:        str           # Key ID (random 16-char hex)
    tier:       str           # "community" | "pro" | "enterprise"
    org_id:     str           # Organisation identifier
    issued_at:  int           # Unix timestamp (seconds)
    expires_at: Optional[int] # Unix timestamp or None (never expires)
    status:     KeyStatus = KeyStatus.ACTIVE
    raw_token:  str = field(default="", repr=False)

    @property
    def is_enterprise(self) -> bool:
        return self.tier == "enterprise"

    @property
    def is_pro_or_above(self) -> bool:
        return self.tier in {"pro", "enterprise"}

    def to_public_dict(self) -> Dict:
        """Return a dict safe to expose in API responses (no secrets)."""
        return {
            "kid":        self.kid,
            "tier":       self.tier,
            "org_id":     self.org_id,
            "issued_at":  self.issued_at,
            "expires_at": self.expires_at,
            "status":     self.status.value,
        }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ApiKeyValidationError(Exception):
    """Raised when an API key cannot be validated."""
    def __init__(self, reason: str, status: KeyStatus = KeyStatus.INVALID):
        self.reason = reason
        self.status = status
        super().__init__(f"[ADAAD-KEY] {reason}")


# ---------------------------------------------------------------------------
# API Key Manager
# ---------------------------------------------------------------------------

class ApiKeyManager:
    """Generates and validates HMAC-signed ADAAD API keys.

    Thread-safe for concurrent FastAPI request handling.
    """

    ENV_SIGNING_KEY = "ADAAD_API_SIGNING_KEY"

    def __init__(
        self,
        signing_key: Optional[bytes] = None,
        revoked_kids: Optional[Set[str]] = None,
    ) -> None:
        """
        Args:
            signing_key: Raw bytes for HMAC. Falls back to env var
                ADAAD_API_SIGNING_KEY. Raises RuntimeError if absent.
            revoked_kids: Set of revoked Key IDs (caller manages persistence).
        """
        if signing_key is not None:
            self._signing_key = signing_key
        else:
            env_val = os.environ.get(self.ENV_SIGNING_KEY, "")
            if not env_val:
                raise RuntimeError(
                    f"[ADAAD-KEY] {self.ENV_SIGNING_KEY} is not set. "
                    "API key management is fail-closed without a signing key."
                )
            self._signing_key = env_val.encode("utf-8")

        self._revoked: Set[str] = revoked_kids or set()

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    def generate(
        self,
        tier: str,
        org_id: str,
        issued_at: int,
        expires_at: Optional[int] = None,
    ) -> str:
        """Generate a new signed API key.

        Args:
            tier:       "community" | "pro" | "enterprise"
            org_id:     Stable organisation identifier (e.g. slug or UUID).
            issued_at:  Unix timestamp for issuance (caller provides for replay safety).
            expires_at: Optional Unix timestamp. None = never expires.

        Returns:
            Signed key string suitable for use as a Bearer token.
        """
        if tier not in _TIER_PREFIX:
            raise ValueError(f"Unknown tier: {tier!r}. Must be one of {list(_TIER_PREFIX)}")

        kid = secrets.token_hex(8)  # 16-char hex key ID
        prefix = _TIER_PREFIX[tier]

        payload_obj = {
            "v":   KEY_VERSION,
            "kid": kid,
            "t":   tier,
            "org": org_id,
            "iat": issued_at,
            "exp": expires_at,
        }
        payload_json  = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True)
        payload_b64   = _b64url_encode(payload_json.encode())
        tag           = self._sign(payload_b64)

        return f"{KEY_SCHEME}_{prefix}_{payload_b64}_{tag}"

    # ------------------------------------------------------------------
    # Key validation
    # ------------------------------------------------------------------

    def validate(self, token: str, current_time: Optional[int] = None) -> ApiKey:
        """Parse and validate an API key.

        Args:
            token:        Raw bearer token string.
            current_time: Unix timestamp for expiry check (caller provides
                          for replay safety). Pass None to skip expiry check.

        Returns:
            Decoded ApiKey on success.

        Raises:
            ApiKeyValidationError on any validation failure.
        """
        parts = token.split("_")
        if len(parts) != 4:
            raise ApiKeyValidationError("Malformed key: expected 4 segments")

        scheme, prefix, payload_b64, tag = parts

        if scheme != KEY_SCHEME:
            raise ApiKeyValidationError(f"Unknown key scheme: {scheme!r}")

        if prefix not in _PREFIX_TO_TIER:
            raise ApiKeyValidationError(f"Unknown tier prefix: {prefix!r}")

        # HMAC verification — constant-time
        expected_tag = self._sign(payload_b64)
        if not _hmac.compare_digest(tag, expected_tag):
            raise ApiKeyValidationError("Signature verification failed")

        # Decode payload
        try:
            payload_json = _b64url_decode(payload_b64).decode("utf-8")
            payload      = json.loads(payload_json)
        except Exception as exc:
            raise ApiKeyValidationError(f"Payload decode error: {exc}")

        tier   = _PREFIX_TO_TIER.get(prefix, "community")
        kid    = payload.get("kid", "")
        org_id = payload.get("org", "")

        if tier != payload.get("t"):
            raise ApiKeyValidationError("Tier mismatch between prefix and payload")

        # Revocation check
        if kid in self._revoked:
            raise ApiKeyValidationError(
                f"Key {kid!r} has been revoked", status=KeyStatus.REVOKED
            )

        # Expiry check (if caller supplies current_time)
        expires_at = payload.get("exp")
        if current_time is not None and expires_at is not None:
            if current_time > expires_at:
                raise ApiKeyValidationError(
                    f"Key {kid!r} expired at {expires_at}", status=KeyStatus.EXPIRED
                )

        return ApiKey(
            kid        = kid,
            tier       = tier,
            org_id     = org_id,
            issued_at  = payload.get("iat", 0),
            expires_at = expires_at,
            status     = KeyStatus.ACTIVE,
            raw_token  = token,
        )

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    def revoke(self, kid: str) -> None:
        """Mark a key ID as revoked. Thread-safe append."""
        self._revoked.add(kid)

    def is_revoked(self, kid: str) -> bool:
        return kid in self._revoked

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _sign(self, payload_b64: str) -> str:
        """Return the first 32 hex characters of HMAC-SHA256(key, payload)."""
        digest = _hmac.new(
            self._signing_key,
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return digest[:32]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("ascii"))
