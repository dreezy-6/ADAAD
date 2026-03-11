<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="900" alt="ADAAD — Autonomous Device-Anchored Adaptive Development"/>
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg"/>
  </a>
  &nbsp;
  <img alt="Version" src="https://img.shields.io/badge/version-6.2.0-00d4ff?style=flat-square&labelColor=060d14"/>
  <img alt="Phase" src="https://img.shields.io/badge/phase-13%20–%20max%20exposure-f59e0b?style=flat-square&labelColor=060d14"/>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-7b61ff?style=flat-square&labelColor=060d14"/>
  <img alt="Android" src="https://img.shields.io/badge/android-free-3ddc84?style=flat-square&labelColor=060d14"/>
  <img alt="PyPI" src="https://img.shields.io/badge/pip_install-adaad-00d4ff?style=flat-square&labelColor=060d14"/>
  &nbsp;
  <img alt="Governance" src="https://img.shields.io/badge/governance-fail--closed-ef4444?style=flat-square&labelColor=060d14"/>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square&labelColor=060d14"/>
</p>

<br/>

<h2 align="center">The only AI coding system that can prove — cryptographically — exactly what it changed and why.</h2>

<p align="center">
  <strong>Copilot suggests. Cursor autocompletes. ADAAD governs.</strong><br/>
  Three competing AI agents. A genetic algorithm. A 16-rule constitutional gate.<br/>
  Nothing ships without a SHA-256 hash-chained, deterministically replayable audit trail.<br/>
  <em>Free forever. MIT licensed. Self-hosted. No telemetry.</em>
</p>

<p align="center">
  <a href="#-60-second-install"><strong>⚡ Install in 60s</strong></a> ·
  <a href="#the-problem-with-every-other-ai-coding-tool"><strong>The Problem</strong></a> ·
  <a href="#how-adaad-works"><strong>How It Works</strong></a> ·
  <a href="#vs-copilot--cursor--codeium--devin"><strong>Compare</strong></a> ·
  <a href="#pricing"><strong>Pricing</strong></a> ·
  <a href="#-android-app"><strong>Android</strong></a> ·
  <a href="docs/CONSTITUTION.md"><strong>Constitution</strong></a>
</p>

---

## The problem with every other AI coding tool

When GitHub Copilot breaks your build, you have no audit trail. You don't know what changed, whether it was tested under the same conditions, who approved it, or why the AI thought it was safe. That's not a UX problem. **That's an architectural failure.**

Cursor autocompletes. Devin "automates." Every one of these tools generates code and hopes for the best. None of them can answer the question that matters in a production incident, a compliance audit, or a regulated environment:

**"Show me exactly what the AI changed, when, under what conditions, and prove the decision was made correctly."**

ADAAD is the only system built to answer that question.

---

## How ADAAD works

**Three Claude-powered AI agents compete continuously to improve your codebase.**

Every proposal enters a governed pipeline — no exceptions, no shortcuts, no workarounds.

```
┌─────────────────────────────────────────────────────────────────┐
│                      THE ADAAD PIPELINE                         │
│                                                                 │
│  [Architect] ──┐                                                │
│  [Dream]     ──┼──► Genetic Algorithm ──► Constitutional Gate  │
│  [Beast]     ──┘    (BLX-alpha GA)         (16 hard rules)     │
│                     Rank · Cross · Mutate   Pass → Execute      │
│                                             Fail → HALT + Log   │
│                                                       │         │
│                                              SHA-256 Evidence   │
│                                              Ledger (immutable) │
└─────────────────────────────────────────────────────────────────┘
```

[![ADAAD mutation pipeline](docs/assets/adaad-flow.svg)](docs/assets/adaad-flow.svg)

### Step 1 — Three agents propose

| Agent | Persona | What it hunts for |
|:------|:--------|:------------------|
| 🏛️ **Architect** | Systematic, long-horizon | Structural coherence · Dependency cleanup · Interface contracts |
| 💭 **Dream** | Creative, lateral | Novel rewrites · Experimental approaches · Non-obvious improvements |
| 🐉 **Beast** | Aggressive, performance-first | Throughput · Complexity reduction · Raw optimization |

Each agent is a distinct Claude system prompt. They see the same codebase. They produce different proposals. They compete on merit.

### Step 2 — Genetic algorithm ranks and evolves

Candidates cross (BLX-alpha), mutate, and compete across generations. Elite preservation keeps the best alive. UCB1 bandit selection decides which agent strategy gets the next epoch. Fitness weights self-calibrate across epochs via **momentum gradient descent** — the system learns which kinds of improvements are worth making.

### Step 3 — The Constitutional Gate (what makes ADAAD different)

**16 deterministic rules. Evaluated in strict order. One blocking failure = full pipeline halt.**

Not a warning. Not a soft suggestion. A hard stop with a named failure mode written to the evidence ledger.

The `GovernanceGate` is the **only** surface that can approve a mutation. It cannot be:
- Overridden by any agent
- Bypassed by any configuration
- Weakened by a higher pricing tier
- Circumvented by any operator or PR

This is architectural enforcement, not documentation.

### Step 4 — Deterministic replay + immutable evidence

Every approved mutation is hash-chained into an append-only SHA-256 ledger. Signed. Permanent. Months later, re-run any epoch with `--replay audit` and prove byte-for-byte that the exact same inputs produced the exact same outputs under the exact same governance rules. Divergence halts the pipeline and logs the delta.

> [!NOTE]
> **What "deterministic replay" means in practice:** A compliance audit, a regulated industry review, or a security incident investigation can re-run any past decision from scratch and verify it independently. No other AI coding tool offers this.

### Step 5 — Self-calibrating intelligence

After every epoch, the system updates scoring weights (momentum gradient descent, LR=0.05), bandit strategy (UCB1 → Thompson sampling on non-stationary reward at ≥30 epochs), and fitness landscape memory (per-type win/loss rates, plateau detection). Underperforming strategies decay. **The system gets better at choosing what to improve without touching the governance layer.**

---

## vs Copilot / Cursor / Codeium / Devin

| Capability | Copilot | Cursor | Codeium | Devin | **ADAAD** |
|:-----------|:-------:|:------:|:-------:|:-----:|:---------:|
| AI code suggestions | ✅ | ✅ | ✅ | ✅ | ✅ |
| Autonomous mutation loop | — | — | — | partial | **✅** |
| Constitutional governance gate | — | — | — | — | **✅** |
| Deterministic replay verification | — | — | — | — | **✅** |
| SHA-256 cryptographic audit trail | — | — | — | — | **✅** |
| Genetic algorithm candidate ranking | — | — | — | — | **✅** |
| Self-calibrating fitness weights | — | — | — | — | **✅** |
| Multi-repo federation governance | — | — | — | — | **✅** |
| Autonomous roadmap self-amendment | — | — | — | — | **✅** |
| Legally auditable output | — | — | — | — | **✅** |
| Self-hosted, MIT licensed, no telemetry | — | — | partial | — | **✅** |
| Free tier with full governance | — | — | partial | — | **✅** |
| Android companion app | — | — | — | — | **✅** |
| `pip install` CLI | — | — | — | — | **✅** |

The governance moat is real. Copilot and Cursor are autocomplete products at heart. ADAAD is a governed autonomous system. Different category entirely.

---

## ⚡ 60-second install

```bash
# Option A — pip (recommended)
pip install adaad
adaad --dry-run       # preview what would change — nothing is modified
adaad --run           # your first governed epoch

# Option B — clone and onboard
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py     # handles env, deps, schema validation, and dry-run
```

**Requirements:** Python 3.11+ · pip · git · `ADAAD_CLAUDE_API_KEY` (Anthropic API key)

<details>
<summary>What <code>python onboard.py</code> does, step by step</summary>

```
onboard.py
  │
  ├─ 1. Verify Python 3.11+
  ├─ 2. Create .venv + install all dependencies
  ├─ 3. Set ADAAD_ENV=dev  (safe default)
  ├─ 4. Initialize workspace  (nexus_setup.py)
  ├─ 5. Validate all governance schemas
  ├─ 6. Run governed dry-run:
  │      python -m app.main --dry-run --replay audit
  └─ 7. Print your personalized next steps
```

Successful output:

```
✔ Python 3.11.9
✔ Virtual environment ready
✔ Dependencies installed
✔ ADAAD_ENV=dev
✔ Workspace initialized
✔ Governance schemas valid
✔ Dry-run complete — no files modified

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ADAAD is ready.

  Run the dashboard:   python server.py
  Run an epoch:        python -m app.main --verbose
  Explore the docs:    docs/README.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

</details>

---

## Code example — first epoch

```python
from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop
import os

loop = EvolutionLoop(
    api_key=os.environ["ADAAD_CLAUDE_API_KEY"],
    generations=3,
)

context = CodebaseContext(
    file_summaries={
        "runtime/autonomy/mutation_scaffold.py": "Core scoring engine.",
        "app/main.py": "Entry point and CLI dispatch.",
    },
    recent_failures=[],
    current_epoch_id="epoch-001",
)

result = loop.run_epoch(context)

print(f"Proposals generated:  {result.total_candidates}")
print(f"Accepted by gate:     {result.accepted_count}")
print(f"Blocked by gate:      {result.total_candidates - result.accepted_count}")
print(f"Recommended agent:    {result.recommended_next_agent}")
print(f"Weight accuracy:      {result.weight_accuracy:.1%}")
print(f"Duration:             {result.duration_seconds:.1f}s")
```

Re-run any epoch with `--replay audit` for byte-identical verification. Divergence is a first-class error.

---

## The autonomous marketing engine

ADAAD promotes itself. No manual posting required after initial setup.

```bash
python market.py             # full autonomous cycle
python market.py --dry-run   # preview — no API calls made
python market.py --status    # platform coverage report
python market.py --queue     # items that require Dustin's manual action
python market.py --discover  # use Claude to find new distribution platforms
```

Runs daily at 9AM UTC via GitHub Actions. Publishes to Dev.to, Hashnode, Reddit. Opens PRs to awesome-lists. All governed by `MarketingGate` and logged to the evidence ledger.

**Active distribution targets (all free, all permanent):**

| Platform | Audience | Status |
|:---------|:---------|:------:|
| `e2b-dev/awesome-ai-agents` | 200k+ monthly visitors | 🟡 PR queued |
| `Shubhamsaboo/awesome-llm-apps` | 150k+ monthly visitors | 🟡 PR queued |
| `vinta/awesome-python` | 500k+ monthly visitors | 🟡 PR queued |
| `awesome-selfhosted/awesome-selfhosted` | 50k+ stars | 🟡 PR queued |
| `ml-tooling/best-of-ml-python` | ML practitioner audience | 🟡 PR queued |
| `anthropics/anthropic-cookbook` | Claude-native developers | 🟡 PR queued |
| Dev.to | 1M+ monthly developers | 🟡 3 articles queued |
| Hashnode | 1M+ monthly developers | 🟡 3 articles queued |
| Reddit (4 subreddits) | r/ML · r/Python · r/selfhosted · r/programming | 🟡 Queued |
| Hacker News Show HN | Front page potential: 5k–50k visitors | ⬜ Manual (Dustin) |
| Product Hunt | 500k+ makers daily | ⬜ Manual (Dustin) |

---

## Full capability surface

<table>
<tr><td><strong>🔁 Deterministic Replay</strong></td><td>Every decision re-runs byte-identical months later. Divergence from original halts the pipeline and logs the exact delta. Prove what happened to an auditor.</td></tr>
<tr><td><strong>🛡️ Constitutional Gating</strong></td><td>16 governance rules evaluated per mutation across three tiers (Sandbox / Stable / Production). One blocking failure = full halt. Architecturally enforced — not configurable, not bypassable.</td></tr>
<tr><td><strong>🧾 Append-Only Evidence Ledger</strong></td><td>Every governed step is SHA-256 hash-chained, signed, and permanently attached to the decision. No retroactive modification is technically possible.</td></tr>
<tr><td><strong>🤖 Three-Agent Pipeline</strong></td><td>Architect (structural), Dream (creative), Beast (performance) — three distinct Claude personas competing under identical governance rules every epoch.</td></tr>
<tr><td><strong>🧬 Genetic Population Evolution</strong></td><td>BLX-alpha crossover, elite preservation, MD5 deduplication, diversity enforcement. UCB1 multi-armed bandit selects agent strategy per generation.</td></tr>
<tr><td><strong>📈 Self-Calibrating Fitness</strong></td><td>Momentum gradient descent (LR=0.05) on scoring weights. Thompson sampling activates on non-stationary reward detection at ≥30 epochs. The system learns your codebase.</td></tr>
<tr><td><strong>🗺️ Fitness Landscape Memory</strong></td><td>Per-type win/loss rates tracked across all epochs. Plateau detection triggers exploration mode. Underperforming strategies decay automatically.</td></tr>
<tr><td><strong>🧪 Policy Simulation DSL</strong></td><td>Replay historical epochs under hypothetical governance constraints — zero side-effects, full audit trail. Test "what if rule 7 had been stricter last quarter?"</td></tr>
<tr><td><strong>🐳 Container Isolation</strong></td><td>cgroup v2 sandboxes — pool-managed, health-probed, lifecycle-audited. Resource bounds are a blocking constitutional rule, not a setting.</td></tr>
<tr><td><strong>🌐 Multi-Node Federation</strong></td><td>Cross-repo mutations with dual-gate enforcement. Divergence in any node blocks promotion. FederatedEvidenceMatrix validates cross-repo determinism.</td></tr>
<tr><td><strong>📝 Roadmap Self-Amendment</strong></td><td>ADAAD proposes changes to its own roadmap. Humans approve. No auto-merge path by constitutional invariant. Parts of this repo were authored by ADAAD itself.</td></tr>
<tr><td><strong>💰 SaaS Tier Engine</strong></td><td>HMAC-SHA256 bearer tokens, Stripe webhook billing, offline tier validation (no DB lookup), sliding-window rate limiting. Full replay-safe capability enforcement.</td></tr>
<tr><td><strong>📣 Autonomous Marketing</strong></td><td>Daily CI cycle: article publishing, awesome-list PRs, social dispatch. ADAAD expands its own distribution surface. Every action governed by MarketingGate.</td></tr>
</table>

---

## Pricing

> **Constitutional guarantee:** Every tier — Community free or Enterprise $499/mo — runs the identical GovernanceGate with the identical 16-rule policy engine. Paying more **never weakens the gate**. It buys capacity and tooling.

| | **Community** | **Pro** | **Enterprise** |
|---|:---:|:---:|:---:|
| **Price** | **Free forever** | **$49 / month** | **$499 / month** |
| Epochs / month | 50 | 500 | Unlimited |
| Candidates / epoch | 3 | 10 | Unlimited |
| API rate limit / min | 10 | 60 | 600 |
| Federation nodes | — | 3 | Unlimited |
| **Android companion app** | ✅ | ✅ | ✅ |
| **Deterministic replay** | ✅ | ✅ | ✅ |
| **Full constitutional gate** | ✅ | ✅ | ✅ |
| **SHA-256 evidence ledger** | ✅ | ✅ | ✅ |
| Reviewer reputation engine | — | ✅ | ✅ |
| Roadmap self-amendment | — | ✅ | ✅ |
| Simulation DSL | — | ✅ | ✅ |
| Aponi IDE integration | — | ✅ | ✅ |
| Webhook integrations | — | ✅ | ✅ |
| Signed audit export | — | ✅ | ✅ |
| SSO / SAML | — | — | ✅ |
| Custom constitutional rules | — | — | ✅ |
| Dedicated onboarding | — | — | ✅ |
| 99.9% SLA | — | — | ✅ |
| Priority support (4hr) | — | — | ✅ |

**[→ Upgrade to Pro](https://innovativeai.io/adaad/upgrade?plan=pro)** · **[→ Enterprise](https://innovativeai.io/adaad/enterprise)** · **[→ Full pricing FAQ](PRICING.md)**

---

## 📱 Android App

Free. Available on all pricing tiers. No subscription required.

- Live monitoring of governed runs and epoch status
- Mutation proposal review and approval — on your phone
- Evidence ledger inspection with SHA-256 drill-down
- Pipeline halt alerts with named failure mode detail
- Roadmap amendment approvals (Pro/Enterprise)

Download the latest APK: [github.com/dreezy-6/ADAAD/releases/latest](../../releases/latest)  
Built and published automatically by `.github/workflows/android-free-release.yml`.

---

## Architecture and governance

ADAAD's governance is not configurable. It is architectural.

```
Constitution (14 hard rules, cannot be overridden)
    └─► Architecture Contract (interface + boundary invariants)
            └─► ArchitectAgent Spec v3.1.0
                    └─► PR Procession Plan (PR order, CI tier, closure state)
```

| Document | Purpose |
|:---------|:--------|
| [Constitution](docs/CONSTITUTION.md) | 14 hard rules. Overrideable by nothing. |
| [Architecture Contract](docs/ARCHITECTURE_CONTRACT.md) | Interface and boundary invariants across all modules. |
| [ArchitectAgent Spec v3.1.0](docs/governance/ARCHITECT_SPEC_v3.1.0.md) | Canonical governance baseline. |
| [PR Procession Plan](docs/governance/ADAAD_PR_PROCESSION_2026-03.md) | Controlling source for PR order and CI tier. |
| [Security Policy](docs/SECURITY.md) | Vulnerability reporting and response. |

---

## What will never be built

Explicit exclusions are part of the constitution:

- **No autonomous promotion to production** — `GovernanceGate` authority cannot be delegated to any agent.
- **No non-deterministic entropy in governance** — Randomness only in proposals (epoch-id seeded), never in gate evaluation.
- **No retroactive evidence** — Hash chain makes post-hoc modification technically impossible.
- **No silent failures** — Every halt produces a named failure mode in the ledger.
- **No tier-based governance weakening** — The constitutional gate is identical at every price point, always.

---

## Documentation

| I want to… | Go here |
|:-----------|:--------|
| 🚀 Get running in 60 seconds | [QUICKSTART.md](QUICKSTART.md) |
| 🧠 Understand the architecture | [Architecture Contract](docs/ARCHITECTURE_CONTRACT.md) |
| 🛡️ Read the governance rules | [Constitution](docs/CONSTITUTION.md) |
| 📣 Run the marketing engine | [market.py](market.py) |
| 💰 Understand pricing | [PRICING.md](PRICING.md) |
| 📱 Install the Android app | [INSTALL_ANDROID.md](INSTALL_ANDROID.md) |
| 📦 Ship a governed release | [Release checklist](docs/release/release_checklist.md) |
| 📊 Full documentation index | [Docs Hub](docs/README.md) |
| 🤝 Contribute | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## Current status — v6.1.0 · Phase 12

| Phase | Status | Released | What shipped |
|:------|:------:|:--------:|:-------------|
| 1 — Core mutation loop | ✅ | v1.0.0 | AIMutationProposer, EvolutionLoop, WeightAdaptor |
| 2 — GA + bandit | ✅ | v1.1.0 | BLX-alpha GA, UCB1 bandit, PopulationManager |
| 3 — Adaptive penalty weights | ✅ | v2.1.0 | Thompson sampling, telemetry feedback loop |
| 4 — Semantic mutation diff | ✅ | v2.2.0 | AST-based scoring, lineage confidence |
| 5 — Multi-repo federation | ✅ | v3.0.0 | FederationBroker, HMAC keys, cross-repo determinism CI |
| 6 — Roadmap self-amendment | ✅ | v3.1.0 | RoadmapAmendmentEngine, ProposalDiffRenderer |
| 6.1 — Simplification contract | ✅ | v3.1.1 | CI-enforced complexity budgets, legacy branch gate |
| 7 — Container isolation | ✅ | v3.2.0 | cgroup v2 sandboxes, pool + lifecycle management |
| 8 — SaaS monetization | ✅ | v3.2.0 | TierEngine, API keys, Stripe billing, FastAPI middleware |
| 9 — Simulation DSL | ✅ | v4.0.0 | Replay harness, hypothetical constraint evaluation |
| 10 — Aponi IDE integration | ✅ | v5.0.0 | Inline evidence viewer, mutation panel, replay inspector |
| 11 — Autonomous marketing | ✅ | v6.0.0 | market.py, dispatchers, daily CI, 7-platform dispatch |
| 12 — Campaign Blitz v2 | ✅ | v6.1.0 | Hashnode, PyPI, 4 new awesome-list PRs, 16-channel outreach queue |
| **13 — Maximum Autonomous Exposure** | **✅** | **v6.2.0** | 15 awesome-list targets, 7 Reddit targets, Hashnode live, 20 AI directories, press kit, PH launch kit, rotating Twitter threads, growth.yml, discussions seeder |

📋 Full roadmap → [ROADMAP.md](ROADMAP.md) · 🔖 Changelog → [CHANGELOG.md](CHANGELOG.md)

---

## About InnovativeAI LLC

**InnovativeAI LLC** is an independent AI research and engineering company founded and led by **Dustin L. Reid** in Blackwell, Oklahoma.

The founding thesis: autonomous AI systems must be governed by hard architectural rules — not soft policies, not configuration flags, not documentation. ADAAD is the proof-of-concept that this is possible and practical.

Dustin designed every layer from scratch across 900+ commits: the three-agent mutation pipeline, genetic population management, self-calibrating fitness engine, constitutional governance model, federated execution architecture, SaaS monetization layer, and the autonomous distribution engine. The system is production-grade today.

> *"Autonomy without accountability isn't progress — it's drift. ADAAD makes every decision traceable, every mutation defensible, and every failure visible."*
> — **Dustin L. Reid**, Founder, InnovativeAI LLC

---

## License

MIT License. See [LICENSE](LICENSE). Compliance gate: `python scripts/validate_license_compliance.py`

---

<p align="center">
  Built by <strong>Dustin L. Reid</strong> · <a href="https://github.com/InnovativeAI-adaad">InnovativeAI LLC</a> · Blackwell, Oklahoma<br/>
  <sub>The only AI coding system with a constitutional governance gate. Free. MIT. Self-hosted.</sub>
</p>
