import copy
import unittest

from replay_benchmark import BenchmarkEvidenceError, compare, run_benchmark


class BenchmarkContractTest(unittest.TestCase):
    def test_same_frozen_fixture_is_inconclusive_without_change(self):
        report = run_benchmark(events=40, levels=5, repeats=5, revision="original")
        later = copy.deepcopy(report)
        later["revision"] = "candidate"
        self.assertEqual(report["correctness"]["best_bid"], "10000")
        self.assertEqual(report["correctness"]["best_ask"], "10002")
        self.assertTrue(report["correctness"]["cold_replay_consistent"])
        self.assertEqual(compare(report, later)["status"], "INCONCLUSIVE_WITHIN_VARIATION")

    def test_reject_changed_output_even_with_faster_timings(self):
        before = run_benchmark(events=30, levels=3, repeats=5, revision="original")
        after = copy.deepcopy(before)
        after["revision"] = "candidate"
        after["timings_ms"]["samples"] = [0.01] * 5
        after["correctness"]["final_sha256"] = "not-correct"
        with self.assertRaisesRegex(BenchmarkEvidenceError, "state differs"):
            compare(before, after)

    def test_reject_different_scenario(self):
        before = run_benchmark(events=30, levels=3, repeats=5, revision="original")
        after = run_benchmark(events=31, levels=3, repeats=5, revision="candidate")
        with self.assertRaisesRegex(BenchmarkEvidenceError, "fixture differs"):
            compare(before, after)


if __name__ == "__main__":
    unittest.main()
