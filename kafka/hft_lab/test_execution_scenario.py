import unittest
from book_replay import BookEvidenceError, DiffDepthBook
from execution_scenario import hypothetical_taker


class HypotheticalExecutionTest(unittest.TestCase):
    def book(self):
        return DiffDepthBook({"lastUpdateId": 100, "bids": [["99", "2"], ["98", "3"]],
                              "asks": [["101", "2"], ["102", "3"]]})

    def test_depth_sweep_fee_and_slippage_are_explicit(self):
        buy = hypothetical_taker(self.book(), side="buy", quantity="3", fee_bps="10",
                                 extra_slippage_bps="5")
        self.assertEqual(buy["gross_quote"], "304")
        self.assertEqual(buy["fee_quote"], "0.304")
        self.assertEqual(buy["extra_slippage_quote"], "0.152")
        self.assertEqual(buy["effective_quote"], "304.456")
        sell = hypothetical_taker(self.book(), side="sell", quantity="3", fee_bps="10")
        self.assertEqual(sell["gross_quote"], "296")
        self.assertEqual(sell["effective_quote"], "295.704")

    def test_no_fabricated_full_fill_or_invalid_costs(self):
        with self.assertRaisesRegex(BookEvidenceError, "insufficient"):
            hypothetical_taker(self.book(), side="buy", quantity="6", fee_bps=0)
        for fee in ("NaN", "-1", "10001", 0.1):
            with self.subTest(fee=fee), self.assertRaises(BookEvidenceError):
                hypothetical_taker(self.book(), side="buy", quantity="1", fee_bps=fee)

    def test_poisoned_book_rejected(self):
        book = self.book()
        with self.assertRaises(BookEvidenceError):
            book.apply({"U": 102, "u": 102, "b": [], "a": []})
        with self.assertRaisesRegex(BookEvidenceError, "resnapshot"):
            hypothetical_taker(book, side="buy", quantity="1", fee_bps=0)


    def test_declared_delay_uses_only_arrival_visible_depth(self):
        from replay_provenance import make_manifest
        from execution_scenario import hypothetical_delayed_taker
        snapshot = {"lastUpdateId": 100, "bids": [["99", "2"]], "asks": [["101", "2"]]}
        events = [
            {"venue": "fixture", "symbol": "TEST", "exchange_ts_ns": 110,
             "U": 101, "u": 101, "b": [], "a": [["101", "0"], ["102", "2"]]},
            {"venue": "fixture", "symbol": "TEST", "exchange_ts_ns": 130,
             "U": 102, "u": 102, "b": [], "a": [["102", "0"], ["103", "2"]]},
        ]
        manifest = make_manifest("fixture", "TEST", "synthetic-v1", snapshot, events)
        result = hypothetical_delayed_taker(
            manifest, snapshot, events, snapshot_ts_ns=90, submit_ts_ns=100,
            delay_ns=10, side="buy", quantity="1", fee_bps="0")
        self.assertEqual(result["submission"]["gross_quote"], "101")
        self.assertEqual(result["arrival"]["gross_quote"], "102")
        self.assertEqual(result["effective_quote_change"], "1")
        result_zero = hypothetical_delayed_taker(
            manifest, snapshot, events, snapshot_ts_ns=90, submit_ts_ns=100,
            delay_ns=0, side="buy", quantity="1", fee_bps="0")
        self.assertEqual(result_zero["effective_quote_change"], "0")
        with self.assertRaisesRegex(BookEvidenceError, "not covered"):
            hypothetical_delayed_taker(
                manifest, snapshot, events, snapshot_ts_ns=90, submit_ts_ns=100,
                delay_ns=31, side="buy", quantity="1", fee_bps="0")

    def test_reject_nonmonotone_event_clock_before_replay(self):
        from replay_provenance import make_manifest
        from execution_scenario import hypothetical_delayed_taker
        snapshot = {"lastUpdateId": 100, "bids": [["99", "2"]], "asks": [["101", "2"]]}
        events = [
            {"venue": "fixture", "symbol": "TEST", "exchange_ts_ns": 120,
             "U": 101, "u": 101, "b": [], "a": []},
            {"venue": "fixture", "symbol": "TEST", "exchange_ts_ns": 110,
             "U": 102, "u": 102, "b": [], "a": []},
        ]
        manifest = make_manifest("fixture", "TEST", "synthetic-v1", snapshot, events)
        with self.assertRaisesRegex(BookEvidenceError, "timestamp order"):
            hypothetical_delayed_taker(
                manifest, snapshot, events, snapshot_ts_ns=90, submit_ts_ns=100,
                delay_ns=10, side="buy", quantity="1", fee_bps=0)


    def test_reject_event_at_or_before_snapshot_clock(self):
        from replay_provenance import make_manifest
        from execution_scenario import hypothetical_delayed_taker
        snapshot = {"lastUpdateId": 100, "bids": [["99", "2"]], "asks": [["101", "2"]]}
        for event_ts in (89, 90):
            with self.subTest(event_ts=event_ts):
                events = [{"venue": "fixture", "symbol": "TEST", "exchange_ts_ns": event_ts,
                           "U": 101, "u": 101, "b": [], "a": []},
                          {"venue": "fixture", "symbol": "TEST", "exchange_ts_ns": 120,
                           "U": 102, "u": 102, "b": [], "a": []}]
                manifest = make_manifest("fixture", "TEST", "synthetic-v1", snapshot, events)
                with self.assertRaisesRegex(BookEvidenceError, "snapshot timestamp"):
                    hypothetical_delayed_taker(
                        manifest, snapshot, events, snapshot_ts_ns=90, submit_ts_ns=100,
                        delay_ns=10, side="buy", quantity="1", fee_bps="0")


if __name__ == "__main__":
    unittest.main()
