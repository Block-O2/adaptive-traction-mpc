#!/usr/bin/env python3
"""Evaluate one shadow-only explicit CR12 rigid-body prediction upgrade."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import (
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.compact_execution_predictor import (
    CompactCuffResponseModelV1,
)
from traction_mpc_stage5.cr12_rigid_body_predictor import (
    CR12RigidBodyPredictionContract,
    CR12RigidBodyPredictionState,
)
import traction_mpc_stage5.goal_mpc_smoke as smoke_module
from traction_mpc_stage5.goal_mpc import _SupportCenteredBatchPreview, support_action
from traction_mpc_stage5.near_limit_shadow import NearLimitShadowTarget
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK

import run_stage5_cr12_compact_predictor_v1 as dataset_util


CONTROL_DT_S = 0.005
PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])
ACCELERATION_LIMIT_RAD_S2 = np.asarray(
    PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
    dtype=float,
)

GROUPS = {
    "development_regression": (0.040, 0.080, 0.120),
    "calibration": (0.145, 0.185, 0.225),
    "historical_regression": (0.100, 0.200, 0.260, 0.280, 0.300),
    "held_out_new": (0.255, 0.285, 0.305),
}
CANDIDATE_OFFSETS_NM = dataset_util.CANDIDATE_OFFSETS_NM


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"unsupported output type {type(value)!r}")


def _target(timestamp_s: float, group: str) -> NearLimitShadowTarget:
    control_index = int(round(timestamp_s / CONTROL_DT_S))
    return NearLimitShadowTarget(
        timestamp_s=timestamp_s,
        task_phase="OUTBOUND",
        mpc_cycle_offset=control_index % 4,
        boundary_proximity=0.0,
        normalized_joint_acceleration=(0.0, 0.0),
        source_trace=f"{group}__t{timestamp_s:.3f}",
    )


def _selected_actions(trace_path: Path) -> dict[float, np.ndarray]:
    with np.load(trace_path) as trace:
        times = np.asarray(trace["time_s"], dtype=float)
        actions = np.asarray(trace["executed_generalized_action_nm"], dtype=float)
    result = {}
    for timestamp in (value for group in GROUPS.values() for value in group):
        index = int(np.argmin(np.abs(times - timestamp)))
        if not np.isclose(times[index], timestamp, atol=1.0e-10, rtol=0.0):
            raise RuntimeError(f"baseline trace lacks {timestamp:.3f} s action")
        result[timestamp] = actions[index].copy()
    return result


def _make_preview(
    clone: Any,
    contract: CR12RigidBodyPredictionContract,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    plant = clone.plant
    graph, runtime = dataset_util.restore_runtime_snapshot(plant, clone.snapshot)
    observation, interface_state, measurement, human_model, context = (
        dataset_util._current_inputs(plant, graph, runtime)
    )
    preview = make_interface_aware_first_action_batch_preview(
        context.preview_command_batch,
        graph["screening_interface_predictor"],
        interface_state,
        q_rad=observation.as_array()[:2],
        human_model=human_model,
        cuff_allocator=graph["cuff_allocator"],
        state_rad_rad_s=observation.as_array(),
        acceleration_limits_rad_s2=ACCELERATION_LIMIT_RAD_S2,
        rigid_body_contract=contract,
        rigid_body_robot_state=CR12RigidBodyPredictionState(
            q_rad=measurement.robot_q_rad,
            dq_rad_s=measurement.robot_dq_rad_s,
            neutral_q_rad=plant.neutral_robot_q,
        ),
    )
    return preview, graph, runtime


def _orientation_error_deg(predicted: np.ndarray, truth: np.ndarray) -> float:
    return float(
        np.degrees(
            np.linalg.norm(Rotation.from_matrix(predicted @ truth.T).as_rotvec())
        )
    )


def _predict_branch(
    clone: Any,
    branch: dict[str, Any],
    contract: CR12RigidBodyPredictionContract,
) -> dict[str, Any]:
    preview, graph, runtime = _make_preview(clone, contract)
    observation = runtime["task_observation"]
    human_model = graph["current_model"]
    current_support = support_action(observation.as_array(), human_model)
    centered = _SupportCenteredBatchPreview(
        preview, current_support, graph["mpc"]._support_action_batch
    )
    action = np.asarray(branch["candidate_action_nm"], dtype=float)
    mpc = graph["mpc"]
    mpc._active_human_model = human_model
    try:
        prediction = centered((action - current_support)[None, :])
    finally:
        mpc._active_human_model = None

    predicted_human = np.asarray(
        prediction.predicted_prefix_states_rad_rad_s[0], dtype=float
    )
    predicted_robot_q = np.asarray(prediction.predicted_prefix_robot_q_rad[0])
    predicted_robot_dq = np.asarray(prediction.predicted_prefix_robot_dq_rad_s[0])
    predicted_position = np.asarray(
        prediction.predicted_prefix_robot_cuff_position_world_m[0]
    )
    predicted_rotation = np.asarray(
        prediction.predicted_prefix_robot_cuff_rotation_world[0]
    )
    predicted_linear = np.asarray(
        prediction.predicted_prefix_robot_cuff_linear_velocity_world_m_s[0]
    )
    predicted_angular = np.asarray(
        prediction.predicted_prefix_robot_cuff_angular_velocity_world_rad_s[0]
    )
    predicted_wrench = np.asarray(
        prediction.predicted_prefix_physical_cuff_wrench_world[0]
    )
    predicted_acceleration = np.asarray(
        prediction.predicted_prefix_acceleration_rad_s2[0, -1]
    )

    layer_rows = []
    force_errors = []
    for index, endpoint in enumerate(branch["endpoints"]):
        truth_wrench = np.asarray(
            endpoint["physical_cuff_wrench_human_site_world"], dtype=float
        )
        force_error = predicted_wrench[index, :3] - truth_wrench[:3]
        force_errors.append(force_error)
        layer_rows.append(
            {
                "offset_ms": 5.0 * (index + 1),
                "robot_q_error_deg": np.degrees(
                    predicted_robot_q[index] - endpoint["robot_q_rad"]
                ),
                "robot_dq_error_deg_s": np.degrees(
                    predicted_robot_dq[index] - endpoint["robot_dq_rad_s"]
                ),
                "cuff_position_error_mm": 1000.0
                * float(
                    np.linalg.norm(
                        predicted_position[index]
                        - endpoint["robot_cuff_position_world_m"]
                    )
                ),
                "cuff_orientation_error_deg": _orientation_error_deg(
                    predicted_rotation[index], endpoint["robot_cuff_rotation_world"]
                ),
                "cuff_linear_velocity_error_mm_s": 1000.0
                * float(
                    np.linalg.norm(
                        predicted_linear[index]
                        - endpoint["robot_cuff_linear_velocity_world_m_s"]
                    )
                ),
                "cuff_angular_velocity_error_deg_s": float(
                    np.degrees(
                        np.linalg.norm(
                            predicted_angular[index]
                            - endpoint[
                                "robot_cuff_angular_velocity_world_rad_s"
                            ]
                        )
                    )
                ),
                "cuff_force_error_world_n": force_error,
                "cuff_force_error_norm_n": float(np.linalg.norm(force_error)),
                "human_q_error_deg": np.degrees(
                    predicted_human[index, :2] - endpoint["human_q_rad"]
                ),
                "human_dq_error_deg_s": np.degrees(
                    predicted_human[index, 2:] - endpoint["human_dq_rad_s"]
                ),
                "truth_contact_active": bool(
                    endpoint["human_table_contact_active"]
                ),
                "truth_contact_force_n": float(
                    endpoint["human_table_contact_force_n"]
                ),
            }
        )

    acceleration_error_deg = np.degrees(
        predicted_acceleration
        - np.asarray(branch["truth_acceleration_20ms_rad_s2"], dtype=float)
    )
    truth_wrenches = np.vstack(
        [row["physical_cuff_wrench_human_site_world"] for row in branch["endpoints"]]
    )
    truth_force_peak = float(np.max(np.linalg.norm(truth_wrenches[:, :3], axis=1)))
    truth_acceleration_violation = bool(
        np.any(
            np.abs(branch["truth_acceleration_20ms_rad_s2"])
            > ACCELERATION_LIMIT_RAD_S2 + 1.0e-12
        )
    )
    truth_force_violation = bool(
        truth_force_peak > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9
    )
    eligible = bool(np.all(branch["command_feasible"]))
    return {
        "layer_rows": layer_rows,
        "predicted_acceleration_20ms_deg_s2": np.degrees(predicted_acceleration),
        "truth_acceleration_20ms_deg_s2": branch[
            "truth_acceleration_20ms_deg_s2"
        ],
        "acceleration_error_deg_s2": acceleration_error_deg,
        "force_error_world_n": np.asarray(force_errors),
        "force_error_norm_n": np.linalg.norm(force_errors, axis=1),
        "supported": bool(prediction.prediction_supported[0]),
        "predicted_accepted": bool(prediction.feasible[0]),
        "existing_command_feasible_all_segments": eligible,
        "truth_acceleration_violation": truth_acceleration_violation,
        "truth_force_violation": truth_force_violation,
        "truth_violating": truth_acceleration_violation or truth_force_violation,
        "truth_benign_eligible": eligible
        and not truth_acceleration_violation
        and not truth_force_violation,
        "predicted_peak_force_n": float(prediction.predicted_peak_force_n[0]),
        "truth_peak_force_n": truth_force_peak,
        "qualified_acceleration_margin_deg_s2": np.degrees(
            prediction.prefix_acceleration_margin_rad_s2[0, -1]
        ),
    }


def _percentile(values: list[np.ndarray | float], percentile: float) -> Any:
    return np.percentile(np.asarray(values, dtype=float), percentile, axis=0)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    acceleration_error = np.vstack(
        [row["prediction"]["acceleration_error_deg_s2"] for row in rows]
    )
    force_vectors = np.concatenate(
        [row["prediction"]["force_error_world_n"] for row in rows], axis=0
    )
    force_norms = np.linalg.norm(force_vectors, axis=1)
    layers = [layer for row in rows for layer in row["prediction"]["layer_rows"]]
    accepted_violations = [
        row
        for row in rows
        if row["prediction"]["predicted_accepted"]
        and row["prediction"]["truth_violating"]
    ]
    benign = [row for row in rows if row["prediction"]["truth_benign_eligible"]]
    accepted_benign = [
        row for row in benign if row["prediction"]["predicted_accepted"]
    ]
    return {
        "candidate_count": len(rows),
        "acceleration_absolute_error_p95_deg_s2": np.percentile(
            np.abs(acceleration_error), 95.0, axis=0
        ),
        "acceleration_absolute_error_max_deg_s2": np.max(
            np.abs(acceleration_error), axis=0
        ),
        "force_vector_rmse_n": float(
            np.sqrt(np.mean(np.sum(force_vectors * force_vectors, axis=1)))
        ),
        "force_error_norm_p95_n": float(np.percentile(force_norms, 95.0)),
        "force_error_norm_max_n": float(np.max(force_norms)),
        "robot_q_error_abs_p95_deg": _percentile(
            [np.abs(layer["robot_q_error_deg"]) for layer in layers], 95.0
        ),
        "robot_dq_error_abs_p95_deg_s": _percentile(
            [np.abs(layer["robot_dq_error_deg_s"]) for layer in layers], 95.0
        ),
        "cuff_position_error_p95_mm": float(
            _percentile([layer["cuff_position_error_mm"] for layer in layers], 95.0)
        ),
        "cuff_orientation_error_p95_deg": float(
            _percentile(
                [layer["cuff_orientation_error_deg"] for layer in layers], 95.0
            )
        ),
        "cuff_linear_velocity_error_p95_mm_s": float(
            _percentile(
                [layer["cuff_linear_velocity_error_mm_s"] for layer in layers],
                95.0,
            )
        ),
        "cuff_angular_velocity_error_p95_deg_s": float(
            _percentile(
                [layer["cuff_angular_velocity_error_deg_s"] for layer in layers],
                95.0,
            )
        ),
        "human_q_error_abs_p95_deg": _percentile(
            [np.abs(layer["human_q_error_deg"]) for layer in layers], 95.0
        ),
        "human_dq_error_abs_p95_deg_s": _percentile(
            [np.abs(layer["human_dq_error_deg_s"]) for layer in layers], 95.0
        ),
        "supported_candidate_count": int(
            sum(row["prediction"]["supported"] for row in rows)
        ),
        "predicted_accepted_count": int(
            sum(row["prediction"]["predicted_accepted"] for row in rows)
        ),
        "truth_violating_count": int(
            sum(row["prediction"]["truth_violating"] for row in rows)
        ),
        "predicted_accepted_truth_violating_count": len(accepted_violations),
        "predicted_accepted_truth_violating_cases": [
            f"{row['group_id']}::{row['candidate_name']}"
            for row in accepted_violations
        ],
        "truth_benign_eligible_count": len(benign),
        "accepted_benign_count": len(accepted_benign),
        "benign_acceptance_coverage": (
            None if not benign else len(accepted_benign) / len(benign)
        ),
        "truth_contact_prefix_count": int(
            sum(layer["truth_contact_active"] for layer in layers)
        ),
    }


def _runtime_benchmark(
    clones: dict[str, Any],
    contract: CR12RigidBodyPredictionContract,
    *,
    repeats_per_state: int,
) -> dict[str, Any]:
    values = []
    statuses = []
    for timestamp in GROUPS["held_out_new"]:
        clone = clones[f"held_out_new__t{timestamp:.3f}"]
        for _ in range(repeats_per_state):
            preview, graph, runtime = _make_preview(clone, contract)
            started = perf_counter()
            _, diagnostics = graph["mpc"].solve_goal(
                runtime["task_observation"],
                runtime["authoritative_task_state"],
                PROVISIONAL_LOW_MODERATE_GOAL_TASK,
                graph["current_model"],
                first_action_batch_preview=preview,
            )
            values.append(1000.0 * (perf_counter() - started))
            statuses.append(str(diagnostics["status"]))
    runtime = np.asarray(values, dtype=float)
    return {
        "sample_count": len(runtime),
        "states": list(GROUPS["held_out_new"]),
        "repeats_per_state": repeats_per_state,
        "p50_ms": float(np.percentile(runtime, 50.0)),
        "p95_ms": float(np.percentile(runtime, 95.0)),
        "p99_ms": float(np.percentile(runtime, 99.0)),
        "maximum_ms": float(np.max(runtime)),
        "deadline_ms": 20.0,
        "deadline_miss_count": int(np.count_nonzero(runtime >= 20.0)),
        "deadline_miss_rate": float(np.mean(runtime >= 20.0)),
        "statuses": statuses,
        "complete_goal_mpc_solve_timed": True,
        "existing_cem_settings_unchanged": True,
        "setup_and_snapshot_restore_excluded": True,
    }


def run(output_dir: Path, *, runtime_repeats_per_state: int) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = tuple(
        _target(timestamp, group)
        for group, timestamps in GROUPS.items()
        for timestamp in timestamps
    )
    captured: dict[str, Any] = {}
    original_capture = smoke_module.capture_diagnostic_continuation_clone

    def capture_wrapper(**kwargs: Any):
        clone = original_capture(**kwargs)
        source = kwargs["trigger_metadata"].get("selection_plan", {}).get(
            "source_trace"
        )
        if source is not None:
            captured[str(source)] = clone
        return clone

    smoke_module.capture_diagnostic_continuation_clone = capture_wrapper
    try:
        baseline = smoke_module.run_goal_mpc_smoke(
            output_dir / "baseline_capture",
            maximum_duration_s=0.335,
            plant_factory=dataset_util._plant_factory,
            plant_case_name="cr12_rigid_body_predictor_v1_dataset_capture",
            near_limit_shadow_targets=targets,
        )
    finally:
        smoke_module.capture_diagnostic_continuation_clone = original_capture
    missing = sorted(
        target.source_trace
        for target in targets
        if target.source_trace not in captured
    )
    if missing:
        raise RuntimeError(f"dataset anchors not captured: {missing}")

    selected = _selected_actions(output_dir / "baseline_capture" / "trace.npz")
    branches = []
    for group, timestamps in GROUPS.items():
        for timestamp in timestamps:
            clone = captured[f"{group}__t{timestamp:.3f}"]
            for candidate_name, offset in CANDIDATE_OFFSETS_NM.items():
                branches.append(
                    dataset_util._branch_truth(
                        clone,
                        group=group,
                        timestamp_s=timestamp,
                        candidate_name=candidate_name,
                        candidate_action_nm=selected[timestamp] + offset,
                    )
                )

    zero_margin_contract = CR12RigidBodyPredictionContract(
        acceleration_margin_rad_s2=np.zeros(2),
        calibration_group_ids=(),
    )
    calibration = [row for row in branches if row["group"] == "calibration"]
    calibration_evaluated = []
    for branch in calibration:
        prediction = _predict_branch(
            captured[branch["group_id"]], branch, zero_margin_contract
        )
        calibration_evaluated.append({**branch, "prediction": prediction})
    calibration_error = np.vstack(
        [row["prediction"]["acceleration_error_deg_s2"] for row in calibration_evaluated]
    )
    margin_deg_s2 = np.max(np.abs(calibration_error), axis=0)
    contract = zero_margin_contract.with_calibration_margin(
        np.radians(margin_deg_s2),
        sorted({row["group_id"] for row in calibration}),
    )
    (output_dir / "rigid_body_prediction_contract_v1.json").write_text(
        json.dumps(contract.record(), indent=2, sort_keys=True), encoding="utf-8"
    )

    evaluated = []
    for branch in branches:
        prediction = _predict_branch(captured[branch["group_id"]], branch, contract)
        evaluated.append({**branch, "prediction": prediction})

    held_out = [row for row in evaluated if row["group"] == "held_out_new"]
    regression = [row for row in evaluated if row["group"] != "held_out_new"]
    held_out_metrics = _metrics(held_out)
    regression_metrics = _metrics(regression)
    per_anchor = {
        f"t{timestamp:.3f}": _metrics(
            [row for row in held_out if np.isclose(row["timestamp_s"], timestamp)]
        )
        for timestamp in GROUPS["held_out_new"]
    }
    runtime = _runtime_benchmark(
        captured, contract, repeats_per_state=runtime_repeats_per_state
    )

    compact_model_path = (
        STAGE5_ROOT
        / "results"
        / "engineering_validation"
        / "cr12_compact_execution_predictor_v1_attempt_03"
        / "compact_execution_model_v1.json"
    )
    compact_model = CompactCuffResponseModelV1.load(compact_model_path)
    compact_same_held_out = []
    for branch in [row for row in branches if row["group"] == "held_out_new"]:
        prediction = dataset_util._predict_branch(
            captured[branch["group_id"]], branch, compact_model
        )
        compact_same_held_out.append({**branch, "prediction": prediction})
    compact_same_held_out_metrics = dataset_util._metrics(compact_same_held_out)

    criteria = {
        "human_acceleration_p95": {
            "threshold_deg_s2": [30.0, 60.0],
            "observed_deg_s2": held_out_metrics[
                "acceleration_absolute_error_p95_deg_s2"
            ],
            "status": (
                "PASS"
                if np.all(
                    np.asarray(
                        held_out_metrics["acceleration_absolute_error_p95_deg_s2"]
                    )
                    <= np.asarray([30.0, 60.0])
                )
                else "FAIL"
            ),
        },
        "cuff_force_prediction": {
            "rmse_threshold_n": 5.0,
            "p95_threshold_n": 10.0,
            "observed_rmse_n": held_out_metrics["force_vector_rmse_n"],
            "observed_p95_n": held_out_metrics["force_error_norm_p95_n"],
            "status": (
                "PASS"
                if held_out_metrics["force_vector_rmse_n"] <= 5.0
                and held_out_metrics["force_error_norm_p95_n"] <= 10.0
                else "FAIL"
            ),
        },
        "finite_set_feasibility": {
            "accepted_truth_violations": held_out_metrics[
                "predicted_accepted_truth_violating_count"
            ],
            "benign_acceptance_coverage": held_out_metrics[
                "benign_acceptance_coverage"
            ],
            "status": (
                "PASS"
                if held_out_metrics["predicted_accepted_truth_violating_count"] == 0
                and (held_out_metrics["benign_acceptance_coverage"] or 0.0) > 0.0
                else "FAIL"
            ),
        },
        "runtime": {
            "p95_threshold_ms": 20.0,
            "observed_p95_ms": runtime["p95_ms"],
            "observed_p99_ms": runtime["p99_ms"],
            "observed_maximum_ms": runtime["maximum_ms"],
            "deadline_miss_count": runtime["deadline_miss_count"],
            "status": "PASS" if runtime["p95_ms"] < 20.0 else "FAIL",
        },
    }
    all_pass = all(item["status"] == "PASS" for item in criteria.values())
    accuracy_improved = bool(
        np.all(
            np.asarray(held_out_metrics["acceleration_absolute_error_p95_deg_s2"])
            < np.asarray(
                compact_same_held_out_metrics[
                    "acceleration_absolute_error_p95_deg_s2"
                ]
            )
        )
        or held_out_metrics["force_vector_rmse_n"]
        < compact_same_held_out_metrics["force_vector_rmse_n"]
    )
    classification = (
        "RP-A — RIGID-BODY PROPAGATION MEETS ACCURACY + RUNTIME REQUIREMENTS"
        if all_pass
        else (
            "RP-B — PREDICTION IMPROVES, BUT ACCURACY OR RUNTIME STILL INSUFFICIENT"
            if accuracy_improved
            else "RP-C — EXPLICIT ROBOT PROPAGATION DOES NOT SOLVE THE PRIMARY GAP"
        )
    )
    summary = {
        "schema": "stage5_cr12_rigid_body_predictor_v1",
        "evidence_category": "bounded_simulation_engineering_validation",
        "shadow_only": True,
        "activated_in_authoritative_control": False,
        "classification": classification,
        "contract": contract.record(),
        "dataset": {
            "groups": GROUPS,
            "candidate_offsets_nm": CANDIDATE_OFFSETS_NM,
            "complete_event_group_split": True,
            "new_held_out_groups": True,
            "historical_groups_used_as_independent_test": False,
            "failed_cases_preserved": True,
            "unvalidated_phases": ["HOLD", "RETURN"],
            "simulation_truth_used_online": False,
            "baseline_abort_status": baseline["task_status"],
            "baseline_abort_reason": baseline["abort_reason"],
            "original_abort_result_preserved": True,
        },
        "held_out_metrics": held_out_metrics,
        "held_out_per_anchor": per_anchor,
        "regression_metrics": regression_metrics,
        "runtime": runtime,
        "criteria": criteria,
        "compact_v1_same_held_out_metrics": compact_same_held_out_metrics,
        "accuracy_improved_by_at_least_one_primary_metric": accuracy_improved,
        "controlled_closed_loop_validation_justified": all_pass,
        "scientific_parameters_changed": False,
        "controller_or_abort_authority_changed": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "evaluated_cases.json").write_text(
        json.dumps(_jsonable(evaluated), indent=2, sort_keys=True), encoding="utf-8"
    )
    np.savez_compressed(
        output_dir / "frozen_dataset.npz",
        group=np.asarray([row["group"] for row in branches]),
        group_id=np.asarray([row["group_id"] for row in branches]),
        candidate_name=np.asarray([row["candidate_name"] for row in branches]),
        candidate_action_nm=np.asarray(
            [row["candidate_action_nm"] for row in branches]
        ),
        truth_acceleration_20ms_rad_s2=np.asarray(
            [row["truth_acceleration_20ms_rad_s2"] for row in branches]
        ),
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
            / "engineering_validation"
            / "cr12_rigid_body_predictor_v1_attempt_03"
        ),
    )
    parser.add_argument("--runtime-repeats-per-state", type=int, default=10)
    args = parser.parse_args()
    if args.runtime_repeats_per_state < 1:
        raise ValueError("runtime repeats must be positive")
    result = run(
        args.output_dir,
        runtime_repeats_per_state=args.runtime_repeats_per_state,
    )
    print(json.dumps(_jsonable(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
