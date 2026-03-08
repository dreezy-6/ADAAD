# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation job queue with JSON/SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest

_TERMINAL_STATES = {"succeeded", "failed"}


class MutationJobQueueStore:
    """Queue storage abstraction for mutation lifecycle jobs.

    Supported states: queued, leased, running, succeeded, failed, quarantined.
    """

    def __init__(
        self,
        path: Path,
        *,
        sqlite_path: Path | None = None,
        backend: str = "json",
        lease_timeout_s: int = 30,
    ) -> None:
        if backend not in {"json", "sqlite"}:
            raise ValueError("invalid_state_backend")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path or path.with_suffix(".sqlite")
        self.backend = backend
        self.lease_timeout_s = int(lease_timeout_s)
        if self.backend == "sqlite":
            self._init_sqlite()

    @staticmethod
    def deterministic_job_id(*, payload: dict[str, Any], dedupe_key: str = "") -> str:
        seed = canonical_json({"dedupe_key": dedupe_key, "payload": payload})
        return sha256_prefixed_digest(seed)

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mutation_jobs (
                    job_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    lease_owner TEXT NOT NULL,
                    lease_expires_at REAL,
                    heartbeat_at REAL,
                    attempt_count INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    error TEXT NOT NULL
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
        rows = [row for row in payload if isinstance(row, dict)]
        return sorted(rows, key=lambda row: (float(row.get("created_at", 0.0)), str(row.get("job_id", ""))))

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

    def list_jobs(self) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            with sqlite3.connect(self.sqlite_path) as conn:
                rows = conn.execute(
                    """
                    SELECT
                        job_id,
                        payload_json,
                        state,
                        dedupe_key,
                        created_at,
                        updated_at,
                        lease_owner,
                        lease_expires_at,
                        heartbeat_at,
                        attempt_count,
                        max_attempts,
                        error
                    FROM mutation_jobs
                    ORDER BY created_at ASC, job_id ASC
                    """
                ).fetchall()
            return [
                {
                    "job_id": row[0],
                    "payload": json.loads(row[1]),
                    "state": row[2],
                    "dedupe_key": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "lease_owner": row[6],
                    "lease_expires_at": row[7],
                    "heartbeat_at": row[8],
                    "attempt_count": row[9],
                    "max_attempts": row[10],
                    "error": row[11],
                }
                for row in rows
            ]
        return self._load_json()

    def _upsert_row(self, row: dict[str, Any]) -> None:
        if self.backend == "sqlite":
            self._init_sqlite()
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.execute(
                    """
                    INSERT INTO mutation_jobs(
                        job_id,payload_json,state,dedupe_key,created_at,updated_at,
                        lease_owner,lease_expires_at,heartbeat_at,attempt_count,max_attempts,error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        payload_json=excluded.payload_json,
                        state=excluded.state,
                        dedupe_key=excluded.dedupe_key,
                        created_at=excluded.created_at,
                        updated_at=excluded.updated_at,
                        lease_owner=excluded.lease_owner,
                        lease_expires_at=excluded.lease_expires_at,
                        heartbeat_at=excluded.heartbeat_at,
                        attempt_count=excluded.attempt_count,
                        max_attempts=excluded.max_attempts,
                        error=excluded.error
                    """,
                    (
                        row["job_id"],
                        canonical_json(row["payload"]),
                        row["state"],
                        row["dedupe_key"],
                        row["created_at"],
                        row["updated_at"],
                        row["lease_owner"],
                        row["lease_expires_at"],
                        row["heartbeat_at"],
                        row["attempt_count"],
                        row["max_attempts"],
                        row["error"],
                    ),
                )
            return
        rows = self._load_json()
        replaced = False
        for index, candidate in enumerate(rows):
            if candidate.get("job_id") == row["job_id"]:
                rows[index] = row
                replaced = True
                break
        if not replaced:
            rows.append(row)
        rows = sorted(rows, key=lambda item: (float(item.get("created_at", 0.0)), str(item.get("job_id", ""))))
        self._save_json(rows)

    def get(self, job_id: str) -> dict[str, Any] | None:
        for row in self.list_jobs():
            if row.get("job_id") == job_id:
                return dict(row)
        return None

    def enqueue(
        self,
        payload: dict[str, Any],
        *,
        dedupe_key: str = "",
        max_attempts: int = 3,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        ts = float(time.time() if now_ts is None else now_ts)
        job_id = self.deterministic_job_id(payload=payload, dedupe_key=dedupe_key)
        existing = self.get(job_id)
        if existing is not None:
            return existing
        row = {
            "job_id": job_id,
            "payload": dict(payload),
            "state": "queued",
            "dedupe_key": dedupe_key,
            "created_at": ts,
            "updated_at": ts,
            "lease_owner": "",
            "lease_expires_at": None,
            "heartbeat_at": None,
            "attempt_count": 0,
            "max_attempts": max(1, int(max_attempts)),
            "error": "",
        }
        self._upsert_row(row)
        return row

    def recover_orphans(self, *, now_ts: float | None = None) -> list[str]:
        ts = float(time.time() if now_ts is None else now_ts)
        recovered: list[str] = []
        for row in self.list_jobs():
            if row.get("state") not in {"leased", "running"}:
                continue
            lease_expires_at = row.get("lease_expires_at")
            if not isinstance(lease_expires_at, (int, float)) or lease_expires_at > ts:
                continue
            row["state"] = "quarantined"
            row["lease_owner"] = ""
            row["lease_expires_at"] = None
            row["heartbeat_at"] = None
            row["updated_at"] = ts
            row["error"] = "worker_orphaned"
            recovered.append(str(row["job_id"]))
            self._upsert_row(row)
        return recovered

    def retry(self, job_id: str, *, now_ts: float | None = None) -> dict[str, Any] | None:
        ts = float(time.time() if now_ts is None else now_ts)
        row = self.get(job_id)
        if row is None:
            return None
        if row.get("state") not in {"failed", "quarantined"}:
            return row
        if int(row.get("attempt_count", 0)) >= int(row.get("max_attempts", 1)):
            return row
        row["state"] = "queued"
        row["lease_owner"] = ""
        row["lease_expires_at"] = None
        row["heartbeat_at"] = None
        row["updated_at"] = ts
        row["error"] = ""
        self._upsert_row(row)
        return row

    def lease_next(self, *, worker_id: str, now_ts: float | None = None) -> dict[str, Any] | None:
        ts = float(time.time() if now_ts is None else now_ts)
        self.recover_orphans(now_ts=ts)
        queued = [row for row in self.list_jobs() if row.get("state") == "queued"]
        if not queued:
            return None
        row = queued[0]
        row["state"] = "leased"
        row["lease_owner"] = worker_id
        row["attempt_count"] = int(row.get("attempt_count", 0)) + 1
        row["heartbeat_at"] = ts
        row["lease_expires_at"] = ts + self.lease_timeout_s
        row["updated_at"] = ts
        self._upsert_row(row)
        return row

    def mark_running(self, *, job_id: str, worker_id: str, now_ts: float | None = None) -> bool:
        ts = float(time.time() if now_ts is None else now_ts)
        row = self.get(job_id)
        if row is None or row.get("state") != "leased" or row.get("lease_owner") != worker_id:
            return False
        row["state"] = "running"
        row["updated_at"] = ts
        self._upsert_row(row)
        return True

    def heartbeat(self, *, job_id: str, worker_id: str, now_ts: float | None = None) -> bool:
        ts = float(time.time() if now_ts is None else now_ts)
        row = self.get(job_id)
        if row is None:
            return False
        if row.get("state") not in {"leased", "running"} or row.get("lease_owner") != worker_id:
            return False
        row["heartbeat_at"] = ts
        row["lease_expires_at"] = ts + self.lease_timeout_s
        row["updated_at"] = ts
        self._upsert_row(row)
        return True

    def complete(self, *, job_id: str, state: str, error: str = "", now_ts: float | None = None) -> bool:
        if state not in {"succeeded", "failed"}:
            raise ValueError("invalid_terminal_state")
        ts = float(time.time() if now_ts is None else now_ts)
        row = self.get(job_id)
        if row is None:
            return False
        if row.get("state") in _TERMINAL_STATES and row.get("state") == state:
            return True
        if row.get("state") not in {"leased", "running", "quarantined", "failed", "succeeded"}:
            return False
        row["state"] = state
        row["error"] = error
        row["lease_owner"] = ""
        row["lease_expires_at"] = None
        row["heartbeat_at"] = None
        row["updated_at"] = ts
        self._upsert_row(row)
        return True
