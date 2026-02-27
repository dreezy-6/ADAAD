# SPDX-License-Identifier: Apache-2.0
"""Strategy primitives for AGM-style runtime decisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class StrategyInput:
    """Typed context consumed by strategy selection."""

    cycle_id: str
    mutation_score: float
    governance_debt_score: float
    horizon_cycles: int = 1
    resource_budget: float = 1.0
    goal_backlog: Mapping[str, float] = field(default_factory=dict)
    lineage_health: float = 1.0
    signals: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    """Normalized strategy output consumed by proposal generation."""

    strategy_id: str
    rationale: str
    confidence: float
    goal_plan: tuple[str, ...] = ()
    priority_queue: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)


class StrategyModule:
    """Deterministic, side-effect-free baseline strategy module."""

    def select(self, context: StrategyInput) -> StrategyDecision:
        normalized_horizon = self._normalize_horizon(context.horizon_cycles)
        normalized_mutation = self._normalize(context.mutation_score)
        normalized_budget = self._normalize(context.resource_budget)
        normalized_debt = self._normalize(context.governance_debt_score)
        normalized_lineage = self._normalize(context.lineage_health)
        backlog_pressure = self._normalize(sum(max(value, 0.0) for value in context.goal_backlog.values()) / 4.0)

        objective_scores = (
            (
                "deliver_immediate_mutation_gain",
                self._normalize(normalized_mutation * (0.75 + 0.25 * normalized_budget)),
                "short",
            ),
            (
                "reduce_backlog_risk",
                self._normalize(backlog_pressure * (0.6 + 0.4 * normalized_budget)),
                "short",
            ),
            (
                "improve_governance_stability",
                self._normalize((1.0 - normalized_debt) * (0.5 + 0.5 * normalized_horizon)),
                "medium",
            ),
            (
                "preserve_lineage_health",
                self._normalize(normalized_lineage * (0.4 + 0.6 * normalized_horizon)),
                "medium",
            ),
        )

        ranked_objectives = tuple(
            sorted(
                objective_scores,
                key=lambda objective: (
                    -objective[1],
                    0 if objective[2] == "short" else 1,
                    objective[0],
                ),
            )
        )
        goal_plan = tuple(objective_id for objective_id, _, _ in ranked_objectives)
        objective_score_map = {objective_id: score for objective_id, score, _ in objective_scores}

        payoff_by_strategy = {
            "adaptive_self_mutate": self._normalize(
                0.7 * objective_score_map["deliver_immediate_mutation_gain"]
                + 0.3 * objective_score_map["reduce_backlog_risk"]
                - 0.2 * objective_score_map["improve_governance_stability"]
            ),
            "conservative_hold": self._normalize(
                0.55 * objective_score_map["improve_governance_stability"]
                + 0.45 * objective_score_map["preserve_lineage_health"]
                - 0.15 * objective_score_map["deliver_immediate_mutation_gain"]
            ),
        }

        priority_queue = tuple(
            strategy_id
            for strategy_id, _ in sorted(
                payoff_by_strategy.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )

        top_objective, top_score, _ = ranked_objectives[0]
        second_score = ranked_objectives[1][1] if len(ranked_objectives) > 1 else top_score
        confidence = self._normalize(0.55 + (top_score - second_score) * 0.9)

        chosen_strategy = priority_queue[0]
        return StrategyDecision(
            strategy_id=chosen_strategy,
            rationale=f"ranked objective '{top_objective}' highest with deterministic payoff mapping",
            confidence=confidence,
            goal_plan=goal_plan,
            priority_queue=priority_queue,
            parameters={
                "horizon_cycles": int(max(context.horizon_cycles, 1)),
                "normalized": {
                    "mutation": normalized_mutation,
                    "governance_debt": normalized_debt,
                    "resource_budget": normalized_budget,
                    "lineage_health": normalized_lineage,
                    "horizon": normalized_horizon,
                },
                "objective_scores": {objective_id: score for objective_id, score, _ in ranked_objectives},
                "strategy_payoff": payoff_by_strategy,
            },
        )

    @staticmethod
    def _normalize(value: float) -> float:
        return min(max(round(float(value), 6), 0.0), 1.0)

    def _normalize_horizon(self, cycles: int) -> float:
        bounded_cycles = min(max(int(cycles), 1), 12)
        return self._normalize(bounded_cycles / 12.0)
