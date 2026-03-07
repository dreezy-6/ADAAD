# Legacy Behavior Constrainment and Deprecation Runbook

## Branch inventory and classification

| File | Legacy branch | Classification | Action |
| --- | --- | --- | --- |
| `security/cryovant.py` | `verify_session` development token path | required migration-only | Keep for migration, gate behind `ADAAD_ENABLE_LEGACY_VERIFY_SESSION`; default disabled in strict/governance contexts. |
| `security/cryovant.py` | `verify_governance_token` dev-token override (`CRYOVANT_DEV_TOKEN`) | required migration-only | Keep for migration, gate behind `ADAAD_ENABLE_LEGACY_DEV_TOKEN_OVERRIDE`; default disabled in strict/governance contexts. |
| `security/cryovant.py` | static signature acceptance (`cryovant-static-*`, `cryovant-dev-*`) | required migration-only | Keep for migration, gate behind `ADAAD_ENABLE_LEGACY_STATIC_SIGNATURES`; fail closed when disabled. |
| `runtime/preflight.py` | `_legacy_validate_mutation` path when `tier is None` | non-critical compatibility | Keep temporarily, gate behind `ADAAD_ENABLE_LEGACY_MUTATION_PREFLIGHT`; fail closed in strict/governance contexts. |
| `runtime/evolution/evidence_bundle.py` | `validate_bundle(..., allow_legacy=True)` coercion path | required migration-only | Keep temporarily, gate behind `ADAAD_ENABLE_LEGACY_EVIDENCE_BUNDLE`; strict/governance contexts ignore `allow_legacy`. |
| `runtime/api/legacy_modes.py` | legacy orchestration facade exports (`BeastModeLoop`, `DreamMode`) | non-critical compatibility | Keep temporarily, gate behind `ADAAD_ENABLE_LEGACY_ORCHESTRATION_MODES`; strict/governance contexts raise fail-closed import error. |

## Feature flags

- `ADAAD_ENABLE_LEGACY_VERIFY_SESSION`
- `ADAAD_ENABLE_LEGACY_DEV_TOKEN_OVERRIDE`
- `ADAAD_ENABLE_LEGACY_STATIC_SIGNATURES`
- `ADAAD_ENABLE_LEGACY_MUTATION_PREFLIGHT`
- `ADAAD_ENABLE_LEGACY_EVIDENCE_BUNDLE`
- `ADAAD_ENABLE_LEGACY_ORCHESTRATION_MODES`

Default behavior: if unset, flags are treated as **disabled** in governance-strict contexts (`ADAAD_ENV in {staging, production, prod}`, replay/recovery strict modes, or `ADAAD_GOVERNANCE_STRICT=1`).

## Deprecation timeline

1. **v3.1.0 (current hardening window):** all legacy behavior is opt-in only under explicit flags in strict/governance flows.
2. **v3.2.0:** emit CRITICAL telemetry whenever any `ADAAD_ENABLE_LEGACY_*` flag is used in any environment.
3. **v3.3.0:** remove `verify_session` and static legacy signature acceptance; remove legacy preflight/evidence coercion flag support.
4. **v3.4.0:** remove `runtime/api/legacy_modes.py` facade and public exports.

## Migration safety requirements

- All governance-critical flows must continue to fail closed when legacy flags are disabled.
- Legacy flags are temporary migration controls only and must never silently override strict mode constraints.
- Rollout must include explicit operator communication and release evidence references before each removal milestone.
