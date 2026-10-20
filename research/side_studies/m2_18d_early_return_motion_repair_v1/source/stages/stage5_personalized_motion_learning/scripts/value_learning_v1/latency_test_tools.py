"""Meaningful accounting guards; executable with Python standard library only."""
import unittest
from latency_tools import DecisionLatency, PIPELINE_STAGES, distribution, preliminary_budget, summarize_decisions


class LatencyAccountingTest(unittest.TestCase):
    def test_inference_only_never_claims_full_latency(self):
        ticks = iter([10,20,30])
        row = DecisionLatency("d",0,3,"v1","p1",clock=lambda: next(ticks))
        with row.stage("value_evaluation"):
            pass
        row.finish(validated=True)
        summary = summarize_decisions([row.record()])
        self.assertEqual(summary["complete_count"],0)
        self.assertIsNone(summary["full_online_decision_latency_ms"]["median"])

    def test_complete_latency_keeps_interstage_gaps(self):
        ticks=iter(range(10,150,10))
        row=DecisionLatency("d",0,3,"v1","p1",clock=lambda: next(ticks))
        for stage in PIPELINE_STAGES:
            with row.stage(stage):
                pass
        row.finish(validated=True)
        record=row.record()
        self.assertTrue(record["complete_pipeline_instrumentation"])
        self.assertEqual(record["observation_to_reference_ready_validated_ms"],.00013)
        self.assertAlmostEqual(sum(record["stages_ms"].values()),.00006)

    def test_fork_is_tighter_than_source_expiry(self):
        budget=preliminary_budget(reference_commit_progress_s=.035,activation_reserve_s=.007)
        self.assertAlmostEqual(budget["preliminary_producer_budget_s"],.028)
        self.assertTrue(budget["strict_before_ceiling"])

    def test_late_reference_has_zero_remaining_budget(self):
        budget=preliminary_budget(reference_commit_progress_s=.035,current_reference_progress_s=.040)
        self.assertEqual(budget["preliminary_producer_budget_s"],0)

    def test_failed_validation_is_preserved(self):
        row=DecisionLatency("d",0,3,"v1","p1",clock=lambda: 100)
        row.finish(validated=False,reason="GEOMETRY_CHANGED")
        record=row.record()
        self.assertEqual(record["error"],"GEOMETRY_CHANGED")
        self.assertIsNone(record["observation_to_reference_ready_validated_ms"])

    def test_percentiles_and_nonfinite(self):
        self.assertEqual(distribution([1,2,3])["median"],2)
        with self.assertRaises(ValueError): distribution([float("nan")])


if __name__ == "__main__":
    unittest.main()
