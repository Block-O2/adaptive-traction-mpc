"""Proposal-only ablation guards; no simulation state or scientific claims."""
from types import SimpleNamespace
import unittest
from latency_replay_benchmark import configure_replay


class ReplayAblationTest(unittest.TestCase):
    def test_default_clears_limit_and_keeps_actual_patterns(self):
        descriptors=[{'id':i} for i in range(6)]
        planner=SimpleNamespace(research_spec={'mode':'VALUE_PATTERN','proposal_descriptors':descriptors,
                                               'legacy_candidate_limit':1,'committed_descriptor':{'id':2}})
        configure_replay(planner,count=3)
        self.assertEqual(planner.research_spec['proposal_descriptors'],descriptors[:3])
        self.assertNotIn('legacy_candidate_limit',planner.research_spec)
        self.assertEqual(planner.research_spec['committed_descriptor'],{'id':2})

    def test_pattern_count_never_fabricates_descriptors(self):
        planner=SimpleNamespace(research_spec={'mode':'VALUE_PATTERN','proposal_descriptors':[{'id':0}]})
        with self.assertRaises(ValueError):configure_replay(planner,count=6)

    def test_single_local_proposal_is_baseline(self):
        planner=SimpleNamespace(research_spec={'mode':'VALUE_RANK'})
        configure_replay(planner,count=1,legacy_limit=3)
        self.assertEqual(planner.research_spec['candidate_offsets'],[0.])
        self.assertEqual(planner.research_spec['legacy_candidate_limit'],3)

    def test_invalid_counts_fail(self):
        planner=SimpleNamespace(research_spec={})
        with self.assertRaises(ValueError):configure_replay(planner,count=0)
        with self.assertRaises(ValueError):configure_replay(planner,count=3,legacy_limit=0)


if __name__=='__main__':unittest.main()
