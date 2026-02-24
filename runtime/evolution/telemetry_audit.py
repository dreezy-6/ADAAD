# SPDX-License-Identifier: Apache-2.0
"""Epoch telemetry audit helpers for entropy governance observability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable

from runtime.evolution.lineage_v2 import LineageLedgerV2


def compute_epoch_entropy_breakdown(epoch_id: str, events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute deterministic declared/observed entropy totals for epoch events."""

    declared_total = 0
    observed_total = 0
    event_count = 0
    source_totals: dict[str, int] = {"runtime_rng": 0, "runtime_clock": 0, "external_io": 0}

    for entry in events:
        if str(entry.get("type") or "") != "PromotionEvent":
            continue
        payload = dict((entry.get("payload") or {}).get("payload") or {})
        event_count += 1

        declared_bits = max(0, int(payload.get("entropy_declared_bits", 0) or 0))
        observed_bits = max(0, int(payload.get("entropy_observed_bits", 0) or 0))

        declared_total += declared_bits
        observed_total += observed_bits

        raw_sources = payload.get("entropy_observed_sources") or []
        normalized_sources = tuple(sorted({str(item).strip().lower() for item in raw_sources if str(item).strip()}))
        for source in normalized_sources:
            source_totals[source] = source_totals.get(source, 0) + observed_bits

    overflow_total = max(0, observed_total - declared_total)
    return {
        "epoch_id": epoch_id,
        "event_count": event_count,
        "declared_total": declared_total,
        "observed_total": observed_total,
        "overflow_total": overflow_total,
        "source_totals": source_totals,
    }


def epoch_entropy_summary(epoch_id: str, ledger: LineageLedgerV2 | None = None) -> Dict[str, Any]:
    """HTTP-friendly deterministic entropy summary for a single epoch."""

    runtime_ledger = ledger or LineageLedgerV2()
    events = runtime_ledger.read_epoch(epoch_id)
    breakdown = compute_epoch_entropy_breakdown(epoch_id, events)
    return {
        "epoch_id": breakdown["epoch_id"],
        "event_count": int(breakdown["event_count"]),
        "declared_total": int(breakdown["declared_total"]),
        "observed_total": int(breakdown["observed_total"]),
        "overflow_total": int(breakdown["overflow_total"]),
        "source_totals": dict(sorted(breakdown["source_totals"].items())),
    }


def get_epoch_entropy_breakdown(epoch_id: str, ledger: LineageLedgerV2 | None = None) -> Dict[str, Any]:
    """Return declared/observed entropy aggregates for an epoch."""

    summary = epoch_entropy_summary(epoch_id, ledger=ledger)
    return {
        "epoch_id": summary["epoch_id"],
        "event_count": summary["event_count"],
        "declared_bits": summary["declared_total"],
        "observed_bits": summary["observed_total"],
        "total_bits": summary["declared_total"] + summary["observed_total"],
        "observed_sources": summary["source_totals"],
    }


def get_epoch_entropy_envelope_summary(epoch_id: str, ledger: LineageLedgerV2 | None = None) -> Dict[str, Any]:
    """Return envelope-unit entropy usage summary for governance decisions in an epoch."""

    runtime_ledger = ledger or LineageLedgerV2()
    decision_events = 0
    accepted = 0
    rejected = 0
    overflow_count = 0
    consumed_total = 0
    consumed_max = 0
    budgets: list[int] = []

    for entry in runtime_ledger.read_epoch(epoch_id):
        event_type = str(entry.get("type") or "")
        if event_type not in {"GovernanceDecisionEvent", "MutationBundleEvent"}:
            continue
        payload = dict(entry.get("payload") or {})
        if "entropy_consumed" not in payload:
            continue

        decision_events += 1
        accepted_flag = bool(payload.get("accepted", event_type == "MutationBundleEvent"))
        if accepted_flag:
            accepted += 1
        else:
            rejected += 1

        consumed = max(0, int(payload.get("entropy_consumed", 0) or 0))
        budget = max(0, int(payload.get("entropy_budget", 0) or 0))
        overflow = bool(payload.get("entropy_overflow", False))

        consumed_total += consumed
        consumed_max = max(consumed_max, consumed)
        budgets.append(budget)
        if overflow:
            overflow_count += 1

    avg_consumed = float(consumed_total / decision_events) if decision_events else 0.0
    avg_budget = float(sum(budgets) / len(budgets)) if budgets else 0.0
    return {
        "epoch_id": epoch_id,
        "decision_events": decision_events,
        "accepted": accepted,
        "rejected": rejected,
        "overflow_count": overflow_count,
        "consumed_total": consumed_total,
        "consumed_max": consumed_max,
        "consumed_avg": avg_consumed,
        "budget_avg": avg_budget,
    }


def detect_entropy_drift(
    lookback_epochs: int = 10,
    ledger: LineageLedgerV2 | None = None,
    *,
    min_decisions_per_epoch: int = 1,
    drift_threshold: float = 1.3,
) -> Dict[str, Any]:
    """Detect trend drift in envelope entropy consumption across recent epochs."""

    runtime_ledger = ledger or LineageLedgerV2()
    epoch_ids = runtime_ledger.list_epoch_ids()
    if lookback_epochs > 0:
        epoch_ids = epoch_ids[-lookback_epochs:]

    samples = [get_epoch_entropy_envelope_summary(epoch_id, ledger=runtime_ledger) for epoch_id in epoch_ids]
    filtered = [item for item in samples if int(item.get("decision_events", 0)) >= int(min_decisions_per_epoch)]

    consumed_avgs = [float(item["consumed_avg"]) for item in filtered]
    if len(consumed_avgs) < 3:
        return {
            "drift_detected": False,
            "reason": "insufficient_data",
            "sample_count": len(consumed_avgs),
            "epochs_considered": epoch_ids,
        }

    baseline_window = consumed_avgs[: min(3, len(consumed_avgs))]
    recent_window = consumed_avgs[-min(3, len(consumed_avgs)) :]

    baseline_mean = float(mean(baseline_window))
    recent_mean = float(mean(recent_window))
    denominator = baseline_mean if baseline_mean > 0 else 1.0
    drift_ratio = float(recent_mean / denominator)
    drift_detected = drift_ratio > float(drift_threshold)

    return {
        "drift_detected": drift_detected,
        "drift_ratio": drift_ratio,
        "baseline_mean": baseline_mean,
        "recent_mean": recent_mean,
        "threshold": float(drift_threshold),
        "sample_count": len(consumed_avgs),
        "epochs_considered": epoch_ids,
        "recommendation": "investigate_entropy_regression" if drift_detected else "stable",
    }


def _profile_entropy_baseline(out: Path, ledger: LineageLedgerV2 | None = None) -> Dict[str, Any]:
    runtime_ledger = ledger or LineageLedgerV2()
    epoch_ids = runtime_ledger.list_epoch_ids()
    overflow_total = 0
    for epoch_id in epoch_ids:
        overflow_total += int(epoch_entropy_summary(epoch_id, ledger=runtime_ledger)["overflow_total"])
    drift = detect_entropy_drift(ledger=runtime_ledger)
    report = {
        "epoch_count": len(epoch_ids),
        "overflow_total": overflow_total,
        "drift_detected": bool(drift.get("drift_detected", False)),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return report


def _main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic entropy baseline artifact")
    parser.add_argument("--out", required=True, help="output artifact path")
    args = parser.parse_args()

    report = _profile_entropy_baseline(Path(args.out))
    if int(report.get("overflow_total", 0)) > 0:
        return 2
    if bool(report.get("drift_detected", False)):
        return 3
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())


__all__ = [
    "compute_epoch_entropy_breakdown",
    "epoch_entropy_summary",
    "get_epoch_entropy_breakdown",
    "get_epoch_entropy_envelope_summary",
    "detect_entropy_drift",
]
