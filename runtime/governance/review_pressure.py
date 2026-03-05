# SPDX-License-Identifier: Apache-2.0
"""Tier calibration and constitutional floor enforcement — ADAAD-7.

Translates reviewer reputation scores into adjusted reviewer-count
recommendations per governance tier, subject to constitutional floor
constraints.

Architectural invariants (EPIC_1):
- Reputation adjusts reviewer COUNT only; it never alters authority or
  voting rights.
- Adjustments are bounded by per-tier min/max configured bounds.
- The constitutional floor — at least one human reviewer — is
  architecturally enforced (never a convention).
- Calibration events are emitted as governance-impact ledger events.
- All calibration logic is deterministic and replay-compatible.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from runtime.governance.foundation.canonical import canonical_json_bytes
from runtime.governance.foundation.hashing import sha256_prefixed_digest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CALIBRATION_EVENT_TYPE = "reviewer_tier_calibration"

# The constitutional floor: minimum reviewers regardless of reputation.
# This value is architecturally enforced and cannot be reduced by reputation.
CONSTITUTIONAL_FLOOR_MIN_REVIEWERS = 1

# Default tier configuration: (base_count, min_count, max_count)
# base_count: nominal reviewer count without reputation influence
# min_count: floor bound after reputation reduction (>= CONSTITUTIONAL_FLOOR)
# max_count: ceiling bound after reputation increase
DEFAULT_TIER_CONFIG: Dict[str, Dict[str, int]] = {
    "low": {"base_count": 1, "min_count": 1, "max_count": 2},
    "standard": {"base_count": 2, "min_count": 1, "max_count": 3},
    "critical": {"base_count": 3, "min_count": 2, "max_count": 4},
    "governance": {"base_count": 3, "min_count": 3, "max_count": 5},
}

# Reputation thresholds for count adjustments
# composite_score >= HIGH_THRESHOLD: reduce count by 1 (within min bound)
# composite_score <= LOW_THRESHOLD:  increase count by 1 (within max bound)
HIGH_REPUTATION_THRESHOLD = 0.80
LOW_REPUTATION_THRESHOLD = 0.40


# ---------------------------------------------------------------------------
# Tier config validation
# ---------------------------------------------------------------------------


def validate_tier_config(tier_config: Mapping[str, Mapping[str, int]]) -> Dict[str, Dict[str, int]]:
    """Validate tier configuration map.

    Raises ValueError if any tier violates:
    - min_count >= CONSTITUTIONAL_FLOOR_MIN_REVIEWERS
    - min_count <= base_count <= max_count
    """
    validated: Dict[str, Dict[str, int]] = {}
    for tier, cfg in tier_config.items():
        base = int(cfg["base_count"])
        lo = int(cfg["min_count"])
        hi = int(cfg["max_count"])
        if lo < CONSTITUTIONAL_FLOOR_MIN_REVIEWERS:
            raise ValueError(
                f"tier {tier!r}: min_count={lo} violates constitutional floor "
                f"(minimum {CONSTITUTIONAL_FLOOR_MIN_REVIEWERS})"
            )
        if not (lo <= base <= hi):
            raise ValueError(
                f"tier {tier!r}: requires min_count <= base_count <= max_count; "
                f"got {lo} <= {base} <= {hi}"
            )
        validated[tier] = {"base_count": base, "min_count": lo, "max_count": hi}
    return validated


# ---------------------------------------------------------------------------
# Core calibration function
# ---------------------------------------------------------------------------


def compute_tier_reviewer_count(
    tier: str,
    composite_score: float,
    *,
    tier_config: Mapping[str, Mapping[str, int]] | None = None,
    high_threshold: float = HIGH_REPUTATION_THRESHOLD,
    low_threshold: float = LOW_REPUTATION_THRESHOLD,
) -> Dict[str, Any]:
    """Compute the adjusted reviewer count for ``tier`` given ``composite_score``.

    Returns a calibration record containing:
    - ``tier``
    - ``composite_score`` (input, clamped to [0.0, 1.0])
    - ``base_count``, ``min_count``, ``max_count`` from tier config
    - ``adjusted_count`` — the calibrated reviewer count
    - ``adjustment`` — delta from base (+1, 0, or -1)
    - ``constitutional_floor_enforced`` — always True
    - ``adjustment_reason`` — human-readable reason string
    - ``calibration_digest`` — deterministic digest of the record
    """
    cfg = validate_tier_config(tier_config if tier_config is not None else DEFAULT_TIER_CONFIG)
    if tier not in cfg:
        raise ValueError(f"Unknown tier {tier!r}; configured tiers: {sorted(cfg.keys())}")

    tier_cfg = cfg[tier]
    base = tier_cfg["base_count"]
    lo = tier_cfg["min_count"]
    hi = tier_cfg["max_count"]

    score = max(0.0, min(1.0, float(composite_score)))

    if score >= high_threshold:
        proposed = base - 1
        reason = f"composite_score={score:.4f} >= high_threshold={high_threshold}; count reduced"
    elif score <= low_threshold:
        proposed = base + 1
        reason = f"composite_score={score:.4f} <= low_threshold={low_threshold}; count increased"
    else:
        proposed = base
        reason = f"composite_score={score:.4f} in nominal band; count unchanged"

    # Clamp to [min_count, max_count]
    adjusted = max(lo, min(hi, proposed))

    # Enforce constitutional floor (redundant safety guard)
    if adjusted < CONSTITUTIONAL_FLOOR_MIN_REVIEWERS:
        adjusted = CONSTITUTIONAL_FLOOR_MIN_REVIEWERS
        reason += " [constitutional_floor_applied]"

    adjustment = adjusted - base

    record: Dict[str, Any] = {
        "tier": tier,
        "composite_score": round(score, 6),
        "base_count": base,
        "min_count": lo,
        "max_count": hi,
        "adjusted_count": adjusted,
        "adjustment": adjustment,
        "constitutional_floor_enforced": True,
        "adjustment_reason": reason,
    }
    record["calibration_digest"] = sha256_prefixed_digest(canonical_json_bytes(record))
    return record


def compute_panel_calibration(
    tier_scores: Mapping[str, float],
    *,
    tier_config: Mapping[str, Mapping[str, int]] | None = None,
    high_threshold: float = HIGH_REPUTATION_THRESHOLD,
    low_threshold: float = LOW_REPUTATION_THRESHOLD,
) -> Dict[str, Dict[str, Any]]:
    """Compute calibrated reviewer counts for multiple tiers at once.

    ``tier_scores`` maps tier name → composite_score.
    Returns a mapping of tier → calibration_record.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for tier, score in tier_scores.items():
        results[tier] = compute_tier_reviewer_count(
            tier,
            score,
            tier_config=tier_config,
            high_threshold=high_threshold,
            low_threshold=low_threshold,
        )
    return results


__all__ = [
    "CALIBRATION_EVENT_TYPE",
    "CONSTITUTIONAL_FLOOR_MIN_REVIEWERS",
    "DEFAULT_TIER_CONFIG",
    "HIGH_REPUTATION_THRESHOLD",
    "LOW_REPUTATION_THRESHOLD",
    "validate_tier_config",
    "compute_tier_reviewer_count",
    "compute_panel_calibration",
]
