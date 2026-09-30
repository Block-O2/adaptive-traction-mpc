"""Unique job and incomplete-boundary reporting guards; no scientific data."""
import unittest
from latency_report_section import unique_updates,stat_table,render_section


class ReportScopeTest(unittest.TestCase):
    def test_update_promoted_and_prepared_is_one_job_not_two(self):
        job={'sha256':'a','path':'candidate.npz','wall_s':.2}
        jobs,pending,failed=unique_updates({'repetition_boundary_updates':[
            dict(job,stage='update_prepared'),dict(job,stage='repetition_boundary_update'),
            dict(job,stage='final_prepared_not_promoted_without_next_boundary'),
            {'sha256':'prior','path':'prior.npz','wall_s':5,'stage':'offline_other_condition_prior_initialization'},
            {'stage':'update_pending','wait_bound_s':2},
            {'stage':'update_failed_previous_model_retained'}]})
        self.assertEqual(len(jobs),1);self.assertEqual(len(pending),1);self.assertEqual(len(failed),1)

    def test_missing_statistics_stay_unmeasured(self):
        self.assertIn('未测量',stat_table([('未采样',{})]))

    def test_cannot_render_fake_completed_host_profile(self):
        with self.assertRaises(ValueError):render_section({}, {'models':{'ridge_full':[]}})


if __name__=='__main__':unittest.main()
