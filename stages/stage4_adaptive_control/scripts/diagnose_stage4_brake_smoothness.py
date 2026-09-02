#!/usr/bin/env python3
"""Strict same-snapshot 5 ms HOLD/BRAKE engineering comparison.

This diagnostic reuses the representative Phase-3 fixtures.  Each A/B branch
is restored from the same MuJoCo integration-state snapshot; only the branch
controller differs.  It is a short engineering diagnostic, not a High-ROM
trajectory rollout or scientific result.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import mujoco
import numpy as np

from scripts.validate_stage4_brake_windows import (
    FIXTURES,
    FailureFixture,
    _estimated_state,
    _initialize,
    _measurement,
    _model,
    _reconstructed_unsafe_action,
    _reference,
)
from traction_mpc_stage3.coupled import CONTROL_DT_S, CONTROL_SUBSTEPS
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.executable_command import preview_stage4_executable_command
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant
from traction_mpc_stage4.track_brake import (
    BRAKE_INFEASIBLE,
    SAFE_BRAKE,
    TrackBrakeSupervisor,
)


@dataclass(frozen=True)
class PlantSnapshot:
    integration_state: np.ndarray
    neutral_robot_q: np.ndarray
    last_joint_torque: np.ndarray
    last_unclipped_joint_torque: np.ndarray
    last_force: np.ndarray
    last_moment: np.ndarray

    @property
    def sha256(self) -> str:
        digest = hashlib.sha256()
        for value in (
            self.integration_state,
            self.neutral_robot_q,
            self.last_joint_torque,
            self.last_unclipped_joint_torque,
            self.last_force,
            self.last_moment,
        ):
            digest.update(np.ascontiguousarray(value).view(np.uint8))
        return digest.hexdigest()


def _integration_state(plant: SensorBoundaryStage4Plant) -> np.ndarray:
    specification = mujoco.mjtState.mjSTATE_INTEGRATION
    state = np.empty(mujoco.mj_stateSize(plant.model, specification))
    mujoco.mj_getState(plant.model, plant.data, state, specification)
    return state


def _snapshot(plant: SensorBoundaryStage4Plant) -> PlantSnapshot:
    return PlantSnapshot(
        integration_state=_integration_state(plant),
        neutral_robot_q=plant.neutral_robot_q.copy(),
        last_joint_torque=plant.last_joint_torque.copy(),
        last_unclipped_joint_torque=plant.last_unclipped_joint_torque.copy(),
        last_force=plant.last_force.copy(),
        last_moment=plant.last_moment.copy(),
    )


def _restore(
    reference: CuffPoseReference,
    snapshot: PlantSnapshot,
) -> SensorBoundaryStage4Plant:
    plant = _initialize(reference)
    specification = mujoco.mjtState.mjSTATE_INTEGRATION
    mujoco.mj_setState(
        plant.model,
        plant.data,
        snapshot.integration_state,
        specification,
    )
    plant.neutral_robot_q = snapshot.neutral_robot_q.copy()
    plant.last_joint_torque = snapshot.last_joint_torque.copy()
    plant.last_unclipped_joint_torque = (
        snapshot.last_unclipped_joint_torque.copy()
    )
    plant.last_force = snapshot.last_force.copy()
    plant.last_moment = snapshot.last_moment.copy()
    mujoco.mj_forward(plant.model, plant.data)
    if not np.array_equal(_integration_state(plant), snapshot.integration_state):
        raise RuntimeError("restored MuJoCo integration state differs from snapshot")
    return plant


def _empty_trace() -> dict[str, list[Any]]:
    return {
        "time_s": [],
        "q_rad": [],
        "dq_rad_s": [],
        "solver_ddq_rad_s2": [],
        "q_ref_rad": [],
        "dq_ref_rad_s": [],
        "ddq_ref_rad_s2": [],
        "force_position_n": [],
        "force_velocity_n": [],
        "force_allocator_n": [],
        "force_total_n": [],
        "measured_cuff_force_n": [],
        "action_nm": [],
        "selected_braking_rate_per_s": [],
        "feasible_candidate_count": [],
        "computation_ms": [],
    }


def _append(
    trace: dict[str, list[Any]],
    *,
    plant: SensorBoundaryStage4Plant,
    reference: CuffPoseReference,
    preview: Any,
    action_nm: np.ndarray,
    rate_per_s: float,
    feasible_candidate_count: int,
    computation_ms: float,
) -> None:
    observation = plant.observe()
    command = preview.command
    trace["time_s"].append(float(observation.time_s))
    trace["q_rad"].append(observation.human_q_rad.copy())
    trace["dq_rad_s"].append(observation.human_dq_rad_s.copy())
    trace["solver_ddq_rad_s2"].append(
        plant.data.qacc[plant.human_dof_indices].copy()
    )
    trace["q_ref_rad"].append(reference.q_rad.copy())
    trace["dq_ref_rad_s"].append(reference.dq_rad_s.copy())
    trace["ddq_ref_rad_s2"].append(reference.ddq_rad_s2.copy())
    trace["force_position_n"].append(command.force_position_n.copy())
    trace["force_velocity_n"].append(command.force_velocity_n.copy())
    trace["force_allocator_n"].append(command.force_allocator_n.copy())
    trace["force_total_n"].append(command.force_total_n.copy())
    trace["measured_cuff_force_n"].append(
        observation.cuff_force_vector_n.copy()
    )
    trace["action_nm"].append(np.asarray(action_nm, dtype=float).copy())
    trace["selected_braking_rate_per_s"].append(float(rate_per_s))
    trace["feasible_candidate_count"].append(int(feasible_candidate_count))
    trace["computation_ms"].append(float(computation_ms))


def _arrays(
    trace: dict[str, list[Any]],
    initial_reference: CuffPoseReference,
    initial_physical_ddq_rad_s2: np.ndarray,
    previous_executed_action_nm: np.ndarray,
) -> dict[str, np.ndarray]:
    result = {name: np.asarray(values) for name, values in trace.items()}
    result["ddq_rad_s2"] = np.gradient(
        result["dq_rad_s"],
        result["time_s"],
        axis=0,
        edge_order=2,
    )
    result["physical_jerk_rad_s3"] = np.gradient(
        result["ddq_rad_s2"],
        result["time_s"],
        axis=0,
        edge_order=2,
    )
    result["solver_jerk_rad_s3"] = np.vstack(
        [
            (
                result["solver_ddq_rad_s2"][0]
                - initial_physical_ddq_rad_s2
            )
            / CONTROL_DT_S,
            np.diff(result["solver_ddq_rad_s2"], axis=0) / CONTROL_DT_S,
        ]
    )
    result["reference_jerk_rad_s3"] = np.vstack(
        [
            (
                result["ddq_ref_rad_s2"][0]
                - initial_reference.ddq_rad_s2
            )
            / CONTROL_DT_S,
            np.diff(result["ddq_ref_rad_s2"], axis=0) / CONTROL_DT_S,
        ]
    )
    result["action_change_nm"] = np.vstack(
        [
            result["action_nm"][0] - previous_executed_action_nm,
            np.diff(result["action_nm"], axis=0),
        ]
    )
    rates = result["selected_braking_rate_per_s"]
    result["braking_rate_change_per_s"] = np.concatenate(
        [[np.nan], np.diff(rates)]
    )
    return result


def _run_branch(
    *,
    kind: str,
    fixture: FailureFixture,
    reference: CuffPoseReference,
    snapshot: PlantSnapshot,
    unsafe_action_nm: np.ndarray,
    previous_executed_action_nm: np.ndarray,
    duration_s: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    plant = _restore(reference, snapshot)
    initial_physical_ddq = plant.data.qacc[plant.human_dof_indices].copy()
    model = _model()
    allocator = default_engineering_cuff_allocator()
    supervisor = TrackBrakeSupervisor() if kind == "brake" else None
    hold = CuffPoseReference(
        q_rad=reference.q_rad.copy(),
        dq_rad_s=np.zeros(2),
        ddq_rad_s2=np.zeros(2),
        world_from_cuff=reference.world_from_cuff,
    )
    trace = _empty_trace()
    termination = "completed"
    rom_events = 0
    robot_limit_events = 0
    count = int(round(duration_s / CONTROL_DT_S))
    for index in range(count):
        observation = plant.observe()
        measurement = _measurement(observation)
        estimated_state = _estimated_state(model, measurement)
        if kind == "brake":
            assert supervisor is not None
            decision = supervisor.command(
                plant=plant,
                measurement=measurement,
                estimated_state=estimated_state,
                human_model=model,
                cuff_allocator=allocator,
                track_reference=reference,
                proposed_action_nm=unsafe_action_nm if index == 0 else None,
                mpc_status=SAFE_ACTION if index == 0 else None,
            )
            if decision.status == BRAKE_INFEASIBLE:
                termination = BRAKE_INFEASIBLE
                break
            assert decision.status == SAFE_BRAKE
            assert decision.reference is not None
            assert decision.action_nm is not None
            assert decision.executable_preview is not None
            selected_reference = decision.reference
            selected_action = decision.action_nm
            preview = decision.executable_preview
            selected_rate = float(decision.selected_braking_rate_per_s)
            feasible_count = decision.feasible_candidate_count
            computation_ms = decision.computation_ms
        elif kind == "abrupt_hold":
            started = perf_counter()
            selected_reference = hold
            selected_action = model.inverse_dynamics(
                estimated_state[:2], estimated_state[2:], np.zeros(2)
            )
            preview = preview_stage4_executable_command(
                plant=plant,
                measurement=measurement,
                action_nm=selected_action,
                estimated_state=estimated_state,
                human_model=model,
                cuff_allocator=allocator,
                reference=selected_reference,
            )
            computation_ms = 1000.0 * (perf_counter() - started)
            selected_rate = np.nan
            feasible_count = int(preview.command.feasible)
        else:
            raise ValueError("branch must be brake or abrupt_hold")
        if (
            not preview.command.feasible
            or float(preview.allocation["force_norm_n"])
            > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9
        ):
            termination = f"{kind}_command_force_infeasible"
            break
        plant.apply_executable_command(preview.command)
        for _ in range(CONTROL_SUBSTEPS):
            plant.step()
        _append(
            trace,
            plant=plant,
            reference=selected_reference,
            preview=preview,
            action_nm=selected_action,
            rate_per_s=selected_rate,
            feasible_candidate_count=feasible_count,
            computation_ms=computation_ms,
        )
        human_q = plant.data.qpos[plant.human_qpos_indices]
        rom_events += int(
            np.any(human_q < np.asarray(HUMAN.q_min_rad) - 1.0e-9)
            or np.any(human_q > np.asarray(HUMAN.q_max_rad) + 1.0e-9)
        )
        robot_q = plant.data.qpos[plant.robot_qpos_indices]
        robot_ranges = plant.model.jnt_range[plant.robot_joint_ids]
        robot_limit_events += int(
            np.any(robot_q < robot_ranges[:, 0] - 1.0e-9)
            or np.any(robot_q > robot_ranges[:, 1] + 1.0e-9)
        )
    arrays = _arrays(
        trace,
        reference,
        initial_physical_ddq,
        previous_executed_action_nm,
    )
    summary = _summarize(
        kind=kind,
        arrays=arrays,
        reference=reference,
        termination=termination,
        rom_events=rom_events,
        robot_limit_events=robot_limit_events,
        warnings=plant.warning_counts(),
    )
    return summary, arrays


def _rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(value, dtype=float) ** 2)))


def _step_metrics(value: np.ndarray) -> dict[str, float]:
    changes = np.diff(np.asarray(value, dtype=float), axis=0)
    norms = np.linalg.norm(changes, axis=1)
    return {
        "step_rms": _rms(changes),
        "step_norm_max": float(np.max(norms)),
    }


def _summarize(
    *,
    kind: str,
    arrays: dict[str, np.ndarray],
    reference: CuffPoseReference,
    termination: str,
    rom_events: int,
    robot_limit_events: int,
    warnings: dict[str, int],
) -> dict[str, Any]:
    force_norm = np.linalg.norm(arrays["force_total_n"], axis=1)
    speed_deg_s = np.linalg.norm(np.degrees(arrays["dq_rad_s"]), axis=1)
    near = np.flatnonzero(speed_deg_s <= 1.0)
    rates = arrays["selected_braking_rate_per_s"]
    finite_rates = rates[np.isfinite(rates)]
    rate_switch_count = (
        int(np.count_nonzero(np.abs(np.diff(finite_rates)) > 1.0e-12))
        if len(finite_rates) > 1
        else 0
    )
    latency = arrays["computation_ms"]
    return {
        "branch": kind,
        "termination": termination,
        "sample_count": int(len(arrays["time_s"])),
        "initial_reference_q_jump_deg": np.degrees(
            arrays["q_ref_rad"][0] - reference.q_rad
        ).tolist(),
        "initial_reference_dq_jump_deg_s": np.degrees(
            arrays["dq_ref_rad_s"][0] - reference.dq_rad_s
        ).tolist(),
        "physical_acceleration_rms_deg_s2": _rms(
            np.degrees(arrays["ddq_rad_s2"])
        ),
        "physical_jerk_rms_deg_s3": _rms(
            np.degrees(arrays["physical_jerk_rad_s3"])
        ),
        "solver_acceleration_rms_deg_s2": _rms(
            np.degrees(arrays["solver_ddq_rad_s2"])
        ),
        "solver_jerk_rms_deg_s3": _rms(
            np.degrees(arrays["solver_jerk_rad_s3"])
        ),
        "reference_acceleration_rms_deg_s2": _rms(
            np.degrees(arrays["ddq_ref_rad_s2"])
        ),
        "reference_jerk_rms_deg_s3": _rms(
            np.degrees(arrays["reference_jerk_rad_s3"])
        ),
        "force_total_peak_n": float(np.max(force_norm)),
        "force_total_over_200_count": int(
            np.count_nonzero(force_norm > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9)
        ),
        "initial_speed_norm_deg_s": float(
            np.linalg.norm(np.degrees(reference.dq_rad_s))
        ),
        "final_speed_norm_deg_s": float(speed_deg_s[-1]),
        "time_to_speed_norm_at_most_1deg_s": (
            float(arrays["time_s"][near[0]] - arrays["time_s"][0])
            if len(near)
            else None
        ),
        "selected_rates_per_s": np.unique(finite_rates).tolist(),
        "rate_switch_count": rate_switch_count,
        "action_change": _step_metrics(arrays["action_nm"]),
        "force_position_change": _step_metrics(arrays["force_position_n"]),
        "force_velocity_change": _step_metrics(arrays["force_velocity_n"]),
        "force_allocator_change": _step_metrics(arrays["force_allocator_n"]),
        "force_total_change": _step_metrics(arrays["force_total_n"]),
        "latency_ms": {
            "mean": float(np.mean(latency)),
            "p95": float(np.percentile(latency, 95.0)),
            "max": float(np.max(latency)),
        },
        "events": {
            "rom_samples": rom_events,
            "robot_limit_samples": robot_limit_events,
            "solver_warnings": warnings,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace-output", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=0.75)
    args = parser.parse_args()
    if args.output.exists() or args.trace_output.exists():
        raise FileExistsError("refusing to overwrite diagnostic output")
    if args.duration_s != 0.75:
        raise ValueError("strict A/B duration is fixed at 0.75 s")
    payload: dict[str, Any] = {
        "evidence_category": "strict_same_snapshot_engineering_diagnostic",
        "duration_s": args.duration_s,
        "full_high_rom_rollout_run": False,
        "fixture_limit": (
            "representative analytic failure-time states and force-matched "
            "unsafe actions; original historical full-state NPZ is unavailable"
        ),
        "runs": [],
    }
    archive: dict[str, np.ndarray] = {}
    for fixture in FIXTURES:
        reference = _reference(fixture)
        common_plant = _initialize(reference)
        measurement = _measurement(common_plant.observe())
        model = _model()
        allocator = default_engineering_cuff_allocator()
        estimated_state = _estimated_state(model, measurement)
        previous_executed_action = model.inverse_dynamics(
            estimated_state[:2],
            estimated_state[2:],
            reference.ddq_rad_s2,
        )
        previous_preview = preview_stage4_executable_command(
            plant=common_plant,
            measurement=measurement,
            action_nm=previous_executed_action,
            estimated_state=estimated_state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        )
        if not previous_preview.command.feasible:
            raise RuntimeError("representative prior TRACK command is not safe")
        common_plant.apply_executable_command(previous_preview.command)
        common_plant._apply_soft_limit()
        mujoco.mj_forward(common_plant.model, common_plant.data)
        common_snapshot = _snapshot(common_plant)
        measurement = _measurement(common_plant.observe())
        estimated_state = _estimated_state(model, measurement)
        unsafe_action, unsafe_force = _reconstructed_unsafe_action(
            fixture=fixture,
            plant=common_plant,
            measurement=measurement,
            state=estimated_state,
            model=model,
            reference=reference,
            allocator=allocator,
        )
        branch_summaries = {}
        for kind in ("abrupt_hold", "brake"):
            summary, arrays = _run_branch(
                kind=kind,
                fixture=fixture,
                reference=reference,
                snapshot=common_snapshot,
                unsafe_action_nm=unsafe_action,
                previous_executed_action_nm=previous_executed_action,
                duration_s=args.duration_s,
            )
            branch_summaries[kind] = summary
            for name, value in arrays.items():
                archive[f"{fixture.name}__{kind}__{name}"] = value
        archive[
            f"{fixture.name}__common__snapshot_integration_state"
        ] = common_snapshot.integration_state
        archive[
            f"{fixture.name}__common__previous_executed_action_nm"
        ] = previous_executed_action
        archive[
            f"{fixture.name}__common__rejected_unsafe_action_nm"
        ] = unsafe_action
        hold_summary = branch_summaries["abrupt_hold"]
        brake_summary = branch_summaries["brake"]
        acceptance = {
            "force_total_within_200_n": bool(
                brake_summary["force_total_over_200_count"] == 0
            ),
            "safe_brake_continuously_feasible": bool(
                brake_summary["termination"] == "completed"
                and brake_summary["sample_count"]
                == int(round(args.duration_s / CONTROL_DT_S))
            ),
            "speed_reaches_at_most_1deg_s": bool(
                brake_summary["time_to_speed_norm_at_most_1deg_s"]
                is not None
            ),
            "no_rom_solver_or_robot_limit_event": bool(
                brake_summary["events"]["rom_samples"] == 0
                and brake_summary["events"]["robot_limit_samples"] == 0
                and not brake_summary["events"]["solver_warnings"]
            ),
            "physical_acceleration_rms_no_worse_than_hold": bool(
                brake_summary["physical_acceleration_rms_deg_s2"]
                <= hold_summary["physical_acceleration_rms_deg_s2"]
            ),
            "physical_jerk_rms_lower_than_hold": bool(
                brake_summary["physical_jerk_rms_deg_s3"]
                < hold_summary["physical_jerk_rms_deg_s3"]
            ),
            "brake_computation_p95_below_5ms": bool(
                brake_summary["latency_ms"]["p95"] < 5.0
            ),
        }
        payload["runs"].append(
            {
                "fixture": fixture.name,
                "snapshot_sha256": common_snapshot.sha256,
                "both_branches_restored_exact_integration_snapshot": True,
                "previous_executed_track_force_n": (
                    previous_preview.command.translational_force_norm_n
                ),
                "reconstructed_unsafe_track_force_n": unsafe_force,
                "acceptance": acceptance,
                **branch_summaries,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(args.trace_output, **archive)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
