"""Mechanical and gate tests for the MuJoCo sleeve/robot plant V2."""

from __future__ import annotations

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.config import (
    PlantV2Config,
    RobotV2Parameters,
)
from traction_mpc.mujoco_sleeve_robot_v2.environment import SleeveRobotEnvironment
from traction_mpc.mujoco_sleeve_robot_v2.model import build_plant_xml
from traction_mpc.mujoco_sleeve_robot_v2.validation import run_validation


@pytest.fixture(scope="module")
def validation_result():
    return run_validation()


def test_old_cr12_asset_is_visual_only_and_not_used_as_plant() -> None:
    robot = RobotV2Parameters()
    root = ET.parse(REPOSITORY_ROOT / robot.provenance_asset).getroot()
    assert len(root.findall("link")) == 1
    assert len(root.findall("joint")) == 0
    assert len(root.findall(".//inertial")) == 0
    assert len(root.findall("transmission")) == 0
    assert robot.provenance_reusable_for_kinematics is False
    assert "CR12-like" in robot.model_label


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


@pytest.mark.parametrize("q2_deg", [2.0, 10.0, 20.0, 30.0])
def test_robot_ik_reaches_sleeve_with_full_cartesian_rank(q2_deg: float) -> None:
    env = SleeveRobotEnvironment()
    observation = env.reset(q2_deg)
    assert np.linalg.norm(observation.ee_position_m - observation.sleeve_position_m) < 1e-5
    assert np.linalg.matrix_rank(env.ee_jacobian(), tol=1e-6) == 3


def test_bilateral_sleeve_and_unilateral_bed_parameters_are_registered() -> None:
    config = PlantV2Config()
    env = SleeveRobotEnvironment(config=config)
    assert config.sleeve_stiffness_n_m == 6000.0
    assert config.sleeve_damping_ns_m == 120.0
    assert config.actuator_cartesian_force_bound_n == 200.0
    assert config.force_veto_bound_n == 200.0
    assert (
        env.model.eq_type[env.model.equality("sleeve_connection").id]
        == mujoco.mjtEq.mjEQ_CONNECT
    )
    assert env.model.geom("bed").contype != 0
    assert env.model.geom("sleeve_geom").contype == 0


def test_bed_start_distinguishes_initialization_from_resting_equilibrium(
    validation_result,
) -> None:
    summary, _ = validation_result
    bed = summary["bed_start"]
    assert bed["stable_by_registered_tail_gate"] is True
    assert bed["initialized_q2_deg"] == 2.0
    assert bed["terminal_2deg_held_without_preload"] is False
    assert bed["max_bed_penetration_mm"] < 2.0
    assert bed["bed_contact_count_transitions"] > 0


def test_fixture_topology_gate_passes_at_all_registered_postures(
    validation_result,
) -> None:
    summary, _ = validation_result
    assert summary["fixture_gate_passed"] is True
    assert len(summary["fixture_probes"]) == 8
    assert all(row["force_direction_cosine"] > 0.95 for row in summary["fixture_probes"])
    assert all(row["sleeve_deformation_over_command"] < 0.01 for row in summary["fixture_probes"])


def test_dynamic_gate_blocks_complete_motion_when_low_angle_equilibria_fail(
    validation_result,
) -> None:
    summary, _ = validation_result
    equilibria = {row["q2_deg"]: row for row in summary["dynamic_equilibria"]}
    assert equilibria[2.0]["passed"] is False
    assert equilibria[10.0]["passed"] is False
    assert equilibria[20.0]["passed"] is True
    assert equilibria[30.0]["passed"] is True
    assert summary["dynamic_authority_gate_passed"] is False
    assert summary["complete_protective_motion"] == "skipped_by_authority_gate"
    assert {row["q2_deg"] for row in summary["dynamic_probes"]} == {20.0, 30.0}
    assert all(row["passed"] for row in summary["dynamic_probes"])
