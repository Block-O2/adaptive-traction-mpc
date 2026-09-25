from __future__ import annotations

import numpy as np

from traction_mpc_stage5.split_acceleration_monitor import (
    SplitAccelerationMonitorV1,
)
from traction_mpc_stage5.transition_response_shadow import (
    ACCELERATION_MONITOR_ABORT,
    EXECUTION_STATE_CHANGE,
    INTERFACE_UNLOADED_TRANSITION,
    MPC_COMMAND_UPDATE,
    SUPPORT_LOAD_STATE_TRANSITION,
    TASK_PHASE_TRANSITION,
    TransitionResponseShadowV2,
)


def _sample(monitor: SplitAccelerationMonitorV1, index: int):
    time_s = 0.005 * index
    return monitor.update(
        sample_timestamp_s=time_s,
        estimated_dq_rad_s=np.array([1.0, -2.0]) * time_s,
        cuff_force_world_n=np.array([50.0 + index, 2.0, 3.0]),
        cuff_moment_world_nm=np.array([4.0, 5.0, 6.0 + index]),
        interface_translation_human_m=np.array([0.001, 0.002, 0.003]),
        interface_velocity_human_m_s=np.array([0.01, 0.02, 0.03]),
        interface_rotation_human_rad=np.array([0.01, 0.02, 0.03]),
        interface_angular_velocity_human_rad_s=np.array([0.1, 0.2, 0.3]),
        command_wrench_world=np.arange(6.0) + index,
        robot_joint_torque_command_nm=np.arange(6.0) + 2.0 * index,
    )


def _context(observer: TransitionResponseShadowV2, index: int, **changes):
    values = {
        "event_timestamp_s": 0.005 * index,
        "mpc_command_update": False,
        "support_load_state": "LOADED_TRACK",
        "task_phase": "OUTBOUND",
        "interface_load_state": "LOADED",
        "execution_state": {"supervisor_mode": "TRACK"},
        "metadata": {"index": index},
    }
    values.update(changes)
    return observer.record_context(**values)


def test_response_window_is_causal_complete_and_contains_all_channels() -> None:
    split = SplitAccelerationMonitorV1()
    observer = TransitionResponseShadowV2()
    first = _sample(split, 0)
    observer.observe(first)
    event = _context(observer, 0, mpc_command_update=True)
    assert event is not None
    for index in range(1, 5):
        observer.observe(_sample(split, index))
    artifact = observer.artifact()

    assert artifact["shadow_only"] is True
    assert artifact["abort_authority"] is False
    assert artifact["hard_threshold_active"] is False
    assert artifact["complete_window_count"] == 1
    record = artifact["events"][0]
    assert record["labels"] == [MPC_COMMAND_UPDATE]
    assert [row["response_elapsed_s"] for row in record["samples"]] == [
        0.0,
        0.005,
        0.010,
        0.015,
        0.020,
    ]
    final = record["samples"][-1]
    assert final["human_motion_20ms_valid"] is True
    assert final["fast_motion_5ms_valid"] is True
    assert final["robot_joint_torque_slew_valid"] is True
    assert len(final["cuff_wrench_world"]) == 6
    assert len(final["interface_translation_human_m"]) == 3
    assert len(final["command_wrench_slew_world_per_s"]) == 6
    shape = record["response_shape_features"]
    assert shape["threshold_free"] is True
    assert shape["classification_or_gate"] is None
    assert shape["signals"]["fast_motion_5ms_acceleration_rad_s2"][
        "valid_sample_count"
    ] == 4
    assert len(
        shape["signals"]["cuff_wrench_world"]["successive_l2_deltas"]
    ) == 4


def test_context_labels_cover_required_transitions_and_execution_changes() -> None:
    split = SplitAccelerationMonitorV1()
    observer = TransitionResponseShadowV2()
    observer.observe(_sample(split, 0))
    assert _context(observer, 0) is None

    observer.observe(_sample(split, 1))
    event = _context(
        observer,
        1,
        support_load_state="UNLOADED_TRANSFER",
        task_phase="HOLD",
        interface_load_state="UNLOADED",
        execution_state={"supervisor_mode": "BRAKE"},
    )
    assert event is not None
    assert SUPPORT_LOAD_STATE_TRANSITION in event.labels
    assert TASK_PHASE_TRANSITION in event.labels
    assert INTERFACE_UNLOADED_TRANSITION in event.labels
    assert f"{EXECUTION_STATE_CHANGE}:supervisor_mode" in event.labels
    transitions = event.metadata["context_transitions"]
    assert transitions["support_load_state"] == {
        "before": "LOADED_TRACK",
        "after": "UNLOADED_TRANSFER",
    }


def test_episode_end_keeps_partial_window_explicit() -> None:
    split = SplitAccelerationMonitorV1()
    observer = TransitionResponseShadowV2()
    observer.observe(_sample(split, 0))
    _context(observer, 0, mpc_command_update=True)
    observer.observe(_sample(split, 1))
    artifact = observer.artifact()

    assert artifact["complete_window_count"] == 0
    assert artifact["partial_window_count"] == 1
    assert artifact["events"][0]["complete_0_to_20ms"] is False
    assert artifact["events"][0]["sample_count"] == 2


def test_acceleration_abort_event_is_shadow_only_and_completes_causally() -> None:
    split = SplitAccelerationMonitorV1()
    observer = TransitionResponseShadowV2()
    observer.observe(_sample(split, 0))
    event = observer.record_acceleration_monitor_abort(
        event_timestamp_s=0.0,
        metadata={"diagnostic_clone_only": True},
    )
    for index in range(1, 5):
        observer.observe(_sample(split, index))
    record = observer.artifact()["events"][0]

    assert event.labels == (ACCELERATION_MONITOR_ABORT,)
    assert record["complete_0_to_20ms"] is True
    assert record["sample_count"] == 5
    assert record["response_shape_features"]["threshold_free"] is True
