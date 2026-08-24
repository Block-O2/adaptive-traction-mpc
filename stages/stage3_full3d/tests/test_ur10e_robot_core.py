from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

from traction_mpc_stage3.frames import ATTACHMENT_FROM_CUFF, WORLD_FROM_BASE
from traction_mpc_stage3.reference import stage2_cuff_pose_reference
from traction_mpc_stage3.robot import (
    ACTUATOR_NAMES,
    BODY_NAMES,
    JOINT_NAMES,
    TORQUE_MODEL_PATH,
    VENDOR_MODEL_PATH,
    UR10eTorqueRobot,
)
from traction_mpc_stage3.validation import run_robot_core_validation


STAGE_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = VENDOR_MODEL_PATH.parent


@pytest.fixture(scope="module")
def validation_result() -> dict[str, object]:
    return run_robot_core_validation(
        sample_count=151,
        gravity_hold_duration_s=0.10,
    )


def test_vendor_snapshot_integrity_and_license() -> None:
    expected = {
        VENDOR_MODEL_PATH: "7495b8efe33e497ffe892b9279acb010671c2b4b5955f499aa2b1d320dd8c871",
        VENDOR_ROOT / "LICENSE": "5ec71ccf66c8d03261448f2441a586765b97f2248c860a1ae19689fb1c45cee6",
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert len(list((VENDOR_ROOT / "assets").glob("*.obj"))) == 20


def test_torque_variant_preserves_vendor_worldbody_and_assets() -> None:
    vendor = ET.parse(VENDOR_MODEL_PATH).getroot()
    torque = ET.parse(TORQUE_MODEL_PATH).getroot()
    assert ET.tostring(vendor.find("asset")) == ET.tostring(torque.find("asset"))
    assert ET.tostring(vendor.find("worldbody")) == ET.tostring(torque.find("worldbody"))
    assert [child.tag for child in vendor.find("actuator")] == ["general"] * 6
    assert [child.tag for child in torque.find("actuator")] == ["motor"] * 6


def test_model_structure_frames_and_inertias(validation_result: dict[str, object]) -> None:
    contract = validation_result["model_contract"]
    assert contract["nq"] == contract["nv"] == contract["nu"] == 6
    assert contract["joint_names"] == list(JOINT_NAMES)
    assert contract["actuator_names"] == list(ACTUATOR_NAMES)
    assert contract["body_names"] == list(BODY_NAMES)
    assert contract["body_parent_names"] == [
        None,
        "base",
        "shoulder_link",
        "upper_arm_link",
        "forearm_link",
        "wrist_1_link",
        "wrist_2_link",
    ]
    assert contract["joint_axes"] == [
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0],
    ]
    assert contract["positive_inertia_body_count"] == contract["nonworld_body_count"] == 7
    assert contract["collision_geom_count"] == 9
    assert contract["visual_only_geom_count"] == 20
    assert contract["attachment_site_body"] == "wrist_3_link"
    np.testing.assert_allclose(contract["attachment_site_position_in_body_m"], [0, 0.1, 0])
    np.testing.assert_allclose(
        contract["attachment_site_quaternion_in_body"],
        [-2**-0.5, 2**-0.5, 0, 0],
    )
    np.testing.assert_allclose(WORLD_FROM_BASE.translation, [1.10, -0.62, 0.04])
    np.testing.assert_allclose(ATTACHMENT_FROM_CUFF.rotation, np.eye(3))
    np.testing.assert_allclose(ATTACHMENT_FROM_CUFF.translation, np.zeros(3))


def test_actuators_are_explicit_one_to_one_torque_motors(
    validation_result: dict[str, object],
) -> None:
    robot = UR10eTorqueRobot()
    assert np.all(robot.model.actuator_biastype[robot.actuator_ids] == mujoco.mjtBias.mjBIAS_NONE)
    np.testing.assert_allclose(robot.model.actuator_gainprm[robot.actuator_ids, 0], 1.0)
    np.testing.assert_allclose(robot.model.actuator_gear[robot.actuator_ids, 0], 1.0)
    np.testing.assert_allclose(robot.torque_limits_nm, [330, 330, 150, 56, 56, 56])
    mapping = validation_result["torque_actuator_mapping"]
    assert mapping["hidden_bias_terms_zero"]
    assert mapping["max_abs_error_nm"] == 0.0
    with pytest.raises(ValueError, match="exceeds modeled actuator limits"):
        robot.command_torque(np.array([331.0, 0, 0, 0, 0, 0]))


def test_fk_and_jacobian_finite_difference(validation_result: dict[str, object]) -> None:
    fk = validation_result["fk"]
    assert fk["finite"]
    np.testing.assert_allclose(
        fk["home_attachment_position_base_m"],
        [-0.1739970945, 0.6909987548, 0.6940004408],
        atol=1e-9,
    )
    assert validation_result["jacobian"]["max_abs_error"] < 1e-7


def test_reference_port_matches_frozen_stage2_source() -> None:
    times = np.linspace(0.0, 15.0, 31)
    code = textwrap.dedent(
        f"""
        import json, math
        import numpy as np
        from traction_mpc.mujoco_sleeve_robot_v2.config import HumanV2Parameters, PlantV2Config
        from traction_mpc.mujoco_sleeve_robot_v2.kinematics import coordinated_posture, human_reference, sleeve_position, sleeve_rotation_matrix
        human = HumanV2Parameters(); config = PlantV2Config()
        start = coordinated_posture(math.radians(3.0))
        rows = []
        for time_s in {times.tolist()!r}:
            ref = human_reference(time_s, start)
            rows.append([ref.q.tolist(), ref.dq.tolist(), ref.ddq.tolist(), sleeve_position(ref.q, human, config).tolist(), sleeve_rotation_matrix(ref.q).tolist()])
        print(json.dumps(rows))
        """
    )
    stage2_src = STAGE_ROOT.parent / "stage2_linkage" / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(stage2_src)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    expected = json.loads(completed.stdout)
    for time_s, row in zip(times, expected, strict=True):
        actual = stage2_cuff_pose_reference(float(time_s))
        np.testing.assert_allclose(actual.q_rad, row[0], atol=1e-14)
        np.testing.assert_allclose(actual.dq_rad_s, row[1], atol=1e-14)
        np.testing.assert_allclose(actual.ddq_rad_s2, row[2], atol=1e-14)
        np.testing.assert_allclose(actual.world_from_cuff.translation, row[3], atol=1e-14)
        np.testing.assert_allclose(actual.world_from_cuff.rotation, row[4], atol=1e-14)


def test_dense_continuous_ik_and_mechanical_state(
    validation_result: dict[str, object],
) -> None:
    ik = validation_result["ik"]
    assert ik["sample_count"] == 151
    assert ik["maximum_position_error_m"] < 1e-8
    assert ik["maximum_rotation_error_rad"] < 1e-8
    assert ik["maximum_individual_joint_step_deg"] < 1.1
    # Regression gate is the modeled limit itself; the measured margin is
    # reported quantitatively rather than promoted as an unapproved safety threshold.
    assert ik["minimum_joint_limit_margin_deg"] > 0.0
    assert ik["minimum_6d_jacobian_singular_value"] > 0.25
    assert ik["maximum_6d_jacobian_condition_number"] < 8.0
    mechanical = validation_result["mechanical"]
    assert mechanical["all_ik_states_finite"]
    assert mechanical["trajectory_self_collision_pairs"] == []
    assert mechanical["trajectory_warning_counts"] == {}


def test_wrench_mapping_gravity_hold_and_modeled_limits(
    validation_result: dict[str, object],
) -> None:
    for check in validation_result["wrench_mapping"].values():
        assert check["mj_applyFT_max_abs_error_nm"] < 1e-12
        assert check["gravity_plus_load_peak_limit_fraction"] < 1.0
    assert validation_result["maximum_synthetic_gravity_plus_load_limit_fraction"] < 0.6
    hold = validation_result["gravity_compensated_hold"]
    assert hold["max_abs_joint_drift_rad"] < 1e-12
    assert hold["max_abs_joint_speed_rad_s"] < 1e-12
    assert hold["peak_gravity_torque_limit_fraction"] < 0.4
    assert hold["warning_counts"] == {}


def test_self_collision_detection_is_active() -> None:
    robot = UR10eTorqueRobot()
    # Deterministic folded model state found by a fixed-seed structure audit.
    # It is not a commanded or safe posture; it only proves collision geoms
    # participate in MuJoCo contact generation.
    robot.set_configuration(
        np.radians([-335.107, 119.117, 157.278, -297.422, 129.537, 228.873])
    )
    assert robot.data.ncon > 0
    assert all(first and second for first, second in robot.contact_pairs())
