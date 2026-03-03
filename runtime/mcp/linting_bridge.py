# SPDX-License-Identifier: Apache-2.0
"""Deterministic lint preview bridge for Aponi editor submissions.

Rationale:
- Reuses MCP mutation analysis (`analyze_mutation`) so preview and queued submission
  both pass through the same governed fitness heuristics.
- Applies lightweight, deterministic rule annotations for operator feedback while
  keeping queue-time governance evaluation as the only authoritative gate.

Expected invariants:
- No hidden mutable cross-proposal state.
- Stable annotation ordering for identical inputs.
- Android resource pressure can throttle preview frequency via
  ``AndroidMonitor.should_throttle()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from runtime.constitution import CONSTITUTION_VERSION
from runtime.mcp.mutation_analyzer import analyze_mutation
from runtime.platform.android_monitor import AndroidMonitor


@dataclass(frozen=True)
class LintConfig:
    max_complexity_delta_warning: float = 0.15
    min_constitutional_compliance: float = 0.5
    min_stability_heuristics: float = 0.4


DEFAULT_LINT_CONFIG = LintConfig()


def _annotation(*, rule: str, severity: str, message: str) -> Dict[str, str]:
    return {
        "rule": rule,
        "severity": severity,
        "message": message,
        "constitution_version": CONSTITUTION_VERSION,
    }


class MutationLintingBridge:
    """Stateless lint-preview bridge for Aponi proposal editor flows."""

    def __init__(
        self,
        *,
        android_monitor: AndroidMonitor | None = None,
        config: LintConfig = DEFAULT_LINT_CONFIG,
    ) -> None:
        self._android_monitor = android_monitor
        self._config = config

    def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        analysis = analyze_mutation(payload)
        annotations: List[Dict[str, str]] = []

        complexity_delta = payload.get("complexity_delta", 0.0)
        if isinstance(complexity_delta, (int, float)) and float(complexity_delta) > self._config.max_complexity_delta_warning:
            annotations.append(
                _annotation(
                    rule="max_complexity_delta",
                    severity="WARNING",
                    message=(
                        f"Complexity delta {float(complexity_delta):.2f} exceeds advisory "
                        f"threshold {self._config.max_complexity_delta_warning:.2f}."
                    ),
                )
            )

        components = analysis.get("component_scores", {})
        constitutional = components.get("constitutional_compliance", 0.5)
        if isinstance(constitutional, (int, float)) and float(constitutional) < self._config.min_constitutional_compliance:
            annotations.append(
                _annotation(
                    rule="constitutional_compliance",
                    severity="BLOCKING",
                    message=(
                        f"Constitutional compliance {float(constitutional):.2f} is below required "
                        f"minimum {self._config.min_constitutional_compliance:.2f}."
                    ),
                )
            )

        stability = components.get("stability_heuristics", 0.5)
        if isinstance(stability, (int, float)) and float(stability) < self._config.min_stability_heuristics:
            annotations.append(
                _annotation(
                    rule="stability_heuristics",
                    severity="BLOCKING",
                    message=(
                        f"Stability heuristics {float(stability):.2f} is below required minimum "
                        f"{self._config.min_stability_heuristics:.2f}."
                    ),
                )
            )

        annotations = sorted(annotations, key=lambda item: (item["severity"], item["rule"], item["message"]))
        return {
            "analysis": analysis,
            "annotations": annotations,
            "preview_authoritative": False,
            "gate": "queue_append_constitutional_evaluation",
            "throttle": self.should_throttle(),
        }

    def should_throttle(self) -> bool:
        if self._android_monitor is None:
            return False
        snapshot = self._android_monitor.snapshot()
        return snapshot.should_throttle()


__all__ = ["LintConfig", "DEFAULT_LINT_CONFIG", "MutationLintingBridge"]
