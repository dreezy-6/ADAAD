# SPDX-License-Identifier: Apache-2.0
"""Deterministic entropy ceiling policy enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from runtime.governance.foundation import sha256_prefixed_digest


class EntropyPolicyViolation(RuntimeError):
    """Raised when an entropy policy ceiling is exceeded."""

    def __init__(self, *, reason: str, detail: Dict[str, Any]) -> None:
        self.reason = str(reason)
        self.detail = dict(detail)
        super().__init__(self.reason)


@dataclass(frozen=True)
class EntropyAnomalyTriageThresholds:
    """Deterministic thresholds for entropy anomaly triage."""

    warning_ratio: float = 0.70
    escalate_ratio: float = 0.90
    critical_ratio: float = 1.00

    def classify(self, *, mutation_ratio: float, epoch_ratio: float, policy_enabled: bool) -> str:
        if not policy_enabled:
            return "disabled"

        dominant_ratio = max(float(mutation_ratio), float(epoch_ratio))
        if dominant_ratio >= float(self.critical_ratio):
            return "critical"
        if dominant_ratio >= float(self.escalate_ratio):
            return "escalate"
        if dominant_ratio >= float(self.warning_ratio):
            return "warning"
        return "normal"


@dataclass(frozen=True)
class EntropyPolicy:
    policy_id: str
    per_mutation_ceiling_bits: int
    per_epoch_ceiling_bits: int
    anomaly_triage: EntropyAnomalyTriageThresholds = EntropyAnomalyTriageThresholds()

    @property
    def policy_hash(self) -> str:
        return sha256_prefixed_digest(
            {
                "policy_id": self.policy_id,
                "per_mutation_ceiling_bits": self.per_mutation_ceiling_bits,
                "per_epoch_ceiling_bits": self.per_epoch_ceiling_bits,
            }
        )

    def enforce(
        self,
        *,
        mutation_bits: int,
        epoch_bits: int,
        declared_bits: int | None = None,
        observed_bits: int = 0,
    ) -> Dict[str, Any]:
        """Enforce mutation/epoch entropy ceilings.

        When ``declared_bits`` is omitted, the method treats ``mutation_bits`` as the
        caller-provided declared baseline and computes ``mutation_bits`` detail as
        ``declared_bits + observed_bits``. Callers that already combined observed bits
        into ``mutation_bits`` should pass ``declared_bits`` explicitly to avoid
        double-counting.
        """
        effective_declared_bits = int(mutation_bits if declared_bits is None else declared_bits)
        effective_observed_bits = max(0, int(observed_bits))
        mutation_total_bits = effective_declared_bits + effective_observed_bits
        effective_epoch_bits = int(epoch_bits)

        detail = {
            "declared_bits": effective_declared_bits,
            "observed_bits": effective_observed_bits,
            "mutation_bits": mutation_total_bits,
            "epoch_bits": effective_epoch_bits,
            "policy_id": self.policy_id,
            "policy_hash": self.policy_hash,
            "per_mutation_ceiling_bits": int(self.per_mutation_ceiling_bits),
            "per_epoch_ceiling_bits": int(self.per_epoch_ceiling_bits),
            "triage_thresholds": {
                "warning_ratio": float(self.anomaly_triage.warning_ratio),
                "escalate_ratio": float(self.anomaly_triage.escalate_ratio),
                "critical_ratio": float(self.anomaly_triage.critical_ratio),
            },
        }

        policy_enabled = int(self.per_mutation_ceiling_bits) > 0 and int(self.per_epoch_ceiling_bits) > 0
        if not policy_enabled:
            return {
                "passed": True,
                "reason": "entropy_policy_disabled",
                "triage_level": self.anomaly_triage.classify(
                    mutation_ratio=0.0,
                    epoch_ratio=0.0,
                    policy_enabled=False,
                ),
                **detail,
            }

        mutation_ratio = mutation_total_bits / float(self.per_mutation_ceiling_bits)
        epoch_ratio = effective_epoch_bits / float(self.per_epoch_ceiling_bits)
        detail["mutation_utilization_ratio"] = mutation_ratio
        detail["epoch_utilization_ratio"] = epoch_ratio
        detail["triage_level"] = self.anomaly_triage.classify(
            mutation_ratio=mutation_ratio,
            epoch_ratio=epoch_ratio,
            policy_enabled=True,
        )

        mutation_exceeded = mutation_total_bits > int(self.per_mutation_ceiling_bits)
        epoch_exceeded = effective_epoch_bits > int(self.per_epoch_ceiling_bits)
        if mutation_exceeded or epoch_exceeded:
            if mutation_exceeded and epoch_exceeded:
                reason = "mutation_and_epoch_entropy_budget_exceeded"
            elif mutation_exceeded:
                reason = "entropy_budget_exceeded"
            else:
                reason = "epoch_entropy_budget_exceeded"
            raise EntropyPolicyViolation(reason=reason, detail=detail)

        return {"passed": True, "reason": "ok", **detail}


def enforce_entropy_policy(
    *,
    policy: EntropyPolicy,
    mutation_bits: int,
    epoch_bits: int,
    declared_bits: int | None = None,
    observed_bits: int = 0,
) -> Dict[str, Any]:
    """Deprecated adapter returning verdict dictionaries without raising."""
    try:
        return policy.enforce(
            mutation_bits=mutation_bits,
            epoch_bits=epoch_bits,
            declared_bits=declared_bits,
            observed_bits=observed_bits,
        )
    except EntropyPolicyViolation as exc:
        return {"passed": False, "reason": "entropy_ceiling_exceeded", **exc.detail}


__all__ = [
    "EntropyAnomalyTriageThresholds",
    "EntropyPolicy",
    "EntropyPolicyViolation",
    "enforce_entropy_policy",
]
