from __future__ import annotations

from copy import deepcopy

from traction_mpc_stage4.mpc_action_pareto_audit import (
    pareto_indices,
    summarize_candidate_call,
)


def _candidate(
    index: int, tracking: float, surface: float, force: float, moment: float
) -> dict[str, object]:
    return {
        "iteration": 0,
        "candidate_index": index,
        "feasible": True,
        "minimum_constraint_margin": 1.0,
        "actual_total_objective": tracking,
        "first_generalized_torque_nm": [float(index), -float(index)],
        "tracking_cost": tracking,
        "q_tracking_cost": tracking,
        "dq_tracking_cost": 0.0,
        "action_cost": 0.0,
        "action_slew_cost": 0.0,
        "base_task_objective": tracking,
        "registered_interaction_cost": 0.01 * (surface + force + moment),
        "registered_interaction_total_objective": (
            tracking + 0.01 * (surface + force + moment)
        ),
        "predicted_resultant_force_n": {"peak": force, "rms": force},
        "predicted_abs_sagittal_moment_nm": {"peak": moment, "rms": moment},
        "predicted_cylindrical_surface_proxy_n": {
            "peak": surface,
            "rms": surface,
        },
    }


def test_pareto_indices_reject_jointly_dominated_candidate() -> None:
    records = [
        _candidate(0, 10.0, 10.0, 10.0, 10.0),
        _candidate(1, 10.1, 8.0, 8.0, 8.0),
        _candidate(2, 11.0, 12.0, 12.0, 12.0),
    ]
    assert pareto_indices(records) == [0, 1]


def test_call_summary_reports_near_tracking_interaction_candidate() -> None:
    records = [
        _candidate(0, 10.0, 100.0, 90.0, 12.0),
        _candidate(1, 10.1, 80.0, 72.0, 9.0),
        _candidate(2, 12.0, 70.0, 65.0, 8.0),
    ]
    capture = {
        "solve_index": 12,
        "wall_time_s": 4.0,
        "candidates": deepcopy(records),
    }
    summary = summarize_candidate_call(
        capture, reference_phase_s=3.0, label="test"
    )
    band = summary["tracking_bands"]["2_percent"]
    assert band["candidate_count"] == 2
    assert band["surface_best_reduction_vs_tracking_best"] == 0.2
    reductions = band["reductions_vs_tracking_best"]
    assert reductions["surface"] == 0.2
    assert reductions["force"] == 0.2
    assert reductions["moment"] == 0.25
