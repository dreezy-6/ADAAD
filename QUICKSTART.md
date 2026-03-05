# ADAAD Quick Start

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)
![Replay: Deterministic](https://img.shields.io/badge/Replay-Deterministic-0ea5e9)

> Fastest path to a working, governed ADAAD run — validated, reproducible, fail-closed.

**Last reviewed:** 2026-03-05

> ✅ **Do this:** Execute the numbered steps in order. Run `./quickstart.sh` as your first confidence check.
>
> ⚠️ **Caveat:** Strict replay checks may fail on first-time local state until replay artifacts stabilize.
>
> 🚫 **Out of scope:** This guide does not cover unattended production deployment hardening.

---

## What success looks like

```bash
./quickstart.sh
```

Validates schemas, runs a deterministic simulation sample, checks founders-law/federation tests, and prints the dashboard start command.

Then run the governed dry-run:

```bash
python -m app.main --dry-run --replay audit --verbose
```

Expected output signals:

```text
[ADAAD] Starting governance spine initialization
[ADAAD] Replay decision: audit
[DREAM] Candidate discovery complete
[GOVERNANCE] constitution: pass
[MUTATION] dry-run only, no files modified
```

---

## Prerequisites

- Python 3.11+
- `pip`
- `git`

```bash
python --version && pip --version && git --version
```

---

## Setup Steps

### 1 — Clone

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
```

### 2 — Virtual environment

macOS / Linux:
```bash
python -m venv .venv && source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv && .\.venv\Scripts\Activate.ps1
```

### 3 — Install dependencies

```bash
pip install -r requirements.server.txt
```

Constrained environment:
```bash
pip install -r requirements.server.txt --no-cache-dir
```

### 4 — Initialize workspace

```bash
python nexus_setup.py
python nexus_setup.py --validate-only        # read-only preflight
python nexus_setup.py --validate-only --json # machine-readable output
```

### 5 — Verify boot

```bash
python -m app.main --replay audit --verbose
```

| Signal | Meaning |
|---|---|
| Boot + replay present, mutation disabled | Environment healthy; no eligible staged work |
| Boot + replay present, mutation enabled | System ready for governed mutation flow |
| Replay divergence or policy rejection | Expected fail-closed behavior; inspect logs |

---

## Governance boot-critical artifacts

These files must exist and parse cleanly before ADAAD can boot:

- `runtime/governance/constitution.yaml`
- `governance/rule_applicability.yaml`

Missing or malformed → ADAAD halts with a constitutional initialization error.

---

## Hermetic runtime (audit / strict replay)

```bash
export ADAAD_FORCE_DETERMINISTIC_PROVIDER=1
export ADAAD_DETERMINISTIC_SEED=ci-strict-replay
export ADAAD_DISABLE_MUTABLE_FS=1
export ADAAD_DISABLE_NETWORK=1
```

Full variable reference: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)

---

## Optional: strict replay mode

```bash
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 \
ADAAD_FORCE_DETERMINISTIC_PROVIDER=1 \
ADAAD_DETERMINISTIC_SEED=ci-strict-replay \
  python -m app.main --verify-replay --replay strict --verbose
```

On first-time setup: run audit mode first to establish a baseline before switching to strict.

---

## Launch the dashboard

```bash
scripts/run_dashboard.sh
# or
python server.py --host 0.0.0.0 --port 8000 --reload
```

- Dashboard UI: `http://127.0.0.1:8000/`
- API health: `http://127.0.0.1:8000/api/health`

UI resolution order: `ui/aponi/index.html` → `ui/enhanced/enhanced_dashboard.html` → auto-generated placeholder.

---

## Quick health checks

```bash
# Recent telemetry
python - <<'PY'
from pathlib import Path
p = Path('reports/metrics.jsonl')
print('metrics_exists=', p.exists())
if p.exists():
    print('\n'.join(p.read_text(encoding='utf-8').splitlines()[-3:]))
PY

# Replay audit
python -m app.main --verify-replay --replay audit --verbose

# Dashboard reachability
curl -sS http://127.0.0.1:8000/state | python -m json.tool
```

---

## Clean reset

macOS / Linux:
```bash
rm -rf reports security/ledger security/replay_manifests
python nexus_setup.py
python nexus_setup.py --validate-only
```

Windows (PowerShell):
```powershell
Remove-Item -Recurse -Force reports, security\ledger, security\replay_manifests
python nexus_setup.py
python nexus_setup.py --validate-only
```

---

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `ModuleNotFoundError` | Re-activate venv: `source .venv/bin/activate && pip install -r requirements.server.txt` |
| Strict replay fails | Run audit mode first to establish baseline: `python -m app.main --replay audit --verbose` |
| Policy rejection appears | Expected fail-closed behavior. Re-run with `--verbose` and review rejection reason. |
| Dashboard unreachable | Confirm server started: `curl -sS http://127.0.0.1:8000/state` |
| Boot exits quickly | Use `--verbose` to see stage-by-stage completion |

---

## Next steps

- [Repository overview](README.md)
- [Single-agent example](examples/single-agent-loop/README.md)
- [Governance model](docs/CONSTITUTION.md)
- [Security and key handling](docs/SECURITY.md)
- [Release checklist](docs/release/release_checklist.md)

---

## Optional: UX-first first run

```bash
python tools/interactive_onboarding.py
python tools/enhanced_cli.py --replay audit --verbose
```

Enhanced dashboard:
```bash
python -m http.server 8081 --directory ui/enhanced
# open http://localhost:8081/enhanced_dashboard.html
```
