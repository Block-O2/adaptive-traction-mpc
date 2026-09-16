from __future__ import annotations

from functools import lru_cache
import importlib.util
from pathlib import Path

import numpy as np

from traction_mpc_stage5.controller_interface import (
    InterfaceHoldPredictionBatch,
)


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_stage5_prefix_optimization_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage5_prefix_optimization_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@lru_cache(maxsize=1)
def _audit_result():
    return AUDIT.equivalence_audit()


def test_prefix_refactor_preserves_all_decision_outputs() -> None:
    result = _audit_result()
    assert result["passed"]
    for snapshot in result["full_solve_snapshots"]:
        assert snapshot["selected_action_max_abs_difference"] == 0.0
        assert snapshot["selected_sequence_max_abs_difference"] == 0.0
        assert snapshot["candidate_cost_max_abs_difference"] == 0.0
        assert snapshot["candidate_constraint_margin_max_abs_difference"] == 0.0
        assert snapshot["elite_indices_exact"]
        assert all(snapshot["selected_diagnostics_exact"].values())
        assert all(row["feasibility_mask_exact"] for row in snapshot["populations"])


def test_prefix_times_interface_state_and_acceleration_semantics_are_preserved() -> None:
    result = _audit_result()
    contract = result["frozen_contract"]
    assert contract["prefix_times_s"] == [0.005, 0.010, 0.015, 0.020]
    assert contract["physical_substep_s"] == 0.00025
    assert contract["horizon_candidates_iterations"] == [15, 32, 2]
    assert contract["acceleration_semantics_version"] == (
        "v2_cumulative_prefix_5_10_15_20ms"
    )
    for snapshot in result["full_solve_snapshots"]:
        for population in snapshot["populations"]:
            assert population["prefix_times_exact"]
            assert population["prefix_feasibility_exact"]
            assert (
                population[
                    "predicted_prefix_interface_displacement_human_m_max_abs_difference"
                ]
                <= AUDIT.TOLERANCE
            )
            assert (
                population[
                    "predicted_prefix_interface_angular_velocity_human_rad_s_max_abs_difference"
                ]
                <= AUDIT.TOLERANCE
            )


def test_multiple_snapshots_and_repeated_solves_have_no_stale_state() -> None:
    result = _audit_result()
    assert {row["label"] for row in result["full_solve_snapshots"]} == {
        "nominal_and_near_acceleration_limit",
        "representative_progressive_theta_5",
    }
    assert {row["label"] for row in result["saved_trace_dynamics_snapshots"]} == {
        "known_conservative_false_positive",
        "retained_real_short_transient_violation",
    }
    assert all(result["deterministic_repeatability"].values())


def test_prefix_diagnostic_fields_do_not_change_command_protocol() -> None:
    fields = InterfaceHoldPredictionBatch.__dataclass_fields__
    assert "predicted_prefix_interface_displacement_human_m" in fields
    assert "predicted_prefix_executable_wrench_world" in fields
    limits = np.asarray(_audit_result()["frozen_contract"]["task_acceleration_limits_rad_s2"])
    np.testing.assert_allclose(limits, np.radians([300.0, 600.0]), atol=0.0, rtol=0.0)
