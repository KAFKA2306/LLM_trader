"""Offline HFT feed-delay calibration from overlapping exchange events.

This module never connects to an exchange, changes strategies, or sends orders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median


REQUIRED_KEYS = ("venue", "symbol", "event_id", "exchange_ts_ns")


class EvidenceError(ValueError):
    """The input cannot support a defensible calibration."""


def read_events(path: Path, *, live: bool) -> tuple[dict[tuple[str, str, str], dict], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    events: dict[tuple[str, str, str], dict] = {}
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EvidenceError(f"{path.name}:{line_number}: invalid JSON") from error
        if not isinstance(row, dict):
            raise EvidenceError(f"{path.name}:{line_number}: expected object")
        if any(key not in row for key in REQUIRED_KEYS):
            raise EvidenceError(f"{path.name}:{line_number}: missing identity or exchange timestamp")
        if any(not isinstance(row[key], str) or not row[key] for key in REQUIRED_KEYS[:3]):
            raise EvidenceError(f"{path.name}:{line_number}: invalid event identity")
        if type(row["exchange_ts_ns"]) is not int or row["exchange_ts_ns"] <= 0:
            raise EvidenceError(f"{path.name}:{line_number}: invalid exchange timestamp")
        if live and (type(row.get("recv_ts_ns")) is not int or row["recv_ts_ns"] <= 0):
            raise EvidenceError(f"{path.name}:{line_number}: missing/invalid receiving timestamp")
        identity = (row["venue"], row["symbol"], row["event_id"])
        if identity in events:
            raise EvidenceError(f"{path.name}:{line_number}: duplicate event identity")
        events[identity] = row
    if not events:
        raise EvidenceError(f"{path.name}: no exchange events")
    return events, digest


def percentile(sorted_values: list[float], fraction: float) -> float:
    rank = (len(sorted_values) - 1) * fraction
    lower = math.floor(rank)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[math.ceil(rank)] * weight


def calibrate(
    historical: Path,
    live: Path,
    *,
    clock_error_ms: float,
    min_pairs: int = 100,
    min_coverage: float = 0.95,
) -> dict:
    if not math.isfinite(clock_error_ms) or clock_error_ms < 0:
        raise EvidenceError("clock_error_ms must be a nonnegative finite bound")
    if min_pairs < 2 or not 0 < min_coverage <= 1:
        raise EvidenceError("invalid minimum evidence thresholds")
    reference, historical_sha256 = read_events(historical, live=False)
    captured, live_sha256 = read_events(live, live=True)
    common = reference.keys() & captured.keys()
    delays_ms = []
    for identity in common:
        if reference[identity]["exchange_ts_ns"] != captured[identity]["exchange_ts_ns"]:
            raise EvidenceError("exchange timestamps differ for a shared event identity")
        delay = (captured[identity]["recv_ts_ns"] - reference[identity]["exchange_ts_ns"]) / 1_000_000
        if delay < -clock_error_ms:
            raise EvidenceError("negative latency exceeds declared clock uncertainty")
        delays_ms.append(delay)
    coverage = len(common) / len(reference)
    if len(common) < min_pairs:
        raise EvidenceError(f"only {len(common)} matched events; need at least {min_pairs}")
    if coverage < min_coverage:
        raise EvidenceError(f"overlap coverage {coverage:.4f} below {min_coverage:.4f}")
    delays_ms.sort()
    med = median(delays_ms)
    return {
        "status": "CALIBRATED_OBSERVATION",
        "scope": "observed feed reception delay; not a trading backtest or profit claim",
        "historical_sha256": historical_sha256,
        "live_sha256": live_sha256,
        "reference_events": len(reference),
        "live_events": len(captured),
        "matched_events": len(common),
        "match_coverage": round(coverage, 6),
        "clock_error_bound_ms": clock_error_ms,
        "delay_ms": {
            "p50": round(percentile(delays_ms, 0.50), 6),
            "p95": round(percentile(delays_ms, 0.95), 6),
            "p99": round(percentile(delays_ms, 0.99), 6),
            "jitter_p95_minus_p50": round(percentile(delays_ms, 0.95) - percentile(delays_ms, 0.50), 6),
            "min": round(delays_ms[0], 6),
            "max": round(delays_ms[-1], 6),
        },
        "limitations": [
            "clock synchronization bound is supplied, not independently measured",
            "capture and historical event identity/exchange timestamp must have the same definition",
            "distribution may change by session, venue, symbol, load and time",
            "order transmission, exchange matching and order acknowledgment are not measured",
            "no queue-position, fees, slippage, adverse-selection or out-of-sample performance inferred",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--clock-error-ms", type=float, required=True)
    parser.add_argument("--min-pairs", type=int, default=100)
    parser.add_argument("--min-coverage", type=float, default=0.95)
    args = parser.parse_args()
    try:
        output = calibrate(
            args.historical,
            args.live,
            clock_error_ms=args.clock_error_ms,
            min_pairs=args.min_pairs,
            min_coverage=args.min_coverage,
        )
    except (EvidenceError, OSError) as error:
        print(json.dumps({"status": "UNVERIFIED", "reason": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
