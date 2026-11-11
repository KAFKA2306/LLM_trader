"""Focused contract tests for exchange event matching and latency bounds."""

import json
import tempfile
import unittest
from pathlib import Path

from latency_calibration import EvidenceError, calibrate


class LatencyCalibrationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name, rows):
        path = self.root / name
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def pair(self, count=5):
        historical = [
            {"venue": "X", "symbol": "BTC", "event_id": str(i), "exchange_ts_ns": 1_000_000_000 + i * 1_000_000}
            for i in range(count)
        ]
        live = [dict(r, recv_ts_ns=r["exchange_ts_ns"] + (i + 1) * 1_000_000) for i, r in enumerate(historical)]
        return historical, live

    def test_calibrates_matching_events_and_reports_provenance(self):
        historical, live = self.pair()
        result = calibrate(self.write("historic.jsonl", historical), self.write("live.jsonl", live), clock_error_ms=0.2, min_pairs=5)
        self.assertEqual(result["status"], "CALIBRATED_OBSERVATION")
        self.assertEqual(result["delay_ms"]["p50"], 3)
        self.assertEqual(result["delay_ms"]["p95"], 4.8)
        self.assertEqual(result["matched_events"], 5)
        self.assertEqual(len(result["live_sha256"]), 64)

    def test_rejects_inadequate_overlap(self):
        historical, live = self.pair()
        with self.assertRaisesRegex(EvidenceError, "coverage"):
            calibrate(self.write("h.jsonl", historical), self.write("l.jsonl", live[:4]), clock_error_ms=0.1, min_pairs=4)

    def test_rejects_mismatched_exchange_time(self):
        historical, live = self.pair()
        live[0]["exchange_ts_ns"] += 1
        with self.assertRaisesRegex(EvidenceError, "timestamps differ"):
            calibrate(self.write("h.jsonl", historical), self.write("l.jsonl", live), clock_error_ms=0.1, min_pairs=5)

    def test_rejects_clock_violations(self):
        historical, live = self.pair()
        live[0]["recv_ts_ns"] = historical[0]["exchange_ts_ns"] - 5_000_000
        with self.assertRaisesRegex(EvidenceError, "negative latency"):
            calibrate(self.write("h.jsonl", historical), self.write("l.jsonl", live), clock_error_ms=0.1, min_pairs=5)

    def test_rejects_duplicate_event_id(self):
        historical, live = self.pair()
        with self.assertRaisesRegex(EvidenceError, "duplicate"):
            calibrate(self.write("h.jsonl", historical + historical[:1]), self.write("l.jsonl", live), clock_error_ms=0.1, min_pairs=5)


if __name__ == "__main__":
    unittest.main()
