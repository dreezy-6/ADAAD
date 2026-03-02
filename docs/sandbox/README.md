# Hardened Sandbox Isolation

This module defines deterministic sandbox governance for mutation test execution.

## Enforcement layers
- **Telemetry-based syscall validation (implemented)**: `runtime.sandbox.syscall_filter` validates observed traces against policy allowlists after execution.
- **Kernel seccomp filter enforcement (partially implemented)**: container mode applies Docker seccomp profiles in-kernel; process mode currently records seccomp policy identity and validates traces, but does not yet install a kernel BPF seccomp filter.
- **Namespace/cgroup hard isolation status**: container mode reports namespace + cgroup constrained execution paths; process mode is best-effort and reports no hard namespace/cgroup isolation.
- **Filesystem write-path allowlist**: `runtime.sandbox.fs_rules`
- **Network egress allowlist**: `runtime.sandbox.network_rules`
- **Resource quotas**: `runtime.sandbox.resources`
- **Isolation backend preparation**: `runtime.sandbox.isolation` (process/container mode abstraction with explicit seccomp/capability/resource profile identifiers)
- **Deterministic preflight rejection**: `runtime.sandbox.preflight` (rejects disallowed command/env/mount operations before execution)

## Determinism and replay
- `HardenedSandboxExecutor` builds deterministic manifests from mutation identity + replay seed, runs deterministic preflight analysis, and applies fail-closed pre-exec isolation preparation before tests execute.
- `TestSandbox` supplies inferred deterministic baseline telemetry (`open/read/write/close`, `reports`) when direct tracing is unavailable; missing syscall telemetry is treated fail-closed by the hardened executor.
- Evidence fields are canonically hashed (`manifest_hash`, `stdout_hash`, `stderr_hash`, `syscall_trace_hash`, `resource_usage_hash`, `evidence_hash`) and include `isolation_mode`, `enforced_controls`, `preflight`, and `runtime_telemetry` metadata so audits can distinguish in-kernel enforcement from best-effort or observed-only controls.
- Evidence is appended to an append-only JSONL ledger (`security/ledger/sandbox_evidence.jsonl`).
- Replay helper `runtime.sandbox.replay.replay_sandbox_execution` verifies this canonical contract from persisted fields (`manifest`, `stdout`, `stderr`, `syscall_trace`, `resource_usage`).

## Integration
- `MutationExecutor` routes test execution through `HardenedSandboxExecutor`.
- `SandboxEvidenceEvent` is appended to lineage and aggregated by checkpoint registry.

## Capability signaling in evidence payloads
- Every `enforced_controls[]` record now includes `capability_flags` with: `enforced_in_kernel`, `best_effort`, `simulated_or_observed_only`, and normalized `mode`.
- `runtime_telemetry` includes explicit control-state indicators for syscall validation and hard isolation status (`hard_isolation`, `hard_isolation_namespaces`, `hard_isolation_cgroups`).
- Release claims must align with these runtime capability signals; CI blocks release claims that assert hardened modes not actually reported as enabled.
