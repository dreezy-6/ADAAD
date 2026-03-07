<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="900" alt="ADAAD — Autonomous Development & Adaptation Architecture"/>
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg"/>
  </a>
  <img alt="Version" src="https://img.shields.io/badge/version-3.1.0--dev-00d4ff?style=flat-square&labelColor=060d14"/>
  <img alt="Phase" src="https://img.shields.io/badge/phase-6%20active-f59e0b?style=flat-square&labelColor=060d14"/>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-7b61ff?style=flat-square&labelColor=060d14"/>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square&labelColor=060d14"/>
  <img alt="Android" src="https://img.shields.io/badge/android-free-3ddc84?style=flat-square&labelColor=060d14"/>
  <img alt="Governance" src="https://img.shields.io/badge/governance-fail--closed-ef4444?style=flat-square&labelColor=060d14"/>
</p>

<p align="center">
  <strong>Self-improving software. Governed at every step.</strong><br/>
  ADAAD proposes, tests, scores, and evolves code mutations — with deterministic replay,<br/>
  constitutional gating, and a full audit trail. Nothing executes without proof.
</p>

---

## What ADAAD does

ADAAD is an **autonomous mutation engine**: AI agents continuously propose code improvements, which are scored by a genetic algorithm population, gated by a constitutional policy engine, and applied only when every deterministic check passes. If anything fails — replay divergence, policy rejection, missing evidence — **the pipeline halts completely**.

<p align="center">
  <img src="docs/assets/adaad-flow.svg" width="860" alt="ADAAD mutation pipeline"/>
</p>

The pipeline never advances past a failed step. No exceptions. No workarounds.

---

## Three agents. One governed loop.

<p align="center">
  <img src="docs/assets/adaad-agents.svg" width="680" alt="ADAAD agent personas"/>
</p>

Each epoch, all three agents propose mutations. Their proposals compete in a genetic-algorithm population — scored, crossed-over, and ranked. The fittest survive. Scoring weights self-calibrate across epochs via momentum gradient descent.

---

## ⚡ Start in 60 seconds

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py
```

> **Requirements:** Python 3.11+ · pip · git

`onboard.py` handles everything: environment setup, workspace init, schema validation, and a governed dry-run. Every step is idempotent — run it again at any time.

<details>
<summary>What onboarding does, step by step</summary>

```
onboard.py
  │
  ├─ 1. Check Python 3.11+
  ├─ 2. Create .venv + install deps
  ├─ 3. Set ADAAD_ENV=dev (safe default)
  ├─ 4. Initialize workspace (nexus_setup.py)
  ├─ 5. Validate governance schemas
  ├─ 6. Run governed dry-run
  │      python -m app.main --dry-run --replay audit
  └─ 7. Print your personalized next steps
```

After a successful onboard:

```
✔ Python 3.12.3
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

---

## Platform capabilities

| | Capability | What it means |
|---|---|---|
| 🔁 | **Deterministic replay** | Every decision re-runs byte-identical. Divergence halts the pipeline. |
| 🛡️ | **Constitutional gating** | 16 governance rules evaluated per mutation. One blocking failure = full halt. |
| 🧾 | **Ledger-anchored evidence** | Every governed step is signed, hashed, and durably attached. |
| 🤖 | **AI mutation proposals** | Three Claude-powered agents produce diverse, scored candidates each epoch. |
| 📈 | **Self-calibrating weights** | Scoring weights adapt via momentum gradient descent across epochs. |
| 🧬 | **Genetic population evolution** | BLX-alpha crossover, elitism, diversity enforcement per generation. |
| 🗺️ | **Fitness landscape memory** | Win/loss rates tracked per mutation type. Plateau triggers exploration mode. |
| 🧪 | **Policy simulation** | Replay historical epochs under hypothetical constraints — zero side-effects. |
| 🐳 | **Container isolation** | cgroup v2 sandboxes — pool-managed, health-probed, lifecycle-audited. |
| 🌐 | **Multi-node federation** | Cross-repo mutations with constitutional dual-gate enforcement (v3.0.0). |
| 📝 | **Roadmap self-amendment** | The engine proposes changes to its own roadmap. Humans approve. (v3.1.0-dev) |

---

## What's active: v3.1.0-dev (Phase 6)

Phase 6 — **Autonomous Roadmap Self-Amendment** — is now active.

| Milestone | Status | Module |
|---|---|---|
| M6-01 `RoadmapAmendmentEngine` | ✅ shipped | `runtime/autonomy/roadmap_amendment_engine.py` |
| M6-02 `ProposalDiffRenderer` | ✅ shipped | `runtime/autonomy/proposal_diff_renderer.py` |
| M6-03 EvolutionLoop wire | 🔵 PR-PHASE6-02 | `runtime/autonomy/loop.py` |
| M6-04 Federated propagation | 🔵 PR-PHASE6-03 | `runtime/governance/federation/mutation_broker.py` |
| M6-05 Android distribution | 🟡 active | `.github/workflows/android-free-release.yml` |

**Constitutional principle:** ADAAD proposes. Humans approve. The roadmap never self-promotes without a human governor sign-off recorded in the governance ledger.

<details>
<summary>Phase history</summary>

| Version | Phase | Capability |
|---|---|---|
| **v3.1.0-dev** | 6 | Roadmap Self-Amendment · Free Android Distribution |
| **v3.0.0** | 5 | Multi-Repo Federation — dual-gate, `FederatedEvidenceMatrix`, HMAC key registry |
| **v2.3.0** | 4 | AST-aware semantic scoring (`SemanticDiffEngine`) + pipeline fast-path primitives |
| **v2.2.0** | 4 | `MutationRouteOptimizer`, `EntropyFastGate`, `ParallelGovernanceGate` |
| **v2.1.0** | 3 | Adaptive penalty weights · Thompson sampling · `WeightAdaptor` Phase 2 |
| **v2.0.0** | 2 | AI mutation engine · UCB1 bandit · epoch telemetry · MCP pipeline tools |
| v1.8 | — | Market × federation × container × Darwinian unified |
| v1.7 | — | Fully autonomous multi-node federation — Raft consensus, gossip |
| v1.6 | — | Real container-level isolation — cgroup v2, orchestrator, health probes |
| v1.0 | — | Stable release — HMAC, 11 constitutional rules, MCP co-pilot |

</details>

---

## 📲 Android App — Free

> No Play Store account required. No fee. Installs like any normal app.

<table>
<tr>
<td width="50%" valign="top">

**⚡ Fastest — Direct APK**

1. Open the [**Releases page →**](../../releases/latest)
2. Tap `adaad-community-*.apk` to download
3. Tap the download → **Install**
4. If prompted: *Allow from this source* → Install

</td>
<td width="50%" valign="top">

**🏆 Recommended — Obtainium (auto-updates)**

1. Install [Obtainium](https://github.com/ImranR98/Obtainium/releases)
2. Tap **+** → paste `github.com/InnovativeAI-adaad/ADAAD`
3. Tap **Save** → **Install**
4. Updates install automatically

</td>
</tr>
<tr>
<td valign="top">

**🌐 No download — Web App (PWA)**

1. Open Chrome on Android
2. Visit `https://innovativeai-adaad.github.io/ADAAD/`
3. ⋮ → **Add to Home screen** → Add

</td>
<td valign="top">

**📦 F-Droid (reproducible builds)**

1. F-Droid → Settings → Repositories → **+**
2. Paste `https://innovativeai-adaad.github.io/adaad-fdroid/repo`
3. Refresh → search *ADAAD* → Install

</td>
</tr>
</table>

📱 **On your phone?** → [**One-tap install page**](https://innovativeai-adaad.github.io/ADAAD/install) has QR codes for every method.

🔐 **Verify integrity:** `apksigner verify --print-certs adaad-community-*.apk`

> Android 8.0+ required · Full guide: [INSTALL_ANDROID.md](INSTALL_ANDROID.md) · Launch playbook: [DISTRIBUTION.md](DISTRIBUTION.md)

---

## The authority invariant

> **One authority. No exceptions.**

`GovernanceGate` is the **only** surface that can approve, sign, or execute a mutation. Market adapters, budget arbitrators, container profilers, and federation consensus all influence fitness scores and resource allocation — but none of them can approve a mutation. That authority belongs exclusively to the constitutional evaluation inside `GovernanceGate`. This is architecturally enforced, not just documented.

---

## Configuration

| Variable | What it does | Required |
|---|---|---|
| `ADAAD_ENV` | Environment mode. Unknown values halt at boot. | Always |
| `ADAAD_CLAUDE_API_KEY` | Anthropic API key for AI mutation proposals. | For AI mode |
| `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` | HMAC signing key. Required in strict environments. | Production |
| `ADAAD_AMENDMENT_TRIGGER_INTERVAL` | Epochs between roadmap amendment evaluations. Default: `10`. | Phase 6 |
| `ADAAD_FEDERATION_HMAC_KEY` | Key material for federated mutation transport. Absent = fail-closed. | Federation |
| `CRYOVANT_DEV_MODE` | Enables dev-only overrides. Rejected in strict envs. | No |

Full reference: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)

---

## Where to go next

| I want to… | Start here |
|---|---|
| Try it in 60 seconds | `python onboard.py` |
| Install on Android | [INSTALL_ANDROID.md](INSTALL_ANDROID.md) |
| Understand the architecture | [docs/EVOLUTION_ARCHITECTURE.md](docs/EVOLUTION_ARCHITECTURE.md) |
| Read the governance constitution | [docs/CONSTITUTION.md](docs/CONSTITUTION.md) |
| Review the canonical spec | [docs/governance/ARCHITECT_SPEC_v3.1.0.md](docs/governance/ARCHITECT_SPEC_v3.1.0.md) |
| Contribute code | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Audit a release | [docs/comms/claims_evidence_matrix.md](docs/comms/claims_evidence_matrix.md) |
| Review the security posture | [docs/SECURITY.md](docs/SECURITY.md) |
| Deploy to production | [docs/release/release_checklist.md](docs/release/release_checklist.md) |
| Distribute the Android app | [DISTRIBUTION.md](DISTRIBUTION.md) |

---

## Non-goals

ADAAD does not: replace human judgment · guarantee semantic correctness · remove required oversight · operate without an audit trail.

---

<!-- ADAAD_VERSION_INFOBOX:START -->
<!-- Auto-generated by scripts/sync_docs_on_merge.py — do not edit manually -->

| Field | Value |
|---|---|
| **Current version** | `3.1.0-dev` |
| **Released** | 2026-03-07 |
| **Git SHA** | `9e4e91d` |
| **Branch** | `main` |

**New in this release:** Phase 6 — Autonomous Roadmap Self-Amendment · ArchitectAgent Spec v3.1.0 · Free Android Distribution

<!-- ADAAD_VERSION_INFOBOX:END -->

---

<p align="center">
  <a href="docs/governance/ARCHITECT_SPEC_v3.1.0.md">Spec v3.1.0</a> ·
  <a href="docs/CONSTITUTION.md">Constitution</a> ·
  <a href="docs/EVOLUTION_ARCHITECTURE.md">Architecture</a> ·
  <a href="ROADMAP.md">Roadmap</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="INSTALL_ANDROID.md">Android</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="docs/SECURITY.md">Security</a>
</p>

<p align="center">
  <sub>MIT License · <a href="LICENSE">LICENSE</a></sub>
</p>
