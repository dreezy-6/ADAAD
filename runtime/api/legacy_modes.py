# SPDX-License-Identifier: Apache-2.0
"""Approved runtime facade for legacy orchestration mode entrypoints."""

from __future__ import annotations

import os


_STRICT_GOVERNANCE_MODES = frozenset({"strict", "audit"})


def _is_truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _legacy_modes_enabled() -> bool:
    configured = os.getenv("ADAAD_ENABLE_LEGACY_ORCHESTRATION_MODES")
    if configured is not None:
        return _is_truthy_env(configured)
    env = (os.getenv("ADAAD_ENV") or "").strip().lower()
    replay_mode = (os.getenv("ADAAD_REPLAY_MODE") or "").strip().lower()
    recovery_tier = (os.getenv("ADAAD_RECOVERY_TIER") or "").strip().lower()
    strict_override = _is_truthy_env(os.getenv("ADAAD_GOVERNANCE_STRICT", ""))
    governance_strict = env in {"staging", "production", "prod"} or replay_mode in _STRICT_GOVERNANCE_MODES or recovery_tier in _STRICT_GOVERNANCE_MODES or strict_override
    return not governance_strict


if not _legacy_modes_enabled():
    raise RuntimeError("legacy_orchestration_modes_disabled")

from app.beast_mode_loop import BeastModeLoop
from app.dream_mode import DreamMode

__all__ = ["BeastModeLoop", "DreamMode"]
