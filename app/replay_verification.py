# SPDX-License-Identifier: Apache-2.0
"""Replay verification orchestration helpers."""

from __future__ import annotations

from typing import Any, Dict


def run_replay_preflight(orchestrator: Any, dump_func: Any, *, verify_only: bool = False) -> Dict[str, Any]:
    mode = orchestrator.replay_mode
    envelope, preflight = orchestrator.replay_service.run_preflight(
        evolution_runtime=orchestrator.evolution_runtime,
        replay_mode=mode,
        replay_epoch=orchestrator.replay_epoch,
        verify_only=verify_only,
    )
    outcome = envelope.payload
    has_divergence = bool(outcome.get("divergence"))
    orchestrator.state["replay_mode"] = mode.value
    orchestrator.state["replay_target"] = preflight.get("verify_target")
    orchestrator.state["replay_decision"] = preflight.get("decision")
    orchestrator.state["replay_results"] = preflight.get("results", [])
    orchestrator.state["replay_divergence"] = has_divergence
    orchestrator.state["status"] = "replay_warning" if has_divergence else "replay_verified"
    orchestrator.state["replay_score"] = outcome.get("replay_score", 1.0)
    if envelope.evidence_refs:
        orchestrator._v(f"Replay manifest written: {envelope.evidence_refs[0]}")
    if envelope.status == "error":
        orchestrator._fail(envelope.reason)
    orchestrator._v("Replay Summary:")
    orchestrator._v(f"  Mode: {mode.value}")
    orchestrator._v(f"  Target: {preflight.get('verify_target')}")
    orchestrator._v(f"  Divergence: {has_divergence}")
    orchestrator._v(f"  Score: {orchestrator.state['replay_score']}")
    if verify_only:
        dump_func()
        return {"verify_only": True, **outcome}
    return {"verify_only": False, **outcome}
