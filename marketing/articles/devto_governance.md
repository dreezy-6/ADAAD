# How ADAAD's 16-rule constitutional gate stops autonomous AI from going wrong

*A technical deep-dive into fail-closed governance, deterministic replay, and cryptographic audit trails.*

---

Every AI coding tool I've used suffers from the same trust problem: I can see *what* it produced, but I can't verify *how* it decided to produce it, whether that decision was safe, or whether I'll get the same decision again if I re-run it. For most tasks, that's fine. For production code, it isn't.

ADAAD solves this with a constitutional governance engine. Here's exactly how it works.

## The governance hierarchy

ADAAD's authority chain is strict and immutable:

```
Constitution (14 hard rules)
    └─► Architecture Contract  
            └─► ArchitectAgent Spec v3.1.0
                    └─► PR Procession Plan
```

No agent, operator, or configuration flag can override a rule higher in this chain. The GovernanceGate evaluates rules top-down in deterministic order.

## What the 16 rules check

Rules span three enforcement tiers:

**Sandbox tier** (development):
- Resource bounds (cgroup v2 CPU/memory limits) — blocking
- Replay determinism verification — blocking
- Evidence ledger continuity (hash chain valid) — blocking

**Stable tier** (staging):
- All Sandbox rules
- Semantic diff within complexity budget
- Import surface delta ≤ threshold
- No orphaned dependencies introduced
- Test coverage delta ≥ 0

**Production tier**:
- All Stable rules
- HMAC signature on evidence bundle
- Federation divergence count = 0
- Human sign-off token present
- GovernanceGate is sole approval authority (architectural invariant test)

Any rule returning `BLOCK` triggers:
1. Full pipeline halt
2. Named failure mode written to evidence ledger
3. Hash-chained record of the halt
4. Replay audit log entry

## What a governance record looks like

```json
{
  "epoch_id": "epoch-2026-03-10-001",
  "candidate_id": "cand-a7f3b2",
  "gate_result": "BLOCKED",
  "blocking_rule": "STABLE_R04_complexity_budget",
  "rule_tier": "stable",
  "evaluated_at": 1741651200,
  "delta": {
    "ast_depth_delta": 4,
    "complexity_budget": 3,
    "exceeded_by": 1
  },
  "prev_hash": "sha256:a4c9f1...",
  "record_hash": "sha256:7e2d8b..."
}
```

Every record is SHA-256 hash-chained to the previous. You cannot insert, modify, or delete a record without breaking the chain — and the replay harness detects this immediately.

## Deterministic replay in practice

The replay harness re-executes any past epoch from stored inputs:

```python
from runtime.governance.replay import ReplayHarness

harness = ReplayHarness(epoch_id="epoch-2026-03-10-001")
result = harness.replay()

assert result.divergence_count == 0  # byte-identical
assert result.ledger_hash == original_hash  # chain intact
```

Divergence halts the process and produces a diff showing exactly which byte changed between the original run and the replay. This makes ADAAD's outputs legally auditable — you can prove to an external auditor, in a compliance review, or in a court proceeding, exactly what the AI changed and that the decision was made correctly.

## The moat

Constitutional governance is hard to replicate. It's not a feature you add — it's a constraint you build around from day one. ADAAD's entire architecture (agent selection, fitness scoring, population management, federation) is downstream of the governance invariant. You can't bolt this onto Copilot or Cursor without rebuilding their core.

That's the moat. The governance gate is permanent competitive differentiation.

---

**GitHub:** https://github.com/InnovativeAI-adaad/ADAAD  
**Author:** Dustin L. Reid · Founder, InnovativeAI LLC
