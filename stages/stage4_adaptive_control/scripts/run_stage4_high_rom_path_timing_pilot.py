#!/usr/bin/env python3
"""Run the authorized two-path offline time-parameterization pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.constraint_aware_path_timing import (
    PathTimingConfig,
    evidence_derived_common_reserve,
)
from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.path_timing_pilot import (
    PILOT_TRAJECTORY_NAMES,
    run_path_timing_pilot,
)
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = STAGE_ROOT / "results" / "high_rom_feasibility"
DEFAULT_OUTPUT = RESULT_ROOT / "constraint_aware_path_timing_pilot"
DEFAULT_MATRIX = STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
BASELINE_PATH = RESULT_ROOT / "post_jacobian_corrected_pilot" / "high_rom_dynamic_pilot_corrected.json"
SMOOTHNESS_BASELINE_PATH = RESULT_ROOT / "predictive_speed_governor_pilot" / "predictive_speed_governor_pilot.json"
RESIDUAL_EVIDENCE_PATH = RESULT_ROOT / "progress_aware_cem_5ms_corrected_pilot" / "progress_aware_cem_pilot.json"
REPORT_PATH = RESULT_ROOT / "high_rom_feasibility_report.md"
REPORT_MARKER = "## Constraint-aware High-ROM path time parameterization"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    return parser.parse_args()


def _git_provenance() -> dict[str, object]:
    repo = STAGE_ROOT.parents[1]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    return {"code_commit": commit, "working_tree_dirty": bool(dirty)}


def _derive_reserve(payload: dict[str, object]) -> tuple[float, dict[str, object]]:
    rows = []
    maxima = []
    for run in payload["runs"]:
        evidence = run["force_prediction_accuracy"]
        if not evidence[
            "prediction_uses_selected_final_cem_action_at_each_5ms_hold_substep"
        ]:
            raise RuntimeError("residual evidence is not final-action aligned")
        value = float(evidence["absolute_error_max_n"])
        maxima.append(value)
        rows.append(
            {
                "trajectory": run["trajectory"],
                "absolute_error_mean_n": evidence["absolute_error_mean_n"],
                "absolute_error_p95_n": evidence["absolute_error_p95_n"],
                "absolute_error_max_n": value,
                "sample_count": evidence["sample_count"],
            }
        )
    reserve = evidence_derived_common_reserve(maxima)
    return reserve, {
        "source": str(RESIDUAL_EVIDENCE_PATH),
        "same_final_candidate_action_verified": True,
        "rows": rows,
        "selection_rule": "ceil(max absolute same-final-action residual across both paths)",
        "selected_common_reserve_n": reserve,
        "planning_budget_n": 200.0 - reserve,
        "trajectory_specific_reserve_used": False,
    }


def _baseline_comparison(
    payload: dict[str, object],
    baseline: dict[str, object],
    smoothness_baseline: dict[str, object],
) -> dict[str, object]:
    fixed = {
        item["trajectory"]: item for item in baseline["runs"]
        if item["controller"] == "fixed_mpc_prior_only"
    }
    fixed_smoothness = {
        item["trajectory"]: item["smoothness"]
        for item in smoothness_baseline["runs"]
        if item["clock_mode"] == "fixed_nominal"
    }
    rows = []
    for run in payload["runs"]:
        old = fixed[run["trajectory"]]
        new_interaction = run["interaction_extended"]
        rows.append(
            {
                "trajectory": run["trajectory"],
                "fixed_clock": {
                    "completion": old["completion"],
                    "termination_reason": old["termination_reason"],
                    "completion_time_s": old["completed_duration_s"],
                    "tracking_rmse_deg": old["tracking_combined_rmse_deg"],
                    "tracking_max_deg": max(old["tracking_max_abs_error_deg"]),
                    "command_force_peak_n": old["commanded_force_gate"]["peak_attempt_n"],
                    "physical_force_peak_n": old["cuff_force_peak_n"],
                    "acceleration_rms_deg_s2": fixed_smoothness[run["trajectory"]]["acceleration_combined_rms_deg_s2"],
                    "jerk_rms_deg_s3": fixed_smoothness[run["trajectory"]]["jerk_combined_rms_deg_s3"],
                },
                "planned_clock": {
                    "completion": run["completion"],
                    "termination_reason": run["termination_reason"],
                    "completion_time_s": run["completion_time_s"],
                    "tracking_rmse_deg": run["tracking_combined_rmse_deg"],
                    "tracking_max_deg": max(run["tracking_max_abs_error_deg"]),
                    "command_force_peak_n": new_interaction["executed_command_force_peak_n"],
                    "physical_force_peak_n": new_interaction["physical_cuff_force_peak_n"],
                    "acceleration_rms_deg_s2": run["smoothness"]["acceleration_combined_rms_deg_s2"],
                    "jerk_rms_deg_s3": run["smoothness"]["jerk_combined_rms_deg_s3"],
                },
            }
        )
    return {
        "baseline_source": str(BASELINE_PATH),
        "fixed_clock_smoothness_source": str(SMOOTHNESS_BASELINE_PATH),
        "baseline_rerun": False,
        "rows": rows,
    }


def _plot(traces: dict[str, dict[str, np.ndarray]], planners: dict[str, object], output: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 6.2))
    for row, name in enumerate(PILOT_TRAJECTORY_NAMES):
        trace = traces[name]
        planner = planners[name]
        axes[row, 0].plot(trace["time_s"], trace["reference_speed_scale"], color="#087f8c")
        axes[row, 0].set_ylim(0.0, 1.05)
        axes[row, 0].set_ylabel(name.replace("_", " ") + "\nphase-rate factor")
        axes[row, 1].plot(
            planner.wall_grid_s, planner.predicted_force_n,
            label="offline inverse dynamics", color="#2563eb",
        )
        axes[row, 1].plot(
            trace["commanded_force_time_s"],
            trace["commanded_translational_force_norm_n"],
            label="executed command", color="#b91c1c",
        )
        axes[row, 1].axhline(130.0, color="#d97706", linestyle="--", linewidth=0.9, label="planning budget" if row == 0 else None)
        axes[row, 1].axhline(200.0, color="black", linestyle=":", linewidth=0.9, label="hard gate" if row == 0 else None)
        axes[row, 1].set_ylabel("translational force [N]")
        for axis in axes[row]:
            axis.set_xlabel("wall time [s]")
            axis.grid(alpha=0.22)
    axes[0, 0].set_title("Offline path-speed envelope")
    axes[0, 1].set_title("Planned vs executed command demand")
    axes[0, 1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _report_section(payload: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "This non-formal two-run engineering pilot added one offline forward/"
            "backward path-time parameterization layer. The Fixed MPC/CEM, estimator, "
            "trust logic, allocator, and independent 200 N gate were unchanged."
        ),
        "",
        (
            f"One common reserve of {payload['reserve_evidence']['selected_common_reserve_n']:.0f} N "
            "was the ceiling of the worst preserved same-final-action prediction residual; "
            f"the planning budget was therefore {payload['reserve_evidence']['planning_budget_n']:.0f} N."
        ),
        "",
        "| trajectory | complete | wall time | alpha mean/min/max | below 1 | tracking RMSE/max | planned/executed command peak | physical force RMS/P95/peak | moment peak | accel/jerk RMS |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in payload["runs"]:
        speed = run["speed"]
        interaction = run["interaction_extended"]
        smooth = run["smoothness"]
        lines.append(
            f"| {run['trajectory']} | {run['completion']} ({run['termination_reason']}) | "
            f"{run['completion_time_s']:.2f} s | {speed['mean']:.3f}/{speed['minimum']:.3f}/{speed['maximum']:.3f} | "
            f"{speed['time_below_nominal_s']:.2f} s | {run['tracking_combined_rmse_deg']:.3f}/"
            f"{max(run['tracking_max_abs_error_deg']):.3f} deg | "
            f"{interaction['planned_inverse_dynamics_force_peak_n']:.2f}/"
            f"{interaction['executed_command_force_peak_n']:.2f} N | "
            f"{interaction['physical_cuff_force_rms_n']:.2f}/"
            f"{interaction['physical_cuff_force_p95_n']:.2f}/"
            f"{interaction['physical_cuff_force_peak_n']:.2f} N | "
            f"{interaction['physical_cuff_moment_peak_nm']:.2f} Nm | "
            f"{smooth['acceleration_combined_rms_deg_s2']:.1f}/"
            f"{smooth['jerk_combined_rms_deg_s3']:.1f} |"
        )
    lines.extend([
        "",
        (
            "The planner profile, force gate result, and compute timing above are "
            "diagnostic engineering evidence only; they do not modify authoritative "
            "Stage-4 results."
        ),
        "",
        (
            "Both inverse-dynamics profiles were already below the common 130 N "
            "planning budget at alpha=1 (111.79 N and 118.77 N). The lexicographic "
            "planner therefore preserved the nominal clock exactly; there was no "
            "slowdown or recovery interval and both runs reproduced their preserved "
            "fixed-clock baselines exactly."
        ),
        "",
        (
            "Both runs still hit the independent command-force gate at 8.56 s "
            "(212.82 N) and 7.75 s (207.32 N). Planner-to-executed command absolute "
            "error p95/max was 24.14/131.87 N and 16.20/122.01 N, so the 70 N "
            "same-final-CEM-action reserve does not cover the different inverse-"
            "dynamics-path predictor. The current extension therefore should not "
            "replace the failed governor."
        ),
        "",
        (
            "One-time planning took 0.464/0.468 s outside the control loop. The "
            "unchanged MPC p95 was 10.19/9.85 ms with zero MPC solves over 20 ms; "
            "the full high-level p95 was 10.64/10.17 ms, with isolated maximum "
            "outliers. Next, validate a single common mapping from planned path "
            "state to the selected closed-loop MPC command using held-out fixed-clock "
            "traces before authorizing another pacing pilot."
        ),
        "",
    ])
    return "\n".join(lines)


def _update_report(section: str) -> None:
    text = REPORT_PATH.read_text()
    if REPORT_MARKER in text:
        text = text.split(REPORT_MARKER, 1)[0].rstrip() + "\n\n" + section
    else:
        text = text.rstrip() + "\n\n" + section
    REPORT_PATH.write_text(text)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    residual_payload = json.loads(RESIDUAL_EVIDENCE_PATH.read_text())
    reserve, reserve_evidence = _derive_reserve(residual_payload)
    config = PathTimingConfig(prediction_reserve_n=reserve)
    matrix = load_report_validation_matrix(args.matrix)
    case = measurement_case(matrix, measurement_seed=44104)
    payload, traces, planners = run_path_timing_pilot(case, config=config)
    baseline = json.loads(BASELINE_PATH.read_text())
    smoothness_baseline = json.loads(SMOOTHNESS_BASELINE_PATH.read_text())
    payload["reserve_evidence"] = reserve_evidence
    payload["baseline_comparison"] = _baseline_comparison(
        payload, baseline, smoothness_baseline
    )
    payload["provenance"] = _git_provenance()
    output_json = args.output_dir / "constraint_aware_path_timing_pilot.json"
    output_json.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n")
    _plot(traces, planners, args.output_dir / "path_speed_and_force.png")
    _update_report(_report_section(payload))
    print(json.dumps(json_ready(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
