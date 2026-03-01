#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""CI gate for key-rotation attestation validation."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from security.key_rotation_attestation import validate_rotation_record


def _parse_iso8601(value: Any) -> datetime:
    text = str(value or "").strip()
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def main() -> int:
    rotation_path = Path(os.getenv("ADAAD_KEY_ROTATION_FILE", "security/keys/rotation.json"))
    status_path = Path(os.getenv("ADAAD_KEY_ROTATION_STATUS_FILE", "key_rotation_status.json"))
    max_age_days = int(os.getenv("ADAAD_KEY_ROTATION_MAX_AGE_DAYS", "90") or "90")

    status: Dict[str, Any] = {
        "verified": False,
        "rotation_file": str(rotation_path),
        "max_age_days": max_age_days,
    }

    try:
        record = json.loads(rotation_path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("rotation_record_not_object")
    except Exception as exc:
        status["error"] = f"load_failed:{exc}"
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
        return 1

    validation = validate_rotation_record(record)
    status.update(
        {
            "rotation_date": str(record.get("rotation_date") or record.get("last_rotation_iso") or ""),
            "policy_days": record.get("policy_days"),
            "attestation_hash_valid": validation.ok,
            "validation_reason": validation.reason,
            "computed_attestation_hash": validation.computed_attestation_hash,
        }
    )
    if not validation.ok:
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
        return 1

    try:
        if record.get("rotation_date"):
            rotation_date = _parse_iso8601(record.get("rotation_date"))
        elif record.get("last_rotation_ts") is not None:
            rotation_date = datetime.fromtimestamp(int(record.get("last_rotation_ts")), tz=timezone.utc)
        else:
            rotation_date = _parse_iso8601(record.get("last_rotation_iso"))
        age_days = max(0.0, (datetime.now(timezone.utc) - rotation_date).total_seconds() / 86400.0)
    except Exception as exc:
        status["error"] = f"rotation_age_parse_failed:{exc}"
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
        return 1

    status["age_days"] = round(age_days, 6)
    status["verified"] = age_days <= max_age_days
    if not status["verified"]:
        status["error"] = f"rotation_stale:{age_days:.2f}>{max_age_days}"

    status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if status["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
