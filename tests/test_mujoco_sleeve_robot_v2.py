"""Mechanical and gate tests for the MuJoCo sleeve/robot plant V2."""

from __future__ import annotations

from pathlib import Path
import sys

import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.config import (
    HumanV2Parameters,
    PlantV2Config,
)
from traction_mpc.mujoco_sleeve_robot_v2.environment import (
    CuffForceCommandLimitError,
    SleeveRobotEnvironment,
)
from traction_mpc.mujoco_sleeve_robot_v2.kinematics import (
    human_reference,
    sleeve_jacobian,
)
from traction_mpc.mujoco_sleeve_robot_v2.model import build_plant_xml
from traction_mpc.mujoco_sleeve_robot_v2.validation import (
    REGISTERED_HUMAN_V2_MISMATCH_CASES,
    RIGID_CUFF_POSTURES_DEG,
    _human_v2_mass_matrix,
    _human_v2_tracking_wrench,
    registered_mismatch_human_v2,
    run_rigid_cuff_posture_validation,
)


@pytest.fixture(scope="module")
def validation_result():
    return run_rigid_cuff_posture_validation()


def test_v2_model_has_six_dof_robot_and_no_tendon_or_carriage() -> None:
    env = SleeveRobotEnvironment()
    xml = build_plant_xml(env.human, env.robot, env.config)
    assert env.model.nq == 8
    assert env.model.nv == 8
    assert env.model.nu == 6
    assert env.model.ntendon == 0
    assert "carriage" not in xml
    assert "tendon" not in xml
    assert 'name="sleeve_connection"' in xml
    assert 'name="sleeve_geom"' in xml


@pytest.mark.parametrize("q2_deg", RIGID_CUFF_POSTURES_DEG)
def test_robot_ik_reaches_sleeve_with_full_pose_rank(q2_deg: float) -> None:
    env = SleeveRobotEnvironment()
    observation = env.reset(q2_deg)
    assert np.linalg.norm(observation.ee_position_m - observation.sleeve_position_m) < 1e-5
    assert observation.sleeve_relative_rotation_rad < 1e-5
    assert np.linalg.matrix_rank(env.ee_pose_jacobian(), tol=1e-6) == 6


def test_bilateral_sleeve_and_unilateral_bed_parameters_are_registered() -> None:
    config = PlantV2Config()
    env = SleeveRobotEnvironment(config=config)
    assert config.sleeve_stiffness_n_m == 6000.0
    assert config.sleeve_damping_ns_m == 120.0
    assert config.actuator_cartesian_force_bound_n == 200.0
    assert config.force_veto_bound_n == 200.0
    assert (
        env.model.eq_type[env.model.equality("sleeve_connection").id]
        == mujoco.mjtEq.mjEQ_WELD
    )
    assert np.allclose(env.model.dof_armature[:2], 0.0)
    assert np.allclose(env.model.dof_armature[2:], 0.003)
    assert env.model.geom("bed").contype != 0
    assert env.model.geom("sleeve_geom").contype == 0


def test_formal_human_v2_cubic_soft_limit_is_retained() -> None:
    human = HumanV2Parameters()
    env = SleeveRobotEnvironment(human=human)
    assert human.soft_limit_margin_rad == pytest.approx(np.radians(5.0))
    assert human.soft_limit_boundary_torque_nm == 25.0
    assert human.soft_limit_damping_nms_rad == 2.0
    assert env.reset(0.0).human_soft_limit_torque_nm[1] == pytest.approx(25.0, abs=1e-6)
    assert env.reset(2.0).human_soft_limit_torque_nm[1] == pytest.approx(5.4, abs=1e-6)
    assert env.reset(5.0).human_soft_limit_torque_nm[1] == pytest.approx(0.0, abs=1e-10)


def test_pose_servo_adds_orientation_control_without_a_moment_gate() -> None:
    env = SleeveRobotEnvironment(fixture_q2_deg=10.0)
    observation = env.reset(10.0)
    target_rotation = (
        Rotation.from_rotvec(np.array([0.0, 0.01, 0.0])).as_matrix()
        @ observation.ee_rotation_matrix
    )
    env.step_cartesian(
        observation.ee_position_m,
        np.zeros(3),
        target_rotation,
        np.zeros(3),
    )
    assert env.last_cartesian_moment_command_nm[1] > 0.0
    assert np.all(
        np.abs(env.last_joint_torque_command_nm)
        <= np.asarray(env.robot.joint_torque_limits_nm) + 1e-9
    )
    assert not hasattr(env.config, "moment_veto_bound_nm")


def test_model_based_cuff_allocation_minimizes_translational_force() -> None:
    human = HumanV2Parameters()
    q = np.radians([5.0, 10.0])
    allocation = _human_v2_tracking_wrench(
        q,
        np.zeros(2),
        human_reference(0.0),
        human,
    )
    force_map = sleeve_jacobian(q, human)[[0, 2], :].T
    moment_map = np.array([1.0, -1.0])
    reconstructed_tau = (
        force_map @ allocation["force_xz_n"]
        + moment_map * allocation["my_nm"]
    )
    assert reconstructed_tau == pytest.approx(
        allocation["tau_required_nm"], abs=1e-10
    )
    assert allocation["allocation_residual_nm"] < 1e-10
    assert allocation["force_norm_n"] < PlantV2Config().force_veto_bound_n


def test_total_translational_cuff_command_enforces_existing_force_gate() -> None:
    env = SleeveRobotEnvironment(fixture_q2_deg=10.0)
    observation = env.reset(10.0)
    feedforward = np.array(
        [env.config.force_veto_bound_n + 1.0, 0.0, 0.0, 0.0, 50.0, 0.0]
    )
    with pytest.raises(CuffForceCommandLimitError):
        env.step_cartesian(
            observation.ee_position_m,
            np.zeros(3),
            observation.ee_rotation_matrix,
            np.zeros(3),
            feedforward,
            True,
        )


def test_six_posture_mass_pose_wrench_and_torque_validation(validation_result) -> None:
    assert tuple(row["q2_deg"] for row in validation_result) == RIGID_CUFF_POSTURES_DEG
    assert all(row["mass_matrix_max_abs_error"] < 1e-10 for row in validation_result)
    assert all(row["relative_position_error_mm"] < 1e-6 for row in validation_result)
    assert all(row["relative_rotation_error_deg"] < 1e-6 for row in validation_result)
    assert all(row["static_wrench_equation_residual_nm"] < 1e-10 for row in validation_result)
    assert all(row["wrench_reconstruction_residual_nm"] < 1e-10 for row in validation_result)
    assert all(row["translational_force_gate_passed"] for row in validation_result)
    assert all(row["robot_torque_limits_respected"] for row in validation_result)


def test_three_degree_wrench_substantially_reduces_previous_point_force(
    validation_result,
) -> None:
    row = next(row for row in validation_result if row["q2_deg"] == 3.0)
    assert row["cuff_force_n"] < 0.5 * 348.0
    assert abs(row["cuff_my_nm"]) > 0.0
    assert row["force_reduction_vs_previous_348n_percent"] > 50.0


def test_registered_human_v2_mismatch_cases_map_without_changing_other_fields() -> None:
    nominal = HumanV2Parameters()
    assert tuple(REGISTERED_HUMAN_V2_MISMATCH_CASES) == (
        "nominal",
        "mild",
        "moderate",
        "adverse",
    )
    moderate, metadata = registered_mismatch_human_v2("moderate")
    assert moderate.body_mass_kg == pytest.approx(1.05 * nominal.body_mass_kg)
    assert moderate.thigh_com_m == pytest.approx(1.05 * nominal.thigh_com_m)
    assert moderate.shank_com_m == pytest.approx(0.95 * nominal.shank_com_m)
    assert moderate.passive_stiffness_nm_rad == pytest.approx((11.0, 11.0))
    assert np.degrees(moderate.q_rest_rad) == pytest.approx((3.0, 8.0))
    assert moderate.sleeve_center_m == pytest.approx(
        1.02 * nominal.sleeve_center_m
    )
    assert moderate.thigh_length_m == nominal.thigh_length_m
    assert moderate.shank_length_m == nominal.shank_length_m
    assert moderate.passive_damping_nms_rad == nominal.passive_damping_nms_rad
    assert moderate.q_min_rad == nominal.q_min_rad
    assert moderate.q_max_rad == nominal.q_max_rad
    assert metadata["mass_scale"] == 1.05


@pytest.mark.parametrize("case_name", REGISTERED_HUMAN_V2_MISMATCH_CASES)
def test_registered_true_plant_mass_matrix_matches_human_v2(case_name: str) -> None:
    human, _ = registered_mismatch_human_v2(case_name)
    env = SleeveRobotEnvironment(human=human, fixture_q2_deg=10.0)
    observation = env.reset(10.0)
    full_mass = np.zeros((env.model.nv, env.model.nv))
    mujoco.mj_fullM(env.model, env.data, full_mass)
    assert full_mass[:2, :2] == pytest.approx(
        _human_v2_mass_matrix(observation.human_q_rad, human), abs=1e-10
    )
