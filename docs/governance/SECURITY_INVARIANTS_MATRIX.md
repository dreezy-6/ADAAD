# SPDX-License-Identifier: Apache-2.0
# Security Invariants Matrix

**Last updated:** 2026-03-05 — Phase 0 Track A hardening complete (PR-HARDEN-01, C-02)

This matrix defines mandatory enforcement invariants for governance-critical execution.

---

## Mode / Tier Invariants

| Replay mode | Recovery tier | Deterministic provider | Network surface | Mutation execution |
| --- | --- | --- | --- | --- |
| `off` | `none` | Optional | Policy-configurable | Allowed when gates pass |
| `off` | `advisory` | Recommended | Policy-configurable | Allowed when gates pass |
| `off` | `conservative` | Recommended | Policy-configurable | Reduced mutation rate |
| `off` | `governance` | **Required** | Denied by recovery policy | Fail-closed if governance checks fail |
| `off` | `critical` | **Required** | Denied by recovery policy | Fail-closed / blocked |
| `strict` | any | **Required** | Denied by strict profile | Fail-closed on divergence |

Backward-compatibility alias: `audit` tier is accepted for deterministic-provider enforcement.

---

## Authentication / Signature Invariants

1. Governance bearer tokens must be cryptographically verifiable (`cryovant-gov-v1`).
2. `CRYOVANT_DEV_TOKEN` override accepted only in explicit dev mode (`ADAAD_ENV=dev` + `CRYOVANT_DEV_MODE`).
3. Payload-bound `cryovant-static-*` signatures accepted only in explicit dev mode.
4. Governance certifier decisions are binding on `import_ok`, `token_ok`, `ast_ok`, and `auth_ok`.
5. **[PR-HARDEN-01]** `ADAAD_ENV` must be a known value at boot; unknown values raise `RuntimeError` in `env_mode()` and `SystemExit` in the boot guard — no silent fallback.
6. **[PR-HARDEN-01]** `CRYOVANT_DEV_MODE` is rejected in `staging`, `production`, and `prod` environments at startup.
7. **[PR-HARDEN-01]** `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` must be present in strict environments; missing key raises `SystemExit` before any service initialization.

---

## Federation Trust Invariants

1. **[PR-SECURITY-01]** Federation message signatures are verified against `governance/federation_trusted_keys.json` — caller-supplied public keys are never accepted.
2. Any `key_id` not present in the trusted registry raises `FederationTransportContractError`.
3. Registry changes require a governance-impact PR with ≥2 reviewer approvals.
4. Registry is loaded at process start; boot fails closed if the registry is unreadable or empty.

See [FEDERATION_KEY_REGISTRY.md](FEDERATION_KEY_REGISTRY.md) for the key rotation runbook.

---

## Sandbox / Execution Invariants

1. **[C-02 / Phase 0]** Sandbox preflight rejects tokens containing shell control operators: `&&`, `||`, `;`, `|`, `` ` ``, `$(`, `${`, `>`, `<`, `<<`.
2. **[C-02]** IFS word-splitting bypass patterns (`$IFS`, `${IFS}`) are blocked at token-analysis time.
3. **[C-02]** Shell evaluation primitives (`eval `, `exec `, `source `) are blocked.
4. **[C-02]** Null-byte injection (`\x00`, `%00`) is blocked.
5. **[C-02]** Disallowed environment keys include: `LD_PRELOAD`, `PYTHONINSPECT`, `LD_LIBRARY_PATH`.
6. Individual command tokens exceeding 512 bytes are rejected as `oversized_command_token`.

---

## Audit Visibility Invariants

- `boot_env_validated` metric emitted on every clean startup.
- `cryovant_legacy_static_payload_signature_rejected` emitted on blocked legacy signatures.
- `cryovant_legacy_static_payload_signature_accepted` emitted on accepted dev-only static signatures.
- `cryovant_missing_signing_key_strict_env` emitted when signing key is absent in strict env.
- Certifier violations include explicit reason-codes for token and code-scan failures.

---

## SPDX / License Compliance Invariants

- All Python source files carry `# SPDX-License-Identifier: Apache-2.0` headers.
- Enforced by `scripts/check_spdx_headers.py`; run with `--fix` to auto-remediate.

---

## Related Documents

- [FEDERATION_KEY_REGISTRY.md](FEDERATION_KEY_REGISTRY.md) — key pinning lifecycle
- [DETERMINISM_CONTRACT_SPEC.md](DETERMINISM_CONTRACT_SPEC.md) — replay determinism guarantees
- [STRICT_REPLAY_INVARIANTS.md](STRICT_REPLAY_INVARIANTS.md) — strict replay enforcement
- [RED_TEAM_THREAT_MODEL_NEXT_PHASE.md](RED_TEAM_THREAT_MODEL_NEXT_PHASE.md) — threat surface
