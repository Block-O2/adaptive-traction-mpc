"""Deterministic preflight checks for the zero-value session contract."""
import unittest

import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import (
    FORBIDDEN_TRANSIENT_FIELDS,
    REQUIRED_PERSISTENT_FIELDS,
    carryover_runtime_fields,
    integrate_measured_wrench,
    zero_value_decision_rows,
)


class SessionStateTests(unittest.TestCase):
    def test_repetition_reset_preserves_only_explicit_state(self):
        previous = {key: object() for key in REQUIRED_PERSISTENT_FIELDS}
        previous["command_response_history"] = object()
        previous.update({key: object() for key in FORBIDDEN_TRANSIENT_FIELDS})
        carried = carryover_runtime_fields(previous)
        self.assertTrue(all(carried[key] is previous[key] for key in REQUIRED_PERSISTENT_FIELDS))
        self.assertIs(carried["command_response_history"], previous["command_response_history"])
        self.assertFalse(set(carried).intersection(FORBIDDEN_TRANSIENT_FIELDS))
        self.assertNotIn("previous_reference", carried)

    def test_missing_persistent_state_rejected(self):
        with self.assertRaises(ValueError):
            carryover_runtime_fields({"plant": object()})

    def test_measured_force_cost_uses_simulation_intervals(self):
        result = integrate_measured_wrench(
            np.array([0.0, 1.0, 3.0]),
            np.array([[3., 0., 0.], [0., 4., 0.], [100., 0., 0.]]),
            np.array([[1., 0., 0.], [0., 2., 0.], [0., 0., 6.]]),
        )
        self.assertEqual(result["J_F_n_s"], 11.0)
        self.assertEqual(result["moment_integral_nm_s"], 5.0)
        self.assertEqual(result["peak_force_n"], 100.0)
        self.assertEqual(result["interval_count"], 2)

    def test_zero_value_rows_leave_baseline_selection_intact(self):
        decision = {
            "phase": "OUTBOUND",
            "value_hook_numeric_value": 0.0,
            "value_hook_configured": False,
            "greedy_label": "baseline_A",
            "executed_label": "baseline_A",
            "selection_mode": "greedy",
            "evaluations": [
                {"label": "baseline_A", "feasible": True, "total_cost": 1.0,
                 "cost_terms": {"task_goal_error": 1.0, "future_value": 0.0},
                 "execution_screen": {"evaluated": True}},
                {"label": "baseline_B", "feasible": True, "total_cost": 2.0,
                 "cost_terms": {"task_goal_error": 2.0, "future_value": 0.0},
                 "execution_screen": {"evaluated": True}},
                {"label": "rejected_C", "feasible": False, "total_cost": None,
                 "cost_terms": {"future_value": None},
                 "execution_screen": {"evaluated": False},
                 "rejection_reason": "geometry"},
            ],
        }
        rows = zero_value_decision_rows([decision])
        self.assertEqual(rows[0]["baseline_selected_waypoint"], "baseline_A")
        self.assertEqual([c["label"] for c in rows[0]["candidate_set"]],
                         ["baseline_A", "baseline_B", "rejected_C"])
        self.assertTrue(all(c["learned_value"] == 0.0 for c in rows[0]["candidate_set"]))
        self.assertFalse(rows[0]["candidate_set"][-1]["evaluated"])
        self.assertEqual(decision["greedy_label"], "baseline_A")

    def test_nonzero_value_is_rejected(self):
        with self.assertRaises(ValueError):
            zero_value_decision_rows([{
                "phase": "OUTBOUND", "value_hook_numeric_value": 1.0,
                "value_hook_configured": False,
                "evaluations": [],
            }])

    def test_scored_nonzero_future_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonzero learned value"):
            zero_value_decision_rows([{
                "phase": "OUTBOUND", "value_hook_numeric_value": 0.0,
                "value_hook_configured": False,
                "evaluations": [{
                    "label": "bad", "feasible": True, "total_cost": 1.5,
                    "cost_terms": {"future_value": 0.5},
                    "execution_screen": {"evaluated": True},
                }],
            }])

    def test_missing_score_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing candidate score status"):
            zero_value_decision_rows([{
                "phase": "OUTBOUND", "value_hook_numeric_value": 0.0,
                "value_hook_configured": False,
                "evaluations": [{
                    "label": "malformed", "feasible": False,
                    "cost_terms": {"future_value": None},
                    "execution_screen": {"evaluated": False},
                    "rejection_reason": "geometry",
                }],
            }])

    def test_inconsistent_unscored_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "malformed unscored candidate"):
            zero_value_decision_rows([{
                "phase": "OUTBOUND", "value_hook_numeric_value": 0.0,
                "value_hook_configured": False,
                "evaluations": [{
                    "label": "malformed", "feasible": False, "total_cost": None,
                    "cost_terms": {"future_value": None},
                    "execution_screen": {"evaluated": True},
                    "rejection_reason": "geometry",
                }],
            }])


if __name__ == "__main__":
    unittest.main()
