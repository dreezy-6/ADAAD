# SPDX-License-Identifier: Apache-2.0
"""Approved runtime facade for legacy agent and mutation entrypoints."""

from app.agents.discovery import agent_path_from_id, iter_agent_dirs, resolve_agent_id
from app.agents.mutation_engine import MutationEngine
from app.agents.mutation_request import MutationRequest, MutationTarget
from app.agents.mutation_strategies import adapt_generated_request_payload, load_skill_weights, select_strategy

__all__ = [
    "MutationEngine",
    "MutationRequest",
    "MutationTarget",
    "adapt_generated_request_payload",
    "agent_path_from_id",
    "iter_agent_dirs",
    "load_skill_weights",
    "resolve_agent_id",
    "select_strategy",
]
