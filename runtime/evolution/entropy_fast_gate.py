# SPDX-License-Identifier: Apache-2.0
"""Entropy fast-gate: lightweight pre-flight entropy budget check.

Evaluates entropy budget compliance *before* heavy scoring or sandbox
execution begins.  When a mutation candidate provably exceeds the declared
entropy budget, the fast-gate returns a ``DENY`` verdict immediately,
saving downstream CPU and preventing nondeterministic execution from
contaminating the scoring pipeline.

Design notes
------------
- All decisions are deterministic given identical inputs.
- No I/O is performed; the gate operates purely on provided metadata.
- Gate verdicts carry a canonical digest for ledger journaling.
- The gate is intentionally fail-closed: any ambiguity returns ``DENY``
  when ``strict=True``, or ``WARN`` when ``strict=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Sequence

from runtime.governance.foundation.hashing import sha256_prefixed_digest

FAST_GATE_VERSION = "v1.0.0"

# Default entropy budget thresholds (bits)
DEFAULT_WARN_BITS: int = 32
DEFAULT_DENY_BITS: int = 64

# Sources that are always deterministic and carry zero entropy cost
ZERO_COST_SOURCES: frozenset[str] = frozenset(
    {"mutation_ops", "lineage_annotation", "doc_update"}
)


class GateVerdict(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    DENY = "DENY"


@dataclass(frozen=True)
class EntropyGateResult:
    """Result of an entropy fast-gate evaluation.

    Attributes
    ----------
    verdict:
        ``ALLOW``, ``WARN``, or ``DENY``.
    mutation_id:
        Mutation candidate identifier.
    estimated_bits:
        Total estimated entropy bits for this mutation.
    budget_bits:
        Configured budget threshold that was applied.
    active_sources:
        Entropy sources detected as active (excluding zero-cost sources).
    reason:
        Human-readable reason code for the verdict.
    gate_digest:
        Canonical sha256 digest for ledger journaling.
    gate_version:
        Version of the gate algorithm.
    """

    verdict: GateVerdict
    mutation_id: str
    estimated_bits: int
    budget_bits: int
    active_sources: tuple[str, ...]
    reason: str
    gate_digest: str
    gate_version: str = FAST_GATE_VERSION

    def to_payload(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "mutation_id": self.mutation_id,
            "estimated_bits": self.estimated_bits,
            "budget_bits": self.budget_bits,
            "active_sources": list(self.active_sources),
            "reason": self.reason,
            "gate_digest": self.gate_digest,
            "gate_version": self.gate_version,
        }

    @property
    def denied(self) -> bool:
        return self.verdict is GateVerdict.DENY


class EntropyFastGate:
    """Pre-flight entropy budget enforcement gate.

    Parameters
    ----------
    warn_bits:
        Threshold (inclusive) at which verdict escalates from ALLOW to WARN.
    deny_bits:
        Threshold (inclusive) at which verdict escalates to DENY.
    strict:
        When ``True``, any ambiguous or unknown source triggers DENY.
        When ``False``, unknown sources trigger WARN.

    Usage
    -----
    >>> gate = EntropyFastGate()
    >>> result = gate.evaluate(
    ...     mutation_id="mut_xyz",
    ...     estimated_bits=12,
    ...     sources=["prng", "mutation_ops"],
    ... )
    >>> result.verdict
    <GateVerdict.ALLOW: 'ALLOW'>
    """

    def __init__(
        self,
        *,
        warn_bits: int = DEFAULT_WARN_BITS,
        deny_bits: int = DEFAULT_DENY_BITS,
        strict: bool = True,
    ) -> None:
        if warn_bits < 0 or deny_bits <= warn_bits:
            raise ValueError("entropy_gate_invalid_thresholds")
        self._warn_bits = warn_bits
        self._deny_bits = deny_bits
        self._strict = strict

    def evaluate(
        self,
        *,
        mutation_id: str,
        estimated_bits: int,
        sources: Sequence[str],
    ) -> EntropyGateResult:
        """Evaluate entropy budget compliance for a mutation candidate.

        Parameters
        ----------
        mutation_id:
            Stable identifier for the mutation candidate.
        estimated_bits:
            Pre-computed entropy estimate (from ``EntropyMetadata``).
        sources:
            Active entropy sources declared by the mutation.
        """
        bits = max(0, int(estimated_bits))

        active: list[str] = [
            s for s in sources if s not in ZERO_COST_SOURCES
        ]

        # Check for explicitly nondeterministic sources (fast deny path)
        nondeterministic_sources = [
            s for s in active if s in {"network", "sandbox_nondeterminism", "runtime_rng"}
        ]

        if nondeterministic_sources:
            reason = f"nondeterministic_source:{nondeterministic_sources[0]}"
            verdict = GateVerdict.DENY if self._strict else GateVerdict.WARN
        elif bits >= self._deny_bits:
            reason = f"entropy_exceeds_deny_budget:{bits}>={self._deny_bits}"
            verdict = GateVerdict.DENY
        elif bits >= self._warn_bits:
            reason = f"entropy_exceeds_warn_budget:{bits}>={self._warn_bits}"
            verdict = GateVerdict.WARN
        else:
            reason = "entropy_within_budget"
            verdict = GateVerdict.ALLOW

        digest_payload = {
            "mutation_id": str(mutation_id),
            "estimated_bits": bits,
            "budget_bits": self._deny_bits,
            "active_sources": sorted(active),
            "verdict": verdict.value,
            "gate_version": FAST_GATE_VERSION,
        }
        gate_digest = sha256_prefixed_digest(digest_payload)

        return EntropyGateResult(
            verdict=verdict,
            mutation_id=str(mutation_id),
            estimated_bits=bits,
            budget_bits=self._deny_bits,
            active_sources=tuple(sorted(active)),
            reason=reason,
            gate_digest=gate_digest,
        )


__all__ = [
    "DEFAULT_DENY_BITS",
    "DEFAULT_WARN_BITS",
    "EntropyFastGate",
    "EntropyGateResult",
    "FAST_GATE_VERSION",
    "GateVerdict",
    "ZERO_COST_SOURCES",
]
