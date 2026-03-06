# SPDX-License-Identifier: Apache-2.0
"""
NonStationarityDetector — detects reward distribution shifts in bandit arms.

Purpose:
    Monitors UCB1 arm win rates across epochs and signals when the reward
    distribution appears to have shifted. A detected shift triggers escalation
    from UCB1 (BanditSelector) to Thompson Sampling (ThompsonBanditSelector),
    which adapts faster to non-stationary environments.

Detection method: Page-Hinkley Test (one-sided sequential change detection).
    - Tracks cumulative deviation from a running mean win rate per arm.
    - Fires when the cumulative sum exceeds THRESHOLD (default: 0.10).
    - Deterministic: all arithmetic is pure float on deterministic inputs.
    - Resets after firing so subsequent shifts can be detected.

Escalation contract:
    NonStationarityDetector is ADVISORY. It returns a bool signal.
    Callers (FitnessLandscape) decide whether to escalate to Thompson.
    GovernanceGate is never referenced here.

Determinism contract:
    detect(win_rates) is a pure function.
    record() mutates internal state only — all mutations are deterministic.
    No entropy, no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Constants ----------------------------------------------------------------

PAGE_HINKLEY_THRESHOLD: float = 0.20    # Cumulative deviation trigger
PAGE_HINKLEY_DELTA: float     = 0.02    # Allowable steady-state noise floor
MIN_OBSERVATIONS: int         = 5       # Don't fire on sparse data
ESCALATION_COOLDOWN: int      = 3       # Epochs between escalation signals


@dataclass
class ArmHistory:
    """Rolling win rate history for one bandit arm."""
    agent:        str
    win_rates:    List[float] = field(default_factory=list)
    ph_sum:       float       = 0.0     # Page-Hinkley cumulative sum
    ph_min:       float       = 0.0     # Page-Hinkley running minimum
    running_mean: float       = 0.0     # EMA of win rates

    def update(self, win_rate: float, ema_alpha: float = 0.20) -> None:
        self.win_rates.append(win_rate)
        # Warm-start: initialise mean to first observation (avoids 0→mean drift)
        if len(self.win_rates) == 1:
            self.running_mean = win_rate
            return  # skip PH on first observation — no deviation to measure
        self.running_mean = ema_alpha * win_rate + (1 - ema_alpha) * self.running_mean
        # Page-Hinkley update — only after warm-start
        deviation = win_rate - self.running_mean - PAGE_HINKLEY_DELTA
        self.ph_sum = self.ph_sum + deviation
        self.ph_min = min(self.ph_min, self.ph_sum)

    @property
    def ph_statistic(self) -> float:
        """Page-Hinkley test statistic: M_t - m_t."""
        return self.ph_sum - self.ph_min

    @property
    def has_sufficient_data(self) -> bool:
        return len(self.win_rates) >= MIN_OBSERVATIONS

    def reset_ph(self) -> None:
        """Reset Page-Hinkley accumulators after escalation."""
        self.ph_sum = 0.0
        self.ph_min = 0.0


class NonStationarityDetector:
    """
    Detects reward distribution shifts across bandit arms.

    Usage:
        detector = NonStationarityDetector()
        detector.record({'architect': 0.6, 'beast': 0.4, 'dream': 0.2})
        if detector.is_non_stationary():
            # escalate to Thompson Sampling
    """

    def __init__(self, threshold: float = PAGE_HINKLEY_THRESHOLD) -> None:
        self._threshold = threshold
        self._arms: Dict[str, ArmHistory] = {}
        self._epochs_since_escalation: int = 0
        self._escalation_count: int = 0

    def record(self, win_rates: Dict[str, float]) -> None:
        """
        Record observed win rates for each arm after an epoch.

        Args:
            win_rates: dict mapping agent name to observed win_rate (0–1).
        """
        for agent, rate in win_rates.items():
            if agent not in self._arms:
                self._arms[agent] = ArmHistory(agent=agent)
            self._arms[agent].update(float(rate))
        self._epochs_since_escalation += 1

    def is_non_stationary(self) -> bool:
        """
        Return True when a distributional shift is detected.

        Conditions:
          - At least one arm has >= MIN_OBSERVATIONS observations.
          - At least one arm's Page-Hinkley statistic exceeds threshold.
          - ESCALATION_COOLDOWN epochs have passed since last escalation.

        Side effect: resets Page-Hinkley accumulators on True (one-shot per shift).
        """
        if self._epochs_since_escalation < ESCALATION_COOLDOWN:
            return False

        triggered_arms = [
            arm for arm in self._arms.values()
            if arm.has_sufficient_data and arm.ph_statistic > self._threshold
        ]

        if not triggered_arms:
            return False

        # Reset after firing — prevents continuous escalation
        for arm in triggered_arms:
            arm.reset_ph()
        self._epochs_since_escalation = 0
        self._escalation_count += 1
        return True

    def arm_statistics(self) -> Dict[str, dict]:
        """Serialisable statistics per arm for health endpoints."""
        return {
            agent: {
                "win_rates":         arm.win_rates[-10:],  # last 10 only
                "running_mean":      round(arm.running_mean, 4),
                "ph_statistic":      round(arm.ph_statistic, 6),
                "ph_threshold":      self._threshold,
                "sufficient_data":   arm.has_sufficient_data,
                "observations":      len(arm.win_rates),
            }
            for agent, arm in self._arms.items()
        }

    def summary(self) -> dict:
        """Serialisable summary for telemetry and MCP tools."""
        return {
            "algorithm":                 "page_hinkley",
            "threshold":                 self._threshold,
            "escalation_count":          self._escalation_count,
            "epochs_since_escalation":   self._epochs_since_escalation,
            "cooldown":                  ESCALATION_COOLDOWN,
            "is_non_stationary":         self.is_non_stationary.__doc__,  # docstring
            "arm_statistics":            self.arm_statistics(),
        }


__all__ = [
    "NonStationarityDetector",
    "ArmHistory",
    "PAGE_HINKLEY_THRESHOLD",
    "PAGE_HINKLEY_DELTA",
    "MIN_OBSERVATIONS",
    "ESCALATION_COOLDOWN",
]
