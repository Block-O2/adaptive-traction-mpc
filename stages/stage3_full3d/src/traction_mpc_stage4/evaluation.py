"""Minimal fixed/adaptive Stage-4 comparison and God-view logging."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    CONTROL_SUBSTEPS,
    CuffForceCommandLimitError,
    CoupledUR10eHumanV2,
    human_cuff_velocity,
)
from traction_mpc_stage3.frames import base_from_attachment_target
from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HUMAN,
    HumanV2Parameters,
    sleeve_jacobian,
    sleeve_position,
)
from traction_mpc_stage3.ik import _initial_solution
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff

from .human_model import (
    allocate_generalized_action,
    nominal_parameter_vector,
    registered_moderate_human,
)
from .identifier import ESTIMATED_PARAMETER_NAMES, WindowedHumanNLS
from .identifiability import run_offline_identifiability_audit
from .mpc import HumanSpaceMPC
from .reference import TEACHING_DURATION_S, teaching_reference


# Existing Stage-3 engineering contact-activity criterion.  This is used only
# to reject estimator windows carrying material bed load; it is not a clinical
# contact or safety threshold.
BED_CONTACT_CONTAMINATION_FORCE_N = 2.0


class Stage4CoupledPlant(CoupledUR10eHumanV2):
    """Stage-4 reset that respects a registered true sleeve-center mismatch."""

    def reset(self, human_q_rad: np.ndarray):
        q = np.asarray(human_q_rad, dtype=float)
        pose = _world_from_cuff(q)
        true_pose = type(pose)(pose.rotation, sleeve_position(q, self.human))
        robot_q = _initial_solution(self._ik_robot, base_from_attachment_target(true_pose))
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.human_qpos_indices] = q
        self.data.qpos[self.robot_qpos_indices] = robot_q
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = 0.0
        self.data.eq_active[self.weld_id] = 1
        self.neutral_robot_q = robot_q.copy()
        self.last_joint_torque[:] = 0.0
        self.last_unclipped_joint_torque[:] = 0.0
        self.last_force[:] = 0.0
        self.last_moment[:] = 0.0
        self._apply_soft_limit()
        mujoco.mj_forward(self.model, self.data)
        return self.observe()


def _finite_observation(observation: Any) -> bool:
    return all(
        np.all(np.isfinite(value))
        for value in (
            observation.human_q_rad,
            observation.human_dq_rad_s,
            observation.robot_q_rad,
            observation.robot_dq_rad_s,
            observation.cuff_force_vector_n,
            observation.cuff_moment_vector_nm,
            observation.joint_torque_command_nm,
        )
    )


def reconstructed_wrench_human_input_nm(
    human_q_rad: np.ndarray,
    cuff_force_world_n: np.ndarray,
    cuff_moment_world_nm: np.ndarray,
) -> np.ndarray:
    """Map the reconstructed virtual F/T measurement by nominal virtual work.

    Only measured joint state, reconstructed wrench, and the fixed nominal
    Human-V2 cuff kinematics enter this channel.  No true MuJoCo Human
    parameter or true-plant Jacobian is used.
    """

    force_torque = sleeve_jacobian(human_q_rad, HUMAN).T @ np.asarray(
        cuff_force_world_n,
        dtype=float,
    )
    moment_y = float(np.asarray(cuff_moment_world_nm, dtype=float)[1])
    return force_torque + np.array([-moment_y, moment_y])


def run_stage4_case(
    *,
    controller_kind: str,
    true_case: str,
    duration_s: float = TEACHING_DURATION_S,
    reference_fn: Callable[[float], CuffPoseReference] = teaching_reference,
    trajectory_label: str = "stage4_teaching_18s",
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if controller_kind not in {"fixed", "adaptive"}:
        raise ValueError("controller_kind must be fixed or adaptive")
    if true_case == "nominal":
        true_human: HumanV2Parameters = HUMAN
        true_metadata: dict[str, Any] = {
            "case": "nominal",
            "mass_scale": 1.0,
            "thigh_com_scale": 1.0,
            "shank_com_scale": 1.0,
            "stiffness_scale": 1.0,
            "rest_offset_deg": [0.0, 0.0],
            "sleeve_center_scale": 1.0,
        }
    elif true_case == "moderate":
        true_human, true_metadata = registered_moderate_human()
    else:
        raise ValueError("true_case must be nominal or moderate")

    plant = Stage4CoupledPlant(true_human)
    initial_reference = reference_fn(0.0)
    observation = plant.reset(initial_reference.q_rad)
    estimator = WindowedHumanNLS()
    mpc = HumanSpaceMPC()
    fixed_model = HUMAN
    high_level_steps = int(round(mpc.config.prediction_dt_s / CONTROL_DT_S))
    identifier_steps = int(round(estimator.config.sample_dt_s / CONTROL_DT_S))
    if high_level_steps * CONTROL_DT_S != mpc.config.prediction_dt_s:
        raise RuntimeError("MPC period must be an integer number of control periods")
    if identifier_steps * CONTROL_DT_S != estimator.config.sample_dt_s:
        raise RuntimeError("identifier period must be an integer number of control periods")

    current_action = np.zeros(2)
    current_allocation = allocate_generalized_action(current_action, observation.human_q_rad, fixed_model)
    estimator_start_state = np.concatenate([observation.human_q_rad, observation.human_dq_rad_s])
    estimator_actions: list[np.ndarray] = []
    estimator_bed_contact_samples: list[bool] = []
    mpc_diagnostics: list[dict[str, Any]] = []
    identifier_diagnostics: list[dict[str, Any]] = []
    observations = [observation]
    references = [initial_reference.q_rad.copy()]
    desired_actions = [current_action.copy()]
    allocated_wrenches = [np.asarray(current_allocation["wrench_world"]).copy()]
    parameter_estimates = [nominal_parameter_vector(ESTIMATED_PARAMETER_NAMES)]
    measured_human_inputs = [
        reconstructed_wrench_human_input_nm(
            observation.human_q_rad,
            observation.cuff_force_vector_n,
            observation.cuff_moment_vector_nm,
        )
    ]
    accepted_update_counts = [0]
    rejected_update_counts = [0]
    estimator_status_codes = [0]
    local_forces = [observation.attachment_rotation_matrix.T @ observation.cuff_force_vector_n]
    local_moments = [observation.attachment_rotation_matrix.T @ observation.cuff_moment_vector_nm]
    torque_fractions = [0.0]
    unintended_contacts: set[tuple[str, str]] = set(observation.unintended_contact_pairs)
    rom_event_count = 0
    force_gate_event_count = 0
    torque_saturation_count = 0
    termination = "completed"
    requested_steps = int(round(duration_s / CONTROL_DT_S))
    estimator_status_code = 0

    for control_index in range(requested_steps):
        current = plant.observe()
        controller_model = estimator.human_model if controller_kind == "adaptive" else fixed_model
        if control_index % high_level_steps == 0:
            state = np.concatenate([current.human_q_rad, current.human_dq_rad_s])
            current_action, solve_diag = mpc.solve(
                state,
                float(plant.data.time),
                reference_fn,
                controller_model,
            )
            mpc_diagnostics.append(solve_diag)
        current_allocation = allocate_generalized_action(
            current_action,
            current.human_q_rad,
            controller_model,
        )
        if float(current_allocation["force_norm_n"]) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            termination = "allocated_cuff_force_gate"
            force_gate_event_count += 1
            break
        reference = reference_fn(float(plant.data.time))
        target_linear_velocity, target_angular_velocity = human_cuff_velocity(
            reference.q_rad, reference.dq_rad_s
        )
        try:
            plant.apply_nominal_cartesian_control(
                reference.world_from_cuff.translation,
                target_linear_velocity,
                reference.world_from_cuff.rotation,
                target_angular_velocity,
                np.asarray(current_allocation["wrench_world"]),
            )
        except CuffForceCommandLimitError:
            termination = "total_commanded_cuff_force_gate"
            force_gate_event_count += 1
            break
        unclipped_fraction = float(np.max(np.abs(plant.last_unclipped_joint_torque) / plant.torque_limits_nm))
        torque_saturation_count += int(unclipped_fraction >= 1.0 - 1e-9)
        control_measured_inputs: list[np.ndarray] = []
        for _ in range(CONTROL_SUBSTEPS):
            observation = plant.step()
            measured_input = reconstructed_wrench_human_input_nm(
                observation.human_q_rad,
                observation.cuff_force_vector_n,
                observation.cuff_moment_vector_nm,
            )
            control_measured_inputs.append(measured_input)
            estimator_bed_contact_samples.append(
                observation.bed_force_n > BED_CONTACT_CONTAMINATION_FORCE_N
            )
            observations.append(observation)
            references.append(reference_fn(observation.time_s).q_rad.copy())
            desired_actions.append(current_action.copy())
            allocated_wrenches.append(np.asarray(current_allocation["wrench_world"]).copy())
            parameter_estimates.append(
                np.array(list(estimator.parameter_estimate().values()))
                if controller_kind == "adaptive"
                else nominal_parameter_vector(ESTIMATED_PARAMETER_NAMES)
            )
            measured_human_inputs.append(measured_input.copy())
            accepted_update_counts.append(estimator.accepted_updates)
            rejected_update_counts.append(estimator.rejected_updates)
            estimator_status_codes.append(estimator_status_code)
            local_forces.append(observation.attachment_rotation_matrix.T @ observation.cuff_force_vector_n)
            local_moments.append(observation.attachment_rotation_matrix.T @ observation.cuff_moment_vector_nm)
            torque_fractions.append(unclipped_fraction)
            unintended_contacts.update(observation.unintended_contact_pairs)
            q = observation.human_q_rad
            rom_event_count += int(
                np.any(q < np.asarray(true_human.q_min_rad) - 1e-9)
                or np.any(q > np.asarray(true_human.q_max_rad) + 1e-9)
            )
            if np.linalg.norm(observation.cuff_force_vector_n) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
                force_gate_event_count += 1
                termination = "physical_cuff_force_gate"
                break
            if not _finite_observation(observation):
                termination = "nonfinite_state_or_wrench"
                break
            if plant.warning_counts():
                termination = "mujoco_solver_warning"
                break
        if termination != "completed":
            break
        estimator_actions.append(np.mean(control_measured_inputs, axis=0))
        if (control_index + 1) % identifier_steps == 0:
            next_state = np.concatenate([observation.human_q_rad, observation.human_dq_rad_s])
            if controller_kind == "adaptive":
                diag = estimator.add_transition(
                    estimator_start_state,
                    np.asarray(estimator_actions),
                    next_state,
                    bed_contact_fraction=float(np.mean(estimator_bed_contact_samples)),
                )
                estimator_status_code = 1 if diag.get("accepted", False) else -1
                if diag["attempted"]:
                    identifier_diagnostics.append(diag)
            estimator_start_state = next_state.copy()
            estimator_actions.clear()
            estimator_bed_contact_samples.clear()

    time = np.array([item.time_s for item in observations])
    q = np.array([item.human_q_rad for item in observations])
    dq = np.array([item.human_dq_rad_s for item in observations])
    q_ref = np.array(references)
    force_local = np.array(local_forces)
    moment_local = np.array(local_moments)
    force_norm = np.linalg.norm(force_local, axis=1)
    force_rate = np.zeros_like(force_local)
    if len(force_local) > 1:
        force_rate[1:] = np.diff(force_local, axis=0) / 0.001
    force_rate_norm = np.linalg.norm(force_rate, axis=1)
    tracking_deg = np.degrees(q - q_ref)
    robot_velocity = np.array([item.robot_dq_rad_s for item in observations])
    completed = bool(termination == "completed" and time[-1] >= duration_s - 0.5 * CONTROL_DT_S)
    adaptive_estimate = estimator.parameter_estimate()
    accepted_identifier = sum(bool(item["accepted"]) for item in identifier_diagnostics)
    solver_failures = mpc.failure_count
    summary = {
        "evidence_category": "stage4_engineering_controller_establishment",
        "controller": f"{controller_kind}_human_space_constrained_mpc",
        "true_human_case": true_case,
        "true_human_parameters": true_metadata,
        "trajectory": trajectory_label,
        "requested_duration_s": duration_s,
        "completed_duration_s": float(time[-1]),
        "termination_reason": termination,
        "completed": completed,
        "tracking": {
            "rmse_deg": np.sqrt(np.mean(tracking_deg**2, axis=0)).tolist(),
            "combined_rmse_deg": float(np.sqrt(np.mean(tracking_deg**2))),
            "max_abs_error_deg": np.max(np.abs(tracking_deg), axis=0).tolist(),
            "rom_event_samples": rom_event_count,
        },
        "interaction_metrics_engineering_not_clinical": {
            "peak_total_translational_force_n": float(np.max(force_norm)),
            "rms_total_translational_force_n": float(np.sqrt(np.mean(force_norm**2))),
            "peak_abs_axial_force_n": float(np.max(np.abs(force_local[:, 0]))),
            "rms_off_axis_shear_force_n": float(np.sqrt(np.mean(np.sum(force_local[:, 1:] ** 2, axis=1)))),
            "peak_off_axis_shear_force_n": float(np.max(np.linalg.norm(force_local[:, 1:], axis=1))),
            "peak_abs_target_sagittal_moment_nm": float(np.max(np.abs(moment_local[:, 1]))),
            "peak_off_axis_moment_nm": float(np.max(np.linalg.norm(moment_local[:, [0, 2]], axis=1))),
            "rms_force_rate_n_s": float(np.sqrt(np.mean(force_rate_norm[1:] ** 2))) if len(force_rate_norm) > 1 else 0.0,
            "peak_force_rate_n_s": float(np.max(force_rate_norm)),
        },
        "robot": {
            "peak_unclipped_torque_limit_fraction": float(np.max(torque_fractions)),
            "torque_saturation_control_samples": torque_saturation_count,
            "peak_abs_joint_velocity_deg_s": np.degrees(np.max(np.abs(robot_velocity), axis=0)).tolist(),
        },
        "events": {
            "force_gate_events": force_gate_event_count,
            "rom_event_samples": rom_event_count,
            "unintended_contact_pairs": [list(item) for item in sorted(unintended_contacts)],
            "mujoco_warning_counts": plant.warning_counts(),
            "mpc_solver_failures": solver_failures,
        },
        "identifier": {
            "ground_truth_used_by_estimator": False,
            "input_action": "reconstructed_actual_cuff_wrench_via_nominal_virtual_work",
            "true_human_jacobian_used_by_estimator": False,
            "bed_contact_used_only_as_update_rejection_gate": True,
            "bed_contact_contamination_force_n": BED_CONTACT_CONTAMINATION_FORCE_N,
            "estimated_parameter_names": list(ESTIMATED_PARAMETER_NAMES),
            "final_estimate": adaptive_estimate if controller_kind == "adaptive" else dict(zip(ESTIMATED_PARAMETER_NAMES, nominal_parameter_vector(ESTIMATED_PARAMETER_NAMES), strict=True)),
            "accepted_updates": accepted_identifier,
            "rejected_updates": estimator.rejected_updates if controller_kind == "adaptive" else 0,
            "last_valid_fallback_count": estimator.rejected_updates if controller_kind == "adaptive" else 0,
        },
        "ground_truth_metrics_feed_controller_or_estimator": False,
        "force_gate_n": CUFF_TRANSLATIONAL_FORCE_GATE_N,
        "moment_limit_nm": None,
    }
    trace = {
        "time_s": time,
        "human_q_deg": np.degrees(q),
        "human_q_ref_deg": np.degrees(q_ref),
        "human_dq_deg_s": np.degrees(dq),
        "robot_q_rad": np.array([item.robot_q_rad for item in observations]),
        "robot_dq_rad_s": robot_velocity,
        "robot_torque_nm": np.array([item.joint_torque_command_nm for item in observations]),
        "robot_torque_limit_fraction": np.asarray(torque_fractions),
        "cuff_force_local_n": force_local,
        "cuff_moment_local_nm": moment_local,
        "cuff_force_rate_local_n_s": force_rate,
        "desired_human_action_nm": np.array(desired_actions),
        "measured_human_input_nm": np.array(measured_human_inputs),
        "allocated_wrench_world": np.array(allocated_wrenches),
        "parameter_estimate": np.array(parameter_estimates),
        "estimator_accepted_update_count": np.asarray(accepted_update_counts),
        "estimator_rejected_update_count": np.asarray(rejected_update_counts),
        "estimator_status_code": np.asarray(estimator_status_codes),
        "bed_contact_count": np.array([item.bed_contact_count for item in observations]),
        "bed_force_n": np.array([item.bed_force_n for item in observations]),
    }
    return summary, trace


def run_minimum_comparison(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    identifiability = run_offline_identifiability_audit()
    cases: dict[str, Any] = {}
    for true_case in ("nominal", "moderate"):
        for controller_kind in ("fixed", "adaptive"):
            name = f"{true_case}_{controller_kind}"
            summary, trace = run_stage4_case(controller_kind=controller_kind, true_case=true_case)
            cases[name] = summary
            (output_dir / f"{name}.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            np.savez_compressed(output_dir / f"{name}_trace.npz", **trace)
    combined = {"identifiability": identifiability, "cases": cases}
    (output_dir / "comparison_summary.json").write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return combined
