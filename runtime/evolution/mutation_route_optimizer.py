# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation route optimizer for staged evaluation pipelines.

Classifies mutations into three evaluation tiers before any scoring work begins,
enabling fast-path truncation for trivial changes and elevated scrutiny routing
for high-risk mutations.

Routing tiers
-------------
TRIVIAL
    Zero code-change mutations (doc-only, metadata, lineage bookkeeping).
    Fast-path: skip heavy scoring, return pre-computed minimal score.

STANDARD
    Normal mutations within established risk bounds.
    Default evaluation pipeline applies.

ELEVATED
    Mutations touching governance, security, replay, or ledger paths.
    Extended evaluation: full scoring + additional axis checks + human review flag.

All routing decisions are deterministic given identical inputs and are journaled
as ``mutation_route_decision`` ledger events for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Mapping, Sequence

from runtime.governance.foundation.canonical import canonical_json
from runtime.governance.foundation.hashing import sha256_prefixed_digest

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

ROUTE_VERSION = "v1.0.0"

#: File path prefixes that automatically escalate to ELEVATED tier.
ELEVATED_PATH_PREFIXES: FrozenSet[str] = frozenset(
    {
        "runtime/governance/",
        "runtime/evolution/replay",
        "security/",
        "runtime/evolution/lineage",
        "runtime/governance/gate",
        "runtime/founders_law",
        "governance/",
        "runtime/evolution/mutation_ledger",
        "runtime/evolution/checkpoint",
    }
)

#: Intent keywords that escalate to ELEVATED tier.
ELEVATED_INTENT_KEYWORDS: FrozenSet[str] = frozenset(
    {
        "governance",
        "ledger",
        "replay",
        "cryovant",
        "constitution",
        "security",
        "lineage",
        "founders_law",
        "key_rotation",
    }
)

#: Op types that are safe for TRIVIAL routing when no code paths are touched.
TRIVIAL_OP_TYPES: FrozenSet[str] = frozenset(
    {
        "doc_update",
        "comment_update",
        "metadata_update",
        "lineage_annotation",
        "version_bump",
    }
)


# ---------------------------------------------------------------------------
# Routing tier
# ---------------------------------------------------------------------------


class RouteTier(str, Enum):
    """Evaluation pipeline tier for a mutation candidate."""

    TRIVIAL = "TRIVIAL"
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"


# ---------------------------------------------------------------------------
# Route decision dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteDecision:
    """Deterministic routing decision for a single mutation candidate.

    Attributes
    ----------
    mutation_id:
        Stable identifier for the candidate mutation.
    tier:
        Assigned evaluation tier.
    reasons:
        Ordered tuple of rule IDs that contributed to the tier assignment.
    skip_heavy_scoring:
        When ``True`` the scorer should return a pre-computed trivial score
        without executing the full scoring pipeline.
    require_human_review:
        When ``True`` the governance gate MUST surface a human review request
        regardless of automated pass/fail outcome.
    decision_digest:
        Canonical sha256 digest of the decision payload for ledger journaling.
    route_version:
        Version string for this routing algorithm (aids deterministic replay).
    """

    mutation_id: str
    tier: RouteTier
    reasons: tuple[str, ...]
    skip_heavy_scoring: bool
    require_human_review: bool
    decision_digest: str
    route_version: str = ROUTE_VERSION

    def to_payload(self) -> Dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "tier": self.tier.value,
            "reasons": list(self.reasons),
            "skip_heavy_scoring": self.skip_heavy_scoring,
            "require_human_review": self.require_human_review,
            "decision_digest": self.decision_digest,
            "route_version": self.route_version,
        }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class MutationRouteOptimizer:
    """Classify a mutation candidate into an evaluation tier deterministically.

    Usage
    -----
    >>> optimizer = MutationRouteOptimizer()
    >>> decision = optimizer.route(
    ...     mutation_id="mut_abc123",
    ...     intent="doc_update",
    ...     ops=[{"type": "doc_update", "target": "README.md"}],
    ...     files_touched=["README.md"],
    ...     loc_added=5,
    ...     loc_deleted=2,
    ... )
    >>> decision.tier
    <RouteTier.TRIVIAL: 'TRIVIAL'>
    """

    def route(
        self,
        *,
        mutation_id: str,
        intent: str,
        ops: Sequence[Mapping[str, Any]],
        files_touched: Sequence[str] = (),
        loc_added: int = 0,
        loc_deleted: int = 0,
        risk_tags: Sequence[str] = (),
    ) -> RouteDecision:
        """Compute a deterministic tier assignment for a mutation candidate.

        Parameters
        ----------
        mutation_id:
            Stable mutation identifier.
        intent:
            Declared mutation intent string (e.g., ``"refactor"``, ``"doc_update"``).
        ops:
            Sequence of mutation operation descriptors.
        files_touched:
            File paths affected by this mutation.
        loc_added:
            Lines of code added.
        loc_deleted:
            Lines of code deleted.
        risk_tags:
            Explicit risk tags from the mutation request.
        """
        reasons: list[str] = []
        tier = RouteTier.STANDARD

        # ── ELEVATED checks (highest precedence) ──────────────────────────
        elevated = self._check_elevated(
            intent=intent,
            ops=ops,
            files_touched=files_touched,
            risk_tags=risk_tags,
            reasons=reasons,
        )
        if elevated:
            tier = RouteTier.ELEVATED

        # ── TRIVIAL checks (only if not already elevated) ─────────────────
        if tier is RouteTier.STANDARD:
            trivial = self._check_trivial(
                intent=intent,
                ops=ops,
                files_touched=files_touched,
                loc_added=loc_added,
                loc_deleted=loc_deleted,
                reasons=reasons,
            )
            if trivial:
                tier = RouteTier.TRIVIAL

        if not reasons:
            reasons.append("default_standard_route")

        skip_heavy = tier is RouteTier.TRIVIAL
        require_human = tier is RouteTier.ELEVATED

        # Build canonical digest over the decision inputs so downstream
        # ledger entries can reference this decision deterministically.
        digest_payload = {
            "mutation_id": str(mutation_id),
            "intent": str(intent),
            "tier": tier.value,
            "reasons": sorted(reasons),
            "loc_added": int(loc_added),
            "loc_deleted": int(loc_deleted),
            "route_version": ROUTE_VERSION,
        }
        decision_digest = sha256_prefixed_digest(digest_payload)

        return RouteDecision(
            mutation_id=str(mutation_id),
            tier=tier,
            reasons=tuple(sorted(reasons)),
            skip_heavy_scoring=skip_heavy,
            require_human_review=require_human,
            decision_digest=decision_digest,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_elevated(
        *,
        intent: str,
        ops: Sequence[Mapping[str, Any]],
        files_touched: Sequence[str],
        risk_tags: Sequence[str],
        reasons: list[str],
    ) -> bool:
        elevated = False

        intent_lower = str(intent or "").lower()
        for kw in ELEVATED_INTENT_KEYWORDS:
            if kw in intent_lower:
                reasons.append(f"elevated_intent:{kw}")
                elevated = True
                break

        for path in files_touched:
            path_str = str(path or "")
            for prefix in ELEVATED_PATH_PREFIXES:
                if path_str.startswith(prefix):
                    reasons.append(f"elevated_path:{prefix}")
                    elevated = True
                    break

        for tag in risk_tags:
            tag_upper = str(tag or "").upper()
            if tag_upper in {"SECURITY", "CRITICAL", "HIGH"}:
                reasons.append(f"elevated_risk_tag:{tag_upper}")
                elevated = True

        for op in ops:
            op_type = str((op or {}).get("type") or "").lower()
            if "governance" in op_type or "ledger" in op_type or "constitution" in op_type:
                reasons.append(f"elevated_op_type:{op_type}")
                elevated = True

        return elevated

    @staticmethod
    def _check_trivial(
        *,
        intent: str,
        ops: Sequence[Mapping[str, Any]],
        files_touched: Sequence[str],
        loc_added: int,
        loc_deleted: int,
        reasons: list[str],
    ) -> bool:
        # Zero-change mutations are always trivial
        if loc_added == 0 and loc_deleted == 0:
            reasons.append("trivial_zero_loc_delta")
            return True

        # All ops must be trivial types
        op_types = {str((op or {}).get("type") or "").lower() for op in ops}
        if op_types and op_types.issubset({t.lower() for t in TRIVIAL_OP_TYPES}):
            # No touched file may be a source module
            non_source = all(
                not str(p).endswith(".py")
                and not str(p).endswith(".yaml")
                and not str(p).endswith(".json")
                for p in files_touched
            )
            if non_source:
                reasons.append("trivial_doc_or_metadata_ops_only")
                return True

        intent_lower = str(intent or "").lower()
        if intent_lower in {"doc_update", "comment_update", "metadata_update"}:
            if loc_added + loc_deleted <= 20:
                reasons.append("trivial_intent_small_delta")
                return True

        return False


# ---------------------------------------------------------------------------
# Convenience fast-path score for TRIVIAL mutations
# ---------------------------------------------------------------------------


def trivial_route_score() -> Dict[str, Any]:
    """Return a pre-computed deterministic score for TRIVIAL-tier mutations.

    Callers should apply this score directly, bypassing the heavy scoring
    pipeline, when ``RouteDecision.skip_heavy_scoring`` is ``True``.
    """
    return {
        "score": 0.15,
        "tier": RouteTier.TRIVIAL.value,
        "passed_syntax": True,
        "passed_tests": True,
        "passed_constitution": True,
        "performance_delta": 0.0,
        "route_version": ROUTE_VERSION,
        "fast_path": True,
    }


__all__ = [
    "ELEVATED_INTENT_KEYWORDS",
    "ELEVATED_PATH_PREFIXES",
    "MutationRouteOptimizer",
    "RouteTier",
    "RouteDecision",
    "ROUTE_VERSION",
    "TRIVIAL_OP_TYPES",
    "trivial_route_score",
]
