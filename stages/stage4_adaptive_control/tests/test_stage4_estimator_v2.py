from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.reference import _world_from_cuff
from traction_mpc_stage4.estimator_v2 import (
    AccumulatedCuffGeometryEstimator,
    BaseParameterHumanModel,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from traction_mpc_stage4.human_model import inverse_dynamics
from traction_mpc_stage4.reference import cold_start_teaching_reference


def test_nominal_base_parameters_reproduce_human_v2_inverse_dynamics() -> None:
    initial = cold_start_teaching_reference(0.0)
    geometry_identifier = AccumulatedCuffGeometryEstimator(
        initial.world_from_cuff.translation,
        initial.world_from_cuff.rotation,
        initial.q_rad,
    )
    model = BaseParameterHumanModel(
        geometry_identifier.geometry, nominal_base_parameters()
    )
    q = np.radians([32.0, 48.0])
    dq = np.radians([7.0, -4.0])
    ddq = np.radians([18.0, 11.0])
    np.testing.assert_allclose(
        model.inverse_dynamics(q, dq, ddq),
        inverse_dynamics(q, dq, ddq, HUMAN),
        atol=1e-11,
    )
    np.testing.assert_allclose(
        dynamic_regressor_row(q, dq, ddq) @ nominal_base_parameters(),
        inverse_dynamics(q, dq, ddq, HUMAN),
        atol=1e-11,
    )


def test_nominal_pose_history_makes_geometry_trustworthy_without_truth_input() -> None:
    initial = cold_start_teaching_reference(0.0)
    estimator = AccumulatedCuffGeometryEstimator(
        initial.world_from_cuff.translation,
        initial.world_from_cuff.rotation,
        initial.q_rad,
    )
    for time in np.arange(0.0, 7.01, 0.02):
        reference = cold_start_teaching_reference(float(time))
        pose = _world_from_cuff(reference.q_rad)
        estimator.add_pose(
            float(time), pose.translation, pose.rotation, contaminated=False
        )
    assert estimator.trustworthy_time_s is not None
    assert estimator.accepted_updates > 0
    np.testing.assert_allclose(
        estimator.geometry.thigh_length_m, HUMAN.thigh_length_m, atol=2e-4
    )
    np.testing.assert_allclose(
        estimator.geometry.cuff_distance_m, HUMAN.sleeve_center_m, atol=2e-4
    )


def test_estimated_geometry_allocation_recovers_generalized_action() -> None:
    initial = cold_start_teaching_reference(0.0)
    geometry_identifier = AccumulatedCuffGeometryEstimator(
        initial.world_from_cuff.translation,
        initial.world_from_cuff.rotation,
        initial.q_rad,
    )
    model = BaseParameterHumanModel(
        geometry_identifier.geometry, nominal_base_parameters()
    )
    action = np.array([42.0, -9.0])
    allocation = model.allocate_generalized_action(
        action, np.radians([35.0, 52.0])
    )
    assert allocation["allocation_residual_nm"] < 1e-10
    assert np.all(np.isfinite(allocation["wrench_world"]))
