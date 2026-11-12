"""Small, repeatable L2 replay benchmark for an evidence-first research harness.

Synthetic inputs test code behaviour and local computational cost, not trading PnL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

from book_replay import DiffDepthBook


class BenchmarkEvidenceError(ValueError):
    """Comparison evidence is missing or not comparable."""


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fixture(events: int, levels: int) -> tuple[dict, list[dict]]:
    if type(events) is not int or not 1 <= events <= 100_000:
        raise BenchmarkEvidenceError("events must be between 1 and 100000")
    if type(levels) is not int or not 2 <= levels <= 1000:
        raise BenchmarkEvidenceError("levels must be between 2 and 1000")
    snapshot = {
        "lastUpdateId": 100,
        "bids": [[str(10_000 - i), "2"] for i in range(levels)],
        "asks": [[str(10_002 + i), "2"] for i in range(levels)],
    }
    updates = []
    for i in range(events):
        offset = 1 + (i // 2) % (levels - 1)  # Never edit the best bid/ask.
        bid = i % 2 == 0
        price = 10_000 - offset if bid else 10_002 + offset
        change = [[str(price), "0" if i % 7 == 0 else str(1 + i % 3)]]
        updates.append({
            "U": 101 + i, "u": 101 + i,
            "b": change if bid else [], "a": [] if bid else change,
        })
    return snapshot, updates


def _state_digest(book: DiffDepthBook) -> str:
    return _digest({
        "last_id": book.last_id,
        "bids": [[str(p), str(q)] for p, q in sorted(book.bids.items())],
        "asks": [[str(p), str(q)] for p, q in sorted(book.asks.items())],
    })


def _replay(snapshot: dict, updates: list[dict]) -> tuple[str, tuple[str, str]]:
    book = DiffDepthBook(snapshot)
    for event in updates:
        if not book.apply(event):
            raise BenchmarkEvidenceError("unexpected stale event in frozen fixture")
    top = book.top()
    if book.last_id != 100 + len(updates) or top != (10_000, 10_002):
        # Decimal and integer compare exactly; no floats in the book.
        raise BenchmarkEvidenceError("replay correctness invariant failed")
    return _state_digest(book), (str(top[0]), str(top[1]))


def run_benchmark(*, events: int = 2000, levels: int = 50, repeats: int = 7, revision: str) -> dict:
    if type(repeats) is not int or not 5 <= repeats <= 25:
        raise BenchmarkEvidenceError("repeats must be between 5 and 25")
    if not isinstance(revision, str) or not revision.strip():
        raise BenchmarkEvidenceError("revision must identify the evaluated code")
    snapshot, updates = _fixture(events, levels)
    expected_hash, top = _replay(snapshot, updates)  # Warmup is excluded from timings.
    durations_ns = []
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        result_hash, current_top = _replay(snapshot, updates)
        durations_ns.append(time.perf_counter_ns() - t0)
        if result_hash != expected_hash or current_top != top:
            raise BenchmarkEvidenceError("fresh replay differs from baseline state")
    samples = [round(n / 1_000_000, 6) for n in durations_ns]
    median_ns = statistics.median(durations_ns)
    return {
        "schema_version": 1,
        "status": "CODE_VERIFIED_PERF_OBSERVATION",
        "scope": "synthetic fixture; runtime performance only, not market evidence",
        "revision": revision.strip(),
        "fixture": {"generator": "l2_synthetic_v1", "events": events, "levels": levels,
                    "sha256": _digest({"snapshot": snapshot, "updates": updates})},
        "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                    "platform": platform.platform(), "machine": platform.machine()},
        "correctness": {"final_sha256": expected_hash, "last_update_id": 100 + events,
                        "best_bid": top[0], "best_ask": top[1], "cold_replay_consistent": True},
        "timings_ms": {"samples": samples, "median": round(median_ns / 1_000_000, 6),
                       "minimum": min(samples), "maximum": max(samples),
                       "relative_range": round((max(durations_ns) - min(durations_ns)) / median_ns, 6)},
        "warning": "Host load, CPU governor and background processes are uncontrolled. Never use this as a trading profitability score.",
    }


def compare(before: dict, after: dict) -> dict:
    if before.get("schema_version") != 1 or after.get("schema_version") != 1:
        raise BenchmarkEvidenceError("unsupported benchmark report schema")
    if before.get("fixture") != after.get("fixture"):
        raise BenchmarkEvidenceError("not comparable: frozen fixture differs")
    if before.get("runtime") != after.get("runtime"):
        raise BenchmarkEvidenceError("not comparable: runtime fingerprint differs")
    if before.get("correctness") != after.get("correctness"):
        raise BenchmarkEvidenceError("replay output regression: state differs")
    if any(r.get("status") != "CODE_VERIFIED_PERF_OBSERVATION" for r in (before, after)):
        raise BenchmarkEvidenceError("invalid report status")
    for r in (before, after):
        times = r.get("timings_ms", {})
        samples = times.get("samples", [])
        if not isinstance(samples, list) or len(samples) < 5 or any(
            not isinstance(t, (int, float)) or not math.isfinite(t) or t <= 0 for t in samples
        ):
            raise BenchmarkEvidenceError("invalid timing samples")
    old = statistics.median(before["timings_ms"]["samples"])
    new = statistics.median(after["timings_ms"]["samples"])
    speedup = old / new
    # A deliberately conservative heuristic. Not a confidence interval or causality proof.
    def variation(r: dict) -> float:
        s = r["timings_ms"]["samples"]
        return (max(s) - min(s)) / statistics.median(s)
    noise_floor = max(0.05, 2 * variation(before), 2 * variation(after))
    delta = (old - new) / old
    if delta > noise_floor:
        outcome = "CANDIDATE_SPEEDUP_REPLICATE"
    elif delta < -noise_floor:
        outcome = "CANDIDATE_REGRESSION_RECHECK"
    else:
        outcome = "INCONCLUSIVE_WITHIN_VARIATION"
    return {
        "status": outcome,
        "baseline_revision": before["revision"], "candidate_revision": after["revision"],
        "fixture_sha256": before["fixture"]["sha256"],
        "relative_median_change": round(delta, 6),
        "median_speedup_ratio": round(speedup, 6),
        "heuristic_noise_floor": round(noise_floor, 6),
        "warning": "Heuristic only; independent repeated runs and independent correctness tests are required before adoption.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    run = sub.add_parser("run", help="replay a fixed synthetic case many times")
    run.add_argument("--revision", required=True)
    run.add_argument("--events", type=int, default=2000)
    run.add_argument("--levels", type=int, default=50)
    run.add_argument("--repeats", type=int, default=7)
    run.add_argument("--output", type=Path)
    pair = sub.add_parser("compare", help="compare frozen baseline/candidate observations")
    pair.add_argument("--before", type=Path, required=True)
    pair.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.operation == "run":
            result = run_benchmark(events=args.events, levels=args.levels,
                                   repeats=args.repeats, revision=args.revision)
        else:
            result = compare(json.loads(args.before.read_text(encoding="utf-8")),
                             json.loads(args.after.read_text(encoding="utf-8")))
    except (BenchmarkEvidenceError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"status": "UNVERIFIED", "reason": str(error)}))
        return 2
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.operation == "run" and args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
