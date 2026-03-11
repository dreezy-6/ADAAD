# We built a constitutional AI mutation engine — here's how it works

*Three AI agents. One genetic algorithm. A 16-rule constitution. Nothing ships without proof.*

---

I've been building autonomous AI systems for a while, and I kept running into the same fundamental problem: every AI coding tool can *suggest* code, but none of them can *prove* the suggestion was safe. When something breaks, there's no audit trail. No replay. No "show your work."

So I built ADAAD.

## What ADAAD actually does

**ADAAD** (Autonomous Device-Anchored Adaptive Development) runs three Claude-powered AI agents — Architect, Dream, and Beast — in a continuous loop against your codebase. Each agent proposes code mutations with a distinct focus:

- 🏛️ **Architect** — structural coherence, dependency cleanup, interface contracts
- 💭 **Dream** — creative rewrites, lateral improvements, novel approaches
- 🐉 **Beast** — throughput, complexity reduction, raw performance

These proposals enter a **genetic algorithm** that crosses, mutates, and ranks candidates across generations using BLX-alpha crossover and UCB1 bandit selection.

But here's what makes ADAAD different from everything else.

## The Constitutional Gate

Every surviving candidate — regardless of fitness score — must pass **16 deterministic governance rules** before a single byte changes in your codebase.

```python
# This is the only surface that can approve a mutation
gate = GovernanceGate(tier=Tier.STABLE)
result = gate.evaluate(candidate)

if not result.passed:
    # Full halt. Named failure mode written to evidence ledger.
    raise GovernanceHalt(result.blocking_rule, result.delta)
```

One blocking failure = full halt. Not a warning. A hard stop.

The `GovernanceGate` cannot be:
- Overridden by any agent
- Bypassed by configuration  
- Weakened by a higher pricing tier
- Circumvented by any operator

This is architectural enforcement, not documentation.

## Deterministic replay

Every approved mutation is written to a **SHA-256 hash-chained evidence ledger**. Months later, you can re-run any epoch with `--replay audit` and prove byte-for-byte that the exact same inputs produced the exact same outputs under the exact same governance rules.

```bash
python -m app.main --replay audit --epoch epoch-2026-03-10-001
# → Re-runs the epoch
# → Compares output byte-by-byte  
# → Divergence from original: HALT + log delta
```

No other AI coding tool offers this. When a compliance auditor asks "what did the AI change on March 10th and why?" — ADAAD gives you a signed, replayable answer.

## Self-calibrating fitness

After every epoch, scoring weights update via momentum gradient descent (LR=0.05). Thompson sampling activates after 30 epochs for non-stationary reward detection. The system learns which mutation types are worth pursuing for *your specific codebase* without ever touching the governance layer.

## Getting started

```bash
pip install adaad
adaad --dry-run   # preview — nothing is modified
adaad --run       # first governed epoch
```

Or clone and run `python onboard.py` — it handles environment setup, schema validation, and a governed dry-run in under 60 seconds.

Community tier is **free forever** (MIT). Full governance engine, no credit card.

---

**GitHub:** https://github.com/InnovativeAI-adaad/ADAAD  
**Pricing:** Community (free) · Pro ($49/mo) · Enterprise ($499/mo)  
**Author:** Dustin L. Reid · Founder, InnovativeAI LLC · Blackwell, Oklahoma
