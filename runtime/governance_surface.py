# SPDX-License-Identifier: Apache-2.0
"""Governance surface registry for deterministic hashing and runtime lock controls.

`strip_version_comparison_ephemerals` removes runtime-generated fields that can cause
false divergence during replay/version comparisons.

Worked example (false divergence):
    Baseline payload::

        {
            "verification_result": "pass",
            "nonce": "nonce-1",
            "generated_at": "2026-02-01T00:00:01Z",
            "run_id": "run-a"
        }

    Retried payload::

        {
            "verification_result": "pass",
            "nonce": "nonce-2",
            "generated_at": "2026-02-01T00:00:02Z",
            "run_id": "run-b"
        }

    Without stripping, these compare as divergent even though governance semantics
    are unchanged. Stripping ephemerals yields equivalent material.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

# Explicit digest surface for governance envelope details.
CANONICAL_DETAIL_WHITELIST = frozenset(
    {
        "ok",
        "reason",
        "validator",
        "details",
        "proposal_id",
        "strategy_score",
        "critique_score",
        "agent_id",
        "proposal_hash",
        "bounds_policy_version",
    }
)

# Runtime-only fields that must never impact replay envelope digests.
VOLATILE_DETAIL_KEYS = frozenset(
    {
        "window_start_ts",
        "window_end_ts",
        "resource_usage_snapshot",
        "limits_snapshot",
        "platform_telemetry",
        "observed_measurements",
        "count",
        "rate_per_hour",
        "entries_considered",
        "entries_scoped",
        "event_types",
        "scope",
        "source",
    }
)

# Version comparison requires a broader ephemeral exclusion surface than digest
# canonicalization because replay audits compare runtime snapshots across hosts.
VERSION_COMPARISON_EPHEMERAL_FIELDS = frozenset(
    {
        *VOLATILE_DETAIL_KEYS,
        "nonce",
        "generated_at",
        "run_id",
        "replay_run_id",
        "attempt",
        "host_info",
        "attestation_hash",
        "timestamp",
        "ts",
    }
)


def deterministic_lock_enabled() -> bool:
    return os.getenv("ADAAD_DETERMINISTIC_LOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def canonicalize_governance_details(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s in VOLATILE_DETAIL_KEYS:
                continue
            if key_s in CANONICAL_DETAIL_WHITELIST or key_s.startswith("detail_"):
                cleaned[key_s] = canonicalize_governance_details(item)
            elif isinstance(item, Mapping):
                nested = canonicalize_governance_details(item)
                if nested:
                    cleaned[key_s] = nested
            elif isinstance(item, list):
                cleaned[key_s] = [canonicalize_governance_details(i) for i in item]
        return cleaned
    if isinstance(value, list):
        return [canonicalize_governance_details(item) for item in value]
    return value


def strip_version_comparison_ephemerals(value: Any) -> Any:
    """Recursively strip fields that should not influence replay/version equivalence."""

    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s in VERSION_COMPARISON_EPHEMERAL_FIELDS:
                continue
            cleaned[key_s] = strip_version_comparison_ephemerals(item)
        return cleaned
    if isinstance(value, list):
        return [strip_version_comparison_ephemerals(item) for item in value]
    return value


__all__ = [
    "CANONICAL_DETAIL_WHITELIST",
    "VERSION_COMPARISON_EPHEMERAL_FIELDS",
    "VOLATILE_DETAIL_KEYS",
    "canonicalize_governance_details",
    "deterministic_lock_enabled",
    "strip_version_comparison_ephemerals",
]
