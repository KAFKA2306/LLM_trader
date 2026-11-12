import unittest
from decimal import Decimal
from book_replay import BookEvidenceError, DiffDepthBook


class BookReplayTest(unittest.TestCase):
    def snapshot(self):
        return DiffDepthBook({"lastUpdateId": 100, "bids": [["99", "2"]], "asks": [["101", "3"]]})

    def test_buffered_bridge_continuity_and_deletion(self):
        book = self.snapshot()
        self.assertFalse(book.apply({"U": 90, "u": 100, "b": [], "a": []}))
        self.assertTrue(book.apply({"U": 99, "u": 102, "b": [["99", "0"], ["100", "4"]], "a": []}))
        self.assertEqual(tuple(str(x) for x in book.top()), ("100", "101"))
        self.assertTrue(book.apply({"U": 103, "u": 103, "b": [], "a": [["101", "0"], ["102", "2"]]}))
        self.assertEqual(tuple(str(x) for x in book.top()), ("100", "102"))

    def test_gap_and_duplicate_fail_without_mutating_book(self):
        book = self.snapshot()
        with self.assertRaisesRegex(BookEvidenceError, "missing"):
            book.apply({"U": 102, "u": 102, "b": [], "a": []})
        self.assertEqual(book.last_id, 100)
        self.assertTrue(book.needs_resnapshot)
        with self.assertRaisesRegex(BookEvidenceError, "resnapshot"):
            book.apply({"U": 101, "u": 101, "b": [], "a": []})
        with self.assertRaisesRegex(BookEvidenceError, "resnapshot"):
            book.top()
        # Only a new snapshot creates a trusted state again.
        book = self.snapshot()
        book.apply({"U": 101, "u": 101, "b": [], "a": []})
        with self.assertRaisesRegex(BookEvidenceError, "duplicate"):
            book.apply({"U": 101, "u": 101, "b": [], "a": []})
        self.assertEqual(book.last_id, 101)

    def test_invalid_or_crossed_update_is_atomic(self):
        book = self.snapshot()
        for bids in ([["102", "1"]], [["99", "NaN"]], [["99", "-1"]], [["99", "1"], ["99", "2"]]):
            with self.subTest(bids=bids), self.assertRaises(BookEvidenceError):
                book.apply({"U": 101, "u": 101, "b": bids, "a": []})
            self.assertEqual(book.top(), (Decimal("99"), Decimal("101")))
            self.assertEqual(book.last_id, 100)


if __name__ == "__main__":
    unittest.main()
