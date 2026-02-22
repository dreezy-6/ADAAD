# SPDX-License-Identifier: Apache-2.0
"""Checkpoint chain verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import ZERO_HASH, sha256_prefixed_digest


@dataclass(frozen=True)
class CheckpointVerificationError(RuntimeError):
    """Deterministic checkpoint verification error with stable code."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}:{self.detail}"


class CheckpointVerifier:
    """Verifier for epoch checkpoint materialization in append-only ledgers."""

    @staticmethod
    def _checkpoint_material(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "epoch_id": payload.get("epoch_id"),
            "epoch_digest": payload.get("epoch_digest"),
            "baseline_digest": payload.get("baseline_digest"),
            "mutation_count": payload.get("mutation_count"),
            "promotion_event_count": payload.get("promotion_event_count"),
            "scoring_event_count": payload.get("scoring_event_count"),
            "promotion_policy_hash": payload.get("promotion_policy_hash"),
            "entropy_policy_hash": payload.get("entropy_policy_hash"),
            "evidence_hash": payload.get("evidence_hash"),
            "sandbox_policy_hash": payload.get("sandbox_policy_hash"),
            "prev_checkpoint_hash": payload.get("prev_checkpoint_hash"),
        }

    @staticmethod
    def verify_all_epochs(ledger_path: str | Path) -> Dict[str, Any]:
        ledger = LineageLedgerV2(Path(ledger_path))
        epoch_ids = ledger.list_epoch_ids()
        checkpoint_count = 0

        for epoch_id in epoch_ids:
            previous = ZERO_HASH
            checkpoints: List[Dict[str, Any]] = [
                dict(entry.get("payload") or {})
                for entry in ledger.read_epoch(epoch_id)
                if entry.get("type") == "EpochCheckpointEvent"
            ]
            for index, checkpoint in enumerate(checkpoints):
                prev_hash = str(checkpoint.get("prev_checkpoint_hash") or "")
                if prev_hash != previous:
                    raise CheckpointVerificationError(
                        code="checkpoint_prev_missing",
                        detail=f"epoch={epoch_id};index={index}",
                    )

                expected_hash = sha256_prefixed_digest(CheckpointVerifier._checkpoint_material(checkpoint))
                actual_hash = str(checkpoint.get("checkpoint_hash") or "")
                if actual_hash != expected_hash:
                    raise CheckpointVerificationError(
                        code="checkpoint_hash_mismatch",
                        detail=f"epoch={epoch_id};index={index}",
                    )

                previous = actual_hash
                checkpoint_count += 1

        return {
            "epoch_count": len(epoch_ids),
            "checkpoint_count": checkpoint_count,
            "verified": True,
        }


def verify_checkpoint_chain(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
    checkpoints: List[Dict[str, Any]] = [
        dict(entry.get("payload") or {})
        for entry in ledger.read_epoch(epoch_id)
        if entry.get("type") == "EpochCheckpointEvent"
    ]
    previous = ZERO_HASH
    errors: List[str] = []
    for index, cp in enumerate(checkpoints):
        prev = str(cp.get("prev_checkpoint_hash") or "")
        if prev != previous:
            errors.append(f"prev_checkpoint_mismatch:{index}")
        expected_hash = sha256_prefixed_digest(CheckpointVerifier._checkpoint_material(cp))
        if str(cp.get("checkpoint_hash") or "") != expected_hash:
            errors.append(f"checkpoint_hash_mismatch:{index}")
        previous = str(cp.get("checkpoint_hash") or previous)
    return {"epoch_id": epoch_id, "count": len(checkpoints), "passed": not errors, "errors": errors}


__all__ = ["CheckpointVerifier", "CheckpointVerificationError", "verify_checkpoint_chain"]
