# ADAAD Press Kit

> **For journalists, bloggers, podcast hosts, and newsletter authors.**
> Everything you need to cover ADAAD in 5 minutes.

---

## The One-Sentence Pitch

**ADAAD is an open-source AI system where three autonomous agents continuously
improve your codebase — and every proposed change is blocked, logged, or approved
by a constitutional governance gate that cannot be bypassed, weakened, or bribed.**

---

## The Angles

### 🏛️  The Accountability Angle
*"This startup is building AI that can prove its own decisions were correct."*

Most AI coding tools are black boxes: they make changes and you trust them.
ADAAD takes the opposite bet. Every decision the system makes is:
1. Recorded in a cryptographic evidence ledger before execution
2. Replayable byte-identical months later
3. Governed by 16 rules that halt the entire system if broken

The founder's thesis: autonomous AI needs to be accountable before it's trustworthy.

### 🧬  The Technical Angle
*"Genetic algorithms + LLMs + constitutional rules: the engineering inside ADAAD."*

Three Claude-powered agents with distinct personas compete to improve code.
A genetic algorithm (BLX-alpha crossover, elite preservation) ranks candidates.
The winners hit a constitutional gate — 16 deterministic rules, fail-closed.
Scoring weights self-calibrate via momentum gradient descent. UCB1 bandits
select agent strategy. The whole system is self-amending with human oversight.

### 💰  The Business Angle
*"From Oklahoma to open-source SaaS: InnovativeAI LLC's zero-VC path."*

Dustin Reid built ADAAD from Blackwell, Oklahoma, without VC funding.
The business model: free open-source core (MIT), SaaS tiers on top
($49/month Pro, $499/month Enterprise). The constitutional gate is the same
at every tier — paying more buys capacity, never a governance bypass.

### 🤖  The AI Safety Angle
*"A practical implementation of 'constitutional AI' for code systems."*

The ADAAD constitutional gate demonstrates how governance-by-architecture
differs from governance-by-policy. Rules are not config files that can be
modified at runtime. They are structural invariants — enforced by the absence
of bypass paths, not the presence of checks.

---

## Quick Facts

| | |
|---|---|
| **Product** | ADAAD (Autonomous Device-Anchored Adaptive Development) |
| **Version** | 3.5.0 |
| **Founded** | 2025 |
| **Founder** | Dustin L. Reid |
| **Company** | InnovativeAI LLC |
| **Location** | Blackwell, Oklahoma, USA |
| **License** | MIT (fully open source) |
| **Language** | Python 3.11.9 |
| **AI backbone** | Anthropic Claude API |
| **Free tier** | Community — 50 epochs/month, forever free |
| **Paid tiers** | Pro $49/mo · Enterprise $499/mo |
| **Platforms** | Linux, macOS, Docker, Railway, Render, Fly.io |
| **Mobile** | Free Android companion app |
| **GitHub** | https://github.com/dreezy-6/ADAAD |

---

## Key Claims (Verifiable)

✅ **Constitutional gate is architectural, not configurable** — The `GovernanceGate`
class is the sole approval surface. No code path bypasses it.

✅ **Deterministic replay** — Every epoch decision re-runs byte-identical.
Run `python -m app.main --replay audit --epoch <id>` on any historical epoch.

✅ **SHA-256 hash-chained ledger** — Each governance record includes the hash
of the previous record. Retroactive modification breaks the chain.

✅ **Human sign-off is enforced** — A human-review event must exist in the
evidence ledger before any mutation reaches production. This is rule #9 of 16.

✅ **Governance is identical at all tiers** — The same 16 rules run for
Community (free) and Enterprise ($499/mo) users.

---

## What ADAAD Is Not

❌ Not a code review tool (it proposes mutations, it doesn't review PRs)
❌ Not a test generator (though it preserves test coverage by constitutional rule)
❌ Not a chatbot or coding assistant
❌ Not a replacement for human engineers
❌ Not an opaque "AI magic" system — every decision is explainable and auditable

---

## Interview / Demo Availability

**Dustin L. Reid** is available for:
- Podcast interviews (technical or founder-journey focus)
- Written Q&A (email or async)
- Live code demonstrations of the governance gate
- Academic paper discussions

Contact: dustin@innovativeai.dev
GitHub: https://github.com/dreezy-6
Twitter: @DustinReid

---

## Boilerplate

> ADAAD is an open-source autonomous code mutation system built by InnovativeAI LLC,
> founded by Dustin L. Reid in Blackwell, Oklahoma. Three Claude-powered AI agents
> continuously propose code improvements governed by a 16-rule constitutional gate —
> a fail-closed policy engine that halts all activity on the first rule violation.
> Every decision is recorded in a SHA-256 hash-chained evidence ledger and is
> deterministically replayable. ADAAD is MIT-licensed and available at
> https://github.com/dreezy-6/ADAAD.

---

## Assets

| Asset | Link |
|---|---|
| GitHub repo | https://github.com/dreezy-6/ADAAD |
| Marketing site | https://InnovativeAI-adaad.github.io/ADAAD |
| Pricing | https://github.com/dreezy-6/ADAAD/blob/main/PRICING.md |
| Architecture diagram | `docs/assets/adaad-flow.svg` |
| Constitution (full 16 rules) | `docs/CONSTITUTION.md` |
| Android APK | GitHub Releases |

*This press kit is maintained in the ADAAD repository at `PRESS.md`.*
