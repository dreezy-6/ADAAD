# ADAAD PR Procession Plan — 2026-03

> [!IMPORTANT]
> **Canonical source (automation sequence control):** This document is the controlling source for **active Phase 6 PR order**, dependency graph, CI tier, and status used by ADAAD automation.

**Authority chain:** `docs/CONSTITUTION.md` > `docs/ARCHITECTURE_CONTRACT.md` > `docs/governance/ARCHITECT_SPEC_v3.1.0.md` > this document  
**Last reviewed:** 2026-03-08  
**Active milestone:** `v3.1.0` (Phase 6 close)

---

## 1) Canonical Active Sequence (Phase 6)

### 1.1 Sequence order (authoritative)

```text
PR-PHASE6-01  →  PR-PHASE6-02  →  PR-PHASE6-03  →  PR-PHASE6-04  →  v3.1.0 tag
```

### 1.2 Active PR status + dependency table

| PR ID | Title | Milestone | CI tier | Depends on | Status |
|---|---|---|---|---|---|
| `PR-PHASE6-01` | Phase 6 governance foundations | `v3.1.0` | `critical` | Phase 5 complete (`v3.0.0`) | `merged` |
| `PR-PHASE6-02` | M6-03: Wire RoadmapAmendmentEngine into EvolutionLoop | `v3.1.0` | `critical` | `PR-PHASE6-01` merged | `merged` |
| `PR-PHASE6-03` | M6-04: Federated roadmap propagation | `v3.1.0` | `critical` | `PR-PHASE6-02` merged | `merged` |
| `PR-PHASE6-04` | M6-05: Free Android distribution pipeline close | `v3.1.0` | `standard` | `android-free-release.yml` passing | `active` |

### 1.3 Dependency graph (fail-closed interpretation)

- `PR-PHASE6-04` is the only active unmerged PR in this sequence.
- No PR may be advanced out-of-order.
- `v3.1.0` tag is blocked until `PR-PHASE6-04` is merged and required release gates pass.

---

## 2) Automation Contract Block (Machine-checkable)

The block below is intended for deterministic preflight checks against `.adaad_agent_state.json`.

```yaml
adaad_pr_procession_contract:
  schema_version: "1.0"
  source_of_truth: "docs/governance/ADAAD_PR_PROCESSION_2026-03.md"
  active_phase: "phase6"
  milestone: "v3.1.0"
  ordered_pr_ids:
    - PR-PHASE6-01
    - PR-PHASE6-02
    - PR-PHASE6-03
    - PR-PHASE6-04
  pr_nodes:
    PR-PHASE6-01:
      ci_tier: critical
      depends_on: ["v3.0.0"]
      status: merged
    PR-PHASE6-02:
      ci_tier: critical
      depends_on: ["PR-PHASE6-01"]
      status: merged
    PR-PHASE6-03:
      ci_tier: critical
      depends_on: ["PR-PHASE6-02"]
      status: merged
    PR-PHASE6-04:
      ci_tier: standard
      depends_on: ["android-free-release.yml:pass"]
      status: active
  state_alignment:
    expected_next_pr: PR-PHASE6-04
    expected_last_completed_pr: PR-PHASE6-03
    blocked_reason_must_be_null: true
```

### 2.1 Preflight alignment rules (recommended validator behavior)

A validator comparing this document to `.adaad_agent_state.json` should fail if:
1. `next_pr` is not `PR-PHASE6-04`.
2. `last_completed_pr` is not `PR-PHASE6-03`.
3. Any `pr_nodes.*.status` diverges from this contract.
4. `ordered_pr_ids` is not strict topological order.

---

## 3) Phase 6 Governance and CI Tier Notes

- CI tier assignments align to `docs/governance/ci-gating.md` and `docs/governance/ARCHITECT_SPEC_v3.1.0.md`:
  - `critical`: `PR-PHASE6-02`, `PR-PHASE6-03`
  - `standard`: `PR-PHASE6-04`
- Phase 6 invariants remain mandatory for all applicable PRs:
  - `INVARIANT PHASE6-AUTH-0`
  - `INVARIANT PHASE6-STORM-0`
  - `INVARIANT PHASE6-HUMAN-0`
  - `INVARIANT PHASE6-FED-0`
  - `INVARIANT PHASE6-APK-0`

---

## 4) Superseded Content Archive (Non-Canonical)

The following historical planning blocks are intentionally archived and **must not** be used for active automation routing:

- Legacy Phase 4 execution planning
- Legacy Phase 5 split/merge planning variants
- Earlier additive Phase 6 addendum formatting that allowed dual interpretation

Historical details remain available via git history; this file now contains only the active canonical sequence and machine-checkable contract.

---

## Changelog

- **2026-03-08:** Canonicalized this document to Phase 6 active sequence only; archived superseded Phase 4/5 planning sections; added machine-checkable procession contract for `.adaad_agent_state.json` preflight alignment.
