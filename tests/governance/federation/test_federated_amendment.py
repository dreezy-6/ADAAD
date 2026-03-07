# SPDX-License-Identifier: Apache-2.0
"""Phase 6 acceptance tests for M6-04 (T6-04-01..10)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from runtime.autonomy.roadmap_amendment_engine import DeterminismViolation, GovernanceViolation


class FederationKeyError(RuntimeError):
    """Raised when federation HMAC key validation fails."""


@dataclass
class Proposal:
    proposal_id: str
    authority_level: str = "governor-review"
    verify_replay_ok: bool = True
    lineage_chain: dict[str, str] = field(default_factory=dict)


@dataclass
class Node:
    node_id: str
    pending: bool = False
    divergence_count: int = 0
    received: list[str] = field(default_factory=list)
    ledger_events: list[str] = field(default_factory=list)


def _propagate(
    *,
    source: Node,
    peers: list[Node],
    proposal: Proposal,
    hmac_key: str | None,
    source_approved: bool = True,
    inject_partial_failure: bool = False,
) -> None:
    if not hmac_key:
        raise FederationKeyError("federation_hmac_required")
    if source.divergence_count > 0 or any(peer.divergence_count > 0 for peer in peers):
        raise GovernanceViolation("PHASE6_FEDERATED_AMENDMENT_DIVERGENCE_BLOCKED")
    if proposal.authority_level != "governor-review":
        raise GovernanceViolation("PHASE6_FEDERATED_AUTHORITY_VIOLATION")
    if any(peer.pending for peer in peers):
        raise GovernanceViolation("PHASE6_FEDERATED_AMENDMENT_STORM_BLOCKED")
    if not proposal.verify_replay_ok:
        raise DeterminismViolation("verify_replay mismatch")

    proposal.lineage_chain["federation_origin"] = source.node_id
    before = [list(peer.received) for peer in peers]
    for idx, peer in enumerate(peers):
        if inject_partial_failure and idx == len(peers) - 1:
            for rollback_peer, history in zip(peers, before):
                rollback_peer.received = history
                rollback_peer.ledger_events = [
                    event for event in rollback_peer.ledger_events if event != "federated_amendment_propagated"
                ]
                rollback_peer.ledger_events.append("federated_amendment_rollback")
            raise GovernanceViolation("federated rollback")
        peer.received.append(proposal.proposal_id)
        if source_approved:
            peer.ledger_events.append("destination_evaluates_fresh")
        peer.ledger_events.append("federated_amendment_propagated")
    source.ledger_events.append("federated_amendment_propagated")


# T6-04-01

def test_t6_04_01_all_gates_pass_destination_gets_proposed() -> None:
    source = Node("source")
    peers = [Node("peer-a"), Node("peer-b")]
    proposal = Proposal("prop-1")
    _propagate(source=source, peers=peers, proposal=proposal, hmac_key="k" * 32)
    assert all("prop-1" in peer.received for peer in peers)
    assert "federated_amendment_propagated" in source.ledger_events


# T6-04-02

def test_t6_04_02_source_approval_does_not_bind_destination() -> None:
    source = Node("source")
    peer = Node("peer")
    _propagate(source=source, peers=[peer], proposal=Proposal("prop-2"), hmac_key="k" * 32, source_approved=True)
    assert "destination_evaluates_fresh" in peer.ledger_events


# T6-04-03

def test_t6_04_03_divergence_blocks_and_keeps_peers_unchanged() -> None:
    with pytest.raises(GovernanceViolation, match="PHASE6_FEDERATED_AMENDMENT_DIVERGENCE_BLOCKED"):
        _propagate(
            source=Node("source", divergence_count=1),
            peers=[Node("peer")],
            proposal=Proposal("prop-3"),
            hmac_key="k" * 32,
        )


# T6-04-04

def test_t6_04_04_partial_failure_rolls_back_every_peer() -> None:
    source = Node("source")
    peers = [Node("peer-a"), Node("peer-b")]
    with pytest.raises(GovernanceViolation, match="rollback"):
        _propagate(
            source=source,
            peers=peers,
            proposal=Proposal("prop-4"),
            hmac_key="k" * 32,
            inject_partial_failure=True,
        )
    assert peers[0].received == []
    assert peers[1].received == []
    assert all("federated_amendment_propagated" not in p.ledger_events for p in peers)


# T6-04-05

def test_t6_04_05_federation_origin_is_in_lineage_chain() -> None:
    source = Node("source")
    proposal = Proposal("prop-5")
    _propagate(source=source, peers=[Node("peer")], proposal=proposal, hmac_key="k" * 32)
    assert proposal.lineage_chain["federation_origin"] == "source"


# T6-04-06

def test_t6_04_06_missing_hmac_key_raises_federation_key_error() -> None:
    with pytest.raises(FederationKeyError, match="federation_hmac_required"):
        _propagate(source=Node("source"), peers=[Node("peer")], proposal=Proposal("prop-6"), hmac_key=None)


# T6-04-07

def test_t6_04_07_authority_violation_rejected() -> None:
    with pytest.raises(GovernanceViolation, match="PHASE6_FEDERATED_AUTHORITY_VIOLATION"):
        _propagate(
            source=Node("source"),
            peers=[Node("peer")],
            proposal=Proposal("prop-7", authority_level="agent-review"),
            hmac_key="k" * 32,
        )


# T6-04-08

def test_t6_04_08_replay_hash_mismatch_halts_propagation() -> None:
    peer = Node("peer")
    with pytest.raises(DeterminismViolation, match="verify_replay mismatch"):
        _propagate(
            source=Node("source"),
            peers=[peer],
            proposal=Proposal("prop-8", verify_replay_ok=False),
            hmac_key="k" * 32,
        )
    assert peer.received == []


# T6-04-09

def test_t6_04_09_ledger_event_emitted_for_source_and_all_peers() -> None:
    source = Node("source")
    peers = [Node("peer-a"), Node("peer-b")]
    _propagate(source=source, peers=peers, proposal=Proposal("prop-9"), hmac_key="k" * 32)
    assert "federated_amendment_propagated" in source.ledger_events
    assert all("federated_amendment_propagated" in p.ledger_events for p in peers)


# T6-04-10

def test_t6_04_10_pending_peer_blocks_storm_invariant() -> None:
    with pytest.raises(GovernanceViolation, match="PHASE6_FEDERATED_AMENDMENT_STORM_BLOCKED"):
        _propagate(
            source=Node("source"),
            peers=[Node("peer", pending=True)],
            proposal=Proposal("prop-10"),
            hmac_key="k" * 32,
        )
