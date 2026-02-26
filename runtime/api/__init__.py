# SPDX-License-Identifier: Apache-2.0
"""Public runtime facade package for approved external entrypoints."""

from runtime.api.agents import (
    MutationEngine,
    MutationRequest,
    MutationTarget,
    adapt_generated_request_payload,
    agent_path_from_id,
    iter_agent_dirs,
    load_skill_weights,
    resolve_agent_id,
    select_strategy,
)
from runtime.api.legacy_modes import BeastModeLoop, DreamMode
from runtime.api.mutation import MutationExecutor

__all__ = [
    "BeastModeLoop",
    "DreamMode",
    "MutationEngine",
    "MutationExecutor",
    "MutationRequest",
    "MutationTarget",
    "adapt_generated_request_payload",
    "agent_path_from_id",
    "iter_agent_dirs",
    "load_skill_weights",
    "resolve_agent_id",
    "select_strategy",
]
