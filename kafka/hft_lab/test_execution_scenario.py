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


if __name__ == "__main__":
    unittest.main()
