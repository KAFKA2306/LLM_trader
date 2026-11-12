import unittest
from book_replay import BookEvidenceError
from order_lifecycle import hypothetical_cancel_timeline


class CancelTimelineTest(unittest.TestCase):
    def test_cancel_is_not_instantaneous_and_never_implies_fill(self):
        params = dict(submit_ts_ns=100, accept_delay_ns=10,
                      cancel_ts_ns=120, cancel_delay_ns=20)
        expected = [(105, "PENDING_ACCEPT"), (110, "LIVE_UNFILLED_ASSUMPTION"),
                    (139, "LIVE_UNFILLED_ASSUMPTION"),
                    (140, "CANCELLED_UNFILLED_ASSUMPTION")]
        for when, state in expected:
            with self.subTest(when=when):
                result = hypothetical_cancel_timeline(**params, observation_ts_ns=when)
                self.assertEqual(result["state"], state)
                self.assertEqual(result["fill_status"], "NOT_MODELED")

    def test_rejects_ambiguous_or_impossible_timeline(self):
        cases = [
            dict(submit_ts_ns=100, accept_delay_ns=10, cancel_ts_ns=99,
                 cancel_delay_ns=20, observation_ts_ns=120),
            dict(submit_ts_ns=100, accept_delay_ns=30, cancel_ts_ns=110,
                 cancel_delay_ns=0, observation_ts_ns=140),
            dict(submit_ts_ns=100, accept_delay_ns=10, cancel_ts_ns=120,
                 cancel_delay_ns=20, observation_ts_ns=99),
            dict(submit_ts_ns=100, accept_delay_ns=True, cancel_ts_ns=120,
                 cancel_delay_ns=20, observation_ts_ns=140),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(BookEvidenceError):
                hypothetical_cancel_timeline(**case)

    def test_conservative_risk_gate_checks_worst_case_and_live_state(self):
        from order_lifecycle import hypothetical_cancel_risk_gate
        params = dict(submit_ts_ns=100, accept_delay_ns=10,
                      cancel_ts_ns=120, observation_ts_ns=145)
        safe = hypothetical_cancel_risk_gate(
            **params, cancel_delay_ns_grid=[0, 20],
            max_live_exposure_ns=30)
        self.assertEqual(safe["decision"], "ALLOW")
        unsafe = hypothetical_cancel_risk_gate(
            **params, cancel_delay_ns_grid=[0, 20, 40],
            max_live_exposure_ns=30)
        self.assertEqual(unsafe["decision"], "STOP")
        self.assertEqual(unsafe["reasons"],
                         ["EXPOSURE_LIMIT_EXCEEDED", "POSSIBLY_LIVE_AT_OBSERVATION"])
        with self.assertRaises(BookEvidenceError):
            hypothetical_cancel_risk_gate(
                **params, cancel_delay_ns_grid=[0, -1],
                max_live_exposure_ns=30)

    def test_pending_acceptance_cannot_be_allowed(self):
        from order_lifecycle import hypothetical_cancel_risk_gate
        result = hypothetical_cancel_risk_gate(
            submit_ts_ns=100, accept_delay_ns=50,
            cancel_ts_ns=150, cancel_delay_ns_grid=[0, 10],
            observation_ts_ns=120, max_live_exposure_ns=100)
        self.assertEqual(result["decision"], "STOP")
        self.assertEqual(result["reasons"], ["ACCEPTANCE_PENDING_AT_OBSERVATION"])

    def test_cancel_delay_grid_bounds_and_fail_closed(self):
        from order_lifecycle import hypothetical_cancel_delay_sensitivity
        params = dict(submit_ts_ns=100, accept_delay_ns=10,
                      cancel_ts_ns=120, observation_ts_ns=145)
        r = hypothetical_cancel_delay_sensitivity(
            **params, cancel_delay_ns_grid=[0, 20, 40])
        self.assertEqual([s["state"] for s in r["scenarios"]],
                         ["CANCELLED_UNFILLED_ASSUMPTION",
                          "CANCELLED_UNFILLED_ASSUMPTION",
                          "LIVE_UNFILLED_ASSUMPTION"])
        self.assertEqual((r["min_live_exposure_ns"], r["max_live_exposure_ns"]), (10, 50))
        self.assertEqual(r["fill_status"], "NOT_MODELED")
        for grid in ([], [0, -1], [0, True], [0, 0], [0] * 257):
            with self.subTest(grid=grid), self.assertRaises(BookEvidenceError):
                hypothetical_cancel_delay_sensitivity(**params, cancel_delay_ns_grid=grid)


if __name__ == "__main__":
    unittest.main()
