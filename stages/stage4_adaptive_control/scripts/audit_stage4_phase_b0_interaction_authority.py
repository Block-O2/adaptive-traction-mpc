#!/usr/bin/env python3
"""Audit local pre-spike interaction authority without designing a controller."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from audit_stage4_phase_a_high_rom_interaction import (
    FORCE_GATE_N,
    LYING_BED_SCENARIO,
    _restore_replay_plant,
)
from run_stage4_phase5_high_rom_system_pilot import HIGH_ROM_HUMAN
from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage4.cuff_allocator import (
    sagittal_allocation_matrix,
    sagittal_null_vector,
    sagittal_wrench_to_world_matrix,
)
from traction_mpc_stage4.dynamics_failure_audit import geometry_from_trace_vector
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel
from traction_mpc_stage4.report_validation import write_strict_json


STAGE_ROOT = Path(__file__).resolve().parents[1]
PHASE_A_DIR = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase_a_high_rom_interaction_audit_20260902"
)
DEFAULT_SNAPSHOT = PHASE_A_DIR / "pre_spike_replay_snapshot.npz"
DEFAULT_MANIFEST = PHASE_A_DIR / "pre_spike_replay_snapshot.json"
DEFAULT_EVENT_WINDOW = PHASE_A_DIR / "instrumented_event_window.json"
DEFAULT_LYING_TRACE = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase5_high_rom_system_pilot_20260902"
    / "knee_high_folding_90_120"
    / "trace.npz"
)
DEFAULT_OUTPUT = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase_b0_interaction_authority_audit_20260902"
)
TIMESTEP_S = 0.001
WINDOW_S = 0.005
CENTER_FORCE_N = 199.0


def _array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float)


def _norm(value: Any) -> float:
    return float(np.linalg.norm(_array(value)))


def _command_with_delta(
    original: dict[str, Any],
    torque_limits_nm: np.ndarray,
    *,
    force_delta_n: np.ndarray | None = None,
    moment_delta_nm: np.ndarray | None = None,
) -> dict[str, Any]:
    force_delta = np.zeros(3) if force_delta_n is None else _array(force_delta_n)
    moment_delta = (
        np.zeros(3) if moment_delta_nm is None else _array(moment_delta_nm)
    )
    command = deepcopy(original)
    command["force_total_n"] = (_array(original["force_total_n"]) + force_delta).tolist()
    command["moment_total_nm"] = (
        _array(original["moment_total_nm"]) + moment_delta
    ).tolist()
    jacobian = _array(original["robot_attachment_jacobian"])
    wrench_delta = np.concatenate([force_delta, moment_delta])
    unclipped = _array(original["unclipped_joint_torque_nm"]) + jacobian.T @ wrench_delta
    command["unclipped_joint_torque_nm"] = unclipped.tolist()
    command["joint_torque_command_nm"] = np.clip(
        unclipped, -torque_limits_nm, torque_limits_nm
    ).tolist()
    command["translational_force_norm_n"] = _norm(command["force_total_n"])
    command["margin_to_force_gate_n"] = (
        FORCE_GATE_N - command["translational_force_norm_n"]
    )
    command["feasible"] = bool(
        command["translational_force_norm_n"] <= FORCE_GATE_N + 1.0e-9
    )
    return command


def _replay(
    integration_state: np.ndarray,
    command: dict[str, Any],
    *,
    original_target_position_m: np.ndarray,
    original_target_rotation: np.ndarray,
) -> list[dict[str, Any]]:
    if _norm(command["force_total_n"]) > FORCE_GATE_N + 1.0e-9:
        raise RuntimeError("diagnostic command exceeds independent 200 N gate")
    plant = _restore_replay_plant(
        integration_state,
        command,
        scenario=LYING_BED_SCENARIO,
        timestep_s=TIMESTEP_S,
        iterations=100,
        tolerance=1.0e-8,
    )

    def record(elapsed_ms: int) -> dict[str, Any]:
        item = plant.diagnostic_record(f"authority_{elapsed_ms}ms")
        position = _array(item["cuff_position_world_m"])
        rotation = _array(item["cuff_rotation_world"])
        item["elapsed_ms"] = elapsed_ms
        item["original_task_position_error_m"] = (
            original_target_position_m - position
        ).tolist()
        item["original_task_position_error_norm_m"] = _norm(
            original_target_position_m - position
        )
        item["original_task_rotation_error_rad"] = Rotation.from_matrix(
            original_target_rotation @ rotation.T
        ).as_rotvec().tolist()
        item["original_task_rotation_error_norm_rad"] = _norm(
            item["original_task_rotation_error_rad"]
        )
        return item

    records = [record(0)]
    for step in range(1, int(round(WINDOW_S / TIMESTEP_S)) + 1):
        plant.step()
        records.append(record(step))
    return records


def _response(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "physical_force_world_n": record["physical_cuff_force_world_n"],
        "physical_force_norm_n": record["physical_cuff_force_norm_n"],
        "physical_moment_world_nm": record["physical_cuff_moment_world_nm"],
        "physical_moment_norm_nm": record["physical_cuff_moment_norm_nm"],
        "human_generalized_torque_nm": record["human_constraint_torque_nm"],
        "cuff_position_world_m": record["cuff_position_world_m"],
        "cuff_pose_error_position_m": record["original_task_position_error_m"],
        "cuff_pose_error_position_norm_m": record[
            "original_task_position_error_norm_m"
        ],
        "cuff_pose_error_rotation_rad": record[
            "original_task_rotation_error_rad"
        ],
        "cuff_pose_error_rotation_norm_rad": record[
            "original_task_rotation_error_norm_rad"
        ],
        "human_acceleration_rad_s2": record["human_qdd_rad_s2"],
        "human_acceleration_norm_rad_s2": _norm(record["human_qdd_rad_s2"]),
        "robot_acceleration_rad_s2": record["robot_qdd_rad_s2"],
        "robot_acceleration_norm_rad_s2": _norm(record["robot_qdd_rad_s2"]),
        "executable_command_force_world_n": record["command_force_world_n"],
        "executable_command_force_norm_n": record["command_force_norm_n"],
        "executable_command_moment_world_nm": record["command_moment_world_nm"],
        "executable_command_moment_norm_nm": record["command_moment_norm_nm"],
    }


def _central_sensitivity(
    plus: dict[str, Any], minus: dict[str, Any], denominator: float
) -> dict[str, Any]:
    vector_keys = (
        "physical_force_world_n",
        "physical_moment_world_nm",
        "human_generalized_torque_nm",
        "cuff_pose_error_position_m",
        "cuff_pose_error_rotation_rad",
        "human_acceleration_rad_s2",
        "robot_acceleration_rad_s2",
        "executable_command_force_world_n",
    )
    scalar_keys = (
        "physical_force_norm_n",
        "physical_moment_norm_nm",
        "cuff_pose_error_position_norm_m",
        "cuff_pose_error_rotation_norm_rad",
        "human_acceleration_norm_rad_s2",
        "robot_acceleration_norm_rad_s2",
        "executable_command_force_norm_n",
    )
    result: dict[str, Any] = {}
    for key in vector_keys:
        result[key] = ((_array(plus[key]) - _array(minus[key])) / denominator).tolist()
    for key in scalar_keys:
        result[key] = (float(plus[key]) - float(minus[key])) / denominator
    return result


def _signed_reduction_tradeoff(
    center: dict[str, Any], plus: dict[str, Any], minus: dict[str, Any]
) -> dict[str, Any]:
    candidates = {"plus": plus, "minus": minus}
    selected_sign, selected = min(
        candidates.items(), key=lambda item: item[1]["physical_force_norm_n"]
    )
    force_reduction = (
        float(center["physical_force_norm_n"])
        - float(selected["physical_force_norm_n"])
    )
    displacement = _norm(
        _array(selected["cuff_position_world_m"])
        - _array(center["cuff_position_world_m"])
    )
    human_acceleration_change = _norm(
        _array(selected["human_acceleration_rad_s2"])
        - _array(center["human_acceleration_rad_s2"])
    )
    robot_acceleration_change = _norm(
        _array(selected["robot_acceleration_rad_s2"])
        - _array(center["robot_acceleration_rad_s2"])
    )
    return {
        "lower_force_sign": selected_sign,
        "physical_force_reduction_n": force_reduction,
        "physical_moment_change_nm": (
            float(selected["physical_moment_norm_nm"])
            - float(center["physical_moment_norm_nm"])
        ),
        "cuff_displacement_from_center_m": displacement,
        "human_acceleration_change_norm_rad_s2": human_acceleration_change,
        "robot_acceleration_change_norm_rad_s2": robot_acceleration_change,
        "force_reduction_per_cuff_displacement_n_per_m": (
            force_reduction / max(displacement, 1.0e-15)
        ),
    }


def _channel_definitions(
    original: dict[str, Any],
    center_delta_force_n: np.ndarray,
    measured_force_direction: np.ndarray,
    world_null_wrench: np.ndarray,
) -> list[dict[str, Any]]:
    allocator_force = _array(original["force_allocator_n"])
    allocator_unit = allocator_force / np.linalg.norm(allocator_force)
    direction_axis = measured_force_direction - allocator_unit * float(
        measured_force_direction @ allocator_unit
    )
    direction_axis /= np.linalg.norm(direction_axis)
    feedback_force = _array(original["force_position_n"]) + _array(
        original["force_velocity_n"]
    )
    physical_moment = _array(original["moment_total_nm"])
    moment_axis = physical_moment / np.linalg.norm(physical_moment)
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    return [
        {
            "id": "A1_allocator_force_magnitude",
            "channel": "A allocator translational force magnitude",
            "unit": "N",
            "epsilon": 0.25,
            "force_per_unit": allocator_unit,
            "moment_per_unit": np.zeros(3),
            "equivalent_command_force_perturbation_n": 0.25,
        },
        {
            "id": "A2_allocator_force_direction",
            "channel": "A allocator translational force direction",
            "unit": "N orthogonal force",
            "epsilon": 0.25,
            "force_per_unit": direction_axis,
            "moment_per_unit": np.zeros(3),
            "equivalent_command_force_perturbation_n": 0.25,
        },
        {
            "id": "B_cuff_null_space_lambda",
            "channel": "B cuff null-space lambda",
            "unit": "lambda (force-normalized N)",
            "epsilon": 0.25,
            "force_per_unit": world_null_wrench[:3],
            "moment_per_unit": world_null_wrench[3:],
            "equivalent_command_force_perturbation_n": 0.25,
        },
        {
            "id": "C_commanded_cuff_moment",
            "channel": "C commanded cuff moment",
            "unit": "Nm",
            "epsilon": 0.10,
            "force_per_unit": np.zeros(3),
            "moment_per_unit": moment_axis,
            "equivalent_command_force_perturbation_n": 0.0,
        },
        {
            "id": "D_cartesian_velocity_reference_compliance",
            "channel": "D Cartesian velocity/reference compliance",
            "unit": "m/s target velocity",
            "epsilon": 0.001,
            "force_per_unit": gains.velocity_ns_per_m * measured_force_direction,
            "moment_per_unit": np.zeros(3),
            "equivalent_command_force_perturbation_n": (
                gains.velocity_ns_per_m * 0.001
            ),
        },
        {
            "id": "E_cartesian_pose_reference_compliance",
            "channel": "E Cartesian pose-reference compliance",
            "unit": "m target position",
            "epsilon": 0.00005,
            "force_per_unit": gains.position_n_per_m * measured_force_direction,
            "moment_per_unit": np.zeros(3),
            "equivalent_command_force_perturbation_n": (
                gains.position_n_per_m * 0.00005
            ),
        },
        {
            "id": "F_existing_cartesian_pd_feedback",
            "channel": "F existing Cartesian P/D feedback contribution",
            "unit": "fractional P+D scale",
            "epsilon": 0.001,
            "force_per_unit": feedback_force,
            "moment_per_unit": np.zeros(3),
            "equivalent_command_force_perturbation_n": (
                np.linalg.norm(feedback_force) * 0.001
            ),
        },
    ]


def _dynamic_null_space_audit(
    event_window_path: Path,
    lying_trace_path: Path,
    allocation_matrix: np.ndarray,
    null_vector: np.ndarray,
) -> dict[str, Any]:
    event = json.loads(event_window_path.read_text())
    commands = event["commands"]
    with np.load(lying_trace_path, allow_pickle=False) as trace:
        filter_time = _array(trace["safety_filter_time_s"])
        lambdas = _array(trace["safety_filter_lambda"])
        statuses = np.asarray(trace["safety_filter_status"])
    rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for command in commands:
        time_s = float(command["time_s"])
        filter_index = int(np.argmin(np.abs(filter_time - time_s)))
        force = _array(command["force_total_n"])
        moment = _array(command["moment_total_nm"])
        allocator = np.concatenate(
            [
                _array(command["force_allocator_n"]),
                _array(command["moment_allocator_nm"]),
            ]
        )
        row: dict[str, Any] = {
            "time_s": time_s,
            "filter_status": str(statuses[filter_index]),
            "lambda": float(lambdas[filter_index]),
            "allocator_force_world_n": allocator[:3].tolist(),
            "allocator_moment_world_nm": allocator[3:].tolist(),
            "total_command_force_world_n": force.tolist(),
            "total_command_moment_world_nm": moment.tolist(),
        }
        if previous is None:
            row.update(
                {
                    "delta_lambda": None,
                    "allocator_force_slew_n_per_s": None,
                    "allocator_moment_slew_nm_per_s": None,
                    "total_command_force_slew_n_per_s": None,
                    "total_command_moment_slew_nm_per_s": None,
                    "total_command_vector_slew_mixed_units_per_s": None,
                }
            )
        else:
            dt = time_s - float(previous["time_s"])
            previous_allocator = _array(previous["allocator"])
            previous_force = _array(previous["force"])
            previous_moment = _array(previous["moment"])
            row.update(
                {
                    "delta_lambda": float(lambdas[filter_index] - previous["lambda"]),
                    "allocator_force_slew_n_per_s": _norm(
                        allocator[:3] - previous_allocator[:3]
                    )
                    / dt,
                    "allocator_moment_slew_nm_per_s": _norm(
                        allocator[3:] - previous_allocator[3:]
                    )
                    / dt,
                    "total_command_force_slew_n_per_s": _norm(
                        force - previous_force
                    )
                    / dt,
                    "total_command_moment_slew_nm_per_s": _norm(
                        moment - previous_moment
                    )
                    / dt,
                    "total_command_vector_slew_mixed_units_per_s": _norm(
                        np.concatenate(
                            [force - previous_force, moment - previous_moment]
                        )
                    )
                    / dt,
                }
            )
        rows.append(row)
        previous = {
            "time_s": time_s,
            "lambda": float(lambdas[filter_index]),
            "allocator": allocator,
            "force": force,
            "moment": moment,
        }
    physical = event["steps"]
    physical_rates: list[dict[str, Any]] = []
    for before, after in zip(physical[:-1], physical[1:]):
        dt = float(after["time_s"] - before["time_s"])
        physical_rates.append(
            {
                "time_s": float(after["time_s"]),
                "physical_force_rate_n_per_s": _norm(
                    _array(after["physical_cuff_force_world_n"])
                    - _array(before["physical_cuff_force_world_n"])
                )
                / dt,
                "physical_moment_rate_nm_per_s": _norm(
                    _array(after["physical_cuff_moment_world_nm"])
                    - _array(before["physical_cuff_moment_world_nm"])
                )
                / dt,
            }
        )
    spike_rows = [item for item in rows if item["time_s"] >= 16.035 - 1.0e-9]
    spike_physical_rates = [
        item for item in physical_rates if item["time_s"] >= 16.040 - 1.0e-9
    ]
    return {
        "memoryless_filter": True,
        "null_vector_sagittal_force_normalized": null_vector.tolist(),
        "allocation_matrix": allocation_matrix.tolist(),
        "B_times_null_residual_nm": (allocation_matrix @ null_vector).tolist(),
        "B_times_null_residual_norm_nm": _norm(allocation_matrix @ null_vector),
        "command_rows": rows,
        "physical_rates": physical_rates,
        "spike_command_rows_from_16_035s": spike_rows,
        "spike_physical_rates_from_16_040s": spike_physical_rates,
        "spike_interval_peaks": {
            "maximum_abs_delta_lambda": float(
                max(abs(item["delta_lambda"] or 0.0) for item in spike_rows)
            ),
            "maximum_allocator_force_slew_n_per_s": float(
                max(item["allocator_force_slew_n_per_s"] or 0.0 for item in spike_rows)
            ),
            "maximum_allocator_moment_slew_nm_per_s": float(
                max(item["allocator_moment_slew_nm_per_s"] or 0.0 for item in spike_rows)
            ),
            "maximum_total_command_force_slew_n_per_s": float(
                max(item["total_command_force_slew_n_per_s"] or 0.0 for item in spike_rows)
            ),
            "maximum_total_command_moment_slew_nm_per_s": float(
                max(item["total_command_moment_slew_nm_per_s"] or 0.0 for item in spike_rows)
            ),
            "maximum_physical_force_rate_n_per_s": float(
                max(item["physical_force_rate_n_per_s"] for item in spike_physical_rates)
            ),
            "maximum_physical_moment_rate_nm_per_s": float(
                max(item["physical_moment_rate_nm_per_s"] for item in spike_physical_rates)
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--event-window", type=Path, default=DEFAULT_EVENT_WINDOW)
    parser.add_argument("--lying-trace", type=Path, default=DEFAULT_LYING_TRACE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite audit: {output_dir}")
    manifest = json.loads(args.manifest.resolve().read_text())
    original = manifest["previous_safe_command"]
    with np.load(args.snapshot.resolve(), allow_pickle=False) as loaded:
        snapshot = {name: loaded[name] for name in loaded.files}
    if not np.isclose(float(snapshot["time_s"]), 16.045, atol=1.0e-12):
        raise RuntimeError("pre-spike snapshot time drifted")
    original_plant = _restore_replay_plant(
        snapshot["mujoco_integration_state"],
        original,
        scenario=LYING_BED_SCENARIO,
        timestep_s=TIMESTEP_S,
        iterations=100,
        tolerance=1.0e-8,
    )
    original_state_record = original_plant.diagnostic_record("original_restored")
    torque_limits = original_plant.torque_limits_nm.copy()
    measured_force = _array(original_state_record["physical_cuff_force_world_n"])
    measured_force_direction = measured_force / np.linalg.norm(measured_force)
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    target_position = _array(original_state_record["cuff_position_world_m"]) + (
        _array(original["raw_force_position_n"]) / gains.position_n_per_m
    )
    current_rotation = _array(original_state_record["cuff_rotation_world"])
    target_rotation = (
        Rotation.from_rotvec(
            _array(original["moment_orientation_nm"]) / gains.orientation_nm_per_rad
        ).as_matrix()
        @ current_rotation
    )

    original_force = _array(original["force_total_n"])
    center_delta = (CENTER_FORCE_N / np.linalg.norm(original_force) - 1.0) * original_force
    center_command = _command_with_delta(
        original, torque_limits, force_delta_n=center_delta
    )
    geometry = geometry_from_trace_vector(snapshot["geometry_estimate"])
    human_model = BaseParameterHumanModel(
        geometry,
        snapshot["incumbent_dynamic_base_model"],
        rom_human=HIGH_ROM_HUMAN,
    )
    estimated_q = _array(snapshot["estimated_human_state"])[:2]
    allocation_matrix = sagittal_allocation_matrix(estimated_q, human_model)
    null_vector = sagittal_null_vector(estimated_q, human_model)
    world_mapping = sagittal_wrench_to_world_matrix(estimated_q, human_model)
    world_null_wrench = world_mapping @ null_vector
    channels = _channel_definitions(
        original, center_delta, measured_force_direction, world_null_wrench
    )
    center_records = _replay(
        snapshot["mujoco_integration_state"],
        center_command,
        original_target_position_m=target_position,
        original_target_rotation=target_rotation,
    )
    center_by_ms = {item["elapsed_ms"]: _response(item) for item in center_records}
    audit_rows: list[dict[str, Any]] = []
    npz_payload: dict[str, np.ndarray] = {
        "elapsed_ms": np.arange(0, 6, dtype=int),
        "center_physical_force_world_n": np.asarray(
            [item["physical_cuff_force_world_n"] for item in center_records]
        ),
        "center_physical_moment_world_nm": np.asarray(
            [item["physical_cuff_moment_world_nm"] for item in center_records]
        ),
    }
    for channel in channels:
        epsilon = float(channel["epsilon"])
        force_delta = epsilon * _array(channel["force_per_unit"])
        moment_delta = epsilon * _array(channel["moment_per_unit"])
        plus_command = _command_with_delta(
            center_command,
            torque_limits,
            force_delta_n=force_delta,
            moment_delta_nm=moment_delta,
        )
        minus_command = _command_with_delta(
            center_command,
            torque_limits,
            force_delta_n=-force_delta,
            moment_delta_nm=-moment_delta,
        )
        if not (plus_command["feasible"] and minus_command["feasible"]):
            raise RuntimeError(f"symmetric perturbation crossed gate: {channel['id']}")
        plus_records = _replay(
            snapshot["mujoco_integration_state"],
            plus_command,
            original_target_position_m=target_position,
            original_target_rotation=target_rotation,
        )
        minus_records = _replay(
            snapshot["mujoco_integration_state"],
            minus_command,
            original_target_position_m=target_position,
            original_target_rotation=target_rotation,
        )
        plus_by_ms = {item["elapsed_ms"]: _response(item) for item in plus_records}
        minus_by_ms = {item["elapsed_ms"]: _response(item) for item in minus_records}
        sensitivities = {
            str(ms): _central_sensitivity(
                plus_by_ms[ms], minus_by_ms[ms], 2.0 * epsilon
            )
            for ms in range(1, 6)
        }
        tradeoff = _signed_reduction_tradeoff(
            center_by_ms[5], plus_by_ms[5], minus_by_ms[5]
        )
        equivalent = float(channel["equivalent_command_force_perturbation_n"])
        if equivalent > 0.0:
            tradeoff["force_reduction_per_equivalent_command_force_n_per_n"] = (
                tradeoff["physical_force_reduction_n"] / equivalent
            )
        row = {
            "id": channel["id"],
            "channel": channel["channel"],
            "perturbation_unit": channel["unit"],
            "epsilon": epsilon,
            "force_delta_plus_n": force_delta.tolist(),
            "moment_delta_plus_nm": moment_delta.tolist(),
            "equivalent_command_force_perturbation_n": equivalent,
            "plus_command_force_norm_n": plus_command[
                "translational_force_norm_n"
            ],
            "minus_command_force_norm_n": minus_command[
                "translational_force_norm_n"
            ],
            "sensitivity_by_elapsed_ms": sensitivities,
            "response_1ms": {
                "center": center_by_ms[1],
                "plus": plus_by_ms[1],
                "minus": minus_by_ms[1],
            },
            "response_5ms": {
                "center": center_by_ms[5],
                "plus": plus_by_ms[5],
                "minus": minus_by_ms[5],
            },
            "lower_force_tradeoff_at_5ms": tradeoff,
        }
        audit_rows.append(row)
        safe_id = channel["id"]
        npz_payload[f"{safe_id}_plus_physical_force_world_n"] = np.asarray(
            [item["physical_cuff_force_world_n"] for item in plus_records]
        )
        npz_payload[f"{safe_id}_minus_physical_force_world_n"] = np.asarray(
            [item["physical_cuff_force_world_n"] for item in minus_records]
        )
    dynamic = _dynamic_null_space_audit(
        args.event_window.resolve(),
        args.lying_trace.resolve(),
        allocation_matrix,
        null_vector,
    )
    lambda_row = next(
        item for item in audit_rows if item["id"] == "B_cuff_null_space_lambda"
    )
    command_rows_with_lambda = [
        item for item in dynamic["command_rows"] if item["delta_lambda"] is not None
    ]
    previous_lambda = command_rows_with_lambda[-1]["lambda"] - command_rows_with_lambda[-1][
        "delta_lambda"
    ]
    original_lambda = command_rows_with_lambda[-1]["lambda"]
    continuity_sign = (
        "plus" if previous_lambda > original_lambda else "minus"
    )
    dynamic["continuity_constrained_lambda_snapshot_test"] = {
        "same_integration_state": True,
        "common_199n_center_reason": (
            "provides symmetric diagnostic headroom while preserving the independent "
            "200 N executable-command gate; it is not a controller margin"
        ),
        "previous_lambda": previous_lambda,
        "original_lambda": original_lambda,
        "diagnostic_delta_lambda_toward_previous": (
            0.25 if continuity_sign == "plus" else -0.25
        ),
        "selected_response_sign": continuity_sign,
        "response_5ms": lambda_row["response_5ms"][continuity_sign],
        "center_response_5ms": lambda_row["response_5ms"]["center"],
        "tradeoff": lambda_row["lower_force_tradeoff_at_5ms"],
    }
    ranked = sorted(
        audit_rows,
        key=lambda item: item["lower_force_tradeoff_at_5ms"][
            "physical_force_reduction_n"
        ],
        reverse=True,
    )
    payload = {
        "schema_version": "phase_b0_interaction_authority_audit_v1",
        "evidence_category": "engineering_local_replay_not_formal_or_authoritative",
        "source_snapshot": str(args.snapshot.resolve()),
        "same_exact_integration_state_for_all_experiments": True,
        "replay_window_ms": 5,
        "response_times_reported_ms": [1, 2, 3, 4, 5],
        "small_symmetric_perturbations": True,
        "original_command_force_norm_n": _norm(original["force_total_n"]),
        "common_audit_center_force_norm_n": _norm(center_command["force_total_n"]),
        "common_center_is_diagnostic_not_new_margin": True,
        "all_executable_commands_at_or_below_200n": True,
        "controller_tuned": False,
        "controller_implemented": False,
        "measured_force_direction_world": measured_force_direction.tolist(),
        "center_response_by_elapsed_ms": center_by_ms,
        "channels": audit_rows,
        "ranking_by_5ms_physical_force_reduction_for_tested_step": [
            {
                "id": item["id"],
                **item["lower_force_tradeoff_at_5ms"],
            }
            for item in ranked
        ],
        "dynamic_null_space_audit": dynamic,
    }
    output_dir.mkdir(parents=True)
    write_strict_json(output_dir / "authority_audit.json", payload)
    np.savez_compressed(output_dir / "authority_response.npz", **npz_payload)
    print(
        json.dumps(
            {
                "output": str(output_dir),
                "top_tested_reduction_channel": ranked[0]["id"],
                "top_tested_reduction_n": ranked[0][
                    "lower_force_tradeoff_at_5ms"
                ]["physical_force_reduction_n"],
                "B_null_residual_nm": dynamic["B_times_null_residual_norm_nm"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
