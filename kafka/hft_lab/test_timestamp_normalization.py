"""Contract checks for explicit, class-safe time normalization."""

import unittest

from timestamp_normalization import TimestampEvidenceError, normalize_trade_event, to_nanoseconds


class TimestampNormalizationTest(unittest.TestCase):
    def test_equivalent_explicit_units(self):
        self.assertEqual(to_nanoseconds(1_700_000_000_000, "ms"), 1_700_000_000_000_000_000)
        self.assertEqual(to_nanoseconds(1_700_000_000_000_000, "us"), 1_700_000_000_000_000_000)
        self.assertEqual(to_nanoseconds(1_700_000_000_000_000_000, "ns"), 1_700_000_000_000_000_000)

    def test_live_and_historical_normalize_to_identical_reference_event(self):
        historical = normalize_trade_event(
            {"id": 12, "time": 1_700_000_000_000_000},
            venue="Binance", symbol="BTCUSDT", kind="trade",
            id_field="id", exchange_time_field="time", exchange_time_unit="us",
        )
        live = normalize_trade_event(
            {"t": 12, "T": 1_700_000_000_000, "observed": 1_700_000_000_007_000_000},
            venue="Binance", symbol="BTCUSDT", kind="trade",
            id_field="t", exchange_time_field="T", exchange_time_unit="ms",
            receive_time_field="observed", receive_time_unit="ns",
        )
        self.assertEqual(historical["event_id"], live["event_id"])
        self.assertEqual(historical["exchange_ts_ns"], live["exchange_ts_ns"])
        self.assertEqual(live["recv_ts_ns"] - live["exchange_ts_ns"], 7_000_000)

    def test_aggregate_ids_never_alias_trade_ids(self):
        base = dict(venue="Binance", symbol="BTCUSDT", id_field="id", exchange_time_field="time", exchange_time_unit="us")
        raw = {"id": 12, "time": 1_700_000_000_000_000}
        trade = normalize_trade_event(raw, kind="trade", **base)
        agg = normalize_trade_event(raw, kind="aggTrade", **base)
        self.assertNotEqual(trade["event_id"], agg["event_id"])

    def test_rejects_unknown_units_noninteger_and_overflow(self):
        for value, unit in [(1_700_000_000_000, "auto"), (1.2, "ms"), (True, "ms"), (-1, "us"), (10**19, "ns")]:
            with self.subTest(value=value, unit=unit), self.assertRaises(TimestampEvidenceError):
                to_nanoseconds(value, unit)

    def test_rejects_missing_receive_unit_or_field_and_ambiguous_kind(self):
        fields = dict(venue="Binance", symbol="BTCUSDT", kind="trade", id_field="t", exchange_time_field="T", exchange_time_unit="ms")
        with self.assertRaises(TimestampEvidenceError):
            normalize_trade_event({"t": 1, "T": 1700000000000}, receive_time_field="observed", **fields)
        with self.assertRaises(TimestampEvidenceError):
            normalize_trade_event({"t": 1, "T": 1700000000000}, receive_time_field="observed", receive_time_unit="ns", **fields)
        with self.assertRaises(TimestampEvidenceError):
            normalize_trade_event({"t": 1, "T": 1700000000000}, **dict(fields, kind="depth"))


if __name__ == "__main__":
    unittest.main()
