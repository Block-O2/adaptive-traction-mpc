#!/usr/bin/env python3
"""Run one unchanged CR12 smoke with offline 0.25 ms dynamics telemetry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import mujoco

from traction_mpc_stage4.human_model import dynamic_terms
from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN


EVENT_START_S = 0.300
EVENT_END_S = 0.320


class PhysicsTelemetryMixin:
    """Record pre-integration truth without affecting plant or control."""

    def __init__(self, human: Any, *, interface_parameters: Any) -> None:
        self.physics_records: list[dict[str, Any]] = []
        super().__init__(human, interface_parameters=interface_parameters)

    def step(self):
        # Refresh is the same operation the parent step/observe path performs.
        # Record after current command and interface force are installed, before
        # MuJoCo integrates this 0.25 ms interval.
        self._refresh()
        q = self.data.qpos[self.human_qpos_indices].copy()
        dq = self.data.qvel[self.human_dof_indices].copy()
        qacc = self.data.qacc[self.human_dof_indices].copy()
        mass, coriolis, gravity, passive = dynamic_terms(q, dq, self.human)
        cuff_tau = self.interface_generalized_force[self.human_dof_indices].copy()
        full_mass = np.empty((self.model.nv, self.model.nv), dtype=float)
        mujoco.mj_fullM(self.model, self.data, full_mass)
        mujoco_human_mass = full_mass[np.ix_(self.human_dof_indices, self.human_dof_indices)]
        soft_limit = soft_limit_torque(q, dq, self.human)
        interface = self._evaluate_current_interface()
        self.physics_records.append(
            {
                "time_s": float(self.data.time),
                "q_rad": q,
                "dq_rad_s": dq,
                "mujoco_qacc_rad_s2": qacc,
                "cuff_generalized_input_nm": cuff_tau,
                "mass_matrix": mass,
                "mujoco_human_mass_matrix": mujoco_human_mass,
                "coriolis_nm": coriolis,
                "gravity_nm": gravity,
                "passive_nm": passive,
                "mujoco_qfrc_bias_nm": self.data.qfrc_bias[
                    self.human_dof_indices
                ].copy(),
                "mujoco_qfrc_passive_nm": self.data.qfrc_passive[
                    self.human_dof_indices
                ].copy(),
                "mujoco_qfrc_applied_nm": self.data.qfrc_applied[
                    self.human_dof_indices
                ].copy(),
                "mujoco_qfrc_constraint_nm": self.data.qfrc_constraint[
                    self.human_dof_indices
                ].copy(),
                "soft_limit_generalized_input_nm": soft_limit,
                "physical_cuff_wrench_world": interface.human_wrench_world.copy(),
                "robot_joint_torque_command_nm": self.last_joint_torque.copy(),
            }
        )
        return super().step()


class PhysicsTelemetryCR12Plant(
    PhysicsTelemetryMixin, Stage5CR12SensorBoundaryPlant
):
    pass


class PhysicsTelemetryUR10ePlant(PhysicsTelemetryMixin, Stage5SensorBoundaryPlant):
    pass


def _stack(records: list[dict[str, Any]], name: str) -> np.ndarray:
    return np.asarray([record[name] for record in records], dtype=float)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/cr12_event_diagnosis_attempt_01/cr12_physics_resolution_v3"
        ),
    )
    parser.add_argument("--robot", choices=("cr12", "ur10e"), default="cr12")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    holder: dict[str, Any] = {}

    def plant_factory(parameters):
        plant_class = (
            PhysicsTelemetryCR12Plant
            if args.robot == "cr12"
            else PhysicsTelemetryUR10ePlant
        )
        plant = plant_class(STAGE5_HUMAN, interface_parameters=parameters)
        holder["plant"] = plant
        return plant

    rollout = run_goal_mpc_smoke(
        output / "rollout",
        maximum_duration_s=0.35,
        plant_factory=plant_factory,
        plant_case_name=f"cr12_event_diagnosis__{args.robot}_physics_resolution",
    )
    plant = holder["plant"]
    records = [
        record
        for record in plant.physics_records
        if EVENT_START_S - 1.0e-12 <= record["time_s"] < EVENT_END_S - 1.0e-12
    ]
    expected_count = int(round((EVENT_END_S - EVENT_START_S) / plant.model.opt.timestep))
    if len(records) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} physics records, found {len(records)}"
        )

    time_s = _stack(records, "time_s")
    q = _stack(records, "q_rad")
    dq = _stack(records, "dq_rad_s")
    qacc = _stack(records, "mujoco_qacc_rad_s2")
    cuff_tau = _stack(records, "cuff_generalized_input_nm")
    mass = _stack(records, "mass_matrix")
    mujoco_mass = _stack(records, "mujoco_human_mass_matrix")
    coriolis = _stack(records, "coriolis_nm")
    gravity = _stack(records, "gravity_nm")
    passive = _stack(records, "passive_nm")
    qfrc_bias = _stack(records, "mujoco_qfrc_bias_nm")
    qfrc_passive = _stack(records, "mujoco_qfrc_passive_nm")
    qfrc_applied = _stack(records, "mujoco_qfrc_applied_nm")
    qfrc_constraint = _stack(records, "mujoco_qfrc_constraint_nm")
    soft_limit = _stack(records, "soft_limit_generalized_input_nm")
    wrench = _stack(records, "physical_cuff_wrench_world")
    robot_torque = _stack(records, "robot_joint_torque_command_nm")

    m22 = mujoco_mass[:, 1, 1]
    measured_cuff_tau = qfrc_applied - soft_limit
    contributions = {
        "cuff_generalized_input": measured_cuff_tau[:, 1] / m22,
        "gravity": -gravity[:, 1] / m22,
        "passive_stiffness_damping": qfrc_passive[:, 1] / m22,
        "coriolis_coupling": -(qfrc_bias[:, 1] - gravity[:, 1]) / m22,
        "q1_q2_inertia_coupling": -mujoco_mass[:, 1, 0] * qacc[:, 0] / m22,
        "bed_contact_constraint": qfrc_constraint[:, 1] / m22,
        "soft_limit": soft_limit[:, 1] / m22,
    }
    reconstructed_q2 = sum(contributions.values())
    dt = float(plant.model.opt.timestep)
    endpoint_records = [
        record
        for record in plant.physics_records
        if math.isclose(record["time_s"], EVENT_END_S, abs_tol=1.0e-12)
    ]
    endpoint_dq = (
        np.asarray(endpoint_records[0]["dq_rad_s"], dtype=float).copy()
        if endpoint_records
        else plant.data.qvel[plant.human_dof_indices].copy()
    )
    exact_window_acceleration = (endpoint_dq - dq[0]) / (EVENT_END_S - EVENT_START_S)
    physics_mean_qacc = np.mean(qacc, axis=0)
    contribution_means = {
        name: math.degrees(float(np.mean(values)))
        for name, values in contributions.items()
    }
    all_constraint_time = _stack(plant.physics_records, "time_s")
    all_constraint_force = _stack(
        plant.physics_records, "mujoco_qfrc_constraint_nm"
    )
    all_constraint_norm = np.linalg.norm(all_constraint_force, axis=1)
    active_constraint = all_constraint_norm > 1.0e-9
    event_constraint_norm = np.linalg.norm(qfrc_constraint, axis=1)
    result = {
        "schema": "stage5_robot_event_physics_resolution_v2",
        "robot": args.robot,
        "evidence_category": "focused_offline_engineering_diagnosis",
        "rollout_abort_reason": rollout["abort_reason"],
        "rollout_task_status": rollout["task_status"],
        "event_window_s": [EVENT_START_S, EVENT_END_S],
        "physics_dt_s": dt,
        "physics_interval_count": len(records),
        "exact_endpoint_acceleration_deg_s2": np.degrees(
            exact_window_acceleration
        ).tolist(),
        "mean_mujoco_qacc_deg_s2": np.degrees(physics_mean_qacc).tolist(),
        "q2_mean_contributions_deg_s2": contribution_means,
        "q2_mean_contribution_sum_deg_s2": float(sum(contribution_means.values())),
        "maximum_q2_instantaneous_balance_residual_deg_s2": math.degrees(
            float(np.max(np.abs(qacc[:, 1] - reconstructed_q2)))
        ),
        "maximum_analytic_vs_mujoco_mass_matrix_abs_difference": float(
            np.max(np.abs(mass - mujoco_mass))
        ),
        "maximum_analytic_vs_mujoco_coriolis_abs_difference_nm": float(
            np.max(np.abs(coriolis - (qfrc_bias - gravity)))
        ),
        "maximum_analytic_passive_vs_mujoco_passive_force_abs_difference_nm": float(
            np.max(np.abs(-passive - qfrc_passive))
        ),
        "maximum_interface_vs_applied_cuff_torque_abs_difference_nm": float(
            np.max(np.abs(cuff_tau - measured_cuff_tau))
        ),
        "human_constraint_activity": {
            "first_nonzero_time_s": (
                None
                if not np.any(active_constraint)
                else float(all_constraint_time[np.flatnonzero(active_constraint)[0]])
            ),
            "active_physics_interval_count_full_rollout": int(
                np.count_nonzero(active_constraint)
            ),
            "active_physics_interval_count_event_window": int(
                np.count_nonzero(event_constraint_norm > 1.0e-9)
            ),
            "maximum_generalized_constraint_norm_nm_event_window": float(
                np.max(event_constraint_norm)
            ),
        },
        "cuff_force_norm_n": {
            "minimum": float(np.min(np.linalg.norm(wrench[:, :3], axis=1))),
            "maximum": float(np.max(np.linalg.norm(wrench[:, :3], axis=1))),
        },
        "cuff_moment_norm_nm": {
            "minimum": float(np.min(np.linalg.norm(wrench[:, 3:], axis=1))),
            "maximum": float(np.max(np.linalg.norm(wrench[:, 3:], axis=1))),
        },
        "robot_joint_torque_command_peak_abs_nm": np.max(
            np.abs(robot_torque), axis=0
        ).tolist(),
        "truth_used_online": False,
        "controller_or_authority_changed": False,
        "threshold_changed": False,
        "scientific_parameter_changed": False,
    }
    np.savez_compressed(
        output / "physics_trace.npz",
        time_s=time_s,
        q_rad=q,
        dq_rad_s=dq,
        mujoco_qacc_rad_s2=qacc,
        cuff_generalized_input_nm=cuff_tau,
        mass_matrix=mass,
        mujoco_human_mass_matrix=mujoco_mass,
        coriolis_nm=coriolis,
        gravity_nm=gravity,
        passive_nm=passive,
        mujoco_qfrc_bias_nm=qfrc_bias,
        mujoco_qfrc_passive_nm=qfrc_passive,
        mujoco_qfrc_applied_nm=qfrc_applied,
        mujoco_qfrc_constraint_nm=qfrc_constraint,
        soft_limit_generalized_input_nm=soft_limit,
        physical_cuff_wrench_world=wrench,
        robot_joint_torque_command_nm=robot_torque,
        endpoint_dq_rad_s=endpoint_dq,
    )
    (output / "physics_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
