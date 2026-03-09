# SPDX-License-Identifier: MIT
"""Marketing State Store — ADAAD Phase 11, M11-01.

Persists all marketing actions, results, and target states to
marketing/state/ as append-only JSON files.

Committed to the repo so every GitHub Actions run inherits full history.
This means the engine knows exactly what it last posted to Dev.to,
which awesome-list PRs are open, and what the current exposure coverage is.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Action record ──────────────────────────────────────────────────────────

@dataclass
class MarketingAction:
    """Immutable record of one marketing dispatch attempt."""
    action_id:    str
    target_id:    str
    platform:     str
    content_type: str
    title:        Optional[str]
    success:      bool
    live_url:     Optional[str]
    error:        Optional[str]
    dispatched_at: int
    dry_run:      bool = False
    prev_hash:    str = ""
    record_hash:  str = field(init=False, default="")

    def __post_init__(self) -> None:
        payload = {k: v for k, v in asdict(self).items() if k != "record_hash"}
        self.record_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()


# ─── Target state ───────────────────────────────────────────────────────────

@dataclass
class TargetState:
    target_id:        str
    platform:         str
    status:           str = "pending"       # pending|submitted|live|rejected|rate_limited
    last_action_at:   Optional[int] = None
    live_url:         Optional[str] = None
    submission_count: int = 0
    last_error:       Optional[str] = None
    notes:            str = ""

    def mark_live(self, url: str) -> None:
        self.status          = "live"
        self.live_url        = url
        self.last_action_at  = int(time.time())
        self.submission_count += 1

    def mark_submitted(self) -> None:
        self.status         = "submitted"
        self.last_action_at = int(time.time())
        self.submission_count += 1

    def mark_failed(self, error: str) -> None:
        self.last_error     = error
        self.last_action_at = int(time.time())


# ─── State store ────────────────────────────────────────────────────────────

class MarketingStateStore:
    """Persist marketing state to marketing/state/ directory.

    Files:
      targets.json  — current status of every target
      actions.log   — append-only JSONL of every action taken
    """

    def __init__(self, state_dir: str = "marketing/state") -> None:
        self._dir         = Path(state_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._targets_file = self._dir / "targets.json"
        self._actions_log  = self._dir / "actions.log"
        self._targets: Dict[str, TargetState] = {}
        self._last_hash = ""
        self._load()

    # ── Load / save ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._targets_file.exists():
            raw = json.loads(self._targets_file.read_text())
            for tid, d in raw.items():
                self._targets[tid] = TargetState(**d)

    def _save_targets(self) -> None:
        self._targets_file.write_text(
            json.dumps(
                {tid: asdict(t) for tid, t in self._targets.items()},
                indent=2, default=str,
            )
        )

    # ── Target state ────────────────────────────────────────────────────────

    def get_target(self, target_id: str) -> Optional[TargetState]:
        return self._targets.get(target_id)

    def upsert_target(self, state: TargetState) -> None:
        self._targets[state.target_id] = state
        self._save_targets()

    def all_targets(self) -> List[TargetState]:
        return list(self._targets.values())

    def live_targets(self) -> List[TargetState]:
        return [t for t in self._targets.values() if t.status == "live"]

    def elapsed_since_last_action(self, target_id: str) -> float:
        """Hours since last action on this target (inf if never acted)."""
        t = self._targets.get(target_id)
        if not t or not t.last_action_at:
            return float("inf")
        return (time.time() - t.last_action_at) / 3600

    # ── Action log ──────────────────────────────────────────────────────────

    def log_action(self, action: MarketingAction) -> None:
        """Append action to the evidence log (never modifies past records)."""
        record = asdict(action)
        with self._actions_log.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def recent_actions(self, n: int = 20) -> List[MarketingAction]:
        if not self._actions_log.exists():
            return []
        lines = self._actions_log.read_text().strip().splitlines()
        results = []
        for line in lines[-n:]:
            try:
                d = json.loads(line)
                d.pop("record_hash", None)
                results.append(MarketingAction(**d))
            except Exception:
                pass
        return results

    # ── Coverage ─────────────────────────────────────────────────────────────

    def coverage_report(self, total_known_targets: int = 0) -> Dict[str, Any]:
        all_t  = self.all_targets()
        live   = self.live_targets()
        total  = total_known_targets or len(all_t) or 1
        return {
            "total_targets":  len(all_t),
            "live":           len(live),
            "pending":        sum(1 for t in all_t if t.status == "pending"),
            "submitted":      sum(1 for t in all_t if t.status == "submitted"),
            "rejected":       sum(1 for t in all_t if t.status == "rejected"),
            "coverage_pct":   len(live) / total * 100,
            "live_urls":      [t.live_url for t in live if t.live_url],
        }
