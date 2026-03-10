# Indie Hackers Founder Story — ADAAD / InnovativeAI LLC

**Post title:** `How I built a constitutionally-governed autonomous AI coding system as a solo founder — and why governance is the moat`

---

## The origin

I'm Dustin Reid, founder of InnovativeAI LLC in Blackwell, Oklahoma. I started building ADAAD because I kept seeing the same failure mode in every AI coding tool: they could suggest code, but couldn't prove it was safe.

When Copilot breaks your build, you have no audit trail. You don't know what it changed, whether it was tested under the same conditions, or why it thought the change was correct. That's not a UX problem — it's an architectural one.

## The core insight

Autonomy without accountability isn't progress — it's drift.

ADAAD's answer: every code mutation must pass a 16-rule constitutional policy engine before a single byte changes. The "constitution" is not configuration — it's architecture. You can't override it. The governance gate is the only surface that can approve mutations.

## What I built

Three AI agents (Architect, Dream, Beast) run in a loop:
1. Each proposes code mutations
2. Proposals compete in a genetic algorithm — crossing, mutating, and ranking
3. Fittest candidates go to the GovernanceGate
4. 16 rules evaluated in order. One failure = full halt
5. Approved mutations apply with SHA-256 hash-chained audit trail
6. The scoring weights self-calibrate across epochs via momentum gradient descent

The system also proposes changes to its own roadmap. Humans approve. No auto-merge path exists — constitutional invariant.

## The business model

- **Community**: Free forever (MIT). 50 epochs/month. Full governance.
- **Pro**: $49/month. 500 epochs, more candidates, roadmap amendment access.
- **Enterprise**: $499/month. Unlimited everything, custom constitutional rules, 99.9% SLA.

The constitutional gate is identical at every tier. I refuse to sell a weaker governance model to free users and a stronger one to Enterprise. That's the whole point.

## Traction so far

- 922 commits across Phase 1–12
- Free Android companion app shipping via CI
- Autonomous marketing engine built in (Phase 11) — ADAAD submits itself to awesome-lists
- PyPI package (`pip install adaad`) live in Phase 12

## What I'm looking for

Users willing to run it on their codebase and report what passes/fails the constitutional gate. The governance rules are deterministic — I want real-world feedback on whether the 16 rules are the right 16.

Early Enterprise customers for the $499/mo tier — specifically compliance-heavy teams (fintech, healthcare, government) where "prove what the AI did" is a legal requirement.

---
