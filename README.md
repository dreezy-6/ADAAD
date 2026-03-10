<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="900" alt="ADAAD — Autonomous Device-Anchored Adaptive Development"/>
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg"/>
  </a>
  &nbsp;
  <img alt="Version" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FInnovativeAI-adaad%2FADAAD%2Fmain%2FVERSION&query=%24.version&label=version&color=00d4ff&style=flat-square&labelColor=060d14"/>
  <img alt="Phase" src="https://img.shields.io/badge/phase-12%20campaign%20blitz-f59e0b?style=flat-square&labelColor=060d14"/>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11.9-7b61ff?style=flat-square&labelColor=060d14"/>
  <img alt="Android" src="https://img.shields.io/badge/android-free-3ddc84?style=flat-square&labelColor=060d14"/>
  &nbsp;
  <img alt="Governance" src="https://img.shields.io/badge/governance-fail--closed-ef4444?style=flat-square&labelColor=060d14"/>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square&labelColor=060d14"/>
  <img alt="PyPI" src="https://img.shields.io/badge/pip_install-adaad-00d4ff?style=flat-square&labelColor=060d14"/>
</p>

<br/>

<p align="center">
  <strong>The only AI coding assistant that can legally prove what it did — and why.</strong>
</p>

<p align="center">
  Three Claude-powered AI agents continuously improve your codebase. Every proposed mutation is scored by a<br/>
  genetic algorithm, then must pass a 16-rule constitutional policy engine before a single byte changes.<br/>
  <em>Cryptographically audited. Deterministically replayable. Constitutionally governed. Free forever.</em>
</p>

<p align="center">
  <a href="#-start-in-60-seconds"><strong>⚡ Quick Start</strong></a> ·
  <a href="#how-the-loop-works"><strong>How It Works</strong></a> ·
  <a href="#vs-copilot-cursor-codeium"><strong>vs Copilot / Cursor</strong></a> ·
  <a href="#-android-app--free"><strong>Android App</strong></a> ·
  <a href="#pricing"><strong>Pricing</strong></a> ·
  <a href="docs/CONSTITUTION.md"><strong>Constitution</strong></a> ·
  <a href="ROADMAP.md"><strong>Roadmap</strong></a>
</p>

---

## What is ADAAD?

**ADAAD** (Autonomous Device-Anchored Adaptive Development) is an open-source AI governance and autonomous code mutation system built by **[InnovativeAI LLC](https://github.com/InnovativeAI-adaad)**.

Conceived, designed, and architected entirely by **Dustin L. Reid** — Founder of InnovativeAI LLC — with one founding conviction:

> *"Autonomy without accountability isn't progress — it's drift. ADAAD makes every decision traceable, every mutation defensible, and every failure visible."*
> — **Dustin L. Reid**, Founder, InnovativeAI LLC

### The core problem ADAAD solves

Every AI coding tool today — Copilot, Cursor, Codeium — **suggests code but cannot prove it is safe, correct, or auditable.** When something breaks, you don't know what the AI changed, why, or whether it was tested. ADAAD fixes this at the architectural level, not the policy level.

---

## vs Copilot / Cursor / Codeium

| Capability | Copilot | Cursor | Codeium | **ADAAD** |
|:-----------|:-------:|:------:|:-------:|:---------:|
| AI-powered code suggestions | ✅ | ✅ | ✅ | ✅ |
| Autonomous code mutation | — | — | — | ✅ |
| Constitutional governance gate | — | — | — | ✅ |
| Cryptographic audit trail | — | — | — | ✅ |
| Deterministic replay | — | — | — | ✅ |
| Genetic algorithm candidate ranking | — | — | — | ✅ |
| Self-calibrating fitness weights | — | — | — | ✅ |
| Federated multi-repo support | — | — | — | ✅ |
| Autonomous roadmap self-amendment | — | — | — | ✅ |
| Free tier, MIT licensed | — | — | Partial | ✅ |
| Android companion app | — | — | — | ✅ |
| Legally auditable output | — | — | — | ✅ |

---

## What ADAAD does

Three Claude-powered AI agents continuously propose code improvements. Those proposals compete in a genetic-algorithm population — crossed, mutated, and ranked. The fittest candidates advance to a **constitutional gate**: 16 deterministic rules, evaluated in order. One blocking failure halts everything.

[![ADAAD mutation pipeline: propose → simulate → replay-verify → policy gate → execute → evidence](docs/assets/adaad-flow.svg)](docs/assets/adaad-flow.svg)

After every epoch, scoring weights self-calibrate via momentum gradient descent. Mutation strategies that perform well gain influence. Underperformers decay. **The system learns which kinds of improvements are worth making — without ever bypassing governance.**

---

## Three agents. One loop.

[![Architect, Dream, and Beast agent personas](docs/assets/adaad-agents.svg)](docs/assets/adaad-agents.svg)

| Agent | Personality | Focus |
| --- | --- | --- |
| 🏛️ **Architect** | Systematic, structural | Long-term coherence, dependency cleanup, interface contracts |
| 💭 **Dream** | Creative, exploratory | Novel approaches, experimental rewrites, lateral improvements |
| 🐉 **Beast** | Aggressive, performance-first | Throughput gains, complexity reduction, raw optimization |

Each agent competes on merit inside the same governed pipeline. The **GovernanceGate** evaluates all three identically — no agent gets special treatment.

> [!IMPORTANT]
> `GovernanceGate` is the **only** surface that can approve, sign, or execute a mutation. Fitness scores influence selection — but approval authority belongs exclusively to constitutional evaluation. This is architecturally enforced, not just documented.

---

## ⚡ Start in 60 seconds

```bash
pip install adaad          # or: git clone + python onboard.py
adaad --dry-run            # see what would change, nothing is modified
adaad --run                # first governed epoch
```

**Or clone and run manually:**

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py
```

> **Requirements:** Python 3.11.9 · pip · git

`onboard.py` handles everything: environment setup, workspace init, schema validation, and a governed dry-run. Every step is idempotent — safe to re-run at any time.

<details>
<summary><strong>What onboarding does, step by step</strong></summary>

```
onboard.py
  │
  ├─ 1. Verify Python 3.11.9
  ├─ 2. Create .venv + install dependencies
  ├─ 3. Set ADAAD_ENV=dev  (safe default)
  ├─ 4. Initialize workspace  (nexus_setup.py)
  ├─ 5. Validate governance schemas
  ├─ 6. Run governed dry-run
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

## How the loop works

```python
from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop
import os

loop = EvolutionLoop(
    api_key=os.environ["ADAAD_CLAUDE_API_KEY"],
    generations=3,
)

context = CodebaseContext(
    file_summaries={"runtime/autonomy/mutation_scaffold.py": "Scoring engine."},
    recent_failures=[],
    current_epoch_id="epoch-001",
)

result = loop.run_epoch(context)

print(f"Proposals:   {result.total_candidates}")
print(f"Accepted:    {result.accepted_count}")
print(f"Next agent:  {result.recommended_next_agent}")
print(f"Accuracy:    {result.weight_accuracy:.1%}")
print(f"Duration:    {result.duration_seconds:.1f}s")
```

> [!NOTE]
> Replay mode is always on. Every decision above can be re-run with `--replay audit` to verify byte-identical outputs. Divergence from the original run halts the pipeline and logs the exact delta.

---

## Platform capabilities

<table>
<tr>
  <td><strong>🔁&nbsp; Deterministic Replay</strong></td>
  <td>Every decision re-runs byte-identical. Divergence halts the pipeline and is logged in the evidence ledger.</td>
</tr>
<tr>
  <td><strong>🛡️&nbsp; Constitutional Gating</strong></td>
  <td>16 governance rules evaluated per mutation across three tiers (Sandbox / Stable / Production). One blocking failure = full halt.</td>
</tr>
<tr>
  <td><strong>🧾&nbsp; Append-Only Evidence Ledger</strong></td>
  <td>Every governed step is SHA-256 hash-chained, signed, and permanently attached. No retroactive modification possible.</td>
</tr>
<tr>
  <td><strong>🤖&nbsp; AI Mutation Proposals</strong></td>
  <td>Three Claude-powered agents (Architect / Dream / Beast) produce diverse, scored candidates each epoch via the Anthropic API.</td>
</tr>
<tr>
  <td><strong>📈&nbsp; Self-Calibrating Weights</strong></td>
  <td>Scoring weights adapt via momentum gradient descent across epochs. Underperforming strategies decay automatically.</td>
</tr>
<tr>
  <td><strong>🧬&nbsp; Genetic Population Evolution</strong></td>
  <td>BLX-alpha crossover, elite preservation, and diversity enforcement per generation. UCB1 bandit selects agent strategy.</td>
</tr>
<tr>
  <td><strong>🗺️&nbsp; Fitness Landscape Memory</strong></td>
  <td>Win/loss rates tracked per mutation type. Plateau detection triggers exploration mode via Thompson sampling.</td>
</tr>
<tr>
  <td><strong>🧪&nbsp; Policy Simulation</strong></td>
  <td>Replay historical epochs under hypothetical constraints — zero side-effects, full audit trail.</td>
</tr>
<tr>
  <td><strong>🐳&nbsp; Container Isolation</strong></td>
  <td>cgroup v2 sandboxes — pool-managed, health-probed, lifecycle-audited. Resource bounds are a blocking constitutional rule.</td>
</tr>
<tr>
  <td><strong>🌐&nbsp; Multi-Node Federation</strong></td>
  <td>Cross-repo mutations with dual-gate constitutional enforcement. Divergence in any node blocks promotion.</td>
</tr>
<tr>
  <td><strong>📝&nbsp; Roadmap Self-Amendment</strong></td>
  <td>The engine proposes changes to its own roadmap. Humans approve. No auto-merge path exists — by constitutional invariant.</td>
</tr>
<tr>
  <td><strong>📣&nbsp; Autonomous Marketing Engine</strong></td>
  <td>Governed autonomous distribution across Dev.to, Hashnode, Reddit, awesome-lists, PyPI, and Hacker News. ADAAD promotes itself.</td>
</tr>
</table>

---

## 📱 Android App — Free

ADAAD ships a free Android companion app for monitoring governed runs, reviewing mutation proposals, and approving roadmap amendments — on the go.

```
.github/workflows/android-free-release.yml
```

Download the latest APK from [GitHub Releases](../../releases/latest).

---

## Pricing

> **Constitutional guarantee:** Every tier runs the identical GovernanceGate and the same 16-rule constitutional policy engine. Paying more buys capacity and tooling — never a weaker gate.

| | **Community** | **Pro** | **Enterprise** |
|---|:---:|:---:|:---:|
| **Price** | Free forever | **$49 / month** | **$499 / month** |
| **Epochs / month** | 50 | 500 | Unlimited |
| **Candidates / epoch** | 3 | 10 | Unlimited |
| **Federation nodes** | — | 3 | Unlimited |
| **Android companion** | ✅ | ✅ | ✅ |
| **Deterministic replay** | ✅ | ✅ | ✅ |
| **Constitutional gating** | ✅ | ✅ | ✅ |
| **Evidence ledger** | ✅ | ✅ | ✅ |
| **Roadmap self-amendment** | — | ✅ | ✅ |
| **Simulation DSL** | — | ✅ | ✅ |
| **Webhook integrations** | — | ✅ | ✅ |
| **Custom constitutional rules** | — | — | ✅ |
| **Dedicated onboarding** | — | — | ✅ |
| **99.9% SLA** | — | — | ✅ |

[→ Full pricing details](PRICING.md)

---

## What's Active Now

> 🔄 This section reflects live repository state. Version, phase, and milestone status are always current.

**Phase 12 — Campaign Blitz v2** is the active distribution expansion lane. New channels: Hashnode, PyPI, additional awesome-list targets, Discord community seeding, and newsletter outreach.

| Milestone | Status | Module |
|:---|:---:|:---|
| M12-01 Hashnode dispatcher | ✅ shipped | `runtime/marketing/dispatchers.py` |
| M12-02 PyPI package registration | ✅ shipped | `pyproject.toml` · `setup.cfg` |
| M12-03 Expanded awesome-list PRs | ✅ shipped | `runtime/marketing/engine.py` |
| M12-04 Discord community targets | ✅ shipped | `runtime/marketing/engine.py` |
| M12-05 Newsletter outreach queue | ✅ shipped | `human_queue/newsletters.md` |
| M12-06 README v3 (this file) | ✅ shipped | `README.md` |

📋 Full roadmap → [`ROADMAP.md`](ROADMAP.md)
🔖 Current version → [`VERSION`](VERSION)

---

## Governance model

ADAAD's governance isn't configuration — it's architecture. The hierarchy is strict and cannot be bypassed:

```
Constitution  →  Architecture Contract  →  ArchitectAgent Spec  →  PR Procession
```

- **[Constitution](docs/CONSTITUTION.md)** — 14 hard rules. Cannot be overridden by any agent, operator, or PR.
- **[Architecture Contract](docs/ARCHITECTURE_CONTRACT.md)** — Interface and boundary invariants across all modules.
- **[ArchitectAgent Spec v3.1.0](docs/governance/ARCHITECT_SPEC_v3.1.0.md)** — Canonical spec for the governance baseline.
- **[PR Procession Plan](docs/governance/ADAAD_PR_PROCESSION_2026-03.md)** — Controlling source for PR order, CI tier, and closure state.

---

## Documentation

| I want to… | Go here |
|---|---|
| 🚀 Run ADAAD for the first time | [Quickstart](QUICKSTART.md) |
| 🧠 Understand the architecture | [Architecture Contract](docs/ARCHITECTURE_CONTRACT.md) |
| 🛡️ Review governance posture | [Security](docs/SECURITY.md) · [Constitution](docs/CONSTITUTION.md) |
| 📦 Ship a governed release | [Release checklist](docs/release/release_checklist.md) |
| 💰 Understand pricing | [PRICING.md](PRICING.md) |
| 📊 See the full docs index | [Docs Hub](docs/README.md) |
| 🤝 Contribute | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## Community & Support

- 💬 **[GitHub Discussions](../../discussions)** — architecture questions, use cases, governance proposals
- 🐛 **[Issues](../../issues)** — bug reports and feature requests (governed triage)
- 📧 **Email** — enterprise@innovativeai.llc (Enterprise inquiries)

---

## About InnovativeAI LLC

**InnovativeAI LLC** is an independent AI research and engineering company based in Blackwell, Oklahoma, USA — focused on building governed, transparent, and production-grade autonomous AI systems.

ADAAD is InnovativeAI's flagship open-source project — a proof-of-concept and operational system demonstrating that autonomous AI development pipelines can be made auditable, deterministic, and constitutionally bound from day one.

**Dustin L. Reid** — Founder of InnovativeAI LLC and sole architect of ADAAD — designed every layer: the multi-agent mutation pipeline, genetic population management, self-calibrating fitness engine, constitutional governance model, federated execution architecture, and the autonomous marketing distribution system.

---

## License

ADAAD is released under the **MIT License**. See [`LICENSE`](LICENSE) for details.

Compliance metadata: [`LICENSES.md`](LICENSES.md) and [`NOTICE`](NOTICE)
Compliance gate: `python scripts/validate_license_compliance.py`

---

<p align="center">
  Built with discipline by <strong>Dustin L. Reid</strong> · <a href="https://github.com/InnovativeAI-adaad">InnovativeAI LLC</a> · Blackwell, Oklahoma
</p>
