# SPDX-License-Identifier: Apache-2.0
"""Storage footprint management for ADAAD runtime data."""

from __future__ import annotations

import json
import logging
import shutil
import time
import warnings
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping

from runtime import metrics


LOG = logging.getLogger(__name__)
METRIC_EVENT = "storage_manager_prune_fallback"
USAGE_SCAN_METRIC_EVENT = "storage_manager_usage_scan"
USAGE_INDEX_VERSION = 1


class StorageManager:
    def __init__(
        self,
        data_root: Path,
        max_storage_mb: float = 5000.0,
        failed_candidate_score_threshold: float | None = None,
        snapshot_max_age_days: int | None = None,
        minimum_reclaim_target_mb: float | None = None,
        governance_config: Mapping[str, Any] | None = None,
        runtime_config: Mapping[str, Any] | None = None,
    ):
        self.data_root = data_root
        self.max_storage_mb = max_storage_mb
        self.failed_candidate_score_threshold = self._coerce_float(
            failed_candidate_score_threshold,
            runtime_config,
            governance_config,
            key="failed_candidate_score_threshold",
            default=0.3,
        )
        self.snapshot_max_age_days = int(
            self._coerce_float(
                snapshot_max_age_days,
                runtime_config,
                governance_config,
                key="snapshot_max_age_days",
                default=30.0,
            )
        )
        self.minimum_reclaim_target_mb = self._coerce_optional_float(
            minimum_reclaim_target_mb,
            runtime_config,
            governance_config,
            key="minimum_reclaim_target_mb",
        )
        self.dynamic_agent_pressure = self._coerce_optional_float(
            None,
            runtime_config,
            governance_config,
            key="dynamic_agent_pressure",
        )
        self.storage_usage_reconcile_interval_s = int(
            self._coerce_float(
                None,
                runtime_config,
                governance_config,
                key="storage_usage_reconcile_interval_s",
                default=600.0,
            )
        )
        self.storage_usage_index_path = self.data_root / "data" / "storage_usage_index.json"
        self._last_usage_scan: dict[str, Any] = {}

    def check_and_prune(self) -> dict:
        current_mb = self._get_usage_mb()
        pressure = self._effective_dynamic_pressure()
        storage_cap_mb = self.max_storage_mb * (1.0 - (0.25 * pressure))
        if current_mb < storage_cap_mb:
            return {"pruned": False, "current_mb": round(current_mb, 3), "dynamic_agent_pressure": round(pressure, 3)}

        baseline_mb = current_mb
        pruned_count = self._prune_failed_candidates(pressure=pressure)
        if pruned_count > 0:
            current_mb = self._get_usage_mb()
        should_prune_snapshots = current_mb >= storage_cap_mb
        if self.minimum_reclaim_target_mb is not None:
            reclaimed_mb = max(0.0, baseline_mb - current_mb)
            should_prune_snapshots = should_prune_snapshots or reclaimed_mb < self.minimum_reclaim_target_mb

        if should_prune_snapshots:
            pruned_count += self._prune_old_snapshots(pressure=pressure)

        if pruned_count > 0:
            current_mb = self._get_usage_mb()

        return {
            "pruned": True,
            "pruned_count": pruned_count,
            "current_mb": round(current_mb, 3),
            "dynamic_agent_pressure": round(pressure, 3),
        }

    def _get_usage_mb(self) -> float:
        if not self.data_root.exists():
            self._write_usage_index({"version": USAGE_INDEX_VERSION, "total_bytes": 0, "files": {}, "dirs": {}})
            return 0.0

        started_at = time.perf_counter()
        now = time.time()
        existing_index = self._read_usage_index()
        file_index: dict[str, dict[str, int]] = {
            path: {"size": int(meta.get("size", 0)), "mtime_ns": int(meta.get("mtime_ns", 0))}
            for path, meta in existing_index.get("files", {}).items()
            if isinstance(meta, Mapping)
        }
        dir_index: dict[str, int] = {
            path: int(mtime_ns)
            for path, mtime_ns in existing_index.get("dirs", {}).items()
            if isinstance(path, str)
        }

        last_full_reconcile = float(existing_index.get("last_full_reconcile_ts", 0.0) or 0.0)
        force_full = (now - last_full_reconcile) >= max(0, self.storage_usage_reconcile_interval_s)

        files_statted = 0
        if force_full or not file_index:
            file_index, dir_index, files_statted = self._full_usage_scan()
            total_bytes = sum(meta["size"] for meta in file_index.values())
            last_full_reconcile = now
            scan_mode = "full"
        else:
            file_index, dir_index, files_statted = self._incremental_usage_scan(file_index=file_index, dir_index=dir_index)
            total_bytes = sum(meta["size"] for meta in file_index.values())
            scan_mode = "incremental"

        self._write_usage_index(
            {
                "version": USAGE_INDEX_VERSION,
                "total_bytes": total_bytes,
                "last_full_reconcile_ts": last_full_reconcile,
                "last_scan_ts": now,
                "files": file_index,
                "dirs": dir_index,
            }
        )
        duration_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
        scan_details = {
            "mode": scan_mode,
            "duration_ms": duration_ms,
            "files_statted": files_statted,
            "indexed_files": len(file_index),
            "usage_mb": round(total_bytes / (1024.0 * 1024.0), 6),
        }
        self._last_usage_scan = scan_details
        metrics.log(event_type=USAGE_SCAN_METRIC_EVENT, payload=scan_details)
        return total_bytes / (1024.0 * 1024.0)

    def _full_usage_scan(self) -> tuple[dict[str, dict[str, int]], dict[str, int], int]:
        file_index: dict[str, dict[str, int]] = {}
        dir_index: dict[str, int] = {}
        files_statted = 0
        for root, dirs, files in self.data_root.walk(top_down=True):
            rel_dir = self._relative_key(root)
            dir_index[rel_dir] = root.stat().st_mtime_ns
            dirs.sort()
            files.sort()
            for name in files:
                file_path = root / name
                if file_path == self.storage_usage_index_path:
                    continue
                stat = file_path.stat()
                files_statted += 1
                file_index[self._relative_key(file_path)] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        return file_index, dir_index, files_statted

    def _incremental_usage_scan(
        self,
        *,
        file_index: dict[str, dict[str, int]],
        dir_index: dict[str, int],
    ) -> tuple[dict[str, dict[str, int]], dict[str, int], int]:
        updated_files = dict(file_index)
        updated_dirs: dict[str, int] = {}
        seen_dirs: set[str] = set()
        files_statted = 0

        for root, dirs, files in self.data_root.walk(top_down=True):
            rel_dir = self._relative_key(root)
            seen_dirs.add(rel_dir)
            root_mtime_ns = root.stat().st_mtime_ns
            updated_dirs[rel_dir] = root_mtime_ns
            prior_mtime_ns = int(dir_index.get(rel_dir, -1))
            dirs.sort()
            files.sort()

            if rel_dir == ".":
                root_file_keys = set()
                for name in files:
                    file_path = root / name
                    if file_path == self.storage_usage_index_path:
                        continue
                    stat = file_path.stat()
                    files_statted += 1
                    key = self._relative_key(file_path)
                    root_file_keys.add(key)
                    updated_files[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
                for key in [existing for existing in list(updated_files) if "/" not in existing and existing not in root_file_keys]:
                    del updated_files[key]
                continue

            if prior_mtime_ns == root_mtime_ns:
                continue

            prefix = "" if rel_dir == "." else f"{rel_dir}/"
            for key in list(updated_files):
                if key.startswith(prefix):
                    del updated_files[key]

            for name in files:
                file_path = root / name
                if file_path == self.storage_usage_index_path:
                    continue
                stat = file_path.stat()
                files_statted += 1
                updated_files[self._relative_key(file_path)] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

        deleted_dirs = set(dir_index) - seen_dirs
        for deleted_dir in deleted_dirs:
            prefix = "" if deleted_dir == "." else f"{deleted_dir}/"
            for key in list(updated_files):
                if key.startswith(prefix):
                    del updated_files[key]

        return updated_files, updated_dirs, files_statted

    def _read_usage_index(self) -> dict[str, Any]:
        if not self.storage_usage_index_path.exists():
            return {}
        try:
            payload = json.loads(self.storage_usage_index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        if int(payload.get("version", 0) or 0) != USAGE_INDEX_VERSION:
            return {}
        return payload

    def _write_usage_index(self, payload: Mapping[str, Any]) -> None:
        self.storage_usage_index_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_usage_index_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def _relative_key(self, path: Path) -> str:
        return str(path.relative_to(self.data_root)) if path != self.data_root else "."

    def _prune_failed_candidates(self, *, pressure: float = 0.0) -> int:
        candidates_dir = self.data_root / "candidates"
        if not candidates_dir.exists():
            return 0
        pruned = 0
        for candidate in sorted(candidates_dir.glob("*"), key=lambda path: path.name):
            if not candidate.is_dir():
                continue
            fitness_file = candidate / "fitness.json"
            if not fitness_file.exists():
                continue
            try:
                fitness = json.loads(fitness_file.read_text(encoding="utf-8"))
            except (JSONDecodeError, OSError, ValueError) as exc:
                self._warn(
                    "Failed to read candidate fitness for pruning",
                    path=fitness_file,
                    context={"candidate": str(candidate), "error": type(exc).__name__},
                )
                continue
            try:
                score = float(fitness.get("score", 1.0))
            except ValueError as exc:
                self._warn(
                    "Failed to parse candidate fitness score for pruning",
                    path=fitness_file,
                    context={"candidate": str(candidate), "error": type(exc).__name__},
                )
                continue
            threshold = max(0.05, self.failed_candidate_score_threshold + (0.20 * max(0.0, pressure)))
            if score < threshold:
                shutil.rmtree(candidate, ignore_errors=True)
                pruned += 1
        return pruned

    def _prune_old_snapshots(self, *, pressure: float = 0.0) -> int:
        snapshots_dir = self.data_root / "snapshots"
        if not snapshots_dir.exists():
            return 0
        effective_days = max(1, int(self.snapshot_max_age_days * (1.0 - (0.5 * max(0.0, pressure)))))
        threshold = time.time() - (effective_days * 24 * 60 * 60)
        pruned = 0
        for snapshot in sorted(snapshots_dir.glob("*"), key=lambda path: path.name):
            try:
                if snapshot.stat().st_mtime < threshold:
                    if snapshot.is_dir():
                        shutil.rmtree(snapshot, ignore_errors=True)
                    else:
                        snapshot.unlink(missing_ok=True)
                    pruned += 1
            except (OSError, ValueError) as exc:
                self._warn(
                    "Failed to evaluate or prune snapshot",
                    path=snapshot,
                    context={"error": type(exc).__name__},
                )
                continue
        return pruned

    @staticmethod
    def _warn(message: str, path: Path, context: dict[str, str]) -> None:
        details = {
            "warning_message": message,
            "path": str(path),
            "context": context,
        }
        LOG.warning("storage manager prune fallback", extra=details)
        metrics.log(event_type=METRIC_EVENT, payload=details, level="WARNING")
        warnings.warn(json.dumps(details, sort_keys=True), stacklevel=2)

    def _effective_dynamic_pressure(self) -> float:
        if self.dynamic_agent_pressure is None:
            return 0.0
        return max(0.0, min(1.0, float(self.dynamic_agent_pressure)))

    @staticmethod
    def _coerce_float(
        explicit: float | int | None,
        runtime_config: Mapping[str, Any] | None,
        governance_config: Mapping[str, Any] | None,
        *,
        key: str,
        default: float,
    ) -> float:
        if explicit is not None:
            return float(explicit)
        for source in (runtime_config, governance_config):
            if not isinstance(source, Mapping):
                continue
            value = source.get(key)
            if value is not None:
                return float(value)
        return default

    @staticmethod
    def _coerce_optional_float(
        explicit: float | int | None,
        runtime_config: Mapping[str, Any] | None,
        governance_config: Mapping[str, Any] | None,
        *,
        key: str,
    ) -> float | None:
        if explicit is not None:
            return float(explicit)
        for source in (runtime_config, governance_config):
            if not isinstance(source, Mapping):
                continue
            value = source.get(key)
            if value is not None:
                return float(value)
        return None


__all__ = ["StorageManager"]
