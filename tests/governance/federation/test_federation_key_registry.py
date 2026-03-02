# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json

import pytest

from runtime.governance.federation.key_registry import get_trusted_public_key
from runtime.governance.federation.transport import FederationTransportContractError


def _reset_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("runtime.governance.federation.key_registry._CACHE", None)


def test_registry_loads_trusted_key(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = tmp_path / "federation_trusted_keys.json"
    registry.write_text(
        json.dumps(
            {
                "trusted_keys": [
                    {
                        "key_id": "federation-root-1",
                        "public_key_pem": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("runtime.governance.federation.key_registry._REGISTRY_PATH", registry)
    _reset_cache(monkeypatch)

    assert "BEGIN PUBLIC KEY" in get_trusted_public_key("federation-root-1")


@pytest.mark.parametrize(
    "registry_payload,expected_error",
    [
        ({}, "federation_key_registry_invalid"),
        ({"trusted_keys": []}, "federation_key_registry_invalid"),
        ({"trusted_keys": [{"public_key_pem": "pem-only"}]}, "federation_key_registry_malformed"),
        ({"trusted_keys": [{"key_id": "id-only"}]}, "federation_key_registry_malformed"),
    ],
)
def test_registry_malformed_rejected(tmp_path, monkeypatch: pytest.MonkeyPatch, registry_payload: dict, expected_error: str) -> None:
    registry = tmp_path / "federation_trusted_keys.json"
    registry.write_text(json.dumps(registry_payload), encoding="utf-8")
    monkeypatch.setattr("runtime.governance.federation.key_registry._REGISTRY_PATH", registry)
    _reset_cache(monkeypatch)

    with pytest.raises(FederationTransportContractError, match=expected_error):
        get_trusted_public_key("federation-root-1")


def test_untrusted_key_id_rejected(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = tmp_path / "federation_trusted_keys.json"
    registry.write_text(
        json.dumps(
            {
                "trusted_keys": [
                    {
                        "key_id": "trusted",
                        "public_key_pem": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("runtime.governance.federation.key_registry._REGISTRY_PATH", registry)
    _reset_cache(monkeypatch)

    with pytest.raises(FederationTransportContractError, match="federation_key_id_untrusted:unknown"):
        get_trusted_public_key("unknown")
