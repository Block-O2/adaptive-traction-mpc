from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2, human_cuff_velocity
from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.human import nominal_tracking_wrench
from traction_mpc_stage3.reference import stage2_cuff_pose_reference
from traction_mpc_stage3.robot_backends import (
    CR12DryRunBackend,
    Stage3SimulationBackend,
)
from traction_mpc_stage3.robot_interface import (
    CapabilityStatus,
    CommandMode,
    FrameCalibration,
    FramedPose,
    RobotCommand,
    RobotMode,
    SoftwareLimitResult,
    WatchdogStatus,
)


def _simulation_backend() -> Stage3SimulationBackend:
    plant = CoupledUR10eHumanV2()
    plant.reset(stage2_cuff_pose_reference(0.0, lower_q2_deg=10.0).q_rad)
    backend = Stage3SimulationBackend(plant)
    backend.connect()
    return backend


def _calibration() -> FrameCalibration:
    return FrameCalibration(
        base_frame="cr12_base",
        flange_frame="cr12_flange",
        adapter_frame="test_adapter",
        cuff_frame="test_cuff",
        flange_from_adapter=RigidTransform(
            np.eye(3), np.array([0.01, -0.02, 0.03])
        ),
        adapter_from_cuff=RigidTransform(
            np.eye(3), np.array([0.04, 0.0, -0.01])
        ),
        provenance="unit-test calibrated transform fixture",
    )


def test_robot_state_datatype_units_and_frames() -> None:
    backend = _simulation_backend()
    state = backend.read_state()
    assert state.timestamp_s == 0.0 and state.sequence == 0
    assert state.q_rad.shape == state.dq_rad_s.shape == (6,)
    assert state.jacobian_base_tcp.shape == (6, 6)
    assert state.base_from_flange.parent_frame == "ur10e_base"
    assert state.base_from_flange.child_frame == "wrist_3_link"
    assert state.base_from_tcp.child_frame == "attachment_site"
    assert state.measured_joint_torque_nm is None
    assert state.measured_motor_current_a is None
    assert state.measured_tcp_wrench is None
    assert backend.capabilities.measured_ft_wrench is CapabilityStatus.NOT_SUPPORTED
    assert state.robot_mode is RobotMode.DISABLED


def test_command_modes_are_explicit_and_not_interchangeable() -> None:
    backend = _simulation_backend()
    capabilities = backend.capabilities.command_modes
    assert capabilities[CommandMode.JOINT_TORQUE] is CapabilityStatus.CONFIRMED
    assert capabilities[CommandMode.JOINT_POSITION] is CapabilityStatus.NOT_SUPPORTED
    assert capabilities[CommandMode.JOINT_VELOCITY] is CapabilityStatus.NOT_SUPPORTED
    position = backend.validator.make_command(
        CommandMode.JOINT_POSITION,
        np.zeros(6),
        timestamp_s=0.0,
        deadline_s=0.01,
        enable_requested=True,
    )
    assert not position.software_limit_result.accepted
    receipt = backend.submit_command(position)
    assert not receipt.accepted and not receipt.transmitted


def test_command_datatype_and_software_limit_validation() -> None:
    backend = _simulation_backend()
    valid = backend.validator.make_command(
        CommandMode.JOINT_TORQUE,
        np.array([1.0, -2.0, 3.0, -4.0, 5.0, -6.0]),
        timestamp_s=0.0,
        deadline_s=0.01,
        enable_requested=True,
    )
    assert valid.software_limit_result.accepted
    assert backend.submit_command(valid).transmitted
    excessive = backend.validator.make_command(
        CommandMode.JOINT_TORQUE,
        np.array([331.0, 0, 0, 0, 0, 0]),
        timestamp_s=0.0,
        deadline_s=0.01,
        enable_requested=True,
    )
    assert not excessive.software_limit_result.accepted
    assert "command exceeds software limits" in excessive.software_limit_result.reasons
    forged = RobotCommand(
        CommandMode.JOINT_TORQUE,
        np.array([1000.0, 0, 0, 0, 0, 0]),
        0.0,
        0.01,
        True,
        SoftwareLimitResult(True, CommandMode.JOINT_TORQUE, 0.0, "forged"),
    )
    forged_receipt = backend.submit_command(forged)
    assert not forged_receipt.accepted and not forged_receipt.transmitted
    assert "backend validation failed" in forged_receipt.reason
    with pytest.raises(ValueError, match="deadline"):
        backend.validator.make_command(
            CommandMode.JOINT_TORQUE,
            np.zeros(6),
            timestamp_s=1.0,
            deadline_s=0.5,
            enable_requested=True,
        )
    with pytest.raises(ValueError, match="DISABLED"):
        RobotCommand(
            CommandMode.DISABLED,
            np.ones(6),
            0.0,
            0.1,
            False,
            SoftwareLimitResult(True, CommandMode.DISABLED, 0.0, "test"),
        )


def test_deadline_and_simulation_watchdog_disable_output() -> None:
    backend = _simulation_backend()
    command = backend.validator.make_command(
        CommandMode.JOINT_TORQUE,
        np.ones(6),
        timestamp_s=0.0,
        deadline_s=0.002,
        enable_requested=True,
    )
    assert backend.submit_command(command).accepted
    backend.advance()
    backend.advance()
    state = backend.advance()
    assert state.watchdog.status is WatchdogStatus.EXPIRED
    assert state.robot_mode is RobotMode.FAULT
    np.testing.assert_allclose(backend.plant.data.ctrl[backend.plant.actuator_ids], 0.0)
    retry = backend.validator.make_command(
        CommandMode.JOINT_TORQUE,
        np.zeros(6),
        timestamp_s=float(backend.plant.data.time),
        deadline_s=float(backend.plant.data.time + 0.01),
        enable_requested=True,
    )
    assert "latched" in backend.submit_command(retry).reason
    backend.disconnect()
    backend.connect()
    assert backend.submit_command(retry).accepted


def test_simulation_backend_preserves_stage3c_torque_semantics() -> None:
    direct = CoupledUR10eHumanV2()
    wrapped_plant = CoupledUR10eHumanV2()
    reference = stage2_cuff_pose_reference(0.0, lower_q2_deg=10.0)
    direct.reset(reference.q_rad)
    wrapped_plant.reset(reference.q_rad)
    backend = Stage3SimulationBackend(wrapped_plant)
    backend.connect()
    for _ in range(25):
        observation = direct.observe()
        allocation = nominal_tracking_wrench(
            observation.human_q_rad,
            observation.human_dq_rad_s,
            reference,
        )
        linear, angular = human_cuff_velocity(reference.q_rad, reference.dq_rad_s)
        direct.apply_nominal_cartesian_control(
            reference.world_from_cuff.translation,
            linear,
            reference.world_from_cuff.rotation,
            angular,
            np.asarray(allocation["wrench_world"]),
        )
        command = backend.validator.make_command(
            CommandMode.JOINT_TORQUE,
            direct.last_joint_torque,
            timestamp_s=float(wrapped_plant.data.time),
            deadline_s=float(wrapped_plant.data.time + 0.005),
            enable_requested=True,
        )
        receipt = backend.submit_command(command)
        assert receipt.accepted and receipt.transmitted
        direct.step()
        backend.advance()
        np.testing.assert_array_equal(wrapped_plant.data.qpos, direct.data.qpos)
        np.testing.assert_array_equal(wrapped_plant.data.qvel, direct.data.qvel)


def test_calibrated_adapter_transform_is_injected_not_hardcoded() -> None:
    calibration = _calibration()
    expected = calibration.flange_from_adapter.compose(calibration.adapter_from_cuff)
    np.testing.assert_allclose(
        calibration.flange_from_cuff.translation,
        expected.translation,
    )
    backend = CR12DryRunBackend(calibration)
    assert backend.calibration is calibration
    assert backend.calibration.provenance == "unit-test calibrated transform fixture"


def test_cr12_dry_run_guarantees_no_hardware_transmission() -> None:
    backend = CR12DryRunBackend(_calibration())
    backend.connect()
    assert backend.capabilities.command_modes[CommandMode.JOINT_TORQUE] is CapabilityStatus.UNKNOWN
    result = SoftwareLimitResult(
        accepted=True,
        checked_mode=CommandMode.JOINT_TORQUE,
        checked_at_s=0.0,
        limit_source="malicious test bypass",
    )
    command = RobotCommand(
        mode=CommandMode.JOINT_TORQUE,
        vector=np.zeros(6),
        timestamp_s=0.0,
        deadline_s=1.0,
        enable_requested=True,
        software_limit_result=result,
    )
    receipt = backend.submit_command(command)
    assert not receipt.accepted and not receipt.transmitted
    assert backend.transmitted_command_count == 0
    assert len(backend.audit_log) == 1
    assert "transmission is disabled" in receipt.reason
    with pytest.raises(RuntimeError, match="no documented CR12 state schema"):
        backend.read_state()


def test_pose_rejects_ambiguous_frame_identity() -> None:
    with pytest.raises(ValueError, match="must differ"):
        FramedPose("base", "base", RigidTransform.identity())
