# EPIC 1 — Reviewer Reputation and Calibration Loop (ADAAD-7)

## Scope
This epic introduces reviewer reputation as a calibration mechanism for **reviewer count per tier only**. Reputation does **not** modify reviewer authority, voting rights, or constitutional floor requirements.

## Architectural Invariant
- Reputation can increase or decrease the **number of required reviewers** within configured tier bounds.
- Reputation can never:
  - reduce review requirements below constitutional minimums,
  - grant elevated authority levels,
  - bypass blocking governance rules.

## Initial Scoring Model
Reviewer reputation starts as a weighted composite score with these dimensions:

1. **Latency score** — response timeliness relative to SLA windows.
2. **Override rate score** — frequency of accepted decisions later overridden by higher governance authority.
3. **Long-term mutation impact score** — downstream quality and stability impact of approved mutations.
4. **Governance alignment score** — consistency with constitutional and policy outcomes.

### Initial Weights
- Latency: `0.20`
- Override rate: `0.30`
- Long-term mutation impact: `0.30`
- Governance alignment: `0.20`

(Weights are bootstrap defaults and can be tuned under governance change control.)

### Epoch Weight Snapshot Invariant (Required)
- Reputation weight vector must be snapshotted and journaled per epoch before any scorer execution.
- Replay must consume epoch-scoped weight snapshots from the ledgered epoch context, never the current runtime/config weights.
- Mid-epoch weight changes are disallowed for active scoring windows and must take effect only at the next epoch boundary.

### Scoring Version Binding Invariant (Required)
- Reputation computation must record `scoring_algorithm_version` in epoch context and lifecycle/reputation update events.
- Replay must bind to the `scoring_algorithm_version` active during original score computation.
- Any scoring algorithm change requires a version bump and cannot retroactively reinterpret prior epochs.

## Integration Surfaces
- `runtime/governance/review_quality.py`
  - Hosts scoring updates and calibration logic.
  - Emits normalized reputation scores for tier-level reviewer-count adjustment.
- `schemas/events/pr_lifecycle_event.v1.json`
  - Extended fields capture reviewer action outcomes needed for calibration updates.
  - Event stream becomes the source input for periodic reputation recomputation.

## Guardrails
- Deterministic scoring only; no stochastic sampling.
- Every score update must be replay-compatible from journaled lifecycle events.
- Epoch replay determinism requires using the epoch-specific weight snapshot that was active when scores were computed.
- Replay determinism also requires binding to the epoch-specific `scoring_algorithm_version`.
- Constitutional floor checks execute before any count reduction is accepted.
- Calibration changes are auditable as governance-impact events.
