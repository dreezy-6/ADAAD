# Water (security)

Cryovant enforces environment validation, agent certification, and lineage ancestry checks. Ledger data is stored under `security/ledger/` and must be writable; keys live in `security/keys/` with owner-only permissions. Any failed validation blocks Dream/Beast execution.

Signature verification expects `sha256:<hex>` digests computed from `HMAC-SHA-256(key_bytes, b"cryovant")` and evaluates key files in `security/keys/` using deterministic filename ordering to support key rotation.
