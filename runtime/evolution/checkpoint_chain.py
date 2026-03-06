# SPDX-License-Identifier: Apache-2.0
"""Chained checkpoint digest builder for evolution epoch continuity.

Extends the base :func:`~runtime.evolution.checkpoint.checkpoint_digest`
primitive with a *chain* construct: each checkpoint commits to the digest of
its predecessor, forming a tamper-evident linked sequence analogous to a
hash chain.

Guarantees
----------
- Given identical inputs, ``checkpoint_chain_digest`` always produces the
  same output (deterministic).
- Truncating or reordering the chain is detectable: any interior checkpoint
  depends on all prior entries.
- An empty predecessor is represented as the ``ZERO_HASH`` sentinel, so the
  genesis checkpoint has a well-defined, stable digest.
- Chain verification is O(n) in the number of checkpoints.

Ledger integration
------------------
Each ``ChainedCheckpoint`` carries a ``chain_digest`` field suitable for
direct emission as a ``checkpoint_chain_link`` ledger event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from runtime.evolution.checkpoint import checkpoint_digest
from runtime.governance.foundation.hashing import sha256_prefixed_digest, ZERO_HASH

CHAIN_VERSION = "v1.0.0"


@dataclass(frozen=True)
class ChainedCheckpoint:
    """A checkpoint entry in a tamper-evident chain.

    Attributes
    ----------
    epoch_id:
        Stable epoch identifier.
    payload:
        Arbitrary governance payload for this checkpoint (must be
        JSON-serializable).
    predecessor_digest:
        ``sha256:`` digest of the immediately preceding
        ``ChainedCheckpoint.chain_digest``.  Use ``ZERO_HASH`` for the
        genesis entry.
    payload_digest:
        Canonical digest of ``payload`` alone.
    chain_digest:
        Canonical digest committing to ``(predecessor_digest, payload_digest,
        epoch_id)``.  This is the value propagated as ``predecessor_digest``
        for the next entry.
    chain_version:
        Algorithm version for deterministic replay verification.
    """

    epoch_id: str
    payload: Dict[str, Any]
    predecessor_digest: str
    payload_digest: str
    chain_digest: str
    chain_version: str = CHAIN_VERSION

    def to_ledger_event(self) -> Dict[str, Any]:
        """Return a ledger-ready ``checkpoint_chain_link`` event payload."""
        return {
            "event_type": "checkpoint_chain_link",
            "epoch_id": self.epoch_id,
            "predecessor_digest": self.predecessor_digest,
            "payload_digest": self.payload_digest,
            "chain_digest": self.chain_digest,
            "chain_version": self.chain_version,
        }


def checkpoint_chain_digest(
    payload: Dict[str, Any],
    *,
    epoch_id: str,
    predecessor_digest: str = ZERO_HASH,
) -> ChainedCheckpoint:
    """Build a :class:`ChainedCheckpoint` linking to a predecessor.

    Parameters
    ----------
    payload:
        Governance checkpoint payload for this epoch.
    epoch_id:
        Stable identifier for the epoch being checkpointed.
    predecessor_digest:
        Digest of the previous chain link.  Pass ``ZERO_HASH`` for the
        first entry (genesis).

    Returns
    -------
    ChainedCheckpoint
        Fully constructed, immutable chain entry.

    Examples
    --------
    >>> genesis = checkpoint_chain_digest({"state": "boot"}, epoch_id="epoch_0")
    >>> next_cp = checkpoint_chain_digest(
    ...     {"state": "evolved"},
    ...     epoch_id="epoch_1",
    ...     predecessor_digest=genesis.chain_digest,
    ... )
    >>> next_cp.predecessor_digest == genesis.chain_digest
    True
    """
    payload_digest = checkpoint_digest(payload)  # uses existing sha256_prefixed_digest

    chain_payload = {
        "epoch_id": str(epoch_id),
        "predecessor_digest": str(predecessor_digest),
        "payload_digest": str(payload_digest),
        "chain_version": CHAIN_VERSION,
    }
    chain_dig = sha256_prefixed_digest(chain_payload)

    return ChainedCheckpoint(
        epoch_id=str(epoch_id),
        payload=payload,
        predecessor_digest=str(predecessor_digest),
        payload_digest=payload_digest,
        chain_digest=chain_dig,
    )


def build_checkpoint_chain(
    entries: Iterable[tuple[str, Dict[str, Any]]],
) -> List[ChainedCheckpoint]:
    """Build a complete checkpoint chain from an ordered sequence of entries.

    Parameters
    ----------
    entries:
        Iterable of ``(epoch_id, payload)`` pairs in chronological order.

    Returns
    -------
    list[ChainedCheckpoint]
        Ordered chain with each entry's ``predecessor_digest`` linking to
        the previous entry's ``chain_digest``.

    Raises
    ------
    ValueError
        If ``entries`` is empty.
    """
    chain: List[ChainedCheckpoint] = []
    predecessor = ZERO_HASH

    for epoch_id, payload in entries:
        cp = checkpoint_chain_digest(
            payload,
            epoch_id=epoch_id,
            predecessor_digest=predecessor,
        )
        chain.append(cp)
        predecessor = cp.chain_digest

    if not chain:
        raise ValueError("checkpoint_chain_requires_at_least_one_entry")

    return chain


def verify_checkpoint_chain(chain: List[ChainedCheckpoint]) -> bool:
    """Verify the integrity of a checkpoint chain.

    Checks that each entry's ``predecessor_digest`` matches the previous
    entry's ``chain_digest``, and that each ``chain_digest`` is consistent
    with its declared inputs.

    Parameters
    ----------
    chain:
        Ordered list of :class:`ChainedCheckpoint` entries.

    Returns
    -------
    bool
        ``True`` if the chain is intact; ``False`` if any link is broken
        or any digest is inconsistent.
    """
    if not chain:
        return False

    # Genesis must link to ZERO_HASH
    if chain[0].predecessor_digest != ZERO_HASH:
        return False

    for i, cp in enumerate(chain):
        # Recompute chain_digest and compare
        chain_payload = {
            "epoch_id": cp.epoch_id,
            "predecessor_digest": cp.predecessor_digest,
            "payload_digest": cp.payload_digest,
            "chain_version": cp.chain_version,
        }
        expected_chain = sha256_prefixed_digest(chain_payload)
        if expected_chain != cp.chain_digest:
            return False

        # Verify predecessor linkage (skip genesis)
        if i > 0 and cp.predecessor_digest != chain[i - 1].chain_digest:
            return False

    return True


__all__ = [
    "CHAIN_VERSION",
    "ChainedCheckpoint",
    "build_checkpoint_chain",
    "checkpoint_chain_digest",
    "verify_checkpoint_chain",
]
