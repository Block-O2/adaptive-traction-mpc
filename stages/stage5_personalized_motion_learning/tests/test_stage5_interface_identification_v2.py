from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from traction_mpc_stage5.interface_identification import (
    InterfaceIdentificationSeries,
    InterfaceParameterScales,
    fixed_stage5_human_model,
)
from traction_mpc_stage5.interface_identification_v2 import (
    IdentificationPhysicalPredictorV2,
    PhysicalInterfaceIdentifierV2,
    load_identification_physical_predictor_v2_config,
)


def _series(sample_count: int = 5) -> tuple[InterfaceIdentificationSeries, np.ndarray]:
    model = fixed_stage5_human_model()
    state = np.r_[
        np.radians([5.0, 10.0, 0.0, 0.0]),
        [0.001, 0.0, -0.0015],
        np.zeros(3),
        [0.0, 0.02, 0.0],
        np.zeros(3),
    ]
    command = np.tile(np.array([20.0, 0.0, -30.0, 0.0, 5.0, 0.0]), (sample_count, 1))
    return (
        InterfaceIdentificationSeries(
            time_s=0.005 * np.arange(sample_count),
            phase=np.full(sample_count, "OUTBOUND"),
            robot_measurement=np.zeros((sample_count, 12)),
            measured_wrench_world=np.zeros((sample_count, 6)),
            executed_wrench_world=command,
            base_drive_world_n=np.zeros((sample_count, 3)),
            base_angular_drive_world_nm=np.zeros((sample_count, 3)),
            arrival_human_state=np.tile(state[:4], (sample_count, 1)),
            arrival_interface_state=np.tile(state[4:], (sample_count, 1)),
            source="unit_test",
            legacy_measurement_reconstruction=False,
            reconstruction_closure_max_abs=0.0,
        ),
        state,
    )


def test_v2_config_is_identification_only_and_uses_physics_substeps() -> None:
    config = load_identification_physical_predictor_v2_config()
    assert config.model_version == "stage5_identification_physical_predictor_v2"
    assert config.integration_substep_s == 0.00025
    assert np.all(np.asarray(config.robot_effective_mass_world_kg) > 0.0)


def test_relative_robot_human_kinematics_round_trip() -> None:
    model = fixed_stage5_human_model()
    predictor = IdentificationPhysicalPredictorV2(model)
    _, state = _series()
    robot = predictor._state_to_robot(state)  # noqa: SLF001
    recovered = predictor._relative_state(state[:4], *robot)  # noqa: SLF001
    np.testing.assert_allclose(recovered, state[4:], atol=1.0e-12, rtol=0.0)


def test_constitutive_parameters_remain_physical_kelvin_voigt_scales() -> None:
    model = fixed_stage5_human_model()
    predictor = IdentificationPhysicalPredictorV2(model)
    _, state = _series()
    nominal = predictor.measurement_from_state(InterfaceParameterScales(), state)[12:]
    stiff = predictor.measurement_from_state(
        InterfaceParameterScales(alpha_t=1.2, alpha_r=1.3, alpha_d=1.0), state
    )[12:]
    rotation = model.geometry.cuff_pose(state[:2]).rotation
    nominal_force_human = rotation.T @ nominal[:3]
    stiff_force_human = rotation.T @ stiff[:3]
    np.testing.assert_allclose(stiff_force_human, 1.2 * nominal_force_human)
    nominal_couple_human = rotation.T @ nominal[3:] - np.cross(
        state[4:7], nominal_force_human
    )
    stiff_couple_human = rotation.T @ stiff[3:] - np.cross(
        state[4:7], stiff_force_human
    )
    np.testing.assert_allclose(stiff_couple_human, 1.3 * nominal_couple_human)


def test_v2_does_not_use_old_independent_base_drive_state() -> None:
    series, state = _series()
    predictor = PhysicalInterfaceIdentifierV2()
    parameters = InterfaceParameterScales()
    baseline = predictor.predict_measurements(series, 0, 3, parameters, state)
    changed_drive = replace(
        series,
        base_drive_world_n=np.full_like(series.base_drive_world_n, 1.0e6),
        base_angular_drive_world_nm=np.full_like(
            series.base_angular_drive_world_nm, -1.0e6
        ),
    )
    alternative = predictor.predict_measurements(
        changed_drive, 0, 3, parameters, state
    )
    np.testing.assert_allclose(alternative, baseline, atol=0.0, rtol=0.0)


def test_recorded_executable_command_drives_robot_side_response() -> None:
    series, state = _series()
    predictor = PhysicalInterfaceIdentifierV2()
    baseline = predictor.predict_measurements(
        series, 0, 1, InterfaceParameterScales(), state
    )
    changed = replace(
        series,
        executed_wrench_world=series.executed_wrench_world
        + np.array([5.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    )
    response = predictor.predict_measurements(
        changed, 0, 1, InterfaceParameterScales(), state
    )
    assert response[0, 6] > baseline[0, 6]
    assert np.all(np.isfinite(response))


def test_v2_module_does_not_change_control_grade_predictor_source() -> None:
    source = Path(
        "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
        "interface_identification_v2.py"
    ).read_text(encoding="utf-8")
    assert "NominalInterfaceHoldPredictor" not in source
    assert "GoalDirectedHumanSpaceMPC" not in source
