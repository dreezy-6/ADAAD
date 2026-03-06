# ArchitectAgent Constitutional Specification — v2.0.0

![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)
![ArchitectAgent: Canonical](https://img.shields.io/badge/ArchitectAgent-Canonical-a855f7)
![Version: 2.0.0](https://img.shields.io/badge/version-2.0.0-00d4ff)

> **Authority:** ArchitectAgent · ADAAD Constitutional Governance  
> **Scope:** All subsystems active in v2.0.0  
> **Effective:** 2026-03-06  
> **Supersedes:** All prior architectural notes, informal specs, and inline comments  
> **Status:** CANONICAL — machine-interpretable, audit-ready, replay-verifiable

---

## Preamble

This document is the authoritative architectural and constitutional specification for ADAAD v2.0.0. It defines governance gates, mutation lifecycle rules, determinism invariants, subsystem blueprints, and the authority model. All agents — MutationAgent, IntegrationAgent, AnalysisAgent, EvolutionAgent, and any future agent — must comply with every rule enumerated here. No agent may override, defer, or selectively apply these constraints.

---

## 1. Constitutional Governance Model

### 1.1 Authority Invariant (Non-Negotiable)

```
INVARIANT: GovernanceGate is the ONLY surface that may approve, sign, or execute a mutation.

All other subsystems — AI mutation proposers, market adapters, budget arbitrators,
container profilers, federation brokers, evolution loop orchestrators — are ADVISORY.

Advisory → influences scores and resource allocation.
Advisory → NEVER approves a mutation.

Violation of this invariant is a constitutional fault. Pipeline halts immediately.
```

### 1.2 The Three-Tier Execution Model

| Tier | Scope | Mutation Policy | Review |
|------|-------|-----------------|--------|
| **Tier 0: Production** | `runtime/`, `security/`, `app/main.py`, orchestrator core | Never auto-executed | Human review required before merge |
| **Tier 1: Stable** | `tests/`, `docs/`, most agents | Auto-execute; human reviews logs ≤24h | Automatic rollback on test failure |
| **Tier 2: Sandbox** | `app/agents/test_subject/` | Fully autonomous | Must not affect Tier 0/1 |

**Blast-radius enforcement:** Tier 2 mutations are constitutionally prohibited from modifying any path outside their designated sandbox. Enforcement: `tools/lint_import_paths.py` + `tests/test_sandbox_injection_hardening.py`.

### 1.3 The Fourteen Constitutional Rules

All fourteen rules are evaluated sequentially per mutation. Evaluation is deterministic and order-stable.

| # | Rule ID | Severity | Gate Behavior |
|---|---------|----------|---------------|
| 1 | `single_file_scope` | BLOCKING | Halt on violation |
| 2 | `ast_validity` | BLOCKING | Halt on violation |
| 3 | `import_smoke_test` | WARNING | Log; do not halt |
| 4 | `no_banned_tokens` | BLOCKING | Halt on violation |
| 5 | `signature_required` | BLOCKING | Halt on violation |
| 6 | `max_complexity_delta` | WARNING | Log; do not halt |
| 7 | `test_coverage_maintained` | WARNING | Log; do not halt |
| 8 | `max_mutation_rate` | SANDBOX: ADVISORY · PRODUCTION: BLOCKING | Context-sensitive |
| 9 | `lineage_continuity` | BLOCKING | Halt on violation |
| 10 | `resource_bounds` | BLOCKING | Halt on violation |
| 11 | `entropy_budget_limit` | WARNING · PRODUCTION: BLOCKING | Context-sensitive |
| 12 | `deployment_authority_tier` | ADVISORY | Audit trail only |
| 13 | `revenue_credit_floor` | ADVISORY | Audit trail only |
| 14 | `reviewer_calibration` | ADVISORY | Audit trail only |

**Fail-closed rule:** Any gate producing an unrecognized result (not PASS/FAIL/WARN/ADVISORY) is treated as FAIL. The pipeline halts.

---

## 2. Mutation Lifecycle — v2.0.0 (AI-Driven)

```
EPOCH START
    │
    ▼
[1] STRATEGY SELECTION (FitnessLandscape)
    Purpose: Select optimal agent persona based on win/loss history and plateau detection.
    Inputs:  fitness_landscape_state.json, plateau_threshold=0.20, min_attempts=3
    Pass:    Agent persona selected (ARCHITECT | DREAM | BEAST) with rationale.
    Fail:    Default to ARCHITECT. Log reason. Never block on strategy failure.
    │
    ▼
[2] AI MUTATION PROPOSAL (AIMutationProposer × 3 agents)
    Purpose: Generate ranked mutation candidates via Claude API (claude-sonnet-4-20250514).
    Inputs:  CodebaseContext (file_summaries, recent_failures, epoch_id, context_hash)
    Checks:
      - API response parsed successfully (markdown fence stripping applied)
      - Returned JSON conforms to MutationCandidate schema
      - context_hash bound to proposal (lineage anchor)
      - agent_origin present in {architect, dream, beast}
    Pass:    ≥1 valid MutationCandidate returned per agent.
    Fail:    Empty population captured. Log. Do not halt epoch. Proceed to [3] with empty population.
    Failure Modes:
      - API_TIMEOUT: log, return [], continue
      - MALFORMED_JSON: log, return [], continue
      - INVALID_AGENT_ORIGIN: reject candidate; log; do not halt
    │
    ▼
[3] POPULATION SEEDING (PopulationManager)
    Purpose: Initialize GA population from AI proposals + prior epoch elite roster.
    Inputs:  proposals from [2], elite_roster from prior EpochResult, MAX_POPULATION=12
    Checks:
      - MD5 fingerprint deduplication (4 fields, 3 d.p.)
      - Elite count ≤ ELITE_SIZE=3
    Pass:    Population List[MutationCandidate] with ≥1 member.
    Fail:    Population empty → epoch completes with accepted_count=0. Not an error.
    │
    ▼
[4] GENETIC EVOLUTION (PopulationManager.evolve)
    Purpose: BLX-alpha crossover + diversity enforcement + elite preservation.
    Inputs:  population, generation_count, diversity_pressure
    Checks:
      - BLX-alpha=0.5: result ∈ [lo−extent, hi+extent] where extent=(hi−lo)×0.5
      - CROSSOVER_RATE=0.4 applied per generation
      - Deduplication after each crossover
      - PopulationState.generation incremented per evolve() call
    Pass:    Evolved population ≤ MAX_POPULATION=12, all entries unique.
    Fail:    Crossover failure → retain pre-crossover population. Log.
    │
    ▼
[5] CONSTITUTIONAL GATE (GovernanceGate) ← SINGLE AUTHORITY POINT
    Purpose: Evaluate each candidate against all 14 constitutional rules.
    Inputs:  MutationCandidate, MutationScore, tier classification, ScoringWeights
    Checks:
      - All BLOCKING rules must PASS
      - Adaptive acceptance threshold: adjusted_threshold = base × (1 − diversity_pressure × 0.4)
      - Elitism bonus: +0.05 for children of elite_roster parents (after threshold adjustment)
      - Epoch_id, parent_id, agent_origin, elitism_applied recorded in MutationScore
    Pass:    candidate.score ≥ adjusted_threshold AND all BLOCKING rules PASS
    Fail:    Any BLOCKING rule fails → candidate REJECTED. Not a pipeline halt.
             If ALL candidates rejected → epoch completes with accepted_count=0.
    Dependencies: GovernanceGate (runtime/governance/), MutationScore, ScoringWeights
    │
    ▼
[6] WEIGHT ADAPTATION (WeightAdaptor)
    Purpose: Momentum-based coordinate descent on scoring weights.
    Inputs:  EpochResult, prior weight_adaptor_state.json
    Checks:
      - LR=0.05, momentum=0.85 applied to gain_weight and coverage_weight only
      - MIN_WEIGHT=0.05 ≤ all weights ≤ MAX_WEIGHT=0.70 (clamp enforced)
      - EMA prediction accuracy: alpha=0.3 rolling update
      - risk_penalty and complexity_penalty: STATIC in Phase 1
      - Persisted to data/weight_adaptor_state.json after every adapt() call
    Pass:    State persisted. No weight zeroed or out of bounds.
    Fail:    Persist failure → log, use in-memory weights. Do not halt.
    │
    ▼
[7] LANDSCAPE RECORDING (FitnessLandscape)
    Purpose: Update per-type win/loss ledger for future strategy selection.
    Inputs:  accepted mutations, rejected mutations, mutation_type fields
    Checks:
      - TypeRecord updated: wins, losses, win_rate computed
      - Plateau detection: all types with ≥3 attempts below 20% → switch to DREAM
      - Persisted to data/fitness_landscape_state.json
    Pass:    State persisted. recommended_next_agent updated.
    Fail:    Persist failure → log. Do not halt.
    │
    ▼
[8] EVIDENCE ATTACHMENT
    Purpose: Attach EpochResult to ledger. Finalize lineage chain.
    Inputs:  EpochResult (epoch_id, generation_count, total_candidates, accepted_count,
             top_mutation_ids, weight_accuracy, recommended_next_agent, duration_seconds)
    Checks:
      - All accepted mutations have signed lineage entries
      - Replay proof bundle generated for accepted mutations
      - Evidence row committed to docs/comms/claims_evidence_matrix.md
    Pass:    Ledger updated. Replay bundle written.
    Fail:    Evidence attach failure → EPOCH INVALID. Do not promote. Halt pipeline.
    │
    ▼
EPOCH COMPLETE
```

---

## 3. Invariants Matrix

### 3.1 Determinism Invariants

| ID | Invariant | Enforcement | Failure Response |
|----|-----------|-------------|------------------|
| DET-01 | All mutation scoring is deterministic given fixed ScoringWeights and seed | `core/random_control.py` | Halt; emit replay divergence |
| DET-02 | BLX-alpha crossover produces identical outputs for identical parent inputs | Unit: `test_population_manager.py` | Reject crossover result; log |
| DET-03 | Gate evaluation order is fixed (rule 1–14 always evaluated in sequence) | GovernanceGate implementation | Audit log mandatory |
| DET-04 | Weight adaptation produces identical outputs for identical EpochResult inputs | Unit: `test_weight_adaptor.py` | Log; use prior state |
| DET-05 | context_hash (MD5 of CodebaseContext) is stable across identical inputs | Unit: `test_ai_mutation_proposer.py` | Reject proposal; re-hash required |
| DET-06 | replay_proof bundle is verifiable offline via `tools/verify_replay_bundle.py` | CI + `test_replay_proof.py` | EPOCH INVALID |

### 3.2 Security Invariants

| ID | Invariant | Enforcement | Failure Response |
|----|-----------|-------------|------------------|
| SEC-01 | `eval`, `exec`, `__import__`, `subprocess.call` with shell=True are banned tokens | `no_banned_tokens` rule | BLOCKING halt |
| SEC-02 | All mutations carry HMAC signature before GovernanceGate evaluation | `signature_required` rule | BLOCKING halt |
| SEC-03 | CRYOVANT_DEV_MODE=1 rejected in PRODUCTION and STAGING environments | `cryovant.py` boot check | Immediate process exit |
| SEC-04 | API key (`ADAAD_CLAUDE_API_KEY`) never logged or included in lineage artifacts | AIMutationProposer implementation | Audit: grep for key in artifacts |
| SEC-05 | GovernanceGate is the only mutation approval surface (see §1.1) | Architecture contract | Constitutional fault |
| SEC-06 | Federation gossip events accepted only from trusted key roster | `governance/federation_trusted_keys.json` | Event discarded; alert |

### 3.3 Replay Invariants

| ID | Invariant | Enforcement | Failure Response |
|----|-----------|-------------|------------------|
| REP-01 | Every epoch_id is globally unique (UUID4 or epoch-{timestamp}-{hash}) | EvolutionLoop | Collision → halt |
| REP-02 | simulate_outcomes=True mode never writes to production evidence ledger | EvolutionLoop flag check | Fail-closed |
| REP-03 | Replay divergence detected by comparing input hash + output hash pairs | `tools/verify_replay_bundle.py` | Epoch invalidated |
| REP-04 | Weight state (weight_adaptor_state.json) is included in replay snapshot | Snapshot atomicity | Replay incomplete |

---

## 4. Subsystem Blueprints

### 4.1 AIMutationProposer

**Purpose:** Bridge Claude API to the mutation pipeline. Three agent personas produce diverse proposals each epoch.

| Field | Value |
|-------|-------|
| Model | `claude-sonnet-4-20250514` |
| HTTP | Pure `urllib.request` (zero third-party deps) |
| Personas | `architect` (structural, low-medium risk) · `dream` (experimental, high-gain) · `beast` (conservative, coverage/performance) |
| Entry point | `propose_from_all_agents(context: CodebaseContext) → List[MutationCandidate]` |
| Context binding | `context_hash = MD5(sorted file_summaries + failures + epoch_id)` |
| Robustness | Markdown fence stripping; malformed JSON → empty list; timeout → empty list |

**Notes for MutationAgent:** You receive proposals from this subsystem. Do not invoke it directly; use `EvolutionLoop.run_epoch()`. Never pass raw API key to any logging surface.

### 4.2 EvolutionLoop

**Purpose:** Five-phase epoch orchestrator. Single entry point for the full evolution cycle.

| Field | Value |
|-------|-------|
| Phases | Strategy → Propose → Seed → Evolve → Adapt → Record |
| Result type | `EpochResult` (8 fields: see §2 step [8]) |
| Test mode | `simulate_outcomes=True` derives synthetic outcomes; no CI required |
| Graceful degradation | All phase failures captured; epoch completes with empty results |

**Notes for IntegrationAgent:** `EvolutionLoop` is the only sanctioned orchestration entry point. Do not wire phase components individually outside test harnesses.

### 4.3 WeightAdaptor

**Purpose:** Self-calibrating scoring weight management via momentum gradient descent.

| Field | Value |
|-------|-------|
| Adapting weights | `gain_weight`, `coverage_weight` (Phase 1 only) |
| Static weights | `risk_penalty`, `complexity_penalty` (Phase 2 — post-merge telemetry required) |
| Learning rate | 0.05 |
| Momentum | 0.85 |
| EMA alpha | 0.3 |
| Bounds | MIN=0.05, MAX=0.70 (hard clamp) |
| Persistence | `data/weight_adaptor_state.json` |

**Notes for AnalysisAgent:** Phase 2 weight adaptation (`risk_penalty`, `complexity_penalty`) requires post-merge telemetry evidence before it may be enabled. Do not activate in Phase 1.

### 4.4 FitnessLandscape

**Purpose:** Long-memory win/loss ledger enabling strategy selection across epochs.

| Field | Value |
|-------|-------|
| Ledger | Per-mutation-type `TypeRecord` (wins, losses, win_rate) |
| Plateau threshold | ≥3 attempts below 20% win rate across all tracked types → recommend DREAM |
| Agent mapping | plateau→dream · structural wins→architect · perf/coverage wins→beast |
| Persistence | `data/fitness_landscape_state.json` |
| Phase 2 | UCB1 / Thompson Sampling bandit selector (requires ≥30 recorded epochs) |

### 4.5 PopulationManager

**Purpose:** Genetic algorithm population lifecycle management.

| Field | Value |
|-------|-------|
| Max population | 12 |
| Elite size | 3 |
| Crossover rate | 0.4 |
| BLX-alpha | 0.5 |
| Deduplication | MD5 fingerprint (4 fields, 3 d.p.) |
| Lineage | Crossover children inherit `parent_id=parent_a.mutation_id` |

### 4.6 GovernanceGate (Constitution Enforcement)

**Purpose:** The single authority for mutation approval. Evaluates all 14 rules.

**Notes for all agents:** This subsystem is **read-only** from the perspective of all other agents. Its verdict is final. No agent may retry, override, or bypass a BLOCKING failure. Any such attempt is a constitutional fault.

### 4.7 Evidence Ledger

**Purpose:** Append-only record of all governed decisions.

| Field | Value |
|-------|-------|
| Entries | Immutable after write |
| Integrity | SHA-256 hash chaining |
| Replay bundles | `security/ledger/replay_proofs/*.json` |
| Verification | `tools/verify_replay_bundle.py` (offline-compatible) |
| Attestation | Every promoted mutation requires a signed attestation entry |

### 4.8 Aponi Dashboard

**Purpose:** Human-readable governance observability surface. Read-only view of all governed state.

**Boundary:** Aponi may read from the evidence ledger, governance state, and epoch results. It must never write to any governance-controlled surface, approve mutations, or invoke GovernanceGate directly.

---

## 5. Layer Dependency Model

```
ui/app.main
    ↓ (downward only)
app/mutation_executor
    ↓
adaad/orchestrator
    ↓
runtime/evolution/evolution_loop   runtime/autonomy/ai_mutation_proposer
    ↓                                   ↓
runtime/governance/GovernanceGate ← (gate only; never called by proposer)
    ↓
governance/  (adapter layer — no implementation logic)
```

**Forbidden edges (CI-enforced via `tools/lint_import_paths.py`):**

| Scope | Forbidden |
|-------|-----------|
| `adaad/orchestrator/` | `app`, `ui` |
| `app/mutation_executor.py` | `app.main`, `ui` |
| `runtime/__init__.py` | `app`, `adaad.orchestrator`, `ui` |
| `AIMutationProposer` | `GovernanceGate` (proposer never approves) |
| `WeightAdaptor` | `GovernanceGate` (adaptor never approves) |
| `FitnessLandscape` | `GovernanceGate` (landscape never approves) |

---

## 6. Governance Gate Specifications

### Gate: Version Promotion Gate

| Field | Value |
|-------|-------|
| Purpose | Ensure VERSION, CHANGELOG, agent state, and evidence matrix are consistent before main merge |
| Inputs | `VERSION`, `CHANGELOG.md`, `.adaad_agent_state.json`, `docs/comms/claims_evidence_matrix.md` |
| Checks | VERSION matches CHANGELOG entry · agent state schema_version matches · evidence matrix has entry for milestone · no [Unreleased] content present |
| Pass | All four checks green |
| Fail | Any mismatch → reject merge · emit structured diff |
| Dependencies | Lead Dev pre-merge checklist |

### Gate: Determinism Lint Gate

| Field | Value |
|-------|-------|
| Purpose | Enforce no entropy sources in governed paths |
| Inputs | All `.py` files under `runtime/`, `adaad/`, `security/` |
| Checks | `tools/lint_determinism.py --strict` passes with zero violations |
| Pass | Zero violations |
| Fail | Any violation → CI fails · PR blocked |
| Dependencies | CI workflow `.github/workflows/ci.yml` |

### Gate: Import Boundary Gate

| Field | Value |
|-------|-------|
| Purpose | Enforce layer dependency model |
| Inputs | All `.py` files |
| Checks | `tools/lint_import_paths.py --format=json` → zero boundary violations |
| Pass | Zero violations |
| Fail | Any violation → CI fails · PR blocked |
| Dependencies | CI workflow |

### Gate: Replay Proof Gate

| Field | Value |
|-------|-------|
| Purpose | Verify replay bundle integrity for all accepted mutations in release |
| Inputs | `security/ledger/replay_proofs/*.json` |
| Checks | `tools/verify_replay_bundle.py` exits 0 · no divergence records |
| Pass | Exit 0 · zero divergences |
| Fail | Any divergence → RELEASE BLOCKED |
| Dependencies | Pre-release checklist |

---

## 7. Notes for Downstream Agents

### For MutationAgent
- All proposals must be produced via `EvolutionLoop.run_epoch()` or `AIMutationProposer.propose_from_all_agents()`.
- Never invoke `GovernanceGate` directly — it is invoked by the execution engine, not by proposers.
- All `MutationCandidate` objects must carry `parent_id`, `generation`, `agent_origin`, `epoch_id`, `source_context_hash` fields.
- Adaptive threshold is computed automatically — do not hardcode acceptance thresholds.

### For IntegrationAgent
- The canonical entrypoint is `app/main.py` (`python -m app.main`).
- Wire `EvolutionLoop` as a complete unit — do not wire individual phases.
- All new subsystems must register in `governance/DEPRECATION_REGISTRY.md` if they replace prior components.
- Do not merge any PR with `[Unreleased]` content in CHANGELOG.

### For AnalysisAgent
- Weight state (`data/weight_adaptor_state.json`) must be included in all replay snapshots.
- Phase 2 weight activation (`risk_penalty`, `complexity_penalty` adaptation) requires a separate ArchitectAgent approval gate — do not activate unilaterally.
- Fitness landscape state (`data/fitness_landscape_state.json`) is a governance artifact — treat as append-preferential, not overwrite.
- UCB1/Thompson Sampling bandit requires ≥30 recorded epochs before activation.

### For All Agents
- **Fail closed.** Any ambiguity in gate outcome = FAIL.
- **No silent failures.** Every failure must emit a structured, machine-readable record.
- **Evidence first.** No PR is complete until its evidence row is committed.
- **Determinism always.** If it cannot be replayed exactly, it cannot be approved.

---

## 8. Constitutional Change Control

Any modification to this document requires:

1. ArchitectAgent approval (structured spec diff produced)
2. Human operator sign-off (minimum 1 approval)
3. Version bump to this document's header
4. Entry in `CHANGELOG.md` under the appropriate release
5. No retroactive changes to prior epoch evidence

---

*ArchitectAgent · ADAAD v2.0.0 · Issued 2026-03-06 · Canonical*
