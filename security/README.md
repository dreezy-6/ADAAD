# Water (security)

Cryovant enforces environment validation, agent certification, and lineage ancestry checks. Ledger data is stored under `security/ledger/` and must be writable; keys live in `security/keys/` with owner-only permissions. Any failed validation blocks Dream/Beast execution.

Signature verification expects `sha256:<hex>` digests computed from `HMAC-SHA-256(key_bytes, b"cryovant")` and evaluates key files in `security/keys/` using deterministic filename ordering to support key rotation.

## Key rotation attestation

- `security/key_rotation_attestation.py` validates `security/keys/rotation.json` with deterministic reason codes.
- Validation supports both:
  - full attestation records (`rotation_date`, `previous_rotation_date`, `next_rotation_due`, `policy_days`, `attestation_hash`), and
  - legacy Cryovant metadata (`interval_seconds`, `last_rotation_ts`, `last_rotation_iso`) for migration compatibility.
- Full attestation hashing excludes ephemeral fields (`nonce`, `generated_at`, `host_info`, `attestation_hash`) before canonicalization so replay digests remain stable.
- `KEY_ROTATION_VERIFIED` can be emitted to metrics, lineage, and journal with a frozen payload to avoid post-construction mutation.
