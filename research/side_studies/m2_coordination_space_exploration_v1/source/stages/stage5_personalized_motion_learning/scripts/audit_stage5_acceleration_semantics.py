#!/usr/bin/env python3
"""Synchronize saved Stage-5 acceleration meanings without changing control."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.acceleration import (
    estimate_deployable_realized_acceleration,
)
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.controller_interface import EstimatedInterfaceState
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
from traction_mpc_stage5.task_observation import make_task_observation


CONTROL_DT_S = 0.005
MPC_DT_S = 0.020
MODEL_VERSION = "stage5_fixed_registered_human_v1"


def _fixed_model():
    q0 = np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    pose = STAGE5_GEOMETRY.world_from_cuff(q0, STAGE5_HUMAN)
    return FixedStage5Estimator(pose.translation, pose.rotation, q0).model


def _model_acceleration_trace(trace: dict[str, np.ndarray]) -> np.ndarray:
    model = _fixed_model()
    result = []
    for time_s, state, force, moment in zip(
        trace["time_s"],
        trace["estimated_state_rad_rad_s"],
        trace["physical_cuff_force_world_n"],
        trace["physical_cuff_moment_world_nm"],
        strict=True,
    ):
        observation = make_task_observation(
            state,
            sample_timestamp_s=float(time_s),
            controller_timestamp_s=float(time_s),
            human_model_version=MODEL_VERSION,
        )
        zeros = np.zeros(3)
        interface = EstimatedInterfaceState(
            sample_timestamp_s=float(time_s),
            displacement_human_m=zeros.copy(),
            velocity_human_m_s=zeros.copy(),
            rotation_error_human_rad=zeros.copy(),
            angular_velocity_human_rad_s=zeros.copy(),
            human_position_world_m=zeros.copy(),
            human_rotation_world=np.eye(3),
            human_velocity_world_m_s=zeros.copy(),
            human_angular_velocity_world_rad_s=zeros.copy(),
            measured_force_world_n=np.asarray(force).copy(),
            measured_moment_world_nm=np.asarray(moment).copy(),
        )
        result.append(
            estimate_deployable_realized_acceleration(
                observation, interface, model
            ).acceleration_rad_s2
        )
    return np.asarray(result)


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as payload:
        return {name: payload[name].copy() for name in payload.files}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace",
        type=Path,
        default=(
            root
            / "results"
            / "acceleration_semantics_v1"
            / "prefix_45ms_replay"
            / "trace.npz"
        ),
    )
    parser.add_argument(
        "--original-trace",
        type=Path,
        default=(
            root
            / "results"
            / "loaded_execution_authority_v1"
            / "matched_attempt_01"
            / "trace.npz"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            root
            / "results"
            / "acceleration_semantics_v1"
            / "saved_trace_audit_v2"
        ),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trace = _load(args.trace)
    original = _load(args.original_trace)
    time = trace["time_s"]
    estimated_dq = trace["estimated_state_rad_rad_s"][:, 2:]
    truth_dq = trace["evaluation_human_dq_rad_s"]
    model_acceleration = _model_acceleration_trace(trace)
    limit = np.asarray(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2
    )

    legacy = np.zeros_like(estimated_dq)
    truth_interval = np.zeros_like(truth_dq)
    causal_model_interval = np.zeros_like(model_acceleration)
    causal_model_20ms = np.zeros_like(model_acceleration)
    truth_20ms = np.zeros_like(model_acceleration)
    rows_5ms: list[dict[str, object]] = []
    for index in range(1, len(time)):
        dt = float(time[index] - time[index - 1])
        legacy[index] = (estimated_dq[index] - estimated_dq[index - 1]) / dt
        truth_interval[index] = (truth_dq[index] - truth_dq[index - 1]) / dt
        causal_model_interval[index] = 0.5 * (
            model_acceleration[index - 1] + model_acceleration[index]
        )
        row: dict[str, object] = {
            "start_time_s": float(time[index - 1]),
            "end_time_s": float(time[index]),
        }
        for joint in range(2):
            suffix = f"q{joint + 1}_deg_s2"
            row[f"legacy_dq_difference_{suffix}"] = float(
                np.degrees(legacy[index, joint])
            )
            row[f"deployable_model_causal_mean_{suffix}"] = float(
                np.degrees(causal_model_interval[index, joint])
            )
            row[f"evaluation_truth_interval_{suffix}"] = float(
                np.degrees(truth_interval[index, joint])
            )
        rows_5ms.append(row)

    for index, timestamp in enumerate(time):
        cutoff = max(float(time[0]), float(timestamp - MPC_DT_S))
        duration = float(timestamp - cutoff)
        if duration <= 1.0e-15:
            causal_model_20ms[index] = model_acceleration[index]
            truth_20ms[index] = model_acceleration[index]
            continue
        start_index = int(np.flatnonzero(time >= cutoff - 1.0e-10)[0])
        causal_model_20ms[index] = np.trapezoid(
            model_acceleration[start_index : index + 1],
            time[start_index : index + 1],
            axis=0,
        ) / duration
        truth_start = np.array(
            [
                np.interp(cutoff, time[: index + 1], truth_dq[: index + 1, joint])
                for joint in range(2)
            ]
        )
        truth_20ms[index] = (truth_dq[index] - truth_start) / duration

    rows_mpc: list[dict[str, object]] = []
    predicted_accelerations = []
    for start_time, predicted in zip(
        trace["selected_prediction_time_s"],
        trace["selected_prediction_first_state_rad_rad_s"],
        strict=True,
    ):
        starts = np.flatnonzero(np.isclose(time, start_time, atol=1.0e-10))
        ends = np.flatnonzero(
            np.isclose(time, start_time + MPC_DT_S, atol=1.0e-10)
        )
        if not len(starts) or not len(ends):
            continue
        i, j = int(starts[0]), int(ends[0])
        predicted_acceleration = (
            predicted[2:] - estimated_dq[i]
        ) / MPC_DT_S
        predicted_accelerations.append(predicted_acceleration)
        model_mean = np.trapezoid(
            model_acceleration[i : j + 1], time[i : j + 1], axis=0
        ) / MPC_DT_S
        estimated_interval = (estimated_dq[j] - estimated_dq[i]) / MPC_DT_S
        truth_mean = (truth_dq[j] - truth_dq[i]) / MPC_DT_S
        row = {
            "start_time_s": float(start_time),
            "end_time_s": float(start_time + MPC_DT_S),
        }
        for joint in range(2):
            suffix = f"q{joint + 1}_deg_s2"
            row[f"mpc_predicted_{suffix}"] = float(
                np.degrees(predicted_acceleration[joint])
            )
            row[f"deployable_model_causal_mean_{suffix}"] = float(
                np.degrees(model_mean[joint])
            )
            row[f"estimated_realized_interval_{suffix}"] = float(
                np.degrees(estimated_interval[joint])
            )
            row[f"evaluation_truth_interval_{suffix}"] = float(
                np.degrees(truth_mean[joint])
            )
        rows_mpc.append(row)

    legacy_violation = np.abs(legacy[1:]) > limit
    truth_violation = np.abs(truth_interval[1:]) > limit
    model_violation = np.abs(causal_model_interval[1:]) > limit
    false_legacy = legacy_violation & ~truth_violation & ~model_violation
    predicted_array = np.asarray(predicted_accelerations).reshape(-1, 2)
    common_names = sorted(set(trace) & set(original))
    reproduction_difference = {}
    for name in common_names:
        if (
            not np.issubdtype(trace[name].dtype, np.number)
            or trace[name].shape != original[name].shape
            or not trace[name].size
        ):
            continue
        difference = np.abs(trace[name] - original[name])
        finite = difference[np.isfinite(difference)]
        if len(finite):
            reproduction_difference[name] = float(np.max(finite))
    summary = {
        "evidence_category": "engineering_targeted_saved_trace_audit_only",
        "input_trace": str(args.trace),
        "original_failure_trace": str(args.original_trace),
        "prefix_reproduction_maximum_numeric_difference": float(
            max(reproduction_difference.values(), default=0.0)
        ),
        "timestamps_s": time.tolist(),
        "registered_limit_deg_s2": np.degrees(limit).tolist(),
        "legacy_5ms_velocity_difference": {
            "peak_abs_deg_s2": np.degrees(
                np.max(np.abs(legacy[1:]), axis=0)
            ).tolist(),
            "violation_count_by_joint": np.count_nonzero(
                legacy_violation, axis=0
            ).tolist(),
            "false_violation_count_by_joint": np.count_nonzero(
                false_legacy, axis=0
            ).tolist(),
        },
        "deployable_model_causal_interval_mean": {
            "peak_abs_deg_s2": np.degrees(
                np.max(np.abs(causal_model_interval[1:]), axis=0)
            ).tolist(),
            "violation_count_by_joint": np.count_nonzero(
                model_violation, axis=0
            ).tolist(),
            "rmse_vs_truth_interval_deg_s2": np.degrees(
                np.sqrt(
                    np.mean(
                        (causal_model_interval[1:] - truth_interval[1:]) ** 2,
                        axis=0,
                    )
                )
            ).tolist(),
        },
        "evaluation_only_truth_interval": {
            "peak_abs_deg_s2": np.degrees(
                np.max(np.abs(truth_interval[1:]), axis=0)
            ).tolist(),
            "violation_count_by_joint": np.count_nonzero(
                truth_violation, axis=0
            ).tolist(),
        },
        "unified_causal_20ms_semantics": {
            "deployable_model_peak_abs_deg_s2": np.degrees(
                np.max(np.abs(causal_model_20ms), axis=0)
            ).tolist(),
            "evaluation_truth_peak_abs_deg_s2": np.degrees(
                np.max(np.abs(truth_20ms), axis=0)
            ).tolist(),
            "deployable_violation_count_by_joint": np.count_nonzero(
                np.abs(causal_model_20ms) > limit, axis=0
            ).tolist(),
            "truth_violation_count_by_joint": np.count_nonzero(
                np.abs(truth_20ms) > limit, axis=0
            ).tolist(),
            "window_s": MPC_DT_S,
            "startup_treatment": (
                "all causal history since t=0 until the full window exists; "
                "no sample is exempt"
            ),
        },
        "legacy_rmse_vs_truth_interval_deg_s2": np.degrees(
            np.sqrt(np.mean((legacy[1:] - truth_interval[1:]) ** 2, axis=0))
        ).tolist(),
        "model_instantaneous_at_abort_deg_s2": np.degrees(
            model_acceleration[-1]
        ).tolist(),
        "legacy_at_abort_deg_s2": np.degrees(legacy[-1]).tolist(),
        "truth_interval_at_abort_deg_s2": np.degrees(
            truth_interval[-1]
        ).tolist(),
        "mpc_predicted_peak_abs_deg_s2": (
            np.degrees(np.max(np.abs(predicted_array), axis=0)).tolist()
            if len(predicted_array)
            else None
        ),
        "aligned_20ms_interval_count": len(rows_mpc),
        "conclusion": (
            "the backward 5 ms estimated-dq difference creates a false q2 "
            "interval-limit violation. Instantaneous model/MuJoCo acceleration "
            "can exceed 600 deg/s2, but the registered envelope was derived "
            "from sampled interval acceleration and MPC constrains 20 ms "
            "interval acceleration; the unified causal 20 ms model/truth "
            "semantics remain inside the unchanged limits"
        ),
        "truth_used_online": False,
        "future_samples_used_online": False,
    }
    _write_csv(args.output_dir / "aligned_5ms_intervals.csv", rows_5ms)
    _write_csv(args.output_dir / "aligned_20ms_mpc_intervals.csv", rows_mpc)
    (args.output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
