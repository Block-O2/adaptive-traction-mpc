from dataclasses import replace

import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification import (
    ShadowHumanIdentificationService,
    Stage5HumanIDConfig,
    Stage5HumanIDMeasurement,
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


def _measurement(time_s: float, geometry: PlanarCuffGeometry) -> Stage5HumanIDMeasurement:
    state = np.radians([10.0, 20.0, 1.0, -2.0])
    force = np.array([12.0, 0.0, -35.0])
    moment = np.array([0.0, 2.5, 0.0])
    generalized = geometry.generalized_input_from_wrench(state[:2], force, moment)
    return Stage5HumanIDMeasurement(
        arrival_time_s=time_s,
        sample_time_s=time_s,
        estimated_human_state_rad_rad_s=state,
        measured_human_cuff_force_world_n=force,
        measured_human_cuff_moment_world_nm=moment,
        measured_generalized_human_input_nm=generalized,
        task_phase="OUTBOUND",
        interface_model_version=CONTROLLER_NOMINAL_INTERFACE.model_version,
    )


def test_service_contract_is_shadow_only_and_versioned() -> None:
    geometry = _geometry()
    service = ShadowHumanIdentificationService(geometry)
    status = service.observe(_measurement(0.0, geometry))
    assert status["shadow_only"] is True
    assert status["applied_to_control"] is False
    assert status["trust_state"] == "PRIOR_ONLY"
    assert status["retained_model"]["version"].endswith("v0")
    assert status["retained_model"]["applied_to_control"] is False
    assert service.retained_model is not None


def test_wrong_interface_version_and_duplicate_timestamp_are_rejected() -> None:
    geometry = _geometry()
    service = ShadowHumanIdentificationService(geometry)
    wrong = replace(_measurement(0.0, geometry), interface_model_version="plant_truth")
    status = service.observe(wrong)
    assert status["update_diagnostics"]["reason"] == "interface_model_version_mismatch"

    service = ShadowHumanIdentificationService(geometry)
    service.observe(_measurement(0.0, geometry))
    status = service.observe(_measurement(0.0, geometry))
    assert status["update_diagnostics"]["reason"] == "nonmonotonic_arrival_time"


def test_wrench_and_generalized_input_must_be_consistent() -> None:
    geometry = _geometry()
    service = ShadowHumanIdentificationService(geometry)
    bad = replace(
        _measurement(0.0, geometry),
        measured_generalized_human_input_nm=np.array([99.0, -99.0]),
    )
    status = service.observe(bad)
    assert status["update_diagnostics"]["reason"] == (
        "wrench_generalized_input_inconsistent"
    )
    assert status["measurement_count"] == 0


def test_default_embargo_cannot_publish_before_future_evidence() -> None:
    geometry = _geometry()
    config = Stage5HumanIDConfig()
    service = ShadowHumanIdentificationService(geometry, config)
    # Less than the default 1.8 s minimum future-validation delay even if a
    # challenger were launched immediately.
    for index in range(300):
        service.observe(_measurement(index * 0.005, geometry))
    assert service.summary()["publication_history"] == [
        service.publication_history[0]
    ]
    assert service.summary()["control_model_changed"] is False


def test_measurement_contract_contains_no_truth_field() -> None:
    fields = set(Stage5HumanIDMeasurement.__dataclass_fields__)
    assert all("truth" not in name.lower() for name in fields)
    assert all("mujoco" not in name.lower() for name in fields)
