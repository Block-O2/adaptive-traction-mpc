from dataclasses import fields

import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.minimal_adaptation import (
    dynamic_scale_projection,
    effective_base_parameters,
)
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification import Stage5HumanIDMeasurement
from traction_mpc_stage5.human_identification_reduced import (
    ReducedIntegralScaleIdentifier,
    ReducedShadowHumanIdentificationService,
    reduced_information,
)


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def _in_model_history(scales: np.ndarray, duration_s: float = 2.6):
    geometry = _geometry()
    model = BaseParameterHumanModel(
        geometry,
        effective_base_parameters(scales, nominal_base_parameters(STAGE5_HUMAN)),
        STAGE5_HUMAN,
    )
    times = np.arange(0.0, duration_s + 1.0e-12, 0.005)
    history = []
    for index, time_s in enumerate(times):
        q = np.radians(
            [
                18.0 + 8.0 * np.sin(2.1 * time_s) + 2.0 * np.sin(5.3 * time_s),
                30.0 + 11.0 * np.sin(1.7 * time_s + 0.4),
            ]
        )
        dq = np.radians(
            [
                8.0 * 2.1 * np.cos(2.1 * time_s)
                + 2.0 * 5.3 * np.cos(5.3 * time_s),
                11.0 * 1.7 * np.cos(1.7 * time_s + 0.4),
            ]
        )
        ddq = np.radians(
            [
                -8.0 * 2.1**2 * np.sin(2.1 * time_s)
                - 2.0 * 5.3**2 * np.sin(5.3 * time_s),
                -11.0 * 1.7**2 * np.sin(1.7 * time_s + 0.4),
            ]
        )
        tau = model.inverse_dynamics(q, dq, ddq)
        allocated = model.allocate_generalized_action(tau, q)
        wrench = allocated["wrench_world"]
        history.append(
            {
                "time_s": float(time_s),
                "state": np.concatenate([q, dq]),
                "force_world_n": wrench[:3],
                "moment_world_nm": wrench[3:],
                "generalized_input_nm": tau,
                "contaminated": False,
                "source_index": index,
                "task_phase": "OUTBOUND",
            }
        )
    return geometry, history


def test_frozen_projection_preserves_stiffness_rest_pair_ratios() -> None:
    prior = nominal_base_parameters(STAGE5_HUMAN)
    scales = np.array([1.07, 1.18, 0.91])
    beta = effective_base_parameters(scales, prior)
    assert np.allclose(beta[:5], scales[0] * prior[:5])
    assert np.allclose(beta[5:9], scales[1] * prior[5:9])
    assert np.allclose(beta[9:11], scales[2] * prior[9:11])
    assert np.allclose(beta[7:9] / beta[5:7], prior[7:9] / prior[5:7])
    assert np.allclose(dynamic_scale_projection(prior) @ np.ones(3), prior)


def test_reduced_fit_recovers_in_model_scales_without_truth_input() -> None:
    truth = np.array([1.08, 1.15, 1.20])
    geometry, history = _in_model_history(truth)
    identifier = ReducedIntegralScaleIdentifier()
    result = identifier.attempt(history, geometry, np.ones(3))
    assert result["attempted"] is True
    assert result["accepted"] is True
    assert result["information"]["rank"] == 3
    assert result["information"]["regularization_counted_as_information"] is False
    assert np.max(np.abs(np.asarray(result["candidate_scales"]) - truth)) < 0.012


def test_reduced_information_reports_data_only_rank_and_correlation() -> None:
    matrix = np.array(
        [[1.0, 0.0, 0.2], [0.0, 1.0, -0.1], [0.4, 0.3, 1.0], [0.2, -0.2, 0.5]]
    )
    information = reduced_information(matrix)
    assert information["rank"] == 3
    assert np.isfinite(information["condition_number"])
    assert information["regularization_counted_as_information"] is False


def test_reduced_service_remains_shadow_only_and_truth_free() -> None:
    service = ReducedShadowHumanIdentificationService(_geometry())
    summary = service.summary()
    assert summary["shadow_only"] is True
    assert summary["control_model_changed"] is False
    assert summary["truth_available_to_service"] is False
    publication = summary["retained_model"]
    assert publication["applied_to_control"] is False
    assert publication["shadow_only"] is True
    measurement_fields = {item.name for item in fields(Stage5HumanIDMeasurement)}
    assert all("truth" not in name.lower() for name in measurement_fields)
    assert all("mujoco" not in name.lower() for name in measurement_fields)
