# SPDX-License-Identifier: Apache-2.0

from runtime.intelligence.strategy import StrategyInput, StrategyModule


def test_select_prioritizes_immediate_gain_when_mutation_signal_is_dominant() -> None:
    module = StrategyModule()

    decision = module.select(
        StrategyInput(
            cycle_id="cycle-immediate",
            mutation_score=0.95,
            governance_debt_score=0.7,
            horizon_cycles=2,
            resource_budget=0.9,
            goal_backlog={"fast_patch": 0.5, "cleanup": 0.2},
            lineage_health=0.35,
        )
    )

    assert decision.strategy_id == "adaptive_self_mutate"
    assert decision.goal_plan[0] == "deliver_immediate_mutation_gain"
    assert decision.priority_queue[0] == "adaptive_self_mutate"
    assert decision.confidence > 0.55


def test_select_prioritizes_medium_term_stability_under_long_horizon_pressure() -> None:
    module = StrategyModule()

    decision = module.select(
        StrategyInput(
            cycle_id="cycle-medium",
            mutation_score=0.35,
            governance_debt_score=0.05,
            horizon_cycles=12,
            resource_budget=0.4,
            goal_backlog={"refactor": 0.1},
            lineage_health=0.98,
        )
    )

    assert decision.strategy_id == "conservative_hold"
    assert decision.goal_plan[:2] == (
        "preserve_lineage_health",
        "improve_governance_stability",
    )
    assert decision.priority_queue[0] == "conservative_hold"
    assert 0.55 <= decision.confidence <= 1.0
