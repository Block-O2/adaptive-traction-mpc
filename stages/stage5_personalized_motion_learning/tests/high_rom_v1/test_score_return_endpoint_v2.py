"""Focused scorer-v2 endpoint provenance tests; no simulation."""
from __future__ import annotations

import copy
import unittest

import numpy as np

from score_return_endpoint_v2 import EndpointMappingError, endpoint_from_records


def fixture():
    summary = {"status": "COMPLETE", "task": {"phase_transitions": [
        {"from": "RETURN", "to": "COMPLETE", "state_source_time_s": .995,
         "time_s": 1.0, "actual_completion_commit_ns": 1000000000,
         "estimated_state": [.1, .2, .02, .03]}]}}
    source = {"time_s": .995, "qpos_evaluation_only": [.1, .2],
              "qvel_evaluation_only": [.02, .035]}
    commit = {"time_s": 1.0, "qpos_evaluation_only": [.11, .21],
              "qvel_evaluation_only": [.01, .034]}
    artifacts = {"return_commit_attempts": [{"accepted": True, "action": "COMPLETE",
                  "source_sample_time_s": .995, "final_native_time_s": 1.0,
                  "final_host_ns": 1000000000}],
                 "wall_physics": {"native_states_evaluation_only": [source, commit],
                                  "final_native_boundary_evaluation_only": commit.copy()}}
    trace = {"time_s": np.array([.995]),
             "evaluation_only_human_state_rad_rad_s": np.array([[.1, .2, .02, .035]]),
             "estimated_human_state_rad_rad_s": np.array([[.1, .2, .02, .03]])}
    return summary, artifacts, trace


class EndpointMappingTests(unittest.TestCase):
    def test_exact_commit_state_and_repeatability(self):
        args = fixture()
        first = endpoint_from_records(*args)
        self.assertEqual(first, endpoint_from_records(*args))
        self.assertEqual(first["scorer_time_s"], 1.0)
        self.assertEqual(first["scorer_true_state_evaluation_only_rad_rad_s"],
                         [.11, .21, .01, .034])
        self.assertFalse(first["truth_consumed_by_control"])

    def test_missing_exact_commit_node_rejected(self):
        summary, artifacts, trace = fixture()
        artifacts["wall_physics"]["native_states_evaluation_only"][-1]["time_s"] = 1.00025
        with self.assertRaisesRegex(EndpointMappingError, "last native physics node timestamp"):
            endpoint_from_records(summary, artifacts, trace)

    def test_boundary_state_mismatch_rejected(self):
        summary, artifacts, trace = fixture()
        artifacts["wall_physics"]["final_native_boundary_evaluation_only"]["qvel_evaluation_only"] = [.01, .033]
        with self.assertRaisesRegex(EndpointMappingError, "differs from final boundary"):
            endpoint_from_records(summary, artifacts, trace)

    def test_earlier_scorer_source_mismatch_rejected(self):
        summary, artifacts, trace = fixture()
        trace["time_s"][-1] = .99
        with self.assertRaisesRegex(EndpointMappingError, "scorer-v1 source timestamp"):
            endpoint_from_records(summary, artifacts, trace)


if __name__ == "__main__":
    unittest.main()
