import unittest
from book_replay import BookEvidenceError
from replay_provenance import ProvenanceReplay, make_manifest


class ProvenanceTest(unittest.TestCase):
    def setup_case(self):
        snapshot = {"lastUpdateId": 100, "bids": [["99", "2"]], "asks": [["101", "2"]]}
        events = [{"venue": "binance-spot", "symbol": "BTCUSDT",
                   "U": 101, "u": 101, "b": [["100", "1"]], "a": []}]
        manifest = make_manifest("binance-spot", "BTCUSDT", "synthetic-fixture-v1", snapshot, events)
        return manifest, snapshot, events

    def test_frozen_case_replays(self):
        manifest, snapshot, events = self.setup_case()
        replay = ProvenanceReplay(manifest, snapshot, events)
        self.assertTrue(replay.step())
        self.assertEqual(tuple(map(str, replay.top())), ("100", "101"))
        self.assertFalse(replay.step())

    def test_reject_mixed_symbol_and_mutation(self):
        manifest, snapshot, events = self.setup_case()
        events[0]["symbol"] = "ETHUSDT"
        with self.assertRaisesRegex(BookEvidenceError, "hash mismatch"):
            ProvenanceReplay(manifest, snapshot, events)
        manifest = make_manifest("binance-spot", "BTCUSDT", "synthetic-fixture-v1", snapshot, events)
        with self.assertRaisesRegex(BookEvidenceError, "mixed venue/symbol"):
            ProvenanceReplay(manifest, snapshot, events)

    def test_late_mixed_event_rejected_before_any_replay(self):
        manifest, snapshot, events = self.setup_case()
        events.append({"venue": "binance-spot", "symbol": "ETHUSDT",
                       "U": 102, "u": 102, "b": [], "a": []})
        manifest = make_manifest("binance-spot", "BTCUSDT", "synthetic-fixture-v1", snapshot, events)
        with self.assertRaisesRegex(BookEvidenceError, "event 1"):
            ProvenanceReplay(manifest, snapshot, events)

    def test_reject_snapshot_mismatch_and_isolate_caller_mutation(self):
        manifest, snapshot, events = self.setup_case()
        changed = dict(snapshot, lastUpdateId=99)
        with self.assertRaisesRegex(BookEvidenceError, "snapshot hash mismatch"):
            ProvenanceReplay(manifest, changed, events)
        replay = ProvenanceReplay(manifest, snapshot, events)
        events[0]["b"][0][0] = "98"
        snapshot["bids"][0][0] = "97"
        self.assertTrue(replay.step())
        self.assertEqual(tuple(map(str, replay.top())), ("100", "101"))
        self.assertEqual(replay.book.last_id, 101)


if __name__ == "__main__":
    unittest.main()
