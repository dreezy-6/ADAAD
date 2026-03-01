# SPDX-License-Identifier: Apache-2.0
"""Deterministic replay helpers for lineage epochs."""

from __future__ import annotations

from importlib import util as importlib_util
from typing import Any, Dict

from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation.hashing import sha256_digest
from runtime.governance_surface import strip_version_comparison_ephemerals
from runtime.sandbox.replay import replay_sandbox_execution


class ReplayVersionValidator:
    """Compare replay bundle versions under strict/audit/migration policies."""

    def validate(self, bundle: Dict[str, Any], *, mode: str = "strict") -> Dict[str, Any]:
        if mode not in {"strict", "audit", "migration"}:
            raise ValueError("invalid_replay_version_mode")

        normalized = strip_version_comparison_ephemerals(bundle)
        details: Dict[str, Any] = {
            "required_fields": ["scoring_algorithm_version", "governor_version"],
            "missing_required": [
                field
                for field in ("scoring_algorithm_version", "governor_version")
                if not str(normalized.get(field) or "").strip()
            ],
        }
        if details["missing_required"]:
            return {
                "mode": mode,
                "ok": False,
                "decision": "reject",
                "details": details,
                "mismatches": {},
                "normalized_bundle": normalized,
            }

        expected = {
            "scoring_algorithm_version": str(normalized.get("scoring_algorithm_version") or ""),
            "governor_version": str(normalized.get("governor_version") or ""),
        }
        observed = {
            "replay_scoring_algorithm_version": str(normalized.get("replay_scoring_algorithm_version") or expected["scoring_algorithm_version"]),
            "replay_governor_version": str(normalized.get("replay_governor_version") or expected["governor_version"]),
        }
        mismatches = {}
        if expected["scoring_algorithm_version"] != observed["replay_scoring_algorithm_version"]:
            mismatches["scoring_algorithm_version"] = {
                "expected": expected["scoring_algorithm_version"],
                "observed": observed["replay_scoring_algorithm_version"],
            }
        if expected["governor_version"] != observed["replay_governor_version"]:
            mismatches["governor_version"] = {
                "expected": expected["governor_version"],
                "observed": observed["replay_governor_version"],
            }

        report: Dict[str, Any] = {
            "mode": mode,
            "ok": not mismatches,
            "decision": "allow" if not mismatches else "reject",
            "details": details,
            "mismatches": mismatches,
            "normalized_bundle": normalized,
        }
        if not mismatches:
            return report

        if mode == "strict":
            report["decision"] = "reject"
            report["ok"] = False
            return report
        if mode == "audit":
            report["decision"] = "allow_with_divergence"
            report["ok"] = True
            return report
        if mode == "migration":
            migration = self._migration_rescore(normalized)
            report["migration"] = migration
            report["decision"] = "allow_with_migration_report"
            report["ok"] = True
            return report

        report["decision"] = "unknown_mode"
        report["ok"] = False
        return report

    def _migration_rescore(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        version = str(bundle.get("scoring_algorithm_version") or "").strip()
        if not version:
            return {"ok": False, "reason": "missing_scoring_algorithm_version"}
        module_name = f"runtime.evolution.scoring_algorithm_{version.replace('.', '_').replace('-', '_')}"
        if importlib_util.find_spec(module_name) is not None:
            return {"ok": True, "historical_module": module_name}
        return {
            "ok": True,
            "historical_module": module_name,
            "missing_historical_module": True,
            "reason": "historical_scoring_module_not_found",
        }


class ReplayEngine:
    def __init__(self, ledger: LineageLedgerV2 | None = None) -> None:
        self.ledger = ledger or LineageLedgerV2()

    def reconstruct_epoch(self, epoch_id: str) -> Dict[str, Any]:
        events = self.ledger.read_epoch(epoch_id)
        initial = [e for e in events if e.get("type") == "EpochStartEvent"]
        final = [e for e in events if e.get("type") == "EpochEndEvent"]
        bundles = [e for e in events if e.get("type") == "MutationBundleEvent"]
        sandbox_events = [e for e in events if e.get("type") == "SandboxEvidenceEvent"]
        return {
            "epoch_id": epoch_id,
            "initial_state": initial[0]["payload"] if initial else {},
            "bundles": bundles,
            "sandbox_events": sandbox_events,
            "final_state": final[-1]["payload"] if final else {},
        }

    def compute_incremental_digest_unverified(self, epoch_id: str) -> str:
        """Recompute digest from event payloads without hash-chain integrity checks.

        Intended for forensic / tamper-analysis workflows where the ledger chain
        may already be compromised. For production replay verification use
        :meth:`compute_incremental_digest` which enforces chain integrity first.
        """

        return self.ledger.compute_incremental_epoch_digest_unverified(epoch_id)

    def compute_incremental_digest(self, epoch_id: str) -> str:
        """Recompute digest with chain-integrity verification enforced."""

        return self.ledger.compute_incremental_epoch_digest(epoch_id)

    def replay_epoch(self, epoch_id: str) -> Dict[str, Any]:
        reconstructed = self.reconstruct_epoch(epoch_id)
        replay_digest = self.compute_incremental_digest(epoch_id)
        sandbox_events = reconstructed.get("sandbox_events", [])
        sandbox_replay = [
            replay_sandbox_execution((event.get("payload") or {}).get("manifest", {}), (event.get("payload") or {}))
            for event in sandbox_events
            if isinstance((event.get("payload") or {}).get("manifest"), dict)
        ]
        replay_material = {"reconstructed": reconstructed, "replay_digest": replay_digest, "sandbox_replay": sandbox_replay}
        canonical_digest = sha256_digest(replay_material)
        return {
            "epoch_id": epoch_id,
            "digest": replay_digest,
            "canonical_digest": canonical_digest,
            "events": len(reconstructed.get("bundles", [])),
            "sandbox_replay": sandbox_replay,
        }

    def deterministic_replay(self, epoch_id: str) -> Dict[str, Any]:
        return self.replay_epoch(epoch_id)

    def assert_reachable(self, epoch_id: str, expected_digest: str) -> bool:
        replay = self.replay_epoch(epoch_id)
        return replay["digest"] == expected_digest

    def version_validate(self, bundle: Dict[str, Any], mode: str = "strict") -> Dict[str, Any]:
        return ReplayVersionValidator().validate(bundle, mode=mode)


__all__ = ["ReplayEngine", "ReplayVersionValidator"]
