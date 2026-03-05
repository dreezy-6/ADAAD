# SPDX-License-Identifier: Apache-2.0
# Federation Key Registry

**Status:** Active — Governed by `governance/federation_trusted_keys.json`
**Last reviewed:** 2026-03-05
**Governance impact:** Critical — changes require PR review + CI gate pass

---

## Purpose

The federation key registry prevents caller-supplied public key substitution attacks in the
federation transport layer. Prior to PR-SECURITY-01, `verify_message_signature()` accepted
any public key embedded in the message payload, allowing an attacker to substitute their
own key+signature pair. This document governs the registry lifecycle.

---

## Architecture

```
governance/federation_trusted_keys.json   ← source of truth (in-repo, governance-signed)
       │
       ▼
runtime/governance/federation/key_registry.py   ← loader with in-process cache
       │
       ▼
runtime/governance/federation/transport.py      ← verify_message_signature()
       │                                            calls get_trusted_public_key(key_id)
       ▼
FederationTransportContractError raised if key_id not in registry
```

---

## Registry Format

`governance/federation_trusted_keys.json`:

```json
{
  "trusted_keys": [
    {
      "key_id": "federation-root-1",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `key_id` | string | ✅ | Unique identifier. Referenced in federation message `$.signature.key_id`. |
| `public_key_pem` | string | ✅ | Ed25519 public key in PEM format. |

---

## Adding a Key

1. Generate an Ed25519 key pair:
   ```bash
   python3 -c "
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
   key = Ed25519PrivateKey.generate()
   pub = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
   print(pub.decode())
   "
   ```
2. Add a new entry to `governance/federation_trusted_keys.json` with a unique `key_id`.
3. Open a PR targeting `main` with label `governance-impact`.
4. Obtain ≥ 2 reviewer approvals.
5. Verify CI green — the registry is validated at boot by `key_registry.py`.

---

## Revoking a Key

1. Remove the entry for the `key_id` from `governance/federation_trusted_keys.json`.
2. Open a PR with label `governance-impact` and `security`.
3. After merge, any federation message signed by the revoked key will be rejected
   with `federation_key_id_untrusted:<key_id>`.

---

## Key Rotation Runbook

| Step | Action |
|---|---|
| 1 | Generate replacement key pair (see "Adding a Key" above). |
| 2 | Add new key entry with a new `key_id` (e.g. `federation-root-2`). |
| 3 | Merge PR, deploy. Both old and new keys now accepted. |
| 4 | Update all federation peers to sign with new key_id. |
| 5 | After all peers migrated, remove old key entry in a follow-up PR. |
| 6 | Emit `FEDERATION_KEY_ROTATED` ledger event manually or via rotation script. |

---

## Error Codes

| Code | Meaning |
|---|---|
| `key_registry:unreadable` | Registry file missing or malformed JSON. Boot fails. |
| `federation_key_registry_invalid` | Registry has no `trusted_keys` list or list is empty. |
| `federation_key_registry_malformed` | Individual key entry missing required fields. |
| `federation_key_id_untrusted:<key_id>` | Message presents a key_id not in registry. |

---

## Tests

- `tests/governance/federation/test_federation_key_registry.py` — registry loader unit tests
- `tests/governance/federation/test_federation_transport_trusted_keys.py` — transport integration tests

---

## Related Governance Documents

- [Security Invariants Matrix](SECURITY_INVARIANTS_MATRIX.md)
- [Federation Conflict Runbook](FEDERATION_CONFLICT_RUNBOOK.md)
- [Replay Proof of Legitimacy Exchange](REPLAY_PROOF_OF_LEGITIMACY_EXCHANGE.md)
