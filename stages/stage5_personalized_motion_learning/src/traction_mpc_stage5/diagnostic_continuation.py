"""Isolated frozen-command continuation for Stage-5 transient diagnostics.

The authoritative rollout stops normally.  A cloned plant and a deep-copied
controller/deployable graph then hold the last command that was actually sent
before the abort and collect four additional causal samples.  No MPC,
supervisor, task transition, or abort decision is executed in the clone.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .matched_branch import (
    Stage5RuntimeSnapshot,
    capture_runtime_snapshot,
    restore_runtime_snapshot,
)
from .transition_response_shadow import TransitionResponseShadowV2


DIAGNOSTIC_CONTINUATION_SCHEMA = "stage5_diagnostic_continuation_v1"
DIAGNOSTIC_CONTINUATION_DURATION_S = 0.020


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"unsupported diagnostic-continuation value: {type(value)!r}")


def _estimator_observe(estimator: Any, measurement: Any) -> None:
    estimator.observe(
        time_s=measurement.sample_time_s,
        position_world_m=measurement.attachment_position_m,
        rotation_world_from_cuff=measurement.attachment_rotation_matrix,
        linear_velocity_world_m_s=measurement.attachment_velocity_m_s,
        angular_velocity_world_rad_s=measurement.attachment_angular_velocity_rad_s,
        force_world_n=measurement.cuff_force_vector_n,
        moment_world_nm=measurement.cuff_moment_vector_nm,
        bed_contaminated=False,
    )


@dataclass(frozen=True)
class DiagnosticContinuationClone:
    """In-memory full-state clone captured at one shadow diagnostic trigger."""

    plant: Any
    snapshot: Stage5RuntimeSnapshot
    trigger_timestamp_s: float
    trigger_kind: str
    trigger_metadata: dict[str, Any]
    original_control_index: int


DiagnosticPostAbortClone = DiagnosticContinuationClone


def capture_diagnostic_continuation_clone(
    *,
    plant: Any,
    controller_graph: Mapping[str, Any],
    runtime_state: Mapping[str, Any],
    deployable_start: Mapping[str, Any],
    trigger_timestamp_s: float,
    trigger_kind: str,
    trigger_metadata: Mapping[str, Any],
    original_control_index: int,
) -> DiagnosticContinuationClone:
    """Capture plant, controller, and deployable state without mutating them."""

    if trigger_kind not in {
        "ACCELERATION_MONITOR_ABORT",
        "NEAR_LIMIT_BENIGN_TRIGGER",
    }:
        raise ValueError("unsupported diagnostic continuation trigger")
    clone = deepcopy(plant)
    snapshot = capture_runtime_snapshot(
        plant=plant,
        controller_graph=controller_graph,
        runtime_state=runtime_state,
        deployable_start=deployable_start,
    )
    return DiagnosticContinuationClone(
        plant=clone,
        snapshot=snapshot,
        trigger_timestamp_s=float(trigger_timestamp_s),
        trigger_kind=str(trigger_kind),
        trigger_metadata=dict(_jsonable(trigger_metadata)),
        original_control_index=int(original_control_index),
    )


def capture_diagnostic_post_abort_clone(
    *,
    plant: Any,
    controller_graph: Mapping[str, Any],
    runtime_state: Mapping[str, Any],
    deployable_start: Mapping[str, Any],
    abort_timestamp_s: float,
    abort_reason: str,
    original_control_index: int,
) -> DiagnosticPostAbortClone:
    """Capture plant, controller, and deployable state without mutating them."""

    if abort_reason != "TASK_ACCELERATION_LIMIT":
        raise ValueError("diagnostic continuation is scoped to acceleration aborts")
    return capture_diagnostic_continuation_clone(
        plant=plant,
        controller_graph=controller_graph,
        runtime_state=runtime_state,
        deployable_start=deployable_start,
        trigger_timestamp_s=abort_timestamp_s,
        trigger_kind="ACCELERATION_MONITOR_ABORT",
        trigger_metadata={
            "authoritative_abort_reason": str(abort_reason),
            "authoritative_abort_timestamp_s": float(abort_timestamp_s),
        },
        original_control_index=int(original_control_index),
    )


def run_diagnostic_continuation(
    clone: DiagnosticContinuationClone,
    *,
    control_dt_s: float,
    physics_substeps: int,
    high_level_steps: int,
) -> dict[str, Any]:
    """Hold the last real command and collect exactly +5/+10/+15/+20 ms."""

    if not np.isclose(
        DIAGNOSTIC_CONTINUATION_DURATION_S / control_dt_s,
        4.0,
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise ValueError("diagnostic continuation requires four 5 ms samples")
    if physics_substeps < 1 or high_level_steps < 1:
        raise ValueError("diagnostic continuation scheduler is invalid")

    graph, runtime = restore_runtime_snapshot(clone.plant, clone.snapshot)
    estimator_layer = graph["estimator_layer"]
    mpc_layer = graph["mpc_layer"]
    low_level_layer = graph["low_level_layer"]
    estimator = graph["estimator"]
    interface_observer = graph["interface_observer"]
    split_monitor = graph["split_acceleration_monitor"]
    last_command = runtime["last_executable_command"]
    trigger_sample = split_monitor.latest
    if trigger_sample is None or not np.isclose(
        trigger_sample.sample_timestamp_s,
        clone.trigger_timestamp_s,
        atol=1.0e-10,
        rtol=0.0,
    ):
        raise RuntimeError("cloned split monitor is not aligned to trigger time")
    if interface_observer is None:
        raise ValueError("V1 diagnostic continuation requires nominal observer path")

    response = TransitionResponseShadowV2()
    response.observe(trigger_sample)
    event_metadata = {
            **clone.trigger_metadata,
            "diagnostic_clone_only": True,
            "command_policy": "FROZEN_LAST_EXECUTABLE_COMMAND",
            "new_mpc_or_supervisor_decisions_after_trigger": False,
            "new_mpc_or_supervisor_decisions_after_abort": False,
            "original_rollout_reinterpreted_as_success": False,
            "hard_threshold_active": False,
    }
    if clone.trigger_kind == "ACCELERATION_MONITOR_ABORT":
        response.record_acceleration_monitor_abort(
            event_timestamp_s=clone.trigger_timestamp_s,
            metadata=event_metadata,
        )
    else:
        response.record_near_limit_benign_trigger(
            event_timestamp_s=clone.trigger_timestamp_s,
            metadata=event_metadata,
        )

    offline_truth = []
    truth = clone.plant.observe()
    offline_truth.append(
        {
            "response_elapsed_s": 0.0,
            "human_q_rad": np.asarray(truth.human_q_rad, dtype=float),
            "human_dq_rad_s": np.asarray(truth.human_dq_rad_s, dtype=float),
            "mujoco_human_qacc_rad_s2": np.asarray(
                clone.plant.data.qacc[clone.plant.human_dof_indices], dtype=float
            ),
        }
    )

    current_model_version = str(runtime["current_control_model_version"])
    for offset_index in range(1, 5):
        clone.plant.apply_executable_command(last_command)
        for _ in range(physics_substeps):
            truth = clone.plant.step()

        estimator_measurement = estimator_layer.update(truth)
        mpc_measurement = mpc_layer.update(truth)
        low_level_layer.update(truth)
        continued_control_index = clone.original_control_index + offset_index
        if continued_control_index % high_level_steps == 0:
            _estimator_observe(estimator, estimator_measurement)
        task_observation, interface_state = interface_observer.update(
            mpc_measurement,
            estimator.model,
            human_model_version=current_model_version,
        )
        sample = split_monitor.update(
            sample_timestamp_s=task_observation.sample_timestamp_s,
            estimated_dq_rad_s=task_observation.as_array()[2:],
            cuff_force_world_n=interface_state.measured_force_world_n,
            cuff_moment_world_nm=interface_state.measured_moment_world_nm,
            interface_translation_human_m=interface_state.displacement_human_m,
            interface_velocity_human_m_s=interface_state.velocity_human_m_s,
            interface_rotation_human_rad=interface_state.rotation_error_human_rad,
            interface_angular_velocity_human_rad_s=(
                interface_state.angular_velocity_human_rad_s
            ),
            command_wrench_world=last_command.wrench_total_world,
            robot_joint_torque_command_nm=last_command.joint_torque_command_nm,
        )
        response.observe(sample)
        offline_truth.append(
            {
                "response_elapsed_s": offset_index * control_dt_s,
                "human_q_rad": np.asarray(truth.human_q_rad, dtype=float),
                "human_dq_rad_s": np.asarray(truth.human_dq_rad_s, dtype=float),
                "mujoco_human_qacc_rad_s2": np.asarray(
                    clone.plant.data.qacc[clone.plant.human_dof_indices], dtype=float
                ),
            }
        )

    artifact = response.artifact(time_origin_s=clone.trigger_timestamp_s)
    trigger_events = [
        event
        for event in artifact["events"]
        if clone.trigger_kind in event["labels"]
    ]
    if len(trigger_events) != 1 or not trigger_events[0]["complete_0_to_20ms"]:
        raise RuntimeError("diagnostic response did not complete at 20 ms")
    final_time_s = float(clone.plant.observe().time_s)
    return _jsonable(
        {
            "schema": DIAGNOSTIC_CONTINUATION_SCHEMA,
            "evidence_category": "diagnostic_engineering_continuation_only",
            "shadow_only": True,
            "abort_authority": False,
            "hard_threshold_active": False,
            "diagnostic_clone_isolated": True,
            "original_rollout_modified": False,
            "original_rollout_reinterpreted_as_success": False,
            "scientific_parameters_changed": False,
            "control_policy": "FROZEN_LAST_EXECUTABLE_COMMAND",
            "new_mpc_or_supervisor_decisions_after_abort": False,
            "trigger": {
                "kind": clone.trigger_kind,
                "timestamp_s": clone.trigger_timestamp_s,
                "original_control_index": clone.original_control_index,
                "metadata": clone.trigger_metadata,
            },
            "snapshot": {
                "full_plant_integration_state_captured": True,
                "plant_auxiliary_state_captured": True,
                "controller_graph_deep_copied": True,
                "deployable_state_deep_copied": True,
                "decision_state_sha256": clone.snapshot.decision_state_sha256,
                "controller_graph_keys": sorted(
                    clone.snapshot.controller_graph.keys()
                ),
                "runtime_state_keys": sorted(clone.snapshot.runtime_state.keys()),
            },
            "continuation": {
                "duration_s": DIAGNOSTIC_CONTINUATION_DURATION_S,
                "control_dt_s": control_dt_s,
                "sample_offsets_ms": [0.0, 5.0, 10.0, 15.0, 20.0],
                "final_clone_time_s": final_time_s,
                "exact_duration_verified": bool(
                    np.isclose(
                        final_time_s - clone.trigger_timestamp_s,
                        DIAGNOSTIC_CONTINUATION_DURATION_S,
                        atol=1.0e-10,
                        rtol=0.0,
                    )
                ),
                "transition_response_shadow_v2": artifact,
            },
            "offline_evaluation_only_mujoco_truth": offline_truth,
        }
    )


def run_diagnostic_post_abort_continuation(
    clone: DiagnosticPostAbortClone,
    *,
    control_dt_s: float,
    physics_substeps: int,
    high_level_steps: int,
) -> dict[str, Any]:
    """Compatibility wrapper for the authoritative-abort diagnostic path."""

    result = run_diagnostic_continuation(
        clone,
        control_dt_s=control_dt_s,
        physics_substeps=physics_substeps,
        high_level_steps=high_level_steps,
    )
    result["schema"] = "stage5_post_abort_diagnostic_continuation_v1"
    result["authoritative_abort"] = {
        "reason": clone.trigger_metadata["authoritative_abort_reason"],
        "timestamp_s": clone.trigger_timestamp_s,
        "original_control_index": clone.original_control_index,
    }
    return result


__all__ = [
    "DIAGNOSTIC_CONTINUATION_DURATION_S",
    "DIAGNOSTIC_CONTINUATION_SCHEMA",
    "DiagnosticContinuationClone",
    "DiagnosticPostAbortClone",
    "capture_diagnostic_continuation_clone",
    "capture_diagnostic_post_abort_clone",
    "run_diagnostic_continuation",
    "run_diagnostic_post_abort_continuation",
]
