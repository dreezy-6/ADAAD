# SPDX-License-Identifier: Apache-2.0
"""Organisation Registry — ADAAD Phase 8, M8-06.

Append-only, in-process organisation store. Every org state change is
recorded as an immutable lifecycle event before the in-memory state is
updated (event-sourced pattern).

Callers are responsible for flushing events to persistent storage
(Postgres, DynamoDB, append-only file). This module is the authoritative
in-process accumulator — safe for replay.

Architectural invariants:
- Org state is derived from the event stream (event-sourced). No silent mutations.
- Every state transition emits a governance lifecycle event BEFORE updating state.
- Org IDs are immutable after creation.
- Tier can only move forward through upgrade or backward through cancellation.
- Thread-safe: RLock guards all state mutations.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Org status
# ---------------------------------------------------------------------------

class OrgStatus(str, Enum):
    ACTIVE          = "active"
    GRACE_PERIOD    = "grace_period"   # payment failed, within grace window
    SUSPENDED       = "suspended"      # grace expired, not yet deleted
    DELETED         = "deleted"        # soft-deleted


# ---------------------------------------------------------------------------
# Org lifecycle event types
# ---------------------------------------------------------------------------

ORG_EVENT_CREATED         = "org_created"
ORG_EVENT_TIER_CHANGED    = "org_tier_changed"
ORG_EVENT_STATUS_CHANGED  = "org_status_changed"
ORG_EVENT_KEY_ROTATED     = "org_key_rotated"
ORG_EVENT_DELETED         = "org_deleted"


# ---------------------------------------------------------------------------
# Org model
# ---------------------------------------------------------------------------

@dataclass
class Organisation:
    """Current state of an ADAAD customer organisation."""
    org_id:             str
    display_name:       str
    tier:               str          # "community" | "pro" | "enterprise"
    status:             OrgStatus
    stripe_customer_id: Optional[str]
    active_kid:         Optional[str]   # current API key ID
    created_at:         int             # Unix timestamp
    updated_at:         int             # Unix timestamp
    metadata:           Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_public_dict(self) -> Dict[str, Any]:
        """Safe for API responses — excludes internal fields."""
        return {
            "org_id":       self.org_id,
            "display_name": self.display_name,
            "tier":         self.tier,
            "status":       self.status.value,
            "created_at":   self.created_at,
        }


# ---------------------------------------------------------------------------
# Org lifecycle event
# ---------------------------------------------------------------------------

@dataclass
class OrgLifecycleEvent:
    """Immutable org state-change record."""
    event_type: str
    org_id:     str
    payload:    Dict[str, Any]
    timestamp:  int
    entry_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        payload_json = json.dumps(
            {"event_type": self.event_type, "org_id": self.org_id,
             "payload": self.payload, "timestamp": self.timestamp},
            sort_keys=True, separators=(",", ":")
        )
        self.entry_hash = "sha256:" + hashlib.sha256(payload_json.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "org_id":     self.org_id,
            "payload":    self.payload,
            "timestamp":  self.timestamp,
            "entry_hash": self.entry_hash,
        }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OrgNotFound(Exception):
    def __init__(self, org_id: str):
        super().__init__(f"Organisation not found: {org_id!r}")
        self.org_id = org_id


class OrgAlreadyExists(Exception):
    def __init__(self, org_id: str):
        super().__init__(f"Organisation already exists: {org_id!r}")
        self.org_id = org_id


class OrgStatusError(Exception):
    """Raised when an operation is invalid for the current org status."""


# ---------------------------------------------------------------------------
# Org Registry
# ---------------------------------------------------------------------------

class OrgRegistry:
    """Thread-safe, event-sourced organisation registry.

    Designed to be instantiated once per process and shared across handlers.
    """

    def __init__(self) -> None:
        self._lock   = threading.RLock()
        self._orgs:   Dict[str, Organisation]      = {}
        self._by_stripe: Dict[str, str]            = {}  # stripe_customer_id → org_id
        self._events: List[OrgLifecycleEvent]      = []

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create(
        self,
        org_id:             str,
        display_name:       str,
        tier:               str = "community",
        stripe_customer_id: Optional[str] = None,
        active_kid:         Optional[str] = None,
        metadata:           Optional[Dict[str, Any]] = None,
        now:                Optional[int] = None,
    ) -> Organisation:
        """Create a new organisation. Raises OrgAlreadyExists if org_id taken."""
        ts = now or int(time.time())
        with self._lock:
            if org_id in self._orgs:
                raise OrgAlreadyExists(org_id)

            event = OrgLifecycleEvent(
                event_type = ORG_EVENT_CREATED,
                org_id     = org_id,
                payload    = {
                    "display_name":       display_name,
                    "tier":               tier,
                    "stripe_customer_id": stripe_customer_id,
                    "active_kid":         active_kid,
                },
                timestamp  = ts,
            )
            self._events.append(event)

            org = Organisation(
                org_id             = org_id,
                display_name       = display_name,
                tier               = tier,
                status             = OrgStatus.ACTIVE,
                stripe_customer_id = stripe_customer_id,
                active_kid         = active_kid,
                created_at         = ts,
                updated_at         = ts,
                metadata           = metadata or {},
            )
            self._orgs[org_id] = org
            if stripe_customer_id:
                self._by_stripe[stripe_customer_id] = org_id
            return org

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, org_id: str) -> Organisation:
        with self._lock:
            try:
                return self._orgs[org_id]
            except KeyError:
                raise OrgNotFound(org_id)

    def get_by_stripe(self, stripe_customer_id: str) -> Organisation:
        with self._lock:
            org_id = self._by_stripe.get(stripe_customer_id)
            if not org_id:
                raise OrgNotFound(f"stripe:{stripe_customer_id}")
            return self._orgs[org_id]

    def list_all(self) -> List[Organisation]:
        with self._lock:
            return list(self._orgs.values())

    def count(self) -> Dict[str, int]:
        """Return counts by tier and status."""
        with self._lock:
            tiers:    Dict[str, int] = {}
            statuses: Dict[str, int] = {}
            for org in self._orgs.values():
                tiers[org.tier]              = tiers.get(org.tier, 0) + 1
                statuses[org.status.value]   = statuses.get(org.status.value, 0) + 1
            return {"total": len(self._orgs), "by_tier": tiers, "by_status": statuses}

    # ------------------------------------------------------------------
    # Tier transitions
    # ------------------------------------------------------------------

    def set_tier(
        self,
        org_id:    str,
        new_tier:  str,
        reason:    str = "",
        now:       Optional[int] = None,
    ) -> Organisation:
        """Change an org's tier. Emits org_tier_changed event before updating."""
        ts = now or int(time.time())
        with self._lock:
            org = self.get(org_id)
            old_tier = org.tier

            event = OrgLifecycleEvent(
                event_type = ORG_EVENT_TIER_CHANGED,
                org_id     = org_id,
                payload    = {"from_tier": old_tier, "to_tier": new_tier, "reason": reason},
                timestamp  = ts,
            )
            self._events.append(event)
            org.tier       = new_tier
            org.updated_at = ts
            return org

    def set_status(
        self,
        org_id:     str,
        new_status: OrgStatus,
        reason:     str = "",
        now:        Optional[int] = None,
    ) -> Organisation:
        """Change org status. Emits org_status_changed before updating."""
        ts = now or int(time.time())
        with self._lock:
            org = self.get(org_id)
            event = OrgLifecycleEvent(
                event_type = ORG_EVENT_STATUS_CHANGED,
                org_id     = org_id,
                payload    = {
                    "from_status": org.status.value,
                    "to_status":   new_status.value,
                    "reason":      reason,
                },
                timestamp  = ts,
            )
            self._events.append(event)
            org.status     = new_status
            org.updated_at = ts
            return org

    def rotate_key(
        self,
        org_id:    str,
        new_kid:   str,
        now:       Optional[int] = None,
    ) -> Organisation:
        """Record a key rotation for an org."""
        ts = now or int(time.time())
        with self._lock:
            org = self.get(org_id)
            event = OrgLifecycleEvent(
                event_type = ORG_EVENT_KEY_ROTATED,
                org_id     = org_id,
                payload    = {"old_kid": org.active_kid, "new_kid": new_kid},
                timestamp  = ts,
            )
            self._events.append(event)
            org.active_kid = new_kid
            org.updated_at = ts
            return org

    def soft_delete(self, org_id: str, now: Optional[int] = None) -> Organisation:
        ts = now or int(time.time())
        with self._lock:
            org = self.get(org_id)
            event = OrgLifecycleEvent(
                event_type = ORG_EVENT_DELETED,
                org_id     = org_id,
                payload    = {"previous_status": org.status.value},
                timestamp  = ts,
            )
            self._events.append(event)
            org.status     = OrgStatus.DELETED
            org.updated_at = ts
            return org

    # ------------------------------------------------------------------
    # Event stream
    # ------------------------------------------------------------------

    def flush_events(self) -> List[Dict[str, Any]]:
        """Return all events as dicts and clear the buffer."""
        with self._lock:
            result = [e.to_dict() for e in self._events]
            self._events.clear()
            return result

    def event_count(self) -> int:
        with self._lock:
            return len(self._events)
