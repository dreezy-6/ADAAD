# ADAAD — Next Plan (2026-03-05)

Authority hierarchy: `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > SECURITY_INVARIANTS_MATRIX.md > ADAAD_PR_PLAN_OPTIMIZED.md`  
Baseline SHA: `0df3d3f7a3befe91faf6b327505a8f3e9ae31d49`

## Refresh Assessment

Confirmed complete in source:
- PR-HARDEN-01 / C-01 (`app/main.py`, `security/cryovant.py` + tests)
- C-02 sandbox injection hardening (`runtime/sandbox/preflight.py` + tests)
- PR-SECURITY-01 / C-03 (federation key registry + tests)
- PR-PERF-01 / C-04 (lineage streaming verify path)
- PR-OPS-01 / M-02 (snapshot atomicity/ordering)
- PR-DOCS-01 (`docs/governance/FEDERATION_KEY_REGISTRY.md`)
- PR-LINT-01 (`tools/lint_determinism.py`, workflow wiring)
- H-01 workflow Python pin (`3.11.9`)
- GA-1.1 through GA-1.6 implementation evidence present

## Open Gaps (ordered)

1. **PR-CI-01 formal closure**: implementation exists but tracker/state/release formalization incomplete.
2. **PR-CI-02 SPDX enforcement wiring**: SPDX checker exists; CI baseline enforcement and governance docs/evidence alignment still needed.
3. **GA closure tracker status debt**: tracker controls still `⬜` despite implementation being complete.

## Execution Sequence

`PR-CI-01` → `PR-CI-02` → `v1.1-GA` tag gate → ADAAD-7 PR-7-01..PR-7-05.

## PR-CI-01 Scope (this update)

- Update `docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md` with `✅` for GA-1.1..GA-1.6 and GA-KR.1, including in-repo evidence links.
- Add this plan file to repository governance docs for auditable sequencing reference.
- Add release-note addendum for formal H-01 closure and tracker sign-off progression.

## PR-CI-02 Scope (next)

- Add always-on SPDX header check step to `.github/workflows/ci.yml`.
- Update `docs/GOVERNANCE_ENFORCEMENT.md` required checks table.
- Update `docs/comms/claims_evidence_matrix.md` `spdx-header-compliance` row to include CI enforcement link.

## v1.1-GA Tag Gate

Required before tag:
1. GA tracker complete/signed for GA-1.x and GA-KR.1.
2. SPDX CI enforcement wired and passing.
3. Governance/Security/Runtime sign-offs complete.
4. Governance strict release gate green on tag SHA.
