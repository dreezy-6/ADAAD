# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import base64

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from runtime.governance.federation.transport import (
    FederationTransportContractError,
    compute_message_digest,
    validate_canonical_federation_message,
)


def _signed_policy_exchange_message(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    trusted_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    monkeypatch.setattr("runtime.governance.federation.transport.get_trusted_public_key", lambda _key_id: trusted_pem)

    message: dict[str, object] = {
        "schema_id": "https://adaad.local/schemas/federation_policy_exchange.v1.json",
        "message_type": "policy_exchange",
        "payload": {
            "exchange_id": "ex-1",
            "source_peer_id": "node-a",
            "target_peer_id": "node-b",
            "policy_version": "2.1.0",
            "manifest_digest": "sha256:" + ("a" * 64),
            "sent_at_epoch": 100,
        },
    }
    digest = compute_message_digest(message)
    message["digest"] = digest
    message["signature"] = {
        "algorithm": "ed25519",
        "key_id": "node-a-key",
        "public_key": "attacker-controlled-and-ignored",
        "signature": base64.b64encode(private_key.sign(digest.encode("utf-8"))).decode("ascii"),
    }
    return message


def test_valid_signature_and_digest_pass_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _signed_policy_exchange_message(monkeypatch)

    validated = validate_canonical_federation_message(message)

    assert validated["digest"] == message["digest"]


def test_digest_mismatch_is_rejected_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _signed_policy_exchange_message(monkeypatch)
    message["payload"]["policy_version"] = "2.2.0"

    with pytest.raises(FederationTransportContractError, match=r"\$\.digest:mismatch"):
        validate_canonical_federation_message(message)


def test_invalid_signature_is_rejected_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _signed_policy_exchange_message(monkeypatch)
    signature = dict(message["signature"])
    signature["signature"] = base64.b64encode(b"\x00" * 64).decode("ascii")
    message["signature"] = signature

    with pytest.raises(FederationTransportContractError, match=r"\$\.signature:invalid"):
        validate_canonical_federation_message(message)
