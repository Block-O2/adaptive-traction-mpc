"""Contracts for the fixed dynamic protective-transition diagnostic."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.config import PlantV2Config  # noqa: E402
from traction_mpc.mujoco_sleeve_robot_v2.contact_feasibility import (  # noqa: E402
    preparation_q1,
)
from traction_mpc.mujoco_sleeve_robot_v2.dynamic_transition import (  # noqa: E402
    DynamicTransitionConfig,
    fixed_primitive_sample,
    primitive_duration_s,
    run_dynamic_transition_matrix,
)
from traction_mpc.mujoco_sleeve_robot_v2.environment import (  # noqa: E402
    SleeveRobotEnvironment,
)


def test_retained_soft_limit_torque_matches_human_v2_definition() -> None:
    env = SleeveRobotEnvironment(include_retained_soft_limit_torque=True)
    q = np.radians([0.0, 3.0])
    observation = env.reset_posture(q)
    expected = [25.0, 25.0 * (2.0 / 5.0) ** 3]
    np.testing.assert_allclose(
        observation.retained_soft_limit_torque_nm, expected, atol=1e-6
    )
    human_dofs = [
        env.model.joint(name).dofadr[0] for name in ("hip_joint", "knee_joint")
    ]
    np.testing.assert_allclose(env.data.qfrc_applied[human_dofs], expected, atol=1e-6)
    assert env.human.soft_limit_boundary_torque_nm == 25.0
    assert np.degrees(env.human.soft_limit_margin_rad) == pytest.approx(5.0)


def test_explicit_posture_reset_is_geometrically_consistent() -> None:
    env = SleeveRobotEnvironment(include_retained_soft_limit_torque=True)
    q2 = np.radians(3.0)
    q = np.array([preparation_q1(q2, env.human), q2])
    observation = env.reset_posture(q)
    np.testing.assert_allclose(observation.human_q_rad, q, atol=1e-14)
    assert np.linalg.norm(observation.ee_position_m - observation.sleeve_position_m) < 1e-8
    assert observation.bed_penetration_m <= 1e-9


def test_fixed_primitive_is_c2_and_never_commands_below_floor() -> None:
    config = DynamicTransitionConfig()
    env = SleeveRobotEnvironment(config=PlantV2Config())
    duration = primitive_duration_s(3.0, 20.0, config)
    start = fixed_primitive_sample(0.0, duration, 3.0, 20.0, env)
    finish = fixed_primitive_sample(duration, duration, 3.0, 20.0, env)
    assert np.degrees(start[0][1]) == pytest.approx(3.0)
    assert np.degrees(finish[0][1]) == pytest.approx(20.0)
    np.testing.assert_allclose(start[1], np.zeros(2), atol=1e-14)
    np.testing.assert_allclose(finish[1], np.zeros(2), atol=1e-14)
    samples = [
        fixed_primitive_sample(time, duration, 3.0, 20.0, env)[0][1]
        for time in np.linspace(0.0, duration, 101)
    ]
    assert min(np.degrees(samples)) >= 3.0 - 1e-12


@pytest.fixture(scope="module")
def matrix_result():
    return run_dynamic_transition_matrix()


def test_registered_matrix_preserves_frozen_contract(matrix_result) -> None:
    summary, _ = matrix_result
    assert [row["target_q2_deg"] for row in summary["forward_rows"]] == [
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
    ]
    assert summary["initialization_boundary"]["q2_deg"] == 3.0
    assert summary["model_boundary"]["retained_human_v2_soft_limit_included"] is True
    assert summary["frozen_values"]["force_gate_n"] == 200.0
    assert summary["scientific_variables_changed"] == [
        "apply retained Human V2 cubic soft-limit RHS torque omitted by PR22 MJCF"
    ]


def test_reverse_runs_exist_only_for_successful_forward_candidates(matrix_result) -> None:
    summary, _ = matrix_result
    passed = {
        row["target_q2_deg"]
        for row in summary["forward_rows"]
        if row["status"] == "PASS"
    }
    reverse = {row["start_q2_deg"] for row in summary["reverse_rows"]}
    assert reverse == passed


def test_frozen_matrix_preserves_negative_dynamic_result(matrix_result) -> None:
    summary, traces = matrix_result
    assert all(row["status"] == "FAIL" for row in summary["forward_rows"])
    assert all(
        row["failure_reason"] == "engineering_floor_violation"
        for row in summary["forward_rows"]
    )
    assert all(row["peak_sleeve_force_n"] < 200.0 for row in summary["forward_rows"])
    assert summary["reverse_rows"] == []
    assert summary["continuous_safe_dynamic_bridge_exists"] is False
    for key, trace in traces.items():
        assert key.startswith("forward_")
        assert np.min(trace.q_reference_deg[:, 1]) >= 3.0 - 1e-12
