from __future__ import annotations

import inspect

import numpy as np

from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark
from traction_mpc_stage5.full3d_adaptive_integration_v1.time_contract import (
    build_boundary_time_grid,
    integrate_interval_cost,
    known_motion_alignment_diagnostic,
)


def test_known_motion_exposes_historical_one_step_offset() -> None:
    diagnostic = known_motion_alignment_diagnostic(
        speed_rad_s=0.5, duration_s=0.06, dt_s=0.02
    )
    assert diagnostic["interval_count"] == 3
    assert diagnostic["boundary_sample_count"] == 4
    assert diagnostic["corrected_rmse_rad"] == 0.0
    assert np.isclose(diagnostic["historical_rmse_rad"], 0.01)
    assert np.isclose(diagnostic["historical_first_error_rad"], 0.01)
    assert np.isclose(diagnostic["historical_last_error_rad"], 0.01)


def test_noninteger_duration_has_short_final_interval_and_no_extra_step() -> None:
    grid = build_boundary_time_grid(0.055, 0.02)
    assert np.allclose(grid.boundary_times_s, [0.0, 0.02, 0.04, 0.055])
    assert np.allclose(grid.interval_durations_s, [0.02, 0.02, 0.015])
    assert np.isclose(np.sum(grid.interval_durations_s), 0.055)


def test_force_cost_uses_actual_interval_duration() -> None:
    grid = build_boundary_time_grid(0.055, 0.02)
    assert np.isclose(
        integrate_interval_cost([10.0, 20.0, 40.0], grid.interval_durations_s),
        10.0 * 0.02 + 20.0 * 0.02 + 40.0 * 0.015,
    )


def test_evaluator_preserves_historical_default_and_adds_aligned_v2_branch() -> None:
    source = inspect.getsource(functional_benchmark.run_closed_loop_case)
    loop = source.index("for step in range(task_steps):")
    reference = source.index("ref = reference(time_s)", loop)
    integration = source.index("state_true = _integrate_substeps(", reference)
    true_append = source.index("true_states.append(", integration)
    reference_append = source.index(
        "references.append(np.concatenate([ref.q_rad, ref.dq_rad_s]))",
        true_append,
    )
    assert reference < integration < true_append < reference_append
    assert "int(round(task.duration_s / dt_s)) + 1" in source
    assert 'evaluation_time_contract: str = "historical_post_state_pre_reference_v1"' in source
    assert '"boundary_aligned_v2"' in source
    assert "pre_interval_true_state.copy() if boundary_aligned else state_true.copy()" in source
    assert "len(true_array) == len(executed_interval_durations_s) + 1" in source
