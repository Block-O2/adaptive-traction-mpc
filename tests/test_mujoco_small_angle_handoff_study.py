"""Contracts for the staged MuJoCo small-angle handoff study."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.config import (  # noqa: E402
    HumanV2Parameters,
    PlantV2Config,
)
from traction_mpc.mujoco_sleeve_robot_v2.environment import (  # noqa: E402
    SleeveRobotEnvironment,
)
from traction_mpc.mujoco_sleeve_robot_v2.handoff_study import (  # noqa: E402
    run_staged_handoff_search,
)
from traction_mpc.mujoco_sleeve_robot_v2.kinematics import (  # noqa: E402
    ReferenceSample,
    quintic_boundary_sample,
)
from traction_mpc.mujoco_sleeve_robot_v2.normal_controller import (  # noqa: E402
    NormalControllerConfig,
    original_normal_controller,
)


@pytest.fixture(scope="module")
def staged_result():
    return run_staged_handoff_search()


def test_c2_patch_matches_measured_boundary_state() -> None:
    q0 = np.radians([0.2, 0.7])
    dq0 = np.radians([0.01, -0.02])
    qf = np.radians([5.0, 10.0])
    start = quintic_boundary_sample(0.0, 4.0, q0, dq0, qf)
    finish = quintic_boundary_sample(4.0, 4.0, q0, dq0, qf)
    np.testing.assert_allclose(start.q, q0, atol=1e-14)
    np.testing.assert_allclose(start.dq, dq0, atol=1e-14)
    np.testing.assert_allclose(start.ddq, np.zeros(2), atol=1e-14)
    np.testing.assert_allclose(finish.q, qf, atol=1e-14)
    np.testing.assert_allclose(finish.dq, np.zeros(2), atol=1e-14)
    np.testing.assert_allclose(finish.ddq, np.zeros(2), atol=1e-13)


def test_normal_controller_port_retains_registered_source_values() -> None:
    human = HumanV2Parameters()
    config = NormalControllerConfig()
    assert config.dt_s == 0.002
    assert config.kp == (180.0, 140.0)
    assert config.kd == (28.0, 22.0)
    assert config.force_bound_n == 200.0
    assert config.force_slew_n_s == 250.0
    assert config.lambda_ref == 1e-6
    assert config.lambda_du == 0.0
    assert config.source_function.endswith("bed_supported_v1_robot_controller.m")
    q = np.radians([5.0, 10.0])
    output = original_normal_controller(
        q,
        np.zeros(2),
        ReferenceSample(q, np.zeros(2), np.zeros(2)),
        np.zeros(2),
        np.zeros(2),
        human,
        config,
    )
    np.testing.assert_allclose(output.local_force_n, [-0.5, 0.5], atol=1e-12)
    np.testing.assert_allclose(
        output.desired_robot_torque_nm,
        [40.51759455, -7.57841826],
        atol=1e-8,
    )
    assert output.mapping_condition_number == pytest.approx(27.7906881348)


def test_force_adapter_uses_real_robot_motor_command() -> None:
    config = replace(PlantV2Config(), control_dt_s=0.002)
    env = SleeveRobotEnvironment(config=config)
    initial = env.reset(2.0)
    for _ in range(500):
        env.step_cartesian(initial.ee_position_m, np.zeros(3))
    for _ in range(250):
        env.step_cartesian_force(np.array([10.0, 0.0, 0.0]))
    observation = env.observe()
    assert observation.sleeve_force_vector_n[0] == pytest.approx(10.0, abs=0.02)
    assert np.linalg.norm(observation.joint_torque_command_nm) > 0.0
    assert np.linalg.norm(observation.bed_generalized_torque_nm) > 0.0


def test_staged_search_preserves_candidate_order_and_positive_reference(staged_result) -> None:
    summary, _ = staged_result
    assert summary["tested_candidates_deg"] == [5.0, 8.0, 10.0, 15.0, 20.0, 25.0, 30.0]
    assert summary["q_switch_30_role"] == "positive_reference_only"
    assert summary["scientific_variables_changed"] == []


def test_no_candidate_reaches_handoff_under_frozen_v2_actuator(staged_result) -> None:
    summary, _ = staged_result
    tested = [row for row in summary["candidate_rows"] if row["status"] != "NOT_RUN_STAGED"]
    assert all(row["status"] == "FAIL" for row in tested)
    assert all(row["handoff_reached"] is False for row in tested)
    assert all(row["normal_controller_calls"] == 0 for row in tested)
    mechanisms = {row["q_handoff_deg"]: row["direct_mechanism"] for row in tested}
    assert all(
        mechanisms[angle]
        == "kinematic_takeoff_wrong_generalized_motion_q2_extension"
        for angle in (5.0, 8.0, 10.0)
    )
    assert all(
        mechanisms[angle] == "kinematic_wrong_motion_reached_rom_boundary"
        for angle in (15.0, 20.0, 25.0, 30.0)
    )
    assert summary["minimum_tested_feasible_handoff_deg"] is None
    assert summary["architecture_small_angle_supported"] is False


def test_negative_result_is_not_hidden_by_force_or_sleeve_changes(staged_result) -> None:
    summary, _ = staged_result
    tested = summary["candidate_rows"]
    assert max(row["peak_interaction_force_n"] for row in tested) < 200.0
    assert max(row["maximum_sleeve_deformation_overall_mm"] for row in tested) < 0.2
    assert all(row["protective_stop"] is False for row in tested[:3])
    assert all(row["protective_stop"] is True for row in tested[3:])
    assert tested[-1]["measured_handoff_q_deg"][1] <= -0.05
