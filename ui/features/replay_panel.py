# SPDX-License-Identifier: Apache-2.0
"""Replay panel feature helpers."""

from __future__ import annotations

from typing import Any


def replay_divergence(*, metrics_module: Any, normalize_event_type: Any, replay_divergence_event: str, replay_failure_event: str, lineage_v2: Any, replay_proof_status: Any) -> dict[str, Any]:
    recent = metrics_module.tail(limit=200)
    divergence_events = [
        entry
        for entry in recent
        if normalize_event_type(entry) in {replay_divergence_event, replay_failure_event}
    ]
    return {
        "window": 200,
        "divergence_event_count": len(divergence_events),
        "latest_events": divergence_events[-10:],
        "proof_status": {
            epoch_id: replay_proof_status(epoch_id)
            for epoch_id in lineage_v2.list_epoch_ids()[-10:]
        },
    }
