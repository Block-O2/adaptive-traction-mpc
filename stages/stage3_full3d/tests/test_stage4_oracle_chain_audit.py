from __future__ import annotations

import numpy as np

from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.oracle_chain_audit import _true_geometry, _vector_metrics


def test_true_geometry_recovers_exact_state_from_its_own_pose_and_twist() -> None:
    human, _ = registered_cold_start_perturbed_human()
    q = np.radians([31.0, 67.0])
    dq = np.radians([8.0, -11.0])
    initial_q = np.radians([5.0, 10.0])
    canonical = _true_geometry(
        human,
        np.array(
            [
                human.thigh_length_m * np.cos(initial_q[0])
                + human.sleeve_center_m * np.cos(initial_q[0] - initial_q[1]),
                0.0,
                0.062
                + human.thigh_length_m * np.sin(initial_q[0])
                + human.sleeve_center_m * np.sin(initial_q[0] - initial_q[1]),
            ]
        ),
        np.array(
            [
                [np.cos(initial_q[1] - initial_q[0]), 0.0, np.sin(initial_q[1] - initial_q[0])],
                [0.0, 1.0, 0.0],
                [-np.sin(initial_q[1] - initial_q[0]), 0.0, np.cos(initial_q[1] - initial_q[0])],
            ]
        ),
        initial_q,
    )
    pose = canonical.cuff_pose(q)
    geometry = _true_geometry(human, pose.translation, pose.rotation, q)
    linear, angular = geometry.cuff_velocity(q, dq)
    estimated = geometry.estimate_state(
        pose.translation, pose.rotation, linear, angular
    )
    np.testing.assert_allclose(estimated, np.concatenate([q, dq]), atol=1e-12)


def test_vector_metrics_separates_bias_rmse_and_peak_norm() -> None:
    error = np.array([[1.0, -1.0], [3.0, 1.0]])
    metrics = _vector_metrics(error)
    np.testing.assert_allclose(metrics["bias"], [2.0, 0.0])
    np.testing.assert_allclose(metrics["component_rmse"], [np.sqrt(5.0), 1.0])
    np.testing.assert_allclose(metrics["combined_rmse"], np.sqrt(3.0))
    np.testing.assert_allclose(metrics["peak_norm"], np.sqrt(10.0))
