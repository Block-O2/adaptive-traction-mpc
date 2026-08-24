from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import mujoco
import numpy as np
import pytest

from traction_mpc_stage3.coupled import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    CuffForceCommandLimitError,
    CoupledUR10eHumanV2,
    human_cuff_velocity,
)
from traction_mpc_stage3.human import (
    HUMAN,
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
    mass_matrix,
    nominal_tracking_wrench,
    soft_limit_torque,
)
from traction_mpc_stage3.reference import stage2_cuff_pose_reference
from traction_mpc_stage3.stage3c_validation import run_coupled_scenario


STAGE_ROOT = Path(__file__).resolve().parents[1]


def test_human_v2_port_matches_frozen_stage2_dynamics_and_allocation() -> None:
    samples = [(0.0, 3.0), (2.2, 3.0), (7.8, 3.0), (11.1, 3.0)]
    code = textwrap.dedent(
        f"""
        import json, math
        import numpy as np
        from traction_mpc.mujoco_sleeve_robot_v2.config import HumanV2Parameters
        from traction_mpc.mujoco_sleeve_robot_v2.kinematics import coordinated_posture, human_reference
        from traction_mpc.mujoco_sleeve_robot_v2.validation import _human_v2_mass_matrix, _human_v2_tracking_wrench
        h = HumanV2Parameters(); rows=[]
        start = coordinated_posture(math.radians(3.0))
        for time_s, lower in {samples!r}:
            ref = human_reference(time_s, start)
            q = ref.q + np.radians([0.07, -0.11])
            dq = ref.dq + np.radians([0.3, -0.2])
            a = _human_v2_tracking_wrench(q, dq, ref, h)
            rows.append({{
                'mass': _human_v2_mass_matrix(q,h).tolist(),
                'q': q.tolist(), 'dq': dq.tolist(),
                'tau': a['tau_required_nm'].tolist(),
                'force': a['force_xz_n'].tolist(), 'my': a['my_nm'],
                'wrench': a['wrench_world'].tolist(), 'residual': a['allocation_residual_nm'],
            }})
        print(json.dumps(rows))
        """
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(STAGE_ROOT.parent / "stage2_linkage" / "src")
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    expected = json.loads(completed.stdout)
    for (time_s, lower), row in zip(samples, expected, strict=True):
        reference = stage2_cuff_pose_reference(time_s, lower_q2_deg=lower)
        actual = nominal_tracking_wrench(np.asarray(row["q"]), np.asarray(row["dq"]), reference)
        np.testing.assert_allclose(mass_matrix(np.asarray(row["q"])), row["mass"], atol=1e-14)
        np.testing.assert_allclose(actual["tau_required_nm"], row["tau"], atol=1e-12)
        np.testing.assert_allclose(actual["force_xz_n"], row["force"], atol=1e-12)
        np.testing.assert_allclose(actual["my_nm"], row["my"], atol=1e-12)
        np.testing.assert_allclose(actual["wrench_world"], row["wrench"], atol=1e-12)
        np.testing.assert_allclose(actual["allocation_residual_nm"], row["residual"], atol=1e-12)


def test_frozen_human_parameters_and_soft_limit_contract() -> None:
    assert HUMAN.height_m == 1.72 and HUMAN.body_mass_kg == 75.0
    np.testing.assert_allclose(
        [HUMAN.thigh_length_m, HUMAN.shank_length_m], [0.436880, 0.400760]
    )
    np.testing.assert_allclose([HUMAN.thigh_mass_kg, HUMAN.shank_mass_kg], [7.425, 4.5])
    np.testing.assert_allclose([HUMAN.thigh_com_m, HUMAN.shank_com_m], [0.18916904, 0.1723268])
    np.testing.assert_allclose(
        [HUMAN.thigh_inertia_kg_m2, HUMAN.shank_inertia_kg_m2],
        [0.1275449578128, 0.065046473928],
    )
    assert HUMAN.sleeve_center_m == pytest.approx(0.360684)
    np.testing.assert_allclose(TRACKING_KP_RAD_S2_PER_RAD, [180, 140])
    np.testing.assert_allclose(TRACKING_KD_RAD_S2_PER_RAD_S, [28, 22])
    np.testing.assert_allclose(
        soft_limit_torque(np.radians([0.0, 100.0]), np.array([-1.0, 1.0])),
        [27.0, -27.0],
        atol=1e-6,
    )


@pytest.mark.parametrize("q_deg", ([5.0, 10.0], [1.2162162162162162, 3.0]))
def test_coupled_reset_and_rigid_weld(q_deg: list[float]) -> None:
    plant = CoupledUR10eHumanV2()
    observation = plant.reset(np.radians(q_deg))
    np.testing.assert_allclose(np.degrees(observation.human_q_rad), q_deg, atol=1e-12)
    assert observation.weld_position_error_m < 1e-10
    assert observation.weld_rotation_error_rad < 1e-10
    assert observation.unintended_contact_pairs == ()
    assert plant.model.dof_armature[plant.human_dof_indices].tolist() == [0.0, 0.0]
    assert plant.warning_counts() == {}


def test_wrench_reconstruction_is_virtual_work_consistent() -> None:
    plant = CoupledUR10eHumanV2()
    reference = stage2_cuff_pose_reference(0.0, lower_q2_deg=10.0)
    plant.reset(reference.q_rad)
    allocation = nominal_tracking_wrench(reference.q_rad, np.zeros(2), reference)
    linear, angular = human_cuff_velocity(reference.q_rad, reference.dq_rad_s)
    plant.apply_nominal_cartesian_control(
        reference.world_from_cuff.translation,
        linear,
        reference.world_from_cuff.rotation,
        angular,
        np.asarray(allocation["wrench_world"]),
    )
    observation = plant.step()
    assert observation.cuff_wrench_reconstruction_residual_nm < 1e-9
    assert observation.human_wrench_torque_residual_nm < 1e-9
    np.testing.assert_allclose(
        observation.human_wrench_torque_nm,
        observation.human_constraint_torque_nm,
        atol=1e-9,
    )


def test_translational_force_gate_does_not_create_a_moment_gate() -> None:
    plant = CoupledUR10eHumanV2()
    reference = stage2_cuff_pose_reference(0.0, lower_q2_deg=10.0)
    plant.reset(reference.q_rad)
    with pytest.raises(CuffForceCommandLimitError):
        plant.apply_nominal_cartesian_control(
            reference.world_from_cuff.translation,
            np.zeros(3),
            reference.world_from_cuff.rotation,
            np.zeros(3),
            np.array([CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0, 0, 0, 0, 0, 0]),
        )
    plant.apply_nominal_cartesian_control(
        reference.world_from_cuff.translation,
        np.zeros(3),
        reference.world_from_cuff.rotation,
        np.zeros(3),
        np.array([0, 0, 0, 0, 10_000.0, 0]),
    )
    assert np.linalg.norm(plant.last_moment) > 1000.0


def test_explicit_robot_torque_mapping_under_cuff_load() -> None:
    plant = CoupledUR10eHumanV2()
    reference = stage2_cuff_pose_reference(0.0, lower_q2_deg=10.0)
    plant.reset(reference.q_rad)
    allocation = nominal_tracking_wrench(reference.q_rad, np.zeros(2), reference)
    plant.apply_nominal_cartesian_control(
        reference.world_from_cuff.translation,
        np.zeros(3),
        reference.world_from_cuff.rotation,
        np.zeros(3),
        np.asarray(allocation["wrench_world"]),
    )
    mujoco.mj_forward(plant.model, plant.data)
    np.testing.assert_allclose(
        plant.data.qfrc_actuator[plant.robot_dof_indices],
        plant.last_joint_torque,
        atol=0.0,
    )
    assert np.all(np.abs(plant.last_joint_torque) <= plant.torque_limits_nm)
    assert np.all(plant.model.actuator_biastype[plant.actuator_ids] == mujoco.mjtBias.mjBIAS_NONE)


def test_collision_domains_retain_only_intended_cross_model_contact() -> None:
    plant = CoupledUR10eHumanV2()
    plant.reset(np.radians([5.0, 10.0]))
    assert plant.observe().unintended_contact_pairs == ()
    assert plant.model.geom_contype[plant.bed_geom_id] == 4
    assert plant.model.geom_conaffinity[plant.bed_geom_id] == 2
    for geom_id in plant.human_geom_ids:
        assert plant.model.geom_contype[geom_id] == 2
        assert plant.model.geom_conaffinity[geom_id] == 4
    plant.data.eq_active[plant.weld_id] = 0
    plant.data.qpos[plant.robot_qpos_indices] = np.radians(
        [-335.107, 119.117, 157.278, -297.422, 129.537, 228.873]
    )
    mujoco.mj_forward(plant.model, plant.data)
    assert any(
        {int(plant.data.contact[i].geom1), int(plant.data.contact[i].geom2)}
        <= plant.robot_collision_geom_ids
        for i in range(plant.data.ncon)
    )


def test_short_coupled_dynamics_remain_finite() -> None:
    summary, trace = run_coupled_scenario(
        lower_q2_deg=10.0,
        duration_s=0.05,
        hold_only=True,
    )
    assert summary["termination_reason"] == "completed_hold"
    assert summary["solver"]["warning_counts"] == {}
    assert summary["collision"]["unintended_contact_pairs"] == []
    assert summary["cuff"]["force_gate_respected"]
    assert all(np.all(np.isfinite(value)) for value in trace.values())
