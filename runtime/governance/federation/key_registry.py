# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from typing import Dict

from runtime import ROOT_DIR

_REGISTRY_PATH = ROOT_DIR / "governance" / "federation_trusted_keys.json"
_CACHE: Dict[str, str] | None = None


def _error(code: str, exc: Exception | None = None):
    from .transport import FederationTransportContractError

    if exc is None:
        raise FederationTransportContractError(code)
    raise FederationTransportContractError(code) from exc


def _load_registry() -> Dict[str, str]:
    try:
        raw = json.loads(_REGISTRY_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _error("federation_key_registry_unreadable", exc)

    if not isinstance(raw, dict):
        _error("federation_key_registry_invalid")

    entries = raw.get("trusted_keys")
    if not isinstance(entries, list) or not entries:
        _error("federation_key_registry_invalid")

    mapping: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            _error("federation_key_registry_malformed")
        key_id = entry.get("key_id")
        pem = entry.get("public_key_pem")
        if not isinstance(key_id, str) or not key_id.strip():
            _error("federation_key_registry_malformed")
        if not isinstance(pem, str) or not pem.strip():
            _error("federation_key_registry_malformed")
        normalized_key = key_id.strip()
        if normalized_key in mapping:
            _error("federation_key_registry_duplicate_key_id")
        mapping[normalized_key] = pem
    return mapping


def get_trusted_public_key(key_id: str) -> str:
    global _CACHE
    normalized_key_id = str(key_id or "").strip()
    if not normalized_key_id:
        _error("federation_key_id_missing")
    if _CACHE is None:
        _CACHE = _load_registry()
    try:
        return _CACHE[normalized_key_id]
    except KeyError as exc:
        _error(f"federation_key_id_untrusted:{normalized_key_id}", exc)
