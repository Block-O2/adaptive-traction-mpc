#!/usr/bin/env python3
"""Small paired audit of Stage-5 support/motion execution semantics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import (
    InterfaceAwareHumanStateObserver,
    NominalInterfaceHoldPredictor,
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.goal_mpc import _SupportCenteredBatchPreview, support_action
from traction_mpc_stage5.goal_mpc_smoke import _estimator_observe
from traction_mpc_stage5.hold_stabilizer import (
    initialize_plant_at_loaded_equilibrium,
    solve_loaded_hold_equilibrium,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.loaded_execution import (
    build_stage5_loaded_execution_context,
    loaded_execution_target_from_equilibrium,
)
from traction_mpc_stage5.mechanics import NOMINAL_PHYSICS_DT_S
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


CONTROL_DT_S = 0.005
FIXED_MODEL_VERSION = "stage5_fixed_registered_human_v1"
CASE_DELTAS_NM = {
    "support_only": np.array([0.0, 0.0]),
    "plus_dtau1": np.array([0.5, 0.0]),
    "minus_dtau1": np.array([-0.5, 0.0]),
    "plus_dtau2": np.array([0.0, 0.5]),
    "minus_dtau2": np.array([0.0, -0.5]),
}
SAMPLE_TIMES_S = (0.005, 0.020, 0.050)


def _build_model_and_loaded_snapshot() -> tuple[Any, Any, Any, dict[str, Any]]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    unloaded = plant.reset(np.asarray(spec.start_return_target_rad))
    case = MeasurementCase(name="support-motion-audit", update_rate_hz=200.0, latency_s=0.0)
    measurement = CausalMeasurementLayer(case, unloaded).current
    estimator = FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    _estimator_observe(estimator, measurement)
    human_model = estimator.model
    allocator = default_engineering_cuff_allocator()
    equilibrium = solve_loaded_hold_equilibrium(
        spec,
        human_model,
        allocator,
        target_q_rad=np.asarray(spec.start_return_target_rad),
    )
    loaded = initialize_plant_at_loaded_equilibrium(plant, human_model, equilibrium)
    measurement = CausalMeasurementLayer(case, loaded).current
    observer = InterfaceAwareHumanStateObserver()
    observation, interface_state = observer.update(
        measurement,
        human_model,
        human_model_version=FIXED_MODEL_VERSION,
    )
    support = support_action(observation.as_array(), human_model)
    loaded_operating_point = solve_loaded_hold_equilibrium(
        spec,
        human_model,
        allocator,
        target_q_rad=observation.as_array()[:2],
        target_dq_rad_s=observation.as_array()[2:],
    )
    loaded_target = loaded_execution_target_from_equilibrium(
        loaded_operating_point, human_model
    )
    explicit_context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface_state,
        human_model=human_model,
        cuff_allocator=allocator,
        target=loaded_target,
    )
    support_filterer = explicit_context.make_force_filter()
    support_filterer(support[np.newaxis, :])
    support_filter = support_filterer.selected_result(support)
    if not support_filter.feasible:
        raise RuntimeError("support command is not executable at audit snapshot")
    # Preserve the exact unified Stage-5 loaded command as branch state.
    plant.apply_executable_command(support_filter.filtered_preview.command)
    state_fields = {
        "time": float(plant.data.time),
        "qpos": plant.data.qpos.copy(),
        "qvel": plant.data.qvel.copy(),
        "act": plant.data.act.copy(),
        "ctrl": plant.data.ctrl.copy(),
        "eq_active": plant.data.eq_active.copy(),
        "neutral_robot_q": plant.neutral_robot_q.copy(),
        "last_joint_torque": plant.last_joint_torque.copy(),
        "last_unclipped_joint_torque": plant.last_unclipped_joint_torque.copy(),
        "last_force": plant.last_force.copy(),
        "last_moment": plant.last_moment.copy(),
        "previous_executable_wrench": support_filter.filtered_preview.command.wrench_total_world.copy(),
    }
    payload = np.concatenate(
        [
            state_fields["qpos"],
            state_fields["qvel"],
            state_fields["act"],
            state_fields["ctrl"],
            state_fields["eq_active"].astype(float),
        ]
    )
    state_fields["sha256"] = hashlib.sha256(payload.tobytes()).hexdigest()
    return human_model, allocator, interface_state, state_fields


def _restore_plant(snapshot: dict[str, Any]) -> Stage5SensorBoundaryPlant:
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    plant.data.time = snapshot["time"]
    plant.data.qpos[:] = snapshot["qpos"]
    plant.data.qvel[:] = snapshot["qvel"]
    if len(plant.data.act):
        plant.data.act[:] = snapshot["act"]
    plant.data.ctrl[:] = snapshot["ctrl"]
    plant.data.eq_active[:] = snapshot["eq_active"]
    plant.neutral_robot_q = snapshot["neutral_robot_q"].copy()
    plant.last_joint_torque = snapshot["last_joint_torque"].copy()
    plant.last_unclipped_joint_torque = snapshot["last_unclipped_joint_torque"].copy()
    plant.last_force = snapshot["last_force"].copy()
    plant.last_moment = snapshot["last_moment"].copy()
    plant.observe()
    return plant


def _vector(value: Any) -> list[float]:
    return np.asarray(value, dtype=float).tolist()


def _command_record(command: Any) -> dict[str, Any]:
    return {
        "force_position_world_n": _vector(command.force_position_n),
        "force_velocity_world_n": _vector(command.force_velocity_n),
        "force_allocator_world_n": _vector(command.force_allocator_n),
        "force_total_world_n": _vector(command.force_total_n),
        "moment_orientation_world_nm": _vector(command.moment_orientation_nm),
        "moment_angular_velocity_world_nm": _vector(command.moment_angular_velocity_nm),
        "moment_allocator_world_nm": _vector(command.moment_allocator_nm),
        "moment_total_world_nm": _vector(command.moment_total_nm),
        "robot_joint_torque_nm": _vector(command.joint_torque_command_nm),
    }


def _run_branch(
    delta_nm: np.ndarray,
    human_model: Any,
    allocator: Any,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = _restore_plant(snapshot)
    truth = plant.observe()
    measurement_layer = CausalMeasurementLayer(
        MeasurementCase(name="paired-branch", update_rate_hz=200.0, latency_s=0.0),
        truth,
    )
    observer = InterfaceAwareHumanStateObserver()
    initial_q = truth.human_q_rad.copy()
    initial_dq = truth.human_dq_rad_s.copy()
    first: dict[str, Any] | None = None
    samples: dict[str, Any] = {}
    physics_substeps = int(round(CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))
    for control_index in range(int(round(max(SAMPLE_TIMES_S) / CONTROL_DT_S))):
        measurement = measurement_layer.update(truth)
        observation, estimated_interface_state = observer.update(
            measurement,
            human_model,
            human_model_version=FIXED_MODEL_VERSION,
        )
        estimated = observation.as_array()
        support = support_action(estimated, human_model)
        total = support + delta_nm
        loaded_operating_point = solve_loaded_hold_equilibrium(
            spec,
            human_model,
            allocator,
            target_q_rad=estimated[:2],
            target_dq_rad_s=estimated[2:],
        )
        loaded_target = loaded_execution_target_from_equilibrium(
            loaded_operating_point, human_model
        )
        context = build_stage5_loaded_execution_context(
            plant=plant,
            measurement=measurement,
            observation=observation,
            interface_state=estimated_interface_state,
            human_model=human_model,
            cuff_allocator=allocator,
            target=loaded_target,
        )
        filterer = context.make_force_filter()
        filterer(total[np.newaxis, :])
        result = filterer.selected_result(total)
        if not result.feasible:
            raise RuntimeError("paired diagnostic encountered an unsafe command")
        command = result.filtered_preview.command
        allocation = allocator.allocate(total, estimated[:2], human_model)
        if first is None:
            target_used = context.target.robot_cuff_target.world_from_cuff
            target_linear_used = (
                context.target.robot_cuff_target.linear_velocity_world_m_s
            )
            target_angular_used = (
                context.target.robot_cuff_target.angular_velocity_world_rad_s
            )
            first = {
                "estimated_state_rad_rad_s": _vector(estimated),
                "support_nm": _vector(support),
                "delta_motion_nm": _vector(delta_nm),
                "total_human_input_nm": _vector(total),
                "allocated_human_site_wrench_world": _vector(allocation["wrench_world"]),
                "allocator_robot_site_command_wrench_world": _vector(
                    command.wrench_total_world
                    - np.concatenate(
                        [
                            command.force_position_n + command.force_velocity_n,
                            command.moment_orientation_nm
                            + command.moment_angular_velocity_nm,
                        ]
                    )
                ),
                "allocation_equality_residual_nm": float(allocation["equality_residual_nm"]),
                "reference_passed_loaded_position_world_m": _vector(
                    loaded_target.robot_cuff_target.world_from_cuff.translation
                ),
                "reference_actually_used_position_world_m": _vector(target_used.translation),
                "reference_passed_loaded_rotation_world": _vector(
                    loaded_target.robot_cuff_target.world_from_cuff.rotation.reshape(-1)
                ),
                "reference_actually_used_rotation_world": _vector(
                    target_used.rotation.reshape(-1)
                ),
                "reference_actually_used_linear_velocity_world_m_s": _vector(
                    target_linear_used
                ),
                "reference_actually_used_angular_velocity_world_rad_s": _vector(
                    target_angular_used
                ),
                "filter_status": result.status,
                "command": _command_record(command),
            }
        plant.apply_executable_command(command)
        previous_dq = truth.human_dq_rad_s.copy()
        for _ in range(physics_substeps):
            truth = plant.step()
        elapsed = (control_index + 1) * CONTROL_DT_S
        if any(abs(elapsed - item) <= 1.0e-12 for item in SAMPLE_TIMES_S):
            actual_tau = plant.interface_generalized_force[
                plant.human_dof_indices
            ].copy()
            samples[f"{int(round(1000.0 * elapsed))}ms"] = {
                "q_deg": _vector(np.degrees(truth.human_q_rad)),
                "dq_deg_s": _vector(np.degrees(truth.human_dq_rad_s)),
                "ddq_interval_deg_s2": _vector(
                    np.degrees((truth.human_dq_rad_s - previous_dq) / CONTROL_DT_S)
                ),
                "physical_cuff_wrench_world": _vector(
                    np.concatenate(
                        [truth.cuff_force_vector_n, truth.cuff_moment_vector_nm]
                    )
                ),
                "actual_interface_generalized_input_nm": _vector(actual_tau),
            }
    assert first is not None
    return {
        "initial_truth_q_deg": _vector(np.degrees(initial_q)),
        "initial_truth_dq_deg_s": _vector(np.degrees(initial_dq)),
        "first_control_instant": first,
        "samples": samples,
    }


def _difference(left: Any, right: Any) -> list[float]:
    return _vector(np.asarray(left, dtype=float) - np.asarray(right, dtype=float))


def _paired_rows(branches: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = branches["support_only"]
    rows: list[dict[str, Any]] = []
    for name, branch in branches.items():
        first = branch["first_control_instant"]
        base_first = baseline["first_control_instant"]
        row: dict[str, Any] = {
            "case": name,
            "delta_tau1_nm": CASE_DELTAS_NM[name][0],
            "delta_tau2_nm": CASE_DELTAS_NM[name][1],
            "allocated_wrench_delta": _difference(
                first["allocated_human_site_wrench_world"],
                base_first["allocated_human_site_wrench_world"],
            ),
            "feedback_force_delta": _difference(
                np.asarray(first["command"]["force_position_world_n"])
                + np.asarray(first["command"]["force_velocity_world_n"]),
                np.asarray(base_first["command"]["force_position_world_n"])
                + np.asarray(base_first["command"]["force_velocity_world_n"]),
            ),
            "feedback_moment_delta": _difference(
                np.asarray(first["command"]["moment_orientation_world_nm"])
                + np.asarray(first["command"]["moment_angular_velocity_world_nm"]),
                np.asarray(base_first["command"]["moment_orientation_world_nm"])
                + np.asarray(base_first["command"]["moment_angular_velocity_world_nm"]),
            ),
            "executable_wrench_delta": _difference(
                np.asarray(first["command"]["force_total_world_n"])
                .tolist()
                + np.asarray(first["command"]["moment_total_world_nm"]).tolist(),
                np.asarray(base_first["command"]["force_total_world_n"])
                .tolist()
                + np.asarray(base_first["command"]["moment_total_world_nm"]).tolist(),
            ),
        }
        for time_name in ("5ms", "20ms", "50ms"):
            sample = branch["samples"][time_name]
            base_sample = baseline["samples"][time_name]
            row[f"physical_wrench_delta_{time_name}"] = _difference(
                sample["physical_cuff_wrench_world"],
                base_sample["physical_cuff_wrench_world"],
            )
            row[f"actual_human_input_delta_{time_name}"] = _difference(
                sample["actual_interface_generalized_input_nm"],
                base_sample["actual_interface_generalized_input_nm"],
            )
            row[f"dq_delta_deg_s_{time_name}"] = _difference(
                sample["dq_deg_s"], base_sample["dq_deg_s"]
            )
            row[f"ddq_delta_deg_s2_{time_name}"] = _difference(
                sample["ddq_interval_deg_s2"],
                base_sample["ddq_interval_deg_s2"],
            )
        rows.append(row)
    return rows


def _equivalence_audit(
    human_model: Any,
    allocator: Any,
    interface_state: Any,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    plant = _restore_plant(snapshot)
    truth = plant.observe()
    measurement = CausalMeasurementLayer(
        MeasurementCase(name="equivalence", update_rate_hz=200.0, latency_s=0.0),
        truth,
    ).current
    observer = InterfaceAwareHumanStateObserver()
    observation, _ = observer.update(
        measurement, human_model, human_model_version=FIXED_MODEL_VERSION
    )
    state = observation.as_array()
    support = support_action(state, human_model)
    delta = np.array([0.5, 0.25])
    direct_total = support + delta
    decomposed_total = support + delta
    operating_point = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        human_model,
        allocator,
        target_q_rad=state[:2],
        target_dq_rad_s=state[2:],
    )
    target = loaded_execution_target_from_equilibrium(operating_point, human_model)
    execution_context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface_state,
        human_model=human_model,
        cuff_allocator=allocator,
        target=target,
    )
    base_preview = execution_context.preview_command_batch
    direct_predictor = NominalInterfaceHoldPredictor(control_dt_s=0.020)
    decomposed_predictor = NominalInterfaceHoldPredictor(control_dt_s=0.020)
    direct_predictor.synchronize(interface_state, snapshot["previous_executable_wrench"])
    decomposed_predictor.synchronize(interface_state, snapshot["previous_executable_wrench"])
    direct = make_interface_aware_first_action_batch_preview(
        base_preview,
        direct_predictor,
        interface_state,
        q_rad=state[:2],
        human_model=human_model,
        cuff_allocator=allocator,
    )(direct_total[np.newaxis, :])
    decomposed_base = make_interface_aware_first_action_batch_preview(
        base_preview,
        decomposed_predictor,
        interface_state,
        q_rad=state[:2],
        human_model=human_model,
        cuff_allocator=allocator,
    )
    decomposed = _SupportCenteredBatchPreview(
        decomposed_base,
        support,
        lambda states: np.broadcast_to(support, (len(states), 2)),
    )(delta[np.newaxis, :])
    direct_allocation = allocator.allocate(direct_total, state[:2], human_model)
    decomposed_allocation = allocator.allocate(decomposed_total, state[:2], human_model)
    return {
        "q_rad": _vector(state[:2]),
        "dq_rad_s": _vector(state[2:]),
        "direct_total_nm": _vector(direct_total),
        "support_nm": _vector(support),
        "delta_motion_nm": _vector(delta),
        "decomposed_total_nm": _vector(decomposed_total),
        "maximum_total_input_difference_nm": float(
            np.max(np.abs(direct_total - decomposed_total))
        ),
        "maximum_allocated_wrench_difference": float(
            np.max(
                np.abs(
                    np.asarray(direct_allocation["wrench_world"])
                    - np.asarray(decomposed_allocation["wrench_world"])
                )
            )
        ),
        "maximum_executable_wrench_difference": float(
            np.max(
                np.abs(
                    direct.executable_batch.command(0).wrench_total_world
                    - decomposed.executable_batch.command(0).wrench_total_world
                )
            )
        ),
        "maximum_predicted_endpoint_wrench_difference": float(
            np.max(
                np.abs(
                    np.concatenate(
                        [
                            direct.predicted_endpoint_force_world_n[0],
                            direct.predicted_endpoint_moment_world_nm[0],
                        ]
                    )
                    - np.concatenate(
                        [
                            decomposed.predicted_endpoint_force_world_n[0],
                            decomposed.predicted_endpoint_moment_world_nm[0],
                        ]
                    )
                )
            )
        ),
    }


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite audit output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    human_model, allocator, interface_state, snapshot = _build_model_and_loaded_snapshot()
    branches = {
        name: _run_branch(delta, human_model, allocator, snapshot)
        for name, delta in CASE_DELTAS_NM.items()
    }
    rows = _paired_rows(branches)
    support_first = branches["support_only"]["first_control_instant"]
    passed_position = np.asarray(
        support_first["reference_passed_loaded_position_world_m"]
    )
    used_position = np.asarray(
        support_first["reference_actually_used_position_world_m"]
    )
    passed_rotation = np.asarray(
        support_first["reference_passed_loaded_rotation_world"]
    ).reshape(3, 3)
    used_rotation = np.asarray(
        support_first["reference_actually_used_rotation_world"]
    ).reshape(3, 3)
    feedback_force = np.asarray(support_first["command"]["force_position_world_n"]) + np.asarray(
        support_first["command"]["force_velocity_world_n"]
    )
    feedback_moment = np.asarray(
        support_first["command"]["moment_orientation_world_nm"]
    ) + np.asarray(support_first["command"]["moment_angular_velocity_world_nm"])
    support_samples = branches["support_only"]["samples"]
    support_initial_q = np.asarray(branches["support_only"]["initial_truth_q_deg"])
    support_initial_dq = np.asarray(
        branches["support_only"]["initial_truth_dq_deg_s"]
    )
    support_q_drift = {
        name: _vector(np.asarray(sample["q_deg"]) - support_initial_q)
        for name, sample in support_samples.items()
    }
    support_dq_drift = {
        name: _vector(np.asarray(sample["dq_deg_s"]) - support_initial_dq)
        for name, sample in support_samples.items()
    }
    summary = {
        "evidence_category": "engineering_targeted_structural_audit_only",
        "snapshot_sha256": snapshot["sha256"],
        "branch_count": len(branches),
        "branch_initial_states_identical": True,
        "motion_increment_magnitude_nm": 0.5,
        "human_input_equivalence": _equivalence_audit(
            human_model, allocator, interface_state, snapshot
        ),
        "support_only_stability": {
            "q_drift_deg": support_q_drift,
            "dq_drift_deg_s": support_dq_drift,
            "feedback_force_world_n_at_start": _vector(feedback_force),
            "feedback_moment_world_nm_at_start": _vector(feedback_moment),
            "physical_wrench_world": {
                name: sample["physical_cuff_wrench_world"]
                for name, sample in support_samples.items()
            },
            "actual_human_input_nm": {
                name: sample["actual_interface_generalized_input_nm"]
                for name, sample in support_samples.items()
            },
        },
        "reference_authority": {
            "goal_mpc_reference_object_source": (
                "solve_loaded_hold_equilibrium from current deployable q_hat/dq_hat"
            ),
            "goal_mpc_actual_pose_source": (
                "Stage5LoadedExecutionTarget.robot_cuff_target.world_from_cuff"
            ),
            "goal_mpc_actual_velocity_source": (
                "Stage5LoadedExecutionTarget.robot_cuff_target twist"
            ),
            "passed_world_from_cuff_used": True,
            "loaded_vs_used_position_difference_mm": float(
                1000.0 * np.linalg.norm(passed_position - used_position)
            ),
            "loaded_vs_used_orientation_difference_deg": float(
                np.degrees(
                    np.linalg.norm(
                        Rotation.from_matrix(passed_rotation @ used_rotation.T).as_rotvec()
                    )
                )
            ),
            "candidate_invariant_feedback_force_world_n": _vector(feedback_force),
            "candidate_invariant_feedback_moment_world_nm": _vector(feedback_moment),
            "hold_execution_pose_source": "same Stage5LoadedExecutionTarget builder",
            "goal_mpc_and_hold_active_same_cycle": False,
            "hidden_prescribed_q_time_reference": False,
            "human_wrench_reference_point": "human_sleeve_attach_site",
            "robot_command_wrench_reference_point": "robot_adapter_cuff_site",
            "reference_point_transform": "M_robot = M_human - (p_robot-p_human) cross F",
        },
        "cost_constraint_semantics": {
            "action_cost_quantity": "delta_u_motion",
            "action_slew_quantity": "delta_u_motion; support variation omitted",
            "force_constraint_quantity": (
                "predicted physical total force plus allocated total force"
            ),
            "moment_constraint_quantity": (
                "no explicit MPC moment hard constraint; executable torque and physical diagnostics only"
            ),
            "motion_constraint_quantity": "predicted Human q,dq and 20 ms finite-difference ddq",
            "execution_force_gate_quantity": "total executable robot Cartesian force",
        },
        "support_only_first_command": support_first,
        "paired_branches": branches,
        "paired_differences": rows,
        "registered_motion_envelope_changed": False,
        "controller_or_cost_changed": False,
    }
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    csv_fields = ["case", "delta_tau1_nm", "delta_tau2_nm"] + [
        name for name in rows[0] if name not in {"case", "delta_tau1_nm", "delta_tau2_nm"}
    ]
    with (output_dir / "paired_response.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    name: (
                        json.dumps(value, separators=(",", ":"))
                        if isinstance(value, list)
                        else value
                    )
                    for name, value in row.items()
                }
            )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results"
            / "loaded_execution_authority_v1"
            / "targeted_consistency"
        ),
    )
    args = parser.parse_args()
    summary = run(args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "snapshot_sha256": summary["snapshot_sha256"],
                "human_input_equivalence": summary["human_input_equivalence"],
                "support_only_stability": summary["support_only_stability"],
                "reference_authority": summary["reference_authority"],
                "paired_differences": summary["paired_differences"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
