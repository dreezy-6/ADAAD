# SPDX-License-Identifier: Apache-2.0
"""Reviewer reputation scoring engine — ADAAD-7.

Computes a deterministic, epoch-scoped composite reputation score for each
reviewer from a stream of ``reviewer_action_outcome`` ledger events.

Architectural invariants (from EPIC_1_Reviewer_Reputation.md):
- All scoring functions are pure/deterministic; no wall-clock or random calls.
- Epoch weight snapshots are consumed from the ledgered epoch context.
- Weights may not change mid-epoch; changes take effect only at epoch boundary.
- ``scoring_algorithm_version`` is carried on every epoch context and event.
- Replay must bind to the ``scoring_algorithm_version`` active at scoring time.
- Constitutional floor checks are enforced before count adjustments (PR-7-03).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from runtime.governance.foundation.canonical import canonical_json_bytes
from runtime.governance.foundation.hashing import sha256_prefixed_digest

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

SCORING_ALGORITHM_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Default bootstrap weights (EPIC_1 §Initial Weights)
# These are epoch-default values; callers must pass epoch_weights at runtime.
# ---------------------------------------------------------------------------

DEFAULT_EPOCH_WEIGHTS: Dict[str, float] = {
    "latency": 0.20,
    "override_rate": 0.30,
    "long_term_mutation_impact": 0.30,
    "governance_alignment": 0.20,
}

REVIEWER_REPUTATION_EVENT_TYPE = "reviewer_reputation_update"
EPOCH_WEIGHT_SNAPSHOT_EVENT_TYPE = "reviewer_epoch_weight_snapshot"

# Default SLA in seconds (24 h)
_DEFAULT_SLA_SECONDS = 86_400


# ---------------------------------------------------------------------------
# Weight snapshot helpers
# ---------------------------------------------------------------------------


def validate_epoch_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    """Validate and normalise a weight mapping.

    Raises ValueError if any weight is negative or the sum is not
    sufficiently close to 1.0 (tolerance ±0.001).
    """
    required = {"latency", "override_rate", "long_term_mutation_impact", "governance_alignment"}
    missing = required - set(weights.keys())
    if missing:
        raise ValueError(f"epoch_weights missing required dimensions: {sorted(missing)}")
    validated: Dict[str, float] = {}
    for key in required:
        w = float(weights[key])
        if w < 0.0:
            raise ValueError(f"epoch_weights[{key!r}] must be >= 0; got {w}")
        validated[key] = w
    total = sum(validated.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"epoch_weights must sum to 1.0 (±0.001); got {total:.6f}")
    return validated


def snapshot_digest(epoch_id: str, weights: Mapping[str, float]) -> str:
    """Deterministic digest for an epoch weight snapshot."""
    material = {"epoch_id": epoch_id, "weights": dict(sorted(weights.items()))}
    return sha256_prefixed_digest(canonical_json_bytes(material))


# ---------------------------------------------------------------------------
# Per-reviewer dimension scorers (pure functions)
# ---------------------------------------------------------------------------


def _latency_score(latency_seconds: float, sla_seconds: float) -> float:
    """Score in [0.0, 1.0]; 1.0 = instant, 0.0 = 2× SLA or beyond."""
    if sla_seconds <= 0:
        return 1.0
    ratio = max(0.0, latency_seconds) / sla_seconds
    # Linear decay: 0 → 1.0, 1 → 0.5, 2+ → 0.0
    return max(0.0, 1.0 - (ratio * 0.5))


def _override_rate_score(override_count: int, total_decisions: int) -> float:
    """Score in [0.0, 1.0]; higher = fewer overrides (better)."""
    if total_decisions <= 0:
        return 1.0
    rate = override_count / total_decisions
    return max(0.0, 1.0 - rate)


def _impact_score_aggregated(impact_scores: Sequence[float]) -> float:
    """Average of provided long-term mutation impact scores, or 0.5 if none."""
    if not impact_scores:
        return 0.5
    clamped = [max(0.0, min(1.0, s)) for s in impact_scores]
    return sum(clamped) / len(clamped)


def _alignment_score_aggregated(alignment_scores: Sequence[float]) -> float:
    """Average of provided governance alignment scores, or 0.5 if none."""
    if not alignment_scores:
        return 0.5
    clamped = [max(0.0, min(1.0, s)) for s in alignment_scores]
    return sum(clamped) / len(clamped)


# ---------------------------------------------------------------------------
# Core scorer
# ---------------------------------------------------------------------------


def compute_reviewer_reputation(
    reviewer_id: str,
    events: Iterable[Mapping[str, Any]],
    *,
    epoch_id: str,
    epoch_weights: Mapping[str, float] | None = None,
    scoring_algorithm_version: str = SCORING_ALGORITHM_VERSION,
) -> Dict[str, Any]:
    """Compute reputation score for ``reviewer_id`` from ``events`` in ``epoch_id``.

    Only ``reviewer_action_outcome`` events matching ``reviewer_id`` and
    ``epoch_id`` are consumed. All other events are ignored.

    Returns a score record containing:
    - ``reviewer_id``
    - ``epoch_id``
    - ``scoring_algorithm_version``
    - ``epoch_weight_snapshot_digest`` — digest of weights used
    - ``dimension_scores`` — per-dimension breakdown
    - ``composite_score`` — weighted composite in [0.0, 1.0]
    - ``event_count`` — number of events consumed
    - ``score_digest`` — deterministic digest of this score record
    """
    weights = validate_epoch_weights(epoch_weights if epoch_weights is not None else DEFAULT_EPOCH_WEIGHTS)

    latencies: List[float] = []
    slas: List[float] = []
    override_count = 0
    total_decisions = 0
    impact_scores: List[float] = []
    alignment_scores: List[float] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type") or event.get("type") or "")
        if event_type != "reviewer_action_outcome":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if str(payload.get("reviewer_id") or "") != reviewer_id:
            continue
        if str(payload.get("epoch_id") or "") != epoch_id:
            continue

        total_decisions += 1
        latency = float(payload.get("latency_seconds") or 0.0)
        sla = float(payload.get("sla_seconds") or _DEFAULT_SLA_SECONDS)
        latencies.append(latency)
        slas.append(sla)

        if bool(payload.get("overridden_by_authority", False)):
            override_count += 1

        impact = payload.get("long_term_mutation_impact_score")
        if impact is not None:
            impact_scores.append(float(impact))

        alignment = payload.get("governance_alignment_score")
        if alignment is not None:
            alignment_scores.append(float(alignment))

    # Compute per-dimension scores
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    avg_sla = sum(slas) / len(slas) if slas else float(_DEFAULT_SLA_SECONDS)

    dim_latency = round(_latency_score(avg_latency, avg_sla), 6)
    dim_override = round(_override_rate_score(override_count, total_decisions), 6)
    dim_impact = round(_impact_score_aggregated(impact_scores), 6)
    dim_alignment = round(_alignment_score_aggregated(alignment_scores), 6)

    composite = round(
        weights["latency"] * dim_latency
        + weights["override_rate"] * dim_override
        + weights["long_term_mutation_impact"] * dim_impact
        + weights["governance_alignment"] * dim_alignment,
        6,
    )
    composite = max(0.0, min(1.0, composite))

    weight_digest = snapshot_digest(epoch_id, weights)

    score_record: Dict[str, Any] = {
        "reviewer_id": reviewer_id,
        "epoch_id": epoch_id,
        "scoring_algorithm_version": scoring_algorithm_version,
        "epoch_weight_snapshot_digest": weight_digest,
        "dimension_scores": {
            "latency": dim_latency,
            "override_rate": dim_override,
            "long_term_mutation_impact": dim_impact,
            "governance_alignment": dim_alignment,
        },
        "composite_score": composite,
        "event_count": total_decisions,
        "override_count": override_count,
    }

    # Compute deterministic digest over the score record (excluding score_digest itself)
    score_record["score_digest"] = sha256_prefixed_digest(canonical_json_bytes(score_record))
    return score_record


def compute_epoch_reputation_batch(
    reviewer_ids: Iterable[str],
    events: Iterable[Mapping[str, Any]],
    *,
    epoch_id: str,
    epoch_weights: Mapping[str, float] | None = None,
    scoring_algorithm_version: str = SCORING_ALGORITHM_VERSION,
) -> Dict[str, Dict[str, Any]]:
    """Compute reputation scores for multiple reviewers in one epoch pass.

    Materialises the events iterable once, then scores each reviewer.
    Returns a mapping of reviewer_id → score_record.
    """
    materialized = list(events)
    results: Dict[str, Dict[str, Any]] = {}
    for reviewer_id in reviewer_ids:
        results[reviewer_id] = compute_reviewer_reputation(
            reviewer_id,
            materialized,
            epoch_id=epoch_id,
            epoch_weights=epoch_weights,
            scoring_algorithm_version=scoring_algorithm_version,
        )
    return results


__all__ = [
    "SCORING_ALGORITHM_VERSION",
    "DEFAULT_EPOCH_WEIGHTS",
    "REVIEWER_REPUTATION_EVENT_TYPE",
    "EPOCH_WEIGHT_SNAPSHOT_EVENT_TYPE",
    "validate_epoch_weights",
    "snapshot_digest",
    "compute_reviewer_reputation",
    "compute_epoch_reputation_batch",
]
