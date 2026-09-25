from __future__ import annotations

import inspect
import json
from dataclasses import replace

import numpy as np
import pytest

from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
from traction_mpc_stage5.split_acceleration_monitor import (
    HumanMotionAccelerationAuthorityV1,
    SplitAccelerationMonitorV1,
)


def _update(
    monitor: SplitAccelerationMonitorV1,
    index: int,
    *,
    torque: np.ndarray | None = None,
):
    time_s = 0.005 * index
    return monitor.update(
        sample_timestamp_s=time_s,
        estimated_dq_rad_s=np.array([2.0, -3.0]) * time_s,
        cuff_force_world_n=np.array([1.0 + index, 2.0, 3.0]),
        cuff_moment_world_nm=np.array([0.1, 0.2 + 0.5 * index, 0.3]),
        interface_translation_human_m=np.array([0.001, 0.002, 0.003]),
        interface_velocity_human_m_s=np.array([0.01, 0.02, 0.03]),
        interface_rotation_human_rad=np.array([0.01, 0.02, 0.03]),
        interface_angular_velocity_human_rad_s=np.array([0.1, 0.2, 0.3]),
        command_wrench_world=np.array(
            [10.0 + 2.0 * index, 20.0, 30.0, 1.0, 2.0, 3.0 + index]
        ),
        robot_joint_torque_command_nm=(
            None if torque is None else np.asarray(torque, dtype=float) + index
        ),
    )


def test_human_motion_channel_requires_full_causal_20ms_history() -> None:
    monitor = SplitAccelerationMonitorV1()
    samples = [_update(monitor, index, torque=np.arange(6.0)) for index in range(5)]

    assert not any(sample.human_motion_valid for sample in samples[:4])
    assert samples[3].human_motion_history_coverage_s == pytest.approx(0.015)
    assert samples[4].human_motion_valid
    assert samples[4].human_motion_history_coverage_s == pytest.approx(0.020)
    assert samples[4].human_motion_history_sample_count == 5
    np.testing.assert_allclose(
        samples[4].human_motion_acceleration_rad_s2, [2.0, -3.0]
    )


def test_fast_channel_is_event_aligned_to_one_5ms_interval() -> None:
    monitor = SplitAccelerationMonitorV1()
    first = _update(monitor, 0, torque=np.arange(6.0))
    second = _update(monitor, 1, torque=np.arange(6.0))

    assert not first.fast_motion_valid
    assert second.fast_motion_valid
    assert second.fast_alignment_interval_s == pytest.approx(0.005)
    np.testing.assert_allclose(second.fast_motion_acceleration_rad_s2, [2.0, -3.0])
    np.testing.assert_allclose(
        second.cuff_wrench_slew_world_per_s,
        [200.0, 0.0, 0.0, 0.0, 100.0, 0.0],
    )
    np.testing.assert_allclose(
        second.command_wrench_slew_world_per_s,
        [400.0, 0.0, 0.0, 0.0, 0.0, 200.0],
    )
    np.testing.assert_allclose(second.robot_joint_torque_slew_nm_s, 200.0)
    assert second.robot_joint_torque_slew_valid
    assert second.shadow_only
    assert not second.abort_authority


def test_missing_historical_robot_torque_is_explicit_not_reconstructed() -> None:
    monitor = SplitAccelerationMonitorV1()
    _update(monitor, 0)
    sample = _update(monitor, 1)

    assert not sample.robot_joint_torque_available
    assert not sample.robot_joint_torque_slew_valid
    assert np.all(np.isnan(sample.robot_joint_torque_command_nm))
    assert np.all(np.isnan(sample.robot_joint_torque_slew_nm_s))


def test_duplicate_timestamp_reuses_shadow_record() -> None:
    monitor = SplitAccelerationMonitorV1()
    first = _update(monitor, 0, torque=np.arange(6.0))
    duplicate = _update(monitor, 0, torque=np.arange(6.0))
    assert duplicate is first


def test_split_monitor_has_no_human_model_or_truth_input() -> None:
    parameters = inspect.signature(SplitAccelerationMonitorV1.update).parameters
    assert "human_model" not in parameters
    assert "truth" not in parameters
    assert "qacc" not in parameters
    runtime_source = inspect.getsource(run_goal_mpc_smoke)
    assert "ddq_rad_s2=realized_acceleration.acceleration_rad_s2" not in runtime_source
    assert "human_motion_authority_decision.acceleration_rad_s2" in runtime_source
    assert "include_model_acceleration_authority=False" in runtime_source


def test_human_motion_authority_requires_valid_full_history() -> None:
    monitor = SplitAccelerationMonitorV1()
    authority = HumanMotionAccelerationAuthorityV1(np.radians([300.0, 600.0]))
    warmup = [
        authority.evaluate(_update(monitor, index, torque=np.arange(6.0)))
        for index in range(4)
    ]
    active = authority.evaluate(_update(monitor, 4, torque=np.arange(6.0)))

    assert not any(decision.authority_active for decision in warmup)
    assert all(not decision.violation for decision in warmup)
    assert active.authority_active
    assert active.history_coverage_s == pytest.approx(0.020)
    assert not active.model_based_qdd_used
    assert not active.truth_used_online


def test_human_motion_authority_uses_existing_limits() -> None:
    monitor = SplitAccelerationMonitorV1()
    authority = HumanMotionAccelerationAuthorityV1(np.radians([300.0, 600.0]))
    decision = None
    for index in range(5):
        time_s = 0.005 * index
        sample = monitor.update(
            sample_timestamp_s=time_s,
            estimated_dq_rad_s=np.radians([301.0, 601.0]) * time_s,
            cuff_force_world_n=np.zeros(3),
            cuff_moment_world_nm=np.zeros(3),
            interface_translation_human_m=np.zeros(3),
            interface_velocity_human_m_s=np.zeros(3),
            interface_rotation_human_rad=np.zeros(3),
            interface_angular_velocity_human_rad_s=np.zeros(3),
            command_wrench_world=np.zeros(6),
            robot_joint_torque_command_nm=np.zeros(6),
        )
        decision = authority.evaluate(sample)
    assert decision is not None
    assert decision.authority_active
    assert decision.violation
    assert decision.abort_reason == "TASK_ACCELERATION_LIMIT"


def test_goal_smoke_logs_shadow_channels_without_changing_authority(tmp_path) -> None:
    output = tmp_path / "split-shadow-smoke"
    summary = run_goal_mpc_smoke(output, maximum_duration_s=0.025)
    with np.load(output / "trace.npz", allow_pickle=False) as trace:
        assert len(trace["time_s"]) == 6
        np.testing.assert_array_equal(
            trace["shadow_human_motion_valid"],
            [False, False, False, False, True, True],
        )
        np.testing.assert_allclose(
            trace["shadow_human_motion_history_coverage_s"][-2:], 0.020
        )
        np.testing.assert_array_equal(
            trace["shadow_fast_motion_valid"],
            [False, True, True, True, True, True],
        )
        assert np.all(trace["shadow_robot_joint_torque_available"])
        np.testing.assert_array_equal(
            trace["shadow_robot_joint_torque_slew_valid"],
            [False, True, True, True, True, True],
        )
        assert np.all(
            np.isfinite(trace["shadow_robot_joint_torque_command_nm"])
        )
        assert np.all(
            np.isfinite(trace["shadow_robot_joint_torque_slew_nm_s"][1:])
        )
    contract = summary["split_acceleration_monitor_shadow"]
    assert contract["shadow_only"] is True
    assert contract["abort_authority"] is False
    assert contract["existing_model_based_monitor_remains_authoritative"] is False
    assert contract["human_motion_channel"][
        "signal_consumed_by_separate_abort_authority"
    ] is True
    authority = summary["human_motion_acceleration_authority"]
    assert authority["abort_authority"] is True
    assert authority["model_based_qdd_used"] is False
    assert authority["registered_limit_deg_s2"] == [300.0, 600.0]
    response_contract = summary["transition_response_shadow_v2"]
    assert response_contract["shadow_only"] is True
    assert response_contract["abort_authority"] is False
    assert response_contract["hard_threshold_active"] is False
    artifact = json.loads(
        (output / "transition_response_shadow_v2.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["event_count"] == 3
    assert artifact["complete_window_count"] == 1
    assert artifact["events"][0]["labels"] == ["MPC_COMMAND_UPDATE"]
    assert "TASK_PHASE_TRANSITION" in artifact["events"][-1]["labels"]
    assert "SUPPORT_LOAD_STATE_TRANSITION" in artifact["events"][-1]["labels"]
    assert [
        row["response_elapsed_s"] for row in artifact["events"][0]["samples"]
    ] == pytest.approx([0.0, 0.005, 0.010, 0.015, 0.020])
    assert summary["abort_reason"] == "SMOKE_MAXIMUM_DURATION"


def test_post_abort_diagnostic_clone_preserves_authoritative_rollout(tmp_path) -> None:
    sensitive_spec = replace(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        task_joint_acceleration_limit_rad_s2=tuple(
            np.radians([1.0e-9, 1.0e-9])
        ),
    )
    baseline_dir = tmp_path / "authoritative-only"
    diagnostic_dir = tmp_path / "with-diagnostic-clone"
    baseline = run_goal_mpc_smoke(
        baseline_dir,
        spec=sensitive_spec,
        maximum_duration_s=0.050,
    )
    diagnostic = run_goal_mpc_smoke(
        diagnostic_dir,
        spec=sensitive_spec,
        maximum_duration_s=0.050,
        diagnostic_post_abort_continuation=True,
    )

    assert baseline["abort_reason"] == "TASK_ACCELERATION_LIMIT"
    assert diagnostic["abort_reason"] == baseline["abort_reason"]
    assert diagnostic["task_duration_s"] == baseline["task_duration_s"]
    with np.load(baseline_dir / "trace.npz", allow_pickle=False) as left, np.load(
        diagnostic_dir / "trace.npz", allow_pickle=False
    ) as right:
        assert set(left.files) == set(right.files)
        for name in left.files:
            if left[name].dtype.kind in "OUS":
                np.testing.assert_array_equal(left[name], right[name])
            else:
                np.testing.assert_array_equal(left[name], right[name])

    artifact = json.loads(
        (diagnostic_dir / "diagnostic_post_abort_continuation.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["diagnostic_clone_isolated"] is True
    assert artifact["original_rollout_modified"] is False
    assert artifact["continuation"]["exact_duration_verified"] is True
    assert {
        "estimator_layer",
        "mpc_layer",
        "low_level_layer",
        "estimator",
        "interface_observer",
        "acceleration_monitor",
        "split_acceleration_monitor",
        "mpc",
        "supervisor",
        "current_model",
        "cuff_allocator",
    }.issubset(artifact["snapshot"]["controller_graph_keys"])
    event = artifact["continuation"]["transition_response_shadow_v2"]["events"][0]
    assert event["labels"] == ["ACCELERATION_MONITOR_ABORT"]
    assert event["complete_0_to_20ms"] is True
    assert [sample["response_elapsed_s"] for sample in event["samples"]] == pytest.approx(
        [0.0, 0.005, 0.010, 0.015, 0.020]
    )
    for sample in event["samples"][1:]:
        np.testing.assert_allclose(sample["command_wrench_slew_world_per_s"], 0.0)
        np.testing.assert_allclose(sample["robot_joint_torque_slew_nm_s"], 0.0)
