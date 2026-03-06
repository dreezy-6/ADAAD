# SPDX-License-Identifier: Apache-2.0
"""Fast-path scoring shortcuts for trivial mutation candidates.

Provides deterministic, pre-computed score payloads for mutation categories
where full pipeline execution would be wasteful.  Intended to be called
*before* the heavy ``scoring_algorithm`` pipeline when a
:class:`~runtime.evolution.mutation_route_optimizer.RouteDecision` reports
``skip_heavy_scoring=True``.

Score payloads emitted here are structurally identical to full pipeline
outputs so downstream consumers require no special casing.

Truncation strategy
-------------------
The fast-path skips:
- Static analysis parsing
- LOC complexity weighting
- Risk-tag accumulation
- Fitness evaluator invocation

It always produces deterministic, governance-safe scores by anchoring
to a fixed ``fast_path_score_version`` field that replay verification
can use to confirm fast-path application.
"""

from __future__ import annotations

from typing import Any, Dict

from runtime.governance.foundation.hashing import sha256_prefixed_digest

FAST_PATH_VERSION = "v1.0.0"

# Pre-computed scores for common trivial cases (immutable)
_ZERO_LOC_SCORE: Dict[str, Any] = {
    "score": 0.10,
    "passed_syntax": True,
    "passed_tests": True,
    "passed_constitution": True,
    "performance_delta": 0.0,
    "fast_path_reason": "zero_loc_delta",
    "fast_path_score_version": FAST_PATH_VERSION,
}

_DOC_ONLY_SCORE: Dict[str, Any] = {
    "score": 0.12,
    "passed_syntax": True,
    "passed_tests": True,
    "passed_constitution": True,
    "performance_delta": 0.0,
    "fast_path_reason": "doc_only_ops",
    "fast_path_score_version": FAST_PATH_VERSION,
}

_METADATA_ONLY_SCORE: Dict[str, Any] = {
    "score": 0.11,
    "passed_syntax": True,
    "passed_tests": True,
    "passed_constitution": True,
    "performance_delta": 0.0,
    "fast_path_reason": "metadata_only_ops",
    "fast_path_score_version": FAST_PATH_VERSION,
}


def fast_path_score(
    *,
    mutation_id: str,
    reason: str,
    loc_added: int = 0,
    loc_deleted: int = 0,
) -> Dict[str, Any]:
    """Return a fast-path score payload for a trivial mutation candidate.

    Parameters
    ----------
    mutation_id:
        Stable mutation identifier (used to anchor the score digest).
    reason:
        Short reason token for the fast-path selection
        (e.g., ``"zero_loc_delta"``, ``"doc_only_ops"``).
    loc_added:
        Lines of code added (informational; used in digest).
    loc_deleted:
        Lines of code deleted (informational; used in digest).

    Returns
    -------
    dict
        Score payload with a deterministic ``score_digest`` field.
    """
    base = _select_base_score(reason)
    payload = dict(base)
    payload["mutation_id"] = str(mutation_id)
    payload["loc_added"] = int(loc_added)
    payload["loc_deleted"] = int(loc_deleted)

    # Anchor digest includes mutation-specific fields for replay integrity
    digest_input = {
        "mutation_id": str(mutation_id),
        "score": payload["score"],
        "fast_path_reason": reason,
        "loc_added": int(loc_added),
        "loc_deleted": int(loc_deleted),
        "fast_path_score_version": FAST_PATH_VERSION,
    }
    payload["score_digest"] = sha256_prefixed_digest(digest_input)
    return payload


def _select_base_score(reason: str) -> Dict[str, Any]:
    if "zero_loc" in reason:
        return _ZERO_LOC_SCORE
    if "doc" in reason:
        return _DOC_ONLY_SCORE
    if "metadata" in reason:
        return _METADATA_ONLY_SCORE
    # Default trivial score
    return _ZERO_LOC_SCORE


def is_fast_path_score(score_payload: Dict[str, Any]) -> bool:
    """Return ``True`` if a score payload was produced by the fast-path scorer."""
    return bool(score_payload.get("fast_path_score_version"))


__all__ = [
    "FAST_PATH_VERSION",
    "fast_path_score",
    "is_fast_path_score",
]
