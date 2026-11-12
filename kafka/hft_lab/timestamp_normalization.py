"""Explicit exchange event timestamp normalization for offline HFT research.

This code performs no network I/O and never assumes a timestamp unit.
"""

from __future__ import annotations

from collections.abc import Mapping


class TimestampEvidenceError(ValueError):
    """A source event cannot be normalized without explicit trustworthy fields."""


_NS_PER_UNIT = {"ms": 1_000_000, "us": 1_000, "ns": 1}
_MAX_SIGNED_NS = (1 << 63) - 1
_KINDS = frozenset({"trade", "aggTrade"})


def to_nanoseconds(value: object, unit: str) -> int:
    """Convert a positive integer exchange/receive timestamp with an explicit unit."""
    if unit not in _NS_PER_UNIT:
        raise TimestampEvidenceError("timestamp unit must be explicit: ms, us, or ns")
    if type(value) is not int or value <= 0:
        raise TimestampEvidenceError("timestamp must be a positive integer, not inferred")
    result = value * _NS_PER_UNIT[unit]
    if result > _MAX_SIGNED_NS:
        raise TimestampEvidenceError("timestamp exceeds signed 64-bit nanoseconds")
    return result


def normalize_trade_event(
    event: Mapping[str, object],
    *,
    venue: str,
    symbol: str,
    kind: str,
    id_field: str,
    exchange_time_field: str,
    exchange_time_unit: str,
    receive_time_field: str | None = None,
    receive_time_unit: str | None = None,
) -> dict[str, str | int]:
    """Normalize one explicitly mapped trade event for latency_calibration.py.

    The caller must establish that historical/live raw sources describe the SAME
    trade class and exchange timestamp semantics; this function cannot prove it.
    """
    if not isinstance(event, Mapping) or not all(
        isinstance(s, str) and s for s in (venue, symbol, id_field, exchange_time_field)
    ):
        raise TimestampEvidenceError("venue, symbol and mapping keys are required")
    if kind not in _KINDS:
        raise TimestampEvidenceError("event kind must be trade or aggTrade")
    if (receive_time_field is None) != (receive_time_unit is None):
        raise TimestampEvidenceError("receive timestamp field and unit must be supplied together")
    if id_field not in event or exchange_time_field not in event:
        raise TimestampEvidenceError("explicit identity or exchange timestamp field is missing")
    raw_id = event[id_field]
    if type(raw_id) is int and raw_id >= 0:
        event_id = str(raw_id)
    elif isinstance(raw_id, str) and raw_id.isascii() and raw_id.isdecimal():
        event_id = raw_id
    else:
        raise TimestampEvidenceError("event identity must be a nonnegative trade ID")
    normalized: dict[str, str | int] = {
        "venue": venue,
        "symbol": symbol,
        "event_id": f"{kind}:{event_id}",
        "exchange_ts_ns": to_nanoseconds(event[exchange_time_field], exchange_time_unit),
    }
    if receive_time_field is not None:
        if receive_time_field not in event:
            raise TimestampEvidenceError("explicit receive timestamp field is missing")
        normalized["recv_ts_ns"] = to_nanoseconds(event[receive_time_field], receive_time_unit)
    return normalized
