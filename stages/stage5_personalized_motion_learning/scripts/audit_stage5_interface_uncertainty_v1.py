#!/usr/bin/env python3
"""Reclassify saved Mismatch v1 traces and replay uncertainty decisions."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage4.measurement import ControllerMeasurement
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.interface_uncertainty import (
    InterfaceUncertaintyMonitor,
    load_interface_uncertainty_spec,
    start_episode_uncertainty_aware,
    transition_phase_uncertainty_aware,
    uncertainty_motion_diagnostics,
    uncertainty_motion_violation,
)
from traction_mpc_stage5.task import (
    ControllerCompletionMargin,
    PROVISIONAL_CONTROLLER_COMPLETION_MARGIN,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
    start_episode,
    transition_phase,
    true_episode_complete,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]
MISMATCH_ROOT = STAGE5_ROOT / "results" / "interface_mismatch_v1_attempt03"


def _fixed_model():
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    pose = STAGE5_GEOMETRY.world_from_cuff(
        np.asarray(task.start_return_target_rad), STAGE5_HUMAN
    )
    return FixedStage5Estimator(
        pose.translation,
        pose.rotation,
        np.asarray(task.start_return_target_rad),
    ).model


def _measurement_from_nominal_trace(trace, index: int, model) -> ControllerMeasurement:
    time_s = float(trace["time_s"][index])
    state = np.asarray(trace["estimated_state_rad_rad_s"][index], dtype=float)
    x = np.asarray(trace["estimated_interface_translation_human_m"][index], dtype=float)
    u = np.asarray(trace["estimated_interface_velocity_human_m_s"][index], dtype=float)
    theta = np.asarray(trace["estimated_interface_rotation_human_rad"][index], dtype=float)
    omega = np.asarray(
        trace["estimated_interface_angular_velocity_human_rad_s"][index], dtype=float
    )
    human_pose = model.geometry.cuff_pose(state[:2])
    human_velocity, human_omega = model.geometry.cuff_velocity(state[:2], state[2:])
    relative_rotation = Rotation.from_rotvec(theta).as_matrix()
    robot_rotation = human_pose.rotation @ relative_rotation
    r_world = human_pose.rotation @ x
    robot_position = human_pose.translation + r_world
    robot_omega = human_omega + human_pose.rotation @ omega
    robot_velocity = (
        human_velocity
        + np.cross(human_omega, r_world)
        + human_pose.rotation @ u
    )
    zeros6 = np.zeros(6)
    return ControllerMeasurement(
        arrival_time_s=time_s,
        sample_time_s=time_s,
        robot_q_rad=zeros6.copy(),
        robot_dq_rad_s=zeros6.copy(),
        attachment_position_m=robot_position,
        attachment_rotation_matrix=robot_rotation,
        attachment_velocity_m_s=robot_velocity,
        attachment_angular_velocity_rad_s=robot_omega,
        cuff_force_vector_n=np.asarray(
            trace["physical_cuff_force_world_n"][index], dtype=float
        ),
        cuff_moment_vector_nm=np.asarray(
            trace["physical_cuff_moment_world_nm"][index], dtype=float
        ),
        new_sample=True,
        control_robot_q_rad=zeros6.copy(),
        control_robot_dq_rad_s=zeros6.copy(),
        control_velocity_sample_time_s=time_s,
    )


def _truth_task_completion(trace) -> dict[str, object]:
    task = replace(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        task_joint_velocity_limit_rad_s=None,
        task_joint_acceleration_limit_rad_s2=None,
    )
    q = np.asarray(trace["evaluation_human_q_rad"], dtype=float)
    dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    time = np.asarray(trace["time_s"], dtype=float)
    state = start_episode(task, q[0], dq[0])
    transitions = [{"time_s": float(time[0]), "phase": state.phase.value}]
    for index in range(1, len(time)):
        next_state = transition_phase(
            task,
            state,
            q[index],
            dq[index],
            float(time[index] - time[index - 1]),
            completion_margin=ControllerCompletionMargin(),
        )
        if next_state.phase is not state.phase:
            transitions.append(
                {"time_s": float(time[index]), "phase": next_state.phase.value}
            )
        state = next_state
    return {
        "complete": true_episode_complete(state),
        "terminal_phase": state.phase.value,
        "transitions": transitions,
    }


def _original_classification(cell: dict, trace) -> dict[str, object]:
    online_complete = cell["task_status"] == "COMPLETE"
    online_velocity_ok = all(value >= -1.0e-9 for value in cell["velocity_margin_estimated_deg_s"])
    online_acceleration_ok = all(
        value >= -1.0e-9 for value in cell["acceleration_margin_deployable_deg_s2"]
    )
    truth_velocity_ok = all(value >= -1.0e-9 for value in cell["velocity_margin_truth_deg_s"])
    truth_acceleration_ok = all(
        value >= -1.0e-9 for value in cell["acceleration_margin_truth_deg_s2"]
    )
    truth_completion = (
        {"complete": False, "terminal_phase": "NOT_STARTED", "transitions": []}
        if trace is None
        else _truth_task_completion(trace)
    )
    initialization_failure = cell["abort_reason"] in {
        "INITIAL_CONDITION_OUTSIDE_SETTLED_START_SET",
        "INTERFACE_UNCERTAINTY_START_NOT_SETTLED",
    }
    false_negative = online_velocity_ok and online_acceleration_ok and not (
        truth_velocity_ok and truth_acceleration_ok
    )
    false_positive = (
        cell["task_status"] == "ABORTED"
        and cell["abort_reason"] == "TASK_ACCELERATION_LIMIT"
        and truth_velocity_ok
        and truth_acceleration_ok
    )
    normal_success = (
        online_complete
        and truth_completion["complete"]
        and online_velocity_ok
        and online_acceleration_ok
        and truth_velocity_ok
        and truth_acceleration_ok
    )
    return {
        "online_task_result": cell["task_status"],
        "online_abort_reason": cell["abort_reason"],
        "evaluation_truth_task_completion": truth_completion,
        "online_motion_envelope_compliant": online_velocity_ok and online_acceleration_ok,
        "evaluation_truth_motion_envelope_compliant": truth_velocity_ok and truth_acceleration_ok,
        "false_negative": false_negative,
        "false_positive": false_positive,
        "initialization_settled_start_failure": initialization_failure,
        "normal_successful_completion": normal_success,
    }


def _replay_uncertainty(trace, model) -> dict[str, object]:
    monitor = InterfaceUncertaintyMonitor(load_interface_uncertainty_spec())
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    time = np.asarray(trace["time_s"], dtype=float)
    first = monitor.update(
        _measurement_from_nominal_trace(trace, 0, model),
        model,
        human_model_version="stage5_fixed_registered_human_v1",
    )
    nominal_reconstruction_error = first.nominal.observation.as_array() - np.asarray(
        trace["estimated_state_rad_rad_s"][0], dtype=float
    )
    first_violation = uncertainty_motion_violation(task, first)
    first_violation_details = (
        uncertainty_motion_diagnostics(task, first)
        if first_violation is not None
        else None
    )
    try:
        state = start_episode_uncertainty_aware(task, first)
        start_result = "ACCEPTED"
    except ValueError as error:
        return {
            "start_result": "REJECTED",
            "start_reason": str(error).rsplit(": ", 1)[-1],
            "counterfactual_terminal_phase": "ABORTED",
            "first_uncertainty_violation": first_violation,
            "first_uncertainty_violation_time_s": 0.0 if first_violation else None,
            "first_uncertainty_violation_details": first_violation_details,
            "nominal_trace_reconstruction_peak_abs_error": np.abs(
                nominal_reconstruction_error
            ).tolist(),
        }
    first_violation_time = 0.0 if first_violation else None
    max_state_width = np.ptp(first.state_matrix, axis=0)
    max_acceleration = np.max(np.abs(first.decision_acceleration_matrix), axis=0)
    transitions = [{"time_s": float(time[0]), "phase": state.phase.value}]
    for index in range(1, len(time)):
        estimate = monitor.update(
            _measurement_from_nominal_trace(trace, index, model),
            model,
            human_model_version="stage5_fixed_registered_human_v1",
        )
        nominal_reconstruction_error = np.maximum(
            np.abs(nominal_reconstruction_error),
            np.abs(
                estimate.nominal.observation.as_array()
                - np.asarray(trace["estimated_state_rad_rad_s"][index], dtype=float)
            ),
        )
        max_state_width = np.maximum(max_state_width, np.ptp(estimate.state_matrix, axis=0))
        max_acceleration = np.maximum(
            max_acceleration,
            np.max(np.abs(estimate.decision_acceleration_matrix), axis=0),
        )
        violation = uncertainty_motion_violation(task, estimate)
        if violation is not None and first_violation_time is None:
            first_violation = violation
            first_violation_time = float(time[index])
            first_violation_details = uncertainty_motion_diagnostics(task, estimate)
        next_state = transition_phase_uncertainty_aware(
            task,
            state,
            estimate,
            float(time[index] - time[index - 1]),
            completion_margin=PROVISIONAL_CONTROLLER_COMPLETION_MARGIN,
        )
        if next_state.phase is not state.phase:
            transitions.append(
                {
                    "time_s": float(time[index]),
                    "phase": next_state.phase.value,
                    "reason": next_state.abort_reason,
                }
            )
        state = next_state
        if state.phase is TaskPhase.ABORTED:
            break
    return {
        "start_result": start_result,
        "start_reason": None,
        "counterfactual_terminal_phase": state.phase.value,
        "counterfactual_complete": true_episode_complete(state),
        "counterfactual_transitions": transitions,
        "first_uncertainty_violation": first_violation,
        "first_uncertainty_violation_time_s": first_violation_time,
        "first_uncertainty_violation_details": first_violation_details,
        "nominal_trace_reconstruction_peak_abs_error": nominal_reconstruction_error.tolist(),
        "maximum_empirical_state_width_deg_deg_s": np.degrees(max_state_width).tolist(),
        "maximum_empirical_acceleration_abs_deg_s2": np.degrees(max_acceleration).tolist(),
        "truth_used_online": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "interface_uncertainty_v1",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = json.loads((MISMATCH_ROOT / "sweep_summary.json").read_text())
    model = _fixed_model()
    rows = []
    for cell in aggregate["cells"]:
        trace_path = MISMATCH_ROOT / cell["case"] / "trace.npz"
        if trace_path.exists():
            with np.load(trace_path) as trace:
                classification = _original_classification(cell, trace)
                uncertainty = _replay_uncertainty(trace, model)
        else:
            classification = _original_classification(cell, None)
            uncertainty = {
                "start_result": "REJECTED_BY_EXISTING_NOMINAL_OBSERVER",
                "start_reason": cell["abort_reason"],
                "counterfactual_terminal_phase": "ABORTED",
                "truth_used_online": False,
            }
        rows.append(
            {
                "case": cell["case"],
                "classification": classification,
                "uncertainty_replay": uncertainty,
            }
        )
    result = {
        "schema": "stage5_interface_uncertainty_v1_saved_trace_audit",
        "source": "interface_mismatch_v1_attempt03",
        "new_plant_runs": 0,
        "operating_set": json.loads(
            (STAGE5_ROOT / "configs" / "stage5_interface_uncertainty_v1.json").read_text()
        ),
        "rows": rows,
    }
    output = args.output_dir / "saved_trace_audit.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
