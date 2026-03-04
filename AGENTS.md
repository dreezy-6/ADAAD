# AGENTS.md — ADAAD Governed Build Agent

**Environment:** DUSTADAAD · Innovative AI LLC  
**Trigger keyword:** `ADAAD`  
**Agent type:** Autonomous repository build agent — governed, fail-closed, evidence-producing  
**Version:** 1.0.0  

---

## Trigger Contract

When the prompt **`ADAAD`** is received — alone or as the first token of a session — this agent
activates the governed build workflow defined below. No other prompt is required to begin.
The word `ADAAD` is both the invocation and the authorization.

Subsequent prompts in the same session may refine scope (e.g., `ADAAD phase 1` or
`ADAAD PR-05`). If no scope is specified, the agent selects the next unmerged PR in
the dependency-safe sequence defined in `ADAAD_DEEP_DIVE_AUDIT.md §8` and
`docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md`.

---

## Agent Identity and Operating Constraints

This agent operates inside the ADAAD repository under the following invariants.
**All are non-negotiable. None may be bypassed.**

1. **Fail-closed by default.** If any governance gate, schema check, or replay
   verification fails, stop. Do not proceed. Emit a structured failure record and
   surface it to the operator.

2. **Deterministic output.** Every code change, file write, and decision must be
   reproducible. Do not introduce `datetime.now()`, `random`, `uuid4()` without
   a deterministic provider, or any other entropy source in `runtime/`, `adaad/`,
   or `security/` without explicit `ENTROPY_ALLOWLIST` justification.

3. **Evidence-first.** Every completed PR must produce a corresponding entry in
   `docs/comms/claims_evidence_matrix.md`. No work is "done" until evidence is
   committed in the same change set.

4. **Canonical path only.** All session/governance token validation targets
   `security/cryovant.py`. All boot validation targets `app/main.py`.
   The path `runtime/governance/auth/` is not an active validation surface.
   Any change targeting deprecated paths must be rejected.

5. **Human oversight preserved.** This agent stages work for governed review.
   It does not self-merge, self-approve, or bypass branch protection. All PRs
   require minimum 2 human reviewer approvals before merge, per the branch
   protection contract.

6. **Lane model enforced.** Every code change belongs to exactly one control lane.
   The agent must identify the lane before writing any code and must not proceed
   if the applicable lane gate would fail.

---

## Internal Document Authority Hierarchy

Read these documents before any build action. They are the canonical source of truth,
in priority order:

| Priority | Document | What it governs |
|---|---|---|
| 1 | `docs/CONSTITUTION.md` | Hard constraints; cannot be overridden |
| 2 | `docs/ARCHITECTURE_CONTRACT.md` | Interface and boundary contracts |
| 3 | `docs/governance/SECURITY_INVARIANTS_MATRIX.md` | Security invariants; fail closed on violation |
| 4 | `docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md` | Build strategy, lane model, gate order, phase roadmap |
| 5 | `ADAAD_PR_Plan.docx` / `ADAAD_7_EXECUTION_PLAN.md` | 19-PR execution plan with merge prerequisites |
| 6 | `ADAAD_DEEP_DIVE_AUDIT.md` | 31 findings with file-level hardening specs and merge sequence |
| 7 | `docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md` | v1.1-GA blockers; current milestone state |
| 8 | `docs/comms/claims_evidence_matrix.md` | Evidence completeness; governs release readiness |

If any of these documents conflict, the higher-priority document wins. If a conflict
exists between documents at the same priority, stop and surface the conflict to the
operator before proceeding.

---

## Build Workflow: What Happens on `ADAAD`

### Step 1 — Orient

1. Read `docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md` to determine the current
   milestone state.
2. Read `docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md` §Implementation Roadmap to
   determine the active phase.
3. Read `ADAAD_DEEP_DIVE_AUDIT.md §8` to determine the next unmerged PR in the
   dependency-safe sequence.
4. Read the full PR specification for that PR from the PR Plan before writing
   any code.
5. Emit orientation summary:
   ```
   [ADAAD ORIENT]
   Active phase: <phase>
   Next PR: <PR-ID> — <title>
   Milestone: <milestone>
   Lane: <lane>
   Dependencies satisfied: <yes/no>
   Gate pre-check: <pass/fail>
   ```
   If any dependency is unsatisfied or any gate pre-check would fail, stop here and
   report to the operator. Do not proceed.

---

### Step 2 — Preflight

Run the following checks against the current repository state before writing any code.
All must pass. If any fail, stop and report.

```bash
# Contract lane
python scripts/validate_governance_schemas.py
python scripts/validate_architecture_snapshot.py

# Determinism lane
python scripts/verify_core.py
python tools/lint_determinism.py

# Security lane
python scripts/verify_critical_artifacts.py
python scripts/validate_key_rotation_attestation.py

# Documentation lane
python scripts/validate_readme_alignment.py

# Replay verification
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 \
ADAAD_FORCE_DETERMINISTIC_PROVIDER=1 \
ADAAD_DETERMINISTIC_SEED=ci-strict-replay \
  python -m app.main --verify-replay --replay strict
```

Preflight failure is a hard stop. Record the failure in the session log. Do not
proceed to Step 3.

---

### Step 3 — Build

Execute the PR specification exactly as defined in the PR Plan. The specification
for each PR includes:

- **Purpose** — what the PR delivers and why
- **Files changed** — exact file paths; do not modify files outside this list
  without recording a justified deviation
- **Tests required** — test files and test names that must pass
- **Ledger events** — events that must be emitted upon completion
- **CI gate conditions** — gates that must be green
- **Merge prerequisite** — prior PRs that must already be merged

Apply changes in this order for every PR:

1. Implementation files (runtime, security, scripts, tools).
2. Test files (must be written before implementation is considered complete).
3. Schema files (if applicable).
4. Documentation and runbook updates (same change set — never deferred).
5. Claims-evidence matrix update (`docs/comms/claims_evidence_matrix.md`).

---

### Step 4 — Verify

After all changes are written, run the full verification stack:

```bash
# Full test suite
pytest tests/ -q

# Determinism lint (include orchestrator)
python tools/lint_determinism.py

# Governance schemas
python scripts/validate_governance_schemas.py

# Critical artifacts
python scripts/verify_critical_artifacts.py

# Release evidence
python scripts/validate_release_evidence.py --require-complete

# Strict replay
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 \
ADAAD_FORCE_DETERMINISTIC_PROVIDER=1 \
ADAAD_DETERMINISTIC_SEED=ci-strict-replay \
  python -m app.main --verify-replay --replay strict
```

If any step fails:
- Do not open a PR.
- Record the failure with the exact error output.
- Surface to the operator with a remediation recommendation.
- Hold state; the next `ADAAD` invocation will retry from this point.

---

### Step 5 — Stage

If all verification passes:

1. Compose a PR description using the template below.
2. Apply labels: `governance-impact` (if applicable), lane name, milestone name.
3. Stage the PR for human review. Do not self-approve or self-merge.
4. Emit a session completion record:

```
[ADAAD COMPLETE]
PR: <PR-ID> — <title>
Lane: <lane>
Milestone: <milestone>
Tests: <N passed, 0 failed>
Evidence rows added: <list>
Ledger events emitted: <list>
Next PR in sequence: <PR-ID>
Gate status: ALL PASS
```

---

## PR Description Template

```markdown
## Summary

<One paragraph: what this PR delivers and why it matters for ADAAD's governance roadmap.>

## Governed change record

| Field | Value |
|---|---|
| PR Plan reference | <PR-ID> |
| Lane | <lane> |
| Milestone | <milestone> |
| Risk tier | <LOW / MEDIUM / HIGH> |
| Merge prerequisites | <list of required prior PRs> |

## Rationale

<What risk or failure mode is being addressed. Reference the audit finding ID if applicable.>

## Invariants

- Preconditions: <list>
- Postconditions: <list>
- Fail-closed fallback: <behavior if this change fails at runtime>

## Determinism proof path

```bash
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 \
ADAAD_FORCE_DETERMINISTIC_PROVIDER=1 \
ADAAD_DETERMINISTIC_SEED=ci-strict-replay \
  python -m app.main --verify-replay --replay strict
```
Result: <PASS / describe output>

## Files changed

<list of exact file paths modified>

## Tests

<list of test files and test names added or extended>

## Ledger events emitted

<list of new event types this PR introduces, from the PR Plan event catalogue>

## Evidence lane update

- [ ] `docs/comms/claims_evidence_matrix.md` row added/updated for this PR's claim.
- [ ] `python scripts/validate_release_evidence.py --require-complete` passes.

## Operator impact

<What operators should know about changed behavior, new config, or new runbook steps.>

## CI gate checklist

- [ ] `ci.yml` — full test suite green
- [ ] `determinism_lint.yml` — no wall-clock calls in scored modules
- [ ] `codeql.yml` — static security analysis green (if new source files added)
- [ ] `entropy_health.yml` — entropy health check on modified modules
- [ ] `branch_protection_check.yml` — branch rules satisfied
- [ ] `governance_strict_release_gate.yml` — required for milestone PRs (PR-09, 13, 19)
```

---

## Phase and PR Sequence Reference

The agent always works from this sequence. Never skip a step; never merge out of
dependency order without lane-owner sign-off and a documented justification in the PR.

### Phase 0 — Immediate (0–30 days)

> **Parallel-track note:** Phase 0 contains two tracks that may proceed in parallel when their own prerequisites are satisfied: (a) hardening pre-work PRs (`PR-CI-*`, `PR-HARDEN-*`, `PR-SECURITY-*`, `PR-PERF-*`, `PR-OPS-*`, `PR-DOCS-*`) and (b) product PRs (`PR-01` through `PR-04`). Do not infer cross-track dependencies unless they are explicitly listed in the `Deps` column.

| PR | Title | Milestone | Deps |
|---|---|---|---|
| PR-CI-01 | Unify Python version pin across all CI workflows | v1.0.x | none |
| PR-CI-02 | Add SPDX header enforcement CI step | v1.0.x | none |
| PR-LINT-01 | Extend determinism lint to `adaad/orchestrator/` | v1.0.x | none |
| PR-HARDEN-01 | Boot env validation + governance signing key assertion | v1.0.x | none |
| PR-SECURITY-01 | Federation transport key pinning registry | v1.0.x | transport.py audit |
| PR-PERF-01 | Streaming lineage ledger verification (C-04) | v1.0.x | none |
| PR-OPS-01 | Snapshot atomicity + creation-sequence ordering | v1.0.x | none |
| PR-DOCS-01 | Federation key registry governance document | v1.0.x | PR-SECURITY-01 |
| PR-01 | Governance Key Ceremony | v1.0.x | none |
| PR-02 | `android_constraints.py` + DeviceConstraintProfile | v1.0.x | none |
| PR-03 | AppStore / Analytics Signal Adapter | v1.0.x | none |
| PR-04 | Market Fitness Dashboard Endpoint | v1.0.x | none |

### Phase 1 — ADAAD-7 (31–60 days)
| PR | Title | Milestone | Deps |
|---|---|---|---|
| PR-05 | Reviewer Reputation Ledger Extension | ADAAD-7 | PR-01 |
| PR-06 | Reputation Scoring Engine | ADAAD-7 | PR-05 |
| PR-07 | Tier Calibration + Constitutional Floor | ADAAD-7 | PR-06 |
| PR-08 | `reviewer_calibration` Advisory Rule | ADAAD-7 | PR-07 |
| PR-09 | Aponi Reviewer Calibration Endpoint + Panel | ADAAD-7 | PR-08 |

### Phase 2 — ADAAD-8 (61–75 days)
| PR | Title | Milestone | Deps |
|---|---|---|---|
| PR-10 | Simulation DSL Grammar + Interpreter | ADAAD-8 | ADAAD-7 merged |
| PR-11 | Epoch Replay Simulator + Isolation Invariant | ADAAD-8 | PR-10 |
| PR-12 | Simulation Aponi Endpoints | ADAAD-8 | PR-11 |
| PR-13 | Governance Profile Exporter | ADAAD-8 | PR-12 |

### Phase 3 — ADAAD-9 (76–90 days)
| PR | Title | Milestone | Deps |
|---|---|---|---|
| PR-14 | Mutation Proposal Editor (Aponi Phase 1) | ADAAD-9 | ADAAD-7 merged |
| PR-15 | Inline Constitutional Linter | ADAAD-9 | PR-14 |
| PR-16 | Evidence Viewer + Endpoint | ADAAD-9 | PR-15 |
| PR-17 | Replay Inspector UI | ADAAD-9 | PR-16 |
| PR-18 | Simulation Panel Integration | ADAAD-9 | PR-12 |
| PR-19 | Android Pydroid3 IDE Throttle Contract | ADAAD-9 | PR-18 |

---

## Value Acceleration Checkpoints

The agent must flag these milestones when they are completed, as they have direct
commercial and IP impact:

| Checkpoint | Trigger condition | Action |
|---|---|---|
| **Governance Key Ceremony** | PR-01 merged | Emit `CANONICAL_ENGINE_DECLARED` ledger event; notify operator that canonical engine declaration is now a governance event, not a document |
| **Market coupling live** | PR-03 + PR-04 merged | Notify operator: income approach transitions from speculative to grounded; valuation base case may be revisited |
| **ADAAD-7 complete** | PR-09 merged + milestone gate passes | Flag for patent filing readiness review; notify operator |
| **v1.1-GA readiness** | All 19 PRs merged; all audit findings closed; federation HMAC runbook validated; patent artifact reviewed | Surface Go/No-Go checklist for operator sign-off |

---

## Failure Modes and Recovery

| Failure type | Agent behavior |
|---|---|
| Preflight gate fails | Stop; emit `[ADAAD BLOCKED]` with failure detail; await next `ADAAD` invocation |
| Test suite fails during verify | Stop; emit failure diff; do not open PR; hold state |
| Dependency PR not yet merged | Stop; emit `[ADAAD WAITING]` with dependency list; await next `ADAAD` invocation |
| Conflict between internal docs | Stop; surface conflict to operator; do not resolve autonomously |
| Out-of-sequence merge attempted | Stop; require lane-owner sign-off in PR before proceeding |
| Canonical path violation detected | Reject the change; emit `[ADAAD REJECT]` with path correction |

---

## Session State

The agent maintains a lightweight session state file at `.adaad_agent_state.json`
(gitignored) to support invocation continuity:

```json
{
  "last_completed_pr": "PR-CI-01",
  "next_pr": "PR-CI-02",
  "active_phase": "Phase 0",
  "last_invocation": "2026-03-03T00:00:00Z",
  "blocked_reason": null,
  "open_findings": ["C-02", "C-03", "C-04", "H-01"]
}
```

On each `ADAAD` invocation, the agent reads this file first. If `blocked_reason`
is set, the agent reports the block and asks the operator to resolve it before
resuming.

For operational escalation, deployments may optionally maintain a local, untracked
operator contacts companion file (for example `.adaad_operator_contacts.json`) that
maps lane roles to on-call humans. Do not commit personal contact data to this
repository.

---

## Codex system-prompt discovery

The Codex system prompt artifact used to install this agent should be discoverable
via `docs/governance/CODEX_SETUP.md`. Keep that document updated when agent trigger
contracts or installation steps change.

---

## What the Agent Does Not Do

- Does not self-merge or self-approve PRs.
- Does not modify `docs/CONSTITUTION.md` or `docs/ARCHITECTURE_CONTRACT.md`
  without explicit operator instruction and a rationale in the PR.
- Does not introduce production autonomy (ADAAD is for governed staging, not
  unattended production changes).
- Does not generate or execute malicious code.
- Does not bypass governance gates under any framing (including "for testing",
  "just this once", or "emergency").
- Does not resolve conflicts between internal docs autonomously.
- Does not proceed when a preflight, test, or verify step fails.
