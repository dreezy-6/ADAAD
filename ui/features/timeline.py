# SPDX-License-Identifier: Apache-2.0
"""Evolution timeline feature helpers."""

from __future__ import annotations

from typing import Any


def evolution_timeline(lineage_v2: Any) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for entry in lineage_v2.read_all()[-200:]:
        if not isinstance(entry, dict):
            continue
        timeline.append(
            {
                "epoch": entry.get("epoch_id", entry.get("epoch", "")),
                "mutation_id": entry.get("mutation_id", entry.get("id", "")),
                "fitness_score": entry.get("fitness_score", entry.get("score", 0.0)),
                "risk_tier": entry.get("risk_tier", "unknown"),
                "applied": bool(entry.get("applied", True)),
                "timestamp": entry.get("ts", entry.get("timestamp", "")),
            }
        )
    return timeline
