# SPDX-License-Identifier: Apache-2.0
"""Persistent mutation job transition ledger."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


class MutationJobTransitionStore:
    """Append-only transition persistence for mutation jobs."""

    def __init__(self, path: Path, *, sqlite_path: Path | None = None, backend: str = "json") -> None:
        if backend not in {"json", "sqlite"}:
            raise ValueError("invalid_state_backend")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path or path.with_suffix(".sqlite")
        self.backend = backend
        if self.backend == "sqlite":
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mutation_job_transitions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    at_ts REAL NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )

    def _load_json(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, dict)]

    def _save_json(self, rows: list[dict[str, Any]]) -> None:
        payload = json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            temp_path = Path(handle.name)
        temp_path.replace(self.path)

    def append_transition(
        self,
        *,
        job_id: str,
        from_state: str,
        to_state: str,
        reason: str,
        worker_id: str,
        at_ts: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "job_id": job_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "worker_id": worker_id,
            "at_ts": float(at_ts),
            "metadata": dict(metadata or {}),
        }
        if self.backend == "sqlite":
            self._init_sqlite()
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.execute(
                    """
                    INSERT INTO mutation_job_transitions(
                        job_id, from_state, to_state, reason, worker_id, at_ts, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["job_id"],
                        payload["from_state"],
                        payload["to_state"],
                        payload["reason"],
                        payload["worker_id"],
                        payload["at_ts"],
                        json.dumps(payload["metadata"], sort_keys=True, ensure_ascii=False),
                    ),
                )
            return
        rows = self._load_json()
        rows.append(payload)
        self._save_json(rows)

    def list_transitions(self, *, job_id: str | None = None) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            self._init_sqlite()
            query = (
                "SELECT job_id, from_state, to_state, reason, worker_id, at_ts, metadata_json "
                "FROM mutation_job_transitions"
            )
            params: tuple[Any, ...] = ()
            if job_id is not None:
                query += " WHERE job_id = ?"
                params = (job_id,)
            query += " ORDER BY seq ASC"
            with sqlite3.connect(self.sqlite_path) as conn:
                rows = conn.execute(query, params).fetchall()
            return [
                {
                    "job_id": row[0],
                    "from_state": row[1],
                    "to_state": row[2],
                    "reason": row[3],
                    "worker_id": row[4],
                    "at_ts": row[5],
                    "metadata": json.loads(row[6]),
                }
                for row in rows
            ]
        rows = self._load_json()
        if job_id is not None:
            rows = [row for row in rows if row.get("job_id") == job_id]
        return rows
