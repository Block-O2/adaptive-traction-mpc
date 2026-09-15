#!/usr/bin/env python3
"""Run the preregistered seven-case Acceleration-Semantics V2 checkpoint."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import (
    InitialConditionValidationError,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.interface_robustness_campaign import scaled_interface
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


HISTORICAL_ROOT = STAGE5_ROOT / "results" / "interface_robustness_final_campaign_v1"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "acceleration_semantics_v2_targeted"
PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])
CASES = (
    ("low_low_high", 0.9, 0.9, 1.2, 20260824, "historical_failure"),
    ("low_low_high", 0.9, 0.9, 1.2, 20260825, "historical_pass"),
    ("low_low_high", 0.9, 0.9, 1.2, 20260826, "historical_pass"),
    ("high_low_high", 1.1, 0.9, 1.2, 20260824, "historical_failure"),
    ("high_low_high", 1.1, 0.9, 1.2, 20260825, "historical_pass"),
    ("high_low_high", 1.1, 0.9, 1.2, 20260826, "historical_pass"),
    ("nominal", 1.0, 1.0, 1.0, 20260824, "nominal_baseline"),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def _index_at(trace: dict[str, np.ndarray], time_s: float) -> int:
    matches = np.flatnonzero(
        np.isclose(trace["time_s"], time_s, atol=1.0e-12, rtol=0.0)
    )
    if not len(matches):
        raise ValueError(f"trace has no sample at {time_s:.3f} s")
    return int(matches[0])


def _truth_prefix_acceleration_deg_s2(
    trace: dict[str, np.ndarray], solve_time_s: float = 0.0
) -> list[list[float]]:
    start = _index_at(trace, solve_time_s)
    dq0 = np.asarray(trace["evaluation_human_dq_rad_s"][start], dtype=float)
    result = []
    for prefix in PREFIX_TIMES_S:
        end = _index_at(trace, solve_time_s + float(prefix))
        acceleration = (
            np.asarray(trace["evaluation_human_dq_rad_s"][end], dtype=float)
            - dq0
        ) / prefix
        result.append(np.degrees(acceleration).tolist())
    return result


def _historical_record(condition: str, seed: int) -> dict[str, Any]:
    root = HISTORICAL_ROOT / "core" / condition / f"seed_{seed}"
    summary = _read_json(root / "summary.json")
    trace = _trace(root / "trace.npz")
    action_index = _index_at(trace, 0.005)
    solve_matches = np.flatnonzero(
        np.isclose(
            trace["selected_prediction_time_s"], 0.0, atol=1.0e-12, rtol=0.0
        )
    )
    if not len(solve_matches):
        raise ValueError("historical trace has no t=0 prediction")
    selected = int(solve_matches[0])
    state0 = np.asarray(trace["estimated_state_rad_rad_s"][0], dtype=float)
    state20 = np.asarray(
        trace["selected_prediction_first_state_rad_rad_s"][selected], dtype=float
    )
    try:
        truth_prefix = _truth_prefix_acceleration_deg_s2(trace)
        truth_prefix_source = "saved_campaign_trace"
    except ValueError:
        counterfactual = _read_json(
            HISTORICAL_ROOT
            / "root_cause_audit_v1"
            / "counterfactual_first_action_hold.json"
        )
        match = next(
            item
            for item in counterfactual["results"]
            if item["condition"] == condition and int(item["seed"]) == seed
        )
        truth_prefix = [
            item["truth_interval_acceleration_deg_s2"]
            for item in match["trajectory"]
        ]
        truth_prefix_source = "saved_read_only_counterfactual_hold_audit"
    return {
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "selected_first_total_human_action_nm": np.asarray(
            trace["executed_generalized_action_nm"][action_index], dtype=float
        ).tolist(),
        "mpc_predicted_full_20ms_acceleration_deg_s2": np.degrees(
            (state20[2:] - state0[2:]) / 0.020
        ).tolist(),
        "truth_prefix_acceleration_deg_s2": truth_prefix,
        "truth_prefix_source": truth_prefix_source,
        "source": str(root.relative_to(STAGE5_ROOT)),
        "read_only_frozen_v1_evidence": True,
    }


def _v2_record(
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    historical: dict[str, Any],
) -> dict[str, Any]:
    prefix_matches = np.flatnonzero(
        np.isclose(
            trace["selected_v2_prefix_prediction_time_s"],
            0.0,
            atol=1.0e-12,
            rtol=0.0,
        )
    )
    if not len(prefix_matches):
        raise ValueError("V2 trace has no selected t=0 prefix prediction")
    selected = int(prefix_matches[0])
    action_index = _index_at(trace, 0.005)
    truth_prefix = []
    truth_availability = []
    for prefix_index, prefix in enumerate(PREFIX_TIMES_S):
        try:
            value = _truth_prefix_acceleration_deg_s2(trace)[prefix_index]
            truth_availability.append("v2_executed_trace")
        except ValueError:
            value = historical["truth_prefix_acceleration_deg_s2"][prefix_index]
            truth_availability.append(
                "frozen_v1_counterfactual_same_action"
                if np.allclose(
                    trace["executed_generalized_action_nm"][
                        _index_at(trace, 0.005)
                    ],
                    historical["selected_first_total_human_action_nm"],
                    atol=1.0e-12,
                    rtol=0.0,
                )
                else "unavailable_after_abort"
            )
            if truth_availability[-1] == "unavailable_after_abort":
                value = [None, None]
        truth_prefix.append(value)
    return {
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "phase_transitions": summary["phase_transitions"],
        "task_duration_s": summary["task_duration_s"],
        "selected_first_total_human_action_nm": np.asarray(
            trace["executed_generalized_action_nm"][action_index], dtype=float
        ).tolist(),
        "first_executable_wrench_increment_world": np.asarray(
            trace["selected_v2_prefix_executable_wrench_increment_world"][selected],
            dtype=float,
        ).tolist(),
        "predicted_prefix_acceleration_deg_s2": np.degrees(
            trace["selected_v2_prefix_acceleration_rad_s2"][selected]
        ).tolist(),
        "predicted_prefix_margin_deg_s2": np.degrees(
            trace["selected_v2_prefix_acceleration_margin_rad_s2"][selected]
        ).tolist(),
        "truth_prefix_acceleration_deg_s2": truth_prefix,
        "truth_prefix_source": truth_availability,
        "peak_abs_estimated_joint_velocity_deg_s": summary[
            "peak_abs_estimated_joint_velocity_deg_s"
        ],
        "peak_abs_truth_joint_velocity_deg_s": summary[
            "peak_abs_evaluation_only_joint_velocity_deg_s"
        ],
        "peak_abs_deployable_acceleration_deg_s2": summary[
            "peak_abs_estimated_joint_acceleration_deg_s2"
        ],
        "peak_abs_truth_acceleration_deg_s2": summary[
            "peak_abs_evaluation_only_joint_acceleration_deg_s2"
        ],
        "peak_physical_cuff_force_n": summary["peak_physical_cuff_force_n"],
        "cumulative_physical_cuff_force_n_s": summary[
            "cumulative_physical_cuff_force_n_s"
        ],
        "peak_physical_cuff_moment_nm": summary["peak_physical_cuff_moment_nm"],
        "first_solve_feasible_candidate_evaluations": int(
            trace["mpc_feasible_candidate_evaluations"][0]
        ),
        "first_solve_first_action_feasible_candidate_evaluations": int(
            trace["mpc_first_action_feasible_candidate_evaluations"][0]
        ),
        "mpc_status_counts": summary["mpc_status_counts"],
        "safety_filter_status_counts": summary["safety_filter_status_counts"],
        "brake_event_count": summary["brake_event_count"],
        "force_gate_event_count": summary["force_gate_event_count"],
        "structural_event_count": summary["structural_event_count"],
        "mujoco_warning_counts": summary["mujoco_warning_counts"],
        "mpc_runtime_ms": summary["mpc_runtime_ms"],
        "maximum_normalized_q1_q2_progress_difference": summary[
            "maximum_normalized_q1_q2_progress_difference"
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume-existing", action="store_true")
    args = parser.parse_args()
    output = args.output_dir
    if output.exists() and any(output.iterdir()) and not args.resume_existing:
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    task = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5)
    for index, (name, alpha_t, alpha_r, alpha_d, seed, role) in enumerate(CASES, 1):
        case_output = output / name / f"seed_{seed}"
        historical = _historical_record(name, seed)
        try:
            if args.resume_existing and (case_output / "summary.json").exists():
                summary = _read_json(case_output / "summary.json")
            else:
                summary = run_goal_mpc_smoke(
                case_output,
                spec=task,
                maximum_duration_s=25.0,
                plant_interface_parameters=scaled_interface(
                    alpha_t, alpha_r, alpha_d
                ),
                plant_case_name=f"acceleration_semantics_v2__{name}",
                record_selected_horizon_diagnostics=True,
                use_loaded_local_hold=True,
                stop_on_return_entry=False,
                use_bumpless_return_handoff=True,
                initialize_loaded_equilibrium_with_plant_truth=True,
                interface_uncertainty_spec=None,
                planning_physical_force_ceiling_n=180.0,
                planning_joint_velocity_ceiling_rad_s=tuple(
                    np.radians([15.0, 25.0])
                ),
                    mpc_config=HumanMPCConfig(random_seed=seed),
                )
            trace = _trace(case_output / "trace.npz")
            v2 = _v2_record(summary, trace, historical)
        except InitialConditionValidationError as error:
            v2 = {
                "task_status": "ABORTED",
                "abort_reason": error.diagnostics.get("abort_reason"),
                "initialization_failure": dict(error.diagnostics),
            }
        row = {
            "case": name,
            "seed": seed,
            "role": role,
            "plant_scales": {
                "alpha_t": alpha_t,
                "alpha_r": alpha_r,
                "alpha_d": alpha_d,
            },
            "v1_historical": historical,
            "v2": v2,
        }
        rows.append(row)
        _write_json(output / "progress.json", rows)
        print(
            f"V2 {index}/7 {name} seed={seed} "
            f"status={v2['task_status']} abort={v2.get('abort_reason')}",
            flush=True,
        )
        if role == "historical_failure" and v2.get("task_status") != "COMPLETE":
            print("STOP: historical failure case did not complete under V2", flush=True)
            break
    result = {
        "schema": "stage5_acceleration_semantics_v2_targeted_results",
        "evidence_category": "targeted_engineering_validation",
        "historical_v1_disposition": "EXIT C — STOP THIS IMPLEMENTATION",
        "v1_evidence_rewritten_or_relabelled": False,
        "prefix_times_ms": [5.0, 10.0, 15.0, 20.0],
        "registered_acceleration_limits_deg_s2": [300.0, 600.0],
        "rows": rows,
        "all_predeclared_cases_run": len(rows) == len(CASES),
        "all_v2_complete": len(rows) == len(CASES)
        and all(row["v2"]["task_status"] == "COMPLETE" for row in rows),
        "scope": {
            "new_full_robustness_campaign": False,
            "clinical_or_hardware_validation": False,
            "truth_used_online": False,
            "controller_parameters_retuned": False,
        },
    }
    _write_json(output / "targeted_results.json", result)


if __name__ == "__main__":
    main()
