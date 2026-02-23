#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ADAAD_ROOT="${ADAAD_ROOT:-${DEFAULT_ROOT}}"

# Operational wrapper: provide explicit epoch to deterministic retention evaluator.
NOW_EPOCH="$(date +%s)"

cd "${ADAAD_ROOT}"
PYTHONPATH=. /usr/bin/python3 scripts/enforce_forensic_retention.py \
  --export-dir reports/forensics \
  --retention-days 365 \
  --now-epoch "${NOW_EPOCH}" \
  --enforce
