from __future__ import annotations

import numpy as np

from traction_mpc_stage4.reference import cold_start_joint_reference
from traction_mpc_stage4.trajectory_excitation import (
    load_trajectory_suite,
    run_trajectory_excitation_audit,
    trajectory_case,
    trajectory_joint_reference,
)


def test_suite_is_small_unique_and_anchor_is_exact() -> None:
    suite = load_trajectory_suite()
    assert 4 <= len(suite["cases"]) <= 6
    identifiers = [item["trajectory_id"] for item in suite["cases"]]
    assert len(identifiers) == len(set(identifiers))
    anchor = trajectory_case("registered_high_flexion_23s", suite)
    for time_s in np.linspace(0.0, 23.0, 47):
        expected = cold_start_joint_reference(float(time_s))
        actual = trajectory_joint_reference(anchor, float(time_s))
        for actual_item, expected_item in zip(actual, expected, strict=True):
            np.testing.assert_allclose(actual_item, expected_item, atol=0.0, rtol=0.0)


def test_preregistered_trajectories_are_finite_c2_and_inside_human_rom() -> None:
    suite = load_trajectory_suite()
    for case in suite["cases"]:
        duration = float(case["duration_s"])
        samples = np.asarray(
            [
                np.concatenate(trajectory_joint_reference(case, float(time_s)))
                for time_s in np.linspace(0.0, duration, int(round(duration / 0.01)) + 1)
            ]
        )
        assert np.all(np.isfinite(samples))
        q_deg = np.degrees(samples[:, :2])
        assert np.all(q_deg >= np.array([0.0, 0.0]) - 1e-10)
        assert np.all(q_deg <= np.array([80.0, 100.0]) + 1e-10)
        np.testing.assert_allclose(samples[0, 2:], 0.0, atol=1e-12)
        np.testing.assert_allclose(samples[-1, 2:], 0.0, atol=1e-12)


def test_offline_audit_uses_full_11_base_regressor_without_closed_loop() -> None:
    audit = run_trajectory_excitation_audit()
    assert audit["formal_experiment"] is False
    assert audit["closed_loop_executed"] is False
    assert len(audit["parameter_names"]) == 11
    assert len(audit["cases"]) == 6
    for case in audit["cases"]:
        assert case["integral_regressor_rows"] > 11
        assert len(case["estimator_span_scaled_information_matrix"]) == 11
        # The target uses trapezoidal integration at the frozen 20 ms audit
        # grid, so this is a discretization check rather than exact algebra.
        assert case["nominal_oracle_integral_identity"]["maximum_abs_error_nms"] < 5e-4
