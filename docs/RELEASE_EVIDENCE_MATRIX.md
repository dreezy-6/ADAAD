# Release Evidence Matrix

| Feature | Test | Artifact |
|---|---|---|
| Lineage continuity enforcement | `tests/test_lineage_continuity.py` | `security/ledger/lineage_v2.jsonl` |
| Resource bounds enforcement | `tests/test_resource_bounds.py` | Structured `resource_bounds_exceeded` + `resource_measurements_missing` constitutional events |
| Replay proof bundle | `tests/test_replay_proof.py` | `security/ledger/replay_proofs/*.json` |
| Replay tamper detection | `tests/test_replay_proof_tamper.py` | Offline verification output from `tools/verify_replay_bundle.py` |
| Sandbox hardening | `tests/sandbox/test_syscall_filter.py`, `tests/sandbox/test_fs_rules.py` | Sandbox evidence bundle snapshot/signature |
| Governance CI and branch protection | governance CI jobs, secret scan, and branch protection workflow | `.github/workflows/ci.yml`, `.github/workflows/secret_scan.yml`, `.github/workflows/branch_protection_check.yml` |
| PR-2 core constitutional rules enabled (lineage/resource/complexity/coverage/mutation rate) | `pytest tests/ -k "lineage or resource_bounds or complexity or mutation_rate" -q` | Constitutional policy v0.2.0 + validator/test evidence |

## Gate execution profile

- Release gate trigger: governance/public-readiness tag pushes via `.github/workflows/governance_strict_release_gate.yml`.
- Runtime verification: `tools/verify_replay_bundle.py` against `security/ledger/replay_proofs/*.json`.
- Test validation: governance and sandbox suites executed with `PYTHONPATH=.` to match CI import behavior.
## Sandbox control-state semantics

- Telemetry syscall validation is implemented and fail-closed in executor evidence checks.
- In-kernel seccomp filtering is currently guaranteed only for container backend paths with configured Docker seccomp profiles.
- Namespace/cgroup hard isolation is currently reported as enabled only for container backend paths; process backend remains best-effort.
- Evidence bundles expose per-control capability flags (`enforced_in_kernel`, `best_effort`, `simulated_or_observed_only`) to prevent claim drift.
