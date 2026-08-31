from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from traction_mpc_stage4.force_feasibility_recovery import (
    HOLD,
    RECOVER,
    TERMINATE,
    ForceFeasibilityRecoverySupervisor,
)
from traction_mpc_stage4.high_rom_dynamic_pilot import HighROMPilotTrajectory
from traction_mpc_stage4.measurement import ControllerMeasurement
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant


def _trajectory() -> HighROMPilotTrajectory:
    return HighROMPilotTrajectory("hip_dominant_100_60", (100.0, 60.0))


def _command(action: np.ndarray, reference, force_n: float) -> dict:
    return {
        "action": np.asarray(action, dtype=float).copy(),
        "reference": reference,
        "allocation": {
            "force_norm_n": min(float(force_n), 100.0),
            "wrench_world": np.zeros(6),
        },
        "preview": {"force_norm_n": float(force_n)},
    }


def test_exact_preview_retains_feedback_then_feedforward_order() -> None:
    plant = SensorBoundaryStage4Plant.__new__(SensorBoundaryStage4Plant)
    measurement = ControllerMeasurement(
        arrival_time_s=0.0,
        sample_time_s=0.0,
        robot_q_rad=np.zeros(6),
        robot_dq_rad_s=np.zeros(6),
        attachment_position_m=np.array([0.1, -0.2, 0.3]),
        attachment_rotation_matrix=np.eye(3),
        attachment_velocity_m_s=np.array([0.4, -0.5, 0.6]),
        attachment_angular_velocity_rad_s=np.zeros(3),
        cuff_force_vector_n=np.zeros(3),
        cuff_moment_vector_nm=np.zeros(3),
        new_sample=True,
    )
    target_position = np.array([0.2, -0.1, 0.25])
    target_velocity = np.array([0.5, -0.4, 0.7])
    feedforward = np.array([10.0, -20.0, 30.0, 1.0, 2.0, 3.0])
    preview = plant.preview_measured_nominal_cartesian_command(
        measurement,
        target_position,
        target_velocity,
        np.eye(3),
        np.zeros(3),
        feedforward,
    )
    position = 3000.0 * (target_position - measurement.attachment_position_m)
    velocity = 140.0 * (target_velocity - measurement.attachment_velocity_m_s)
    expected = np.clip(position + velocity, -200.0, 200.0) + feedforward[:3]
    assert np.allclose(preview["position_feedback_world_n"], position)
    assert np.allclose(preview["velocity_feedback_world_n"], velocity)
    assert np.allclose(preview["force_world_n"], expected)
    assert preview["force_norm_n"] == np.linalg.norm(expected)


def test_unsafe_normal_action_is_rejected_into_safe_hold() -> None:
    supervisor = ForceFeasibilityRecoverySupervisor(_trajectory())
    now = 8.0
    proposed = _command(np.array([40.0, -5.0]), supervisor.reference(now), 212.0)

    def evaluate(action, reference):
        force = 90.0 if np.linalg.norm(action) < 1.0e-12 else 212.0
        return _command(action, reference, force)

    mpc = SimpleNamespace(last_action=np.array([40.0, -5.0]))
    selected = supervisor.filter_executable_command(
        wall_time_s=now,
        estimated_state=np.zeros(4),
        proposed_command=proposed,
        mpc_diagnostics={"accepted": True},
        mpc=mpc,
        evaluate_command=evaluate,
    )
    assert supervisor.mode == HOLD
    assert selected["preview"]["force_norm_n"] == 90.0
    assert not np.array_equal(selected["action"], proposed["action"])
    assert np.array_equal(mpc.last_action, selected["action"])
    assert supervisor.rejected_proposal_count == 1


def test_hold_settles_then_recovers_smoothly_when_alpha_one_is_safe() -> None:
    supervisor = ForceFeasibilityRecoverySupervisor(_trajectory())
    now = 8.0
    mpc = SimpleNamespace(last_action=np.zeros(2))

    def evaluate(action, reference):
        return _command(action, reference, 120.0)

    supervisor.filter_executable_command(
        wall_time_s=now,
        estimated_state=np.zeros(4),
        proposed_command=_command(np.ones(2), supervisor.reference(now), 210.0),
        mpc_diagnostics={"accepted": True},
        mpc=mpc,
        evaluate_command=evaluate,
    )
    hold_reference = supervisor.reference(now)
    settled_state = np.concatenate([hold_reference.q_rad, np.zeros(2)])
    for sample_time in (8.02, 8.08, 8.14):
        supervisor.filter_executable_command(
            wall_time_s=sample_time,
            estimated_state=settled_state,
            proposed_command=_command(
                np.zeros(2), supervisor.reference(sample_time), 120.0
            ),
            mpc_diagnostics={"accepted": True},
            mpc=mpc,
            evaluate_command=evaluate,
        )
    assert supervisor.mode == RECOVER
    assert supervisor.summary(8.14)["recovery_classification"] == "TRANSIENT"
    assert supervisor.status(8.14)["speed_scale"] == 0.0
    assert np.isclose(supervisor.status(8.34)["speed_scale"], 0.05)


def test_continuous_scan_finds_speed_recoverable_boundary() -> None:
    supervisor = ForceFeasibilityRecoverySupervisor(_trajectory())
    phase = 8.0
    base_velocity = np.linalg.norm(_trajectory().reference(phase).dq_rad_s)

    def evaluate(action, reference):
        alpha = np.linalg.norm(reference.dq_rad_s) / base_velocity
        return _command(action, reference, 150.0 + 100.0 * alpha)

    maximum, record = supervisor._scan_maximum_safe_alpha(
        8.0, phase, np.zeros(2), evaluate
    )
    assert maximum is not None
    assert 0.499 <= maximum <= 0.5001
    assert record["alpha_zero_force_n"] == 150.0
    assert record["alpha_one_force_n"] == 250.0


def test_hold_terminates_if_no_candidate_is_executable_below_gate() -> None:
    supervisor = ForceFeasibilityRecoverySupervisor(_trajectory())
    now = 8.0

    def evaluate(action, reference):
        return _command(action, reference, 205.0)

    result = supervisor.filter_executable_command(
        wall_time_s=now,
        estimated_state=np.zeros(4),
        proposed_command=_command(np.ones(2), supervisor.reference(now), 210.0),
        mpc_diagnostics={"accepted": True},
        mpc=SimpleNamespace(last_action=np.ones(2)),
        evaluate_command=evaluate,
    )
    assert result["terminate_reason"] == "hold_command_force_infeasible"
    assert supervisor.mode == TERMINATE
    assert supervisor.summary(now)["recovery_classification"] == "UNRECOVERABLE"
