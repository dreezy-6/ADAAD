# Show HN: ADAAD — constitutional AI governance for autonomous code mutation (MIT, free)

## READY TO PASTE — news.ycombinator.com/submit

**Title (copy exactly):**
```
Show HN: ADAAD – Copilot suggests, Cursor autocompletes, ADAAD governs (MIT, free)
```

**Text (copy exactly):**
```
I built this because I kept running into the same problem: every AI coding tool can suggest code, but none of them can prove the suggestion was safe.

ADAAD runs three Claude-powered agents (Architect, Dream, Beast) in a continuous loop against your codebase. Every proposal enters a genetic algorithm, then must pass a 16-rule constitutional gate before a single byte changes. The GovernanceGate is the only surface that can approve mutations — it can't be overridden by any agent, operator, or config flag.

What actually differentiates this from Copilot/Cursor/Devin:

- Deterministic replay: re-run any past epoch months later, get byte-identical outputs. Divergence halts the pipeline and logs the exact delta.
- SHA-256 hash-chained evidence ledger: every governed decision is cryptographically signed and permanently auditable. No retroactive modification is technically possible.
- Constitutional gating: 16 hard rules in strict order. One blocking failure = full halt with a named failure mode written to the ledger.
- Self-calibrating fitness: scoring weights update via momentum gradient descent after every epoch. Thompson sampling activates for non-stationary reward at ≥30 epochs.
- Genetic population: BLX-alpha crossover, UCB1 bandit agent selection, elite preservation.

The governance model is not configurable. It's architectural. Paying more at a higher pricing tier does not weaken the gate — by invariant.

Community tier is free forever (MIT, self-hosted, no telemetry).

pip install adaad && adaad --dry-run

GitHub: https://github.com/InnovativeAI-adaad/ADAAD
```

---

## Timing

**Best window:** Tuesday–Thursday, 8–10 AM US Eastern (peak HN engagement)
**Avoid:** Friday PM, weekends, Monday morning

## After posting

1. Respond to every comment within the first 2 hours — this drives ranking
2. Don't defend, explain. Answer "how does X work?" questions with technical depth
3. Pin a follow-up comment linking to docs/CONSTITUTION.md for the technically curious
4. Screenshot the live post URL and share on LinkedIn/Twitter immediately

## What to expect

Front-page HN post: 5,000–50,000 visitors in 48 hours, 20–200 GitHub stars, 5–50 Pro trial signups.
If it doesn't front-page: the post still indexes in Google within 48 hours and generates long-tail traffic.

## Status

| Item | Status |
|:-----|:------:|
| HN post drafted | ✅ |
| Posted | ⬜ |
| Front page | ⬜ |
| Stars gained | — |
