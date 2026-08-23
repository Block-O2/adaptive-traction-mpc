"""Deterministic contracts for the MuJoCo protective-mode M1 smoke."""

from __future__ import annotations

import math
import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from traction_mpc.mujoco_protective_mode_v1.artifacts import write_case_artifacts
from traction_mpc.mujoco_protective_mode_v1.config import (
    HumanV2Parameters,
    ProtectiveModeConfig,
)
from traction_mpc.mujoco_protective_mode_v1.controller import (
    ProtectiveModeController,
    cuff_kinematics,
)
from traction_mpc.mujoco_protective_mode_v1.environment import ProtectiveModeEnvironment
from traction_mpc.mujoco_protective_mode_v1.experiment import run_case
from traction_mpc.mujoco_protective_mode_v1.reference import (
    ReferenceSample,
    human_v2_reference,
    reference_crossing_time,
)


def test_human_v2_parameters_match_matlab_constructor() -> None:
    parameters = HumanV2Parameters()
    assert parameters.thigh_length_m == pytest.approx(0.43688)
    assert parameters.shank_length_m == pytest.approx(0.40076)
    assert parameters.thigh_mass_kg == pytest.approx(7.425)
    assert parameters.shank_mass_kg == pytest.approx(4.5)
    assert parameters.cuff_location_m == pytest.approx(0.360684)
    assert np.degrees(parameters.q_max_rad) == pytest.approx([80.0, 100.0])


def test_mjcf_has_only_robot_actuators_and_measured_state() -> None:
    environment = ProtectiveModeEnvironment()
    assert environment.model.nq == 4
    assert environment.model.nu == 2
    actuator_joint_ids = set(environment.model.actuator_trnid[:, 0].tolist())
    robot_joint_ids = {
        environment.model.joint("robot_x_joint").id,
        environment.model.joint("robot_z_joint").id,
    }
    assert actuator_joint_ids == robot_joint_ids
    observation = environment.reset()
    assert np.degrees(observation.q_rad) == pytest.approx([0.6756756757, 2.0])
    assert observation.interaction_force_n == pytest.approx(0.0, abs=1e-9)


def test_nominal_kinematics_matches_mujoco_cuff_site() -> None:
    environment = ProtectiveModeEnvironment()
    parameters, config = environment.parameters, environment.config
    q = np.radians([15.8108108108, 30.0])
    environment.data.joint("hip_joint").qpos[0] = q[0]
    environment.data.joint("knee_joint").qpos[0] = q[1]
    mujoco.mj_forward(environment.model, environment.data)
    expected = cuff_kinematics(
        ReferenceSample(q, np.zeros(2), np.zeros(2)), parameters, config
    ).q
    actual = environment.data.site("cuff_site").xpos[[0, 2]]
    assert actual == pytest.approx(expected, abs=1e-11)


def test_taught_reference_switch_crossings_are_symmetric() -> None:
    switch = math.radians(30.0)
    flexion = reference_crossing_time(switch, False)
    returning = reference_crossing_time(switch, True)
    assert human_v2_reference(flexion).q[1] == pytest.approx(switch, abs=1e-12)
    assert human_v2_reference(returning).q[1] == pytest.approx(switch, abs=1e-12)
    assert flexion + returning == pytest.approx(16.0, abs=1e-12)


def test_measured_state_patch_preserves_cartesian_command_continuity() -> None:
    environment = ProtectiveModeEnvironment()
    observation = environment.reset()
    controller = ProtectiveModeController(
        environment.parameters, environment.config, observation.robot_position_m
    )
    bed = controller.command(
        0.0,
        observation.q_rad,
        observation.dq_rad_s,
        observation.robot_position_m,
        0.0,
    )
    measured_q = observation.q_rad + np.radians([0.4, -0.3])
    takeoff = controller.command(
        controller.takeoff_start_s,
        measured_q,
        np.radians([0.2, -0.1]),
        observation.robot_position_m,
        0.0,
    )
    assert takeoff.position_m == pytest.approx(bed.position_m, abs=1e-12)
    assert takeoff.velocity_m_s == pytest.approx(bed.velocity_m_s, abs=1e-12)

    takeoff_end = controller._takeoff_command(controller.normal_start_s)
    normal_start = controller._normal_command(controller.normal_start_s)
    assert takeoff_end.position_m == pytest.approx(normal_start.position_m, abs=1e-10)
    assert takeoff_end.velocity_m_s == pytest.approx(normal_start.velocity_m_s, abs=1e-10)


def test_force_veto_routes_to_continuous_braking_command() -> None:
    environment = ProtectiveModeEnvironment()
    observation = environment.reset()
    controller = ProtectiveModeController(
        environment.parameters, environment.config, observation.robot_position_m
    )
    previous = controller.command(
        0.0,
        observation.q_rad,
        observation.dq_rad_s,
        observation.robot_position_m,
        0.0,
    )
    stopped = controller.command(
        0.1,
        observation.q_rad,
        observation.dq_rad_s,
        observation.robot_position_m,
        environment.config.force_veto_limit_n + 1,
    )
    assert stopped.mode == "PROTECTIVE_STOP"
    assert stopped.automatic_force_veto
    assert stopped.position_m == pytest.approx(previous.position_m, abs=1e-12)
    assert stopped.velocity_m_s == pytest.approx(previous.velocity_m_s, abs=1e-12)


def test_short_physics_run_is_finite_and_bed_force_is_solver_generated() -> None:
    environment = ProtectiveModeEnvironment()
    observation = environment.reset()
    controller = ProtectiveModeController(
        environment.parameters, environment.config, observation.robot_position_m
    )
    for _ in range(50):
        command = controller.command(
            observation.time_s,
            observation.q_rad,
            observation.dq_rad_s,
            observation.robot_position_m,
            observation.interaction_force_n,
        )
        observation = environment.step(command)
    assert np.all(np.isfinite(observation.q_rad))
    assert np.isfinite(observation.interaction_force_n)
    assert observation.bed_force_n >= 0
    assert observation.bed_contact_count >= 0


def test_registered_baseline_retains_observed_negative_result() -> None:
    result = run_case()
    assert result.metrics["classification"] == "TERMINAL_UNSTABLE_OR_INCOMPLETE"
    assert not result.metrics["mechanical_complete"]
    assert result.metrics["mode_sequence"] == (
        "BED_START>KINEMATIC_TAKEOFF>NORMAL_REHAB>KINEMATIC_LANDING>TERMINAL"
    )
    assert result.metrics["takeoff_end_q2_deg"] < 2.0
    assert result.metrics["max_interaction_force_n"] < result.config.force_veto_limit_n


def test_manual_veto_probe_and_artifacts(tmp_path) -> None:
    config = ProtectiveModeConfig()
    environment = ProtectiveModeEnvironment(HumanV2Parameters(), config)
    observation = environment.reset()
    timing = ProtectiveModeController(
        HumanV2Parameters(), config, observation.robot_position_m
    )
    veto_time = timing.takeoff_start_s + 0.5 * config.transition_duration_s
    result = run_case(config, "manual_veto_probe", veto_time)
    assert result.metrics["classification"] == "MANUAL_VETO_PROBE"
    assert result.metrics["veto_robot_braking_distance_mm"] is not None
    assert result.metrics["veto_peak_interaction_force_n"] is not None
    write_case_artifacts(result, tmp_path, make_gif=False)
    assert (tmp_path / "manual_veto_probe" / "timeseries.csv").is_file()
    assert (tmp_path / "manual_veto_probe" / "synchronized_timeseries.png").is_file()
