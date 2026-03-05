# SPDX-License-Identifier: Apache-2.0
"""Economic ingestion pipeline contracts for AGM runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from runtime.economic.schema import MarketSignal, MarketSnapshot

_UTC = timezone.utc
_ZERO_OFFSET = timedelta(0)


class MarketIngestionError(ValueError):
    """Raised when market payload event-time validation fails."""


class MarketIngestion:
    """Normalizes raw market payloads into typed snapshots."""

    def parse(self, *, snapshot_id: str, payloads: Iterable[dict[str, object]]) -> MarketSnapshot:
        signals: list[MarketSignal] = []
        for idx, payload in enumerate(payloads):
            source = str(payload.get("source", "unknown"))
            symbol = str(payload.get("symbol", "UNKNOWN"))
            value = float(payload.get("value", 0.0))
            observed_at = payload.get("observed_at")
            if isinstance(observed_at, datetime):
                ts = observed_at
                if ts.tzinfo is None:
                    raise MarketIngestionError(f"payload[{idx}]:observed_at_missing_timezone")
                if ts.utcoffset() != _ZERO_OFFSET:
                    ts = ts.astimezone(_UTC)
            elif isinstance(observed_at, str) and observed_at:
                try:
                    ts = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise MarketIngestionError(f"payload[{idx}]:invalid_observed_at_format") from exc
                if ts.tzinfo is None:
                    raise MarketIngestionError(f"payload[{idx}]:observed_at_missing_timezone")
                if ts.utcoffset() != _ZERO_OFFSET:
                    ts = ts.astimezone(_UTC)
            else:
                raise MarketIngestionError(f"payload[{idx}]:missing_observed_at")
            tags = payload.get("tags")
            normalized_tags = tags if isinstance(tags, dict) else {}
            signals.append(
                MarketSignal(
                    source=source,
                    symbol=symbol,
                    value=value,
                    observed_at=ts,
                    tags={str(k): str(v) for k, v in normalized_tags.items()},
                )
            )
        return MarketSnapshot(snapshot_id=snapshot_id, signals=tuple(signals))
