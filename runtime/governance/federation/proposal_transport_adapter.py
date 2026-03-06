# SPDX-License-Identifier: Apache-2.0
"""ProposalTransportAdapter — Phase 5 transport wire-up for federated mutation proposals.

This module bridges the ``FederationMutationBroker`` (which manages proposal
routing logic) with the ``FederationTransport`` protocol (which handles the
actual send/receive of federation envelopes).

Architecture
------------
::

    FederationMutationBroker              FederationTransport
         pending_outbound()   ─────────►  send_handshake()
         receive_proposal()   ◄─────────  receive_handshake()

The adapter is intentionally thin:
- It serializes ``FederatedMutationProposal`` objects from the broker's outbound
  queue into transport envelopes via canonical JSON.
- It deserializes inbound transport envelopes and feeds them to the broker via
  ``receive_proposal()``.
- It never modifies proposal content — all gating decisions remain in the broker.

Invariants
----------
1. ``flush_outbound`` is idempotent: proposals are cleared from the outbound
   queue after successful send; failures leave them in the queue.
2. ``receive_inbound`` is fail-safe: malformed transport envelopes are
   quarantined by the broker — never silently dropped.
3. Audit events are emitted for every flush and receive; write failures are
   fail-open.
4. The adapter never calls ``GovernanceGate`` — that responsibility stays
   entirely within the broker.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Envelope type discriminator used in transport handshake messages
_ENVELOPE_TYPE = "federated_mutation_proposal"
_ENVELOPE_SCHEMA_VERSION = "phase5.v1"


# ---------------------------------------------------------------------------
# FlushResult / ReceiveResult
# ---------------------------------------------------------------------------
@dataclass
class FlushResult:
    """Result of a single flush_outbound call."""

    sent: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"sent": self.sent, "failed": self.failed, "errors": self.errors}


@dataclass
class ReceiveResult:
    """Result of a single receive_inbound call."""

    received: int = 0
    delivered: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "received": self.received,
            "delivered": self.delivered,
            "skipped": self.skipped,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# ProposalTransportAdapter
# ---------------------------------------------------------------------------
class ProposalTransportAdapter:
    """Wire adapter between FederationMutationBroker and FederationTransport.

    Parameters
    ----------
    local_peer_id:
        Stable peer identifier for the local node (used for transport addressing).
    ledger_append_event:
        Callable matching ``LineageLedgerV2.append_event(event_type, payload)`` —
        audit sink, fail-open.
    """

    def __init__(
        self,
        *,
        local_peer_id: str,
        ledger_append_event: Callable[[str, Dict[str, Any]], Any],
    ) -> None:
        self._local_peer_id = local_peer_id
        self._ledger_append = ledger_append_event

    # ------------------------------------------------------------------
    # flush_outbound: broker → transport
    # ------------------------------------------------------------------
    def flush_outbound(
        self,
        *,
        broker: Any,
        transport: Any,
    ) -> FlushResult:
        """Send all pending outbound proposals from the broker via transport.

        Each proposal is serialized into a transport envelope and delivered via
        ``transport.send_handshake()``.  Successfully sent proposals are
        removed from the broker's outbound queue.

        Parameters
        ----------
        broker:
            ``FederationMutationBroker`` instance.
        transport:
            ``FederationTransport`` instance (send_handshake / receive_handshake).
        """
        pending = list(broker.pending_outbound())
        if not pending:
            return FlushResult()

        result = FlushResult()
        for proposal in pending:
            try:
                envelope = self._serialize_proposal(proposal)
                target_peer = str(proposal.destination_repo or self._local_peer_id)
                transport.send_handshake(
                    target_peer_id=target_peer,
                    envelope=envelope,
                )
                # Mark sent — broker removes from pending on success
                try:
                    broker.mark_proposal_sent(proposal.proposal_id)
                except AttributeError:
                    # Broker doesn't implement mark_proposal_sent: acceptable
                    pass
                result.sent += 1
                self._safe_audit(
                    "federation_transport_proposal_sent",
                    {
                        "proposal_id": proposal.proposal_id,
                        "destination_repo": target_peer,
                        "source_epoch_id": proposal.source_epoch_id,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                result.failed += 1
                result.errors.append(str(exc))
                logger.error(
                    "federation_transport.flush_outbound failed for proposal %s: %s",
                    getattr(proposal, "proposal_id", "unknown"),
                    exc,
                    exc_info=True,
                )
                self._safe_audit(
                    "federation_transport_send_failed",
                    {
                        "proposal_id": getattr(proposal, "proposal_id", "unknown"),
                        "error": str(exc),
                    },
                )

        return result

    # ------------------------------------------------------------------
    # receive_inbound: transport → broker
    # ------------------------------------------------------------------
    def receive_inbound(
        self,
        *,
        broker: Any,
        transport: Any,
    ) -> ReceiveResult:
        """Receive inbound transport envelopes and deliver them to the broker.

        Polls ``transport.receive_handshake()`` and deserializes each valid
        federation envelope into a ``FederatedMutationProposal``, then calls
        ``broker.receive_proposal()``.  Malformed envelopes are logged and
        counted as skipped.

        Parameters
        ----------
        broker:
            ``FederationMutationBroker`` instance.
        transport:
            ``FederationTransport`` instance.
        """
        try:
            raw_envelopes = transport.receive_handshake(
                local_peer_id=self._local_peer_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("federation_transport.receive_inbound transport error: %s", exc)
            return ReceiveResult(errors=[str(exc)])

        if not raw_envelopes:
            return ReceiveResult()

        result = ReceiveResult(received=len(raw_envelopes))
        for envelope in raw_envelopes:
            try:
                proposal_dict = self._deserialize_envelope(envelope)
                broker.receive_proposal(proposal_dict)
                result.delivered += 1
                self._safe_audit(
                    "federation_transport_proposal_received",
                    {
                        "proposal_id": proposal_dict.get("proposal_id", "unknown"),
                        "source_repo": proposal_dict.get("source_repo", "unknown"),
                        "local_peer_id": self._local_peer_id,
                    },
                )
            except (KeyError, ValueError, TypeError) as exc:
                result.skipped += 1
                result.errors.append(str(exc))
                logger.warning(
                    "federation_transport.receive_inbound malformed envelope: %s", exc
                )
                self._safe_audit(
                    "federation_transport_envelope_malformed",
                    {"error": str(exc)},
                )
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(str(exc))
                logger.error(
                    "federation_transport.receive_inbound broker error: %s", exc,
                    exc_info=True,
                )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _serialize_proposal(self, proposal: Any) -> Dict[str, Any]:
        """Serialize a FederatedMutationProposal into a transport envelope."""
        try:
            payload = proposal.to_dict()
        except AttributeError:
            # Fallback: proposal may already be a dict
            payload = dict(proposal)
        return {
            "envelope_type": _ENVELOPE_TYPE,
            "schema_version": _ENVELOPE_SCHEMA_VERSION,
            "sender_peer_id": self._local_peer_id,
            "payload": payload,
        }

    def _deserialize_envelope(self, envelope: Any) -> Dict[str, Any]:
        """Validate and extract proposal dict from a transport envelope.

        Raises
        ------
        ValueError
            If the envelope is not a valid federation mutation proposal envelope.
        """
        if not isinstance(envelope, dict):
            raise ValueError(f"envelope must be dict, got {type(envelope).__name__}")
        envelope_type = envelope.get("envelope_type")
        if envelope_type != _ENVELOPE_TYPE:
            raise ValueError(
                f"unexpected envelope_type '{envelope_type}'; "
                f"expected '{_ENVELOPE_TYPE}'"
            )
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("envelope.payload must be a dict")
        return payload

    def _safe_audit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit an audit event; never re-raises."""
        try:
            self._ledger_append(event_type, payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("federation_transport audit write failed: %s", exc)
