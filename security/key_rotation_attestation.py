# SPDX-License-Identifier: Apache-2.0
"""Deterministic key-rotation attestation validation and event emission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Dict, Mapping

from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from security.ledger import journal

KEY_ROTATION_VERIFIED = "KEY_ROTATION_VERIFIED"
ATTESTATION_EPHEMERAL_FIELDS = frozenset({"nonce", "generated_at", "host_info", "attestation_hash"})


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str
    normalized_record: Dict[str, Any]
    computed_attestation_hash: str


def _strip_ephemeral(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a deterministic copy with non-attested fields removed."""
    return {str(k): v for k, v in dict(record).items() if str(k) not in ATTESTATION_EPHEMERAL_FIELDS}


def compute_attestation_hash(record: Mapping[str, Any]) -> str:
    """Compute deterministic attestation digest over canonicalized non-ephemeral content."""
    canonical = canonical_json(_strip_ephemeral(record))
    return sha256_prefixed_digest(canonical)


def _parse_iso8601(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("missing_timestamp")
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def validate_rotation_record(record: Mapping[str, Any]) -> ValidationResult:
    """Validate required attestation schema and semantic invariants."""
    normalized = dict(record)
    # Backward-compatibility path for existing Cryovant rotation metadata.
    legacy_required = ("interval_seconds", "last_rotation_ts", "last_rotation_iso")
    if all(field in normalized for field in legacy_required) and "rotation_date" not in normalized:
        try:
            parsed_interval = int(normalized.get("interval_seconds"))
        except (TypeError, ValueError):
            return ValidationResult(False, "interval_seconds_invalid", normalized, "")
        if parsed_interval < 0:
            return ValidationResult(False, "interval_seconds_invalid", normalized, "")

        try:
            parsed_rotation_ts = int(normalized.get("last_rotation_ts"))
        except (TypeError, ValueError):
            return ValidationResult(False, "last_rotation_ts_invalid", normalized, "")
        if parsed_rotation_ts < 0:
            return ValidationResult(False, "last_rotation_ts_invalid", normalized, "")

        if not isinstance(normalized.get("last_rotation_iso"), str):
            return ValidationResult(False, "last_rotation_iso_invalid", normalized, "")
        return ValidationResult(True, "ok", normalized, "")

    required = {
        "rotation_date",
        "previous_rotation_date",
        "next_rotation_due",
        "policy_days",
        "attestation_hash",
    }
    missing = sorted(key for key in required if key not in normalized)
    if missing:
        return ValidationResult(False, f"missing_required:{','.join(missing)}", normalized, "")

    try:
        rotation_date = _parse_iso8601(normalized.get("rotation_date"))
        previous_rotation_date = _parse_iso8601(normalized.get("previous_rotation_date"))
        next_rotation_due = _parse_iso8601(normalized.get("next_rotation_due"))
    except ValueError as exc:
        return ValidationResult(False, f"invalid_iso8601:{exc}", normalized, "")

    if rotation_date <= previous_rotation_date:
        return ValidationResult(False, "rotation_not_monotonic", normalized, "")

    try:
        policy_days = int(normalized.get("policy_days"))
    except (TypeError, ValueError):
        return ValidationResult(False, "invalid_policy_days", normalized, "")
    if policy_days <= 0:
        return ValidationResult(False, "invalid_policy_days", normalized, "")

    expected_due = rotation_date + timedelta(days=policy_days)
    due_delta_days = abs((next_rotation_due - expected_due).total_seconds()) / 86400.0
    if due_delta_days > 1.0:
        return ValidationResult(False, "next_rotation_due_mismatch", normalized, "")

    computed = compute_attestation_hash(normalized)
    if str(normalized.get("attestation_hash") or "") != computed:
        return ValidationResult(False, "attestation_hash_mismatch", normalized, computed)

    return ValidationResult(True, "ok", normalized, computed)


def emit_key_rotation_verified(
    record: Mapping[str, Any],
    *,
    ledger: LineageLedgerV2 | None = None,
    metrics_module: Any | None = None,
    journal_module: Any | None = None,
) -> Mapping[str, Any]:
    """Emit immutable key-rotation verification payload to all audit sinks."""
    payload = MappingProxyType(dict(record))
    event_payload = dict(payload)
    event_payload.setdefault("event_type", KEY_ROTATION_VERIFIED)

    resolved_metrics = metrics_module
    if resolved_metrics is None:
        from runtime import metrics as resolved_metrics

    resolved_journal = journal_module or journal
    resolved_ledger = ledger or LineageLedgerV2()

    resolved_metrics.log(event_type=KEY_ROTATION_VERIFIED, payload=event_payload, level="INFO")
    resolved_ledger.append_event(KEY_ROTATION_VERIFIED, event_payload)
    resolved_journal.record_rotation_event(action=KEY_ROTATION_VERIFIED, payload=event_payload)
    return payload


__all__ = [
    "ATTESTATION_EPHEMERAL_FIELDS",
    "KEY_ROTATION_VERIFIED",
    "ValidationResult",
    "_strip_ephemeral",
    "compute_attestation_hash",
    "validate_rotation_record",
    "emit_key_rotation_verified",
]
