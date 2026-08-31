#!/usr/bin/env python3
"""Run the two authorized joint-control/progress CEM High-ROM pilots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.progress_aware_cem_pilot import (
    PILOT_TRAJECTORY_NAMES,
    run_progress_aware_cem_pilot,
)
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = STAGE_ROOT / "results" / "high_rom_feasibility"
DEFAULT_OUTPUT = RESULT_ROOT / "progress_aware_cem_5ms_corrected_pilot"
DEFAULT_MATRIX = STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
BASELINE_PATH = (
    RESULT_ROOT
    / "post_jacobian_corrected_pilot"
    / "high_rom_dynamic_pilot_corrected.json"
)
REPORT_PATH = RESULT_ROOT / "high_rom_feasibility_report.md"
REPORT_MARKER = "## Corrected 5 ms joint control-progress CEM High-ROM pilot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    return parser.parse_args()


def _git_provenance() -> dict[str, object]:
    repo = STAGE_ROOT.parents[1]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"code_commit": commit, "working_tree_dirty": bool(dirty)}


def _baseline_comparison(
    payload: dict[str, object], baseline_payload: dict[str, object]
) -> dict[str, object]:
    fixed = {
        item["trajectory"]: item
        for item in baseline_payload["runs"]
        if item["controller"] == "fixed_mpc_prior_only"
    }
    rows = []
    for run in payload["runs"]:
        before = fixed[run["trajectory"]]
        rows.append(
            {
                "trajectory": run["trajectory"],
                "preserved_fixed_clock": {
                    "completion": before["completion"],
                    "termination_reason": before["termination_reason"],
                    "completion_time_s": before["completed_duration_s"],
                    "tracking_combined_rmse_deg": before[
                        "tracking_combined_rmse_deg"
                    ],
                    "tracking_max_abs_error_deg": max(
                        before["tracking_max_abs_error_deg"]
                    ),
                    "command_force_peak_n": before["commanded_force_gate"][
                        "peak_attempt_n"
                    ],
                    "physical_cuff_force_peak_n": before["cuff_force_peak_n"],
                },
                "joint_cem": {
                    "completion": run["completion"],
                    "termination_reason": run["termination_reason"],
                    "completion_time_s": run["completion_time_s"],
                    "tracking_combined_rmse_deg": run[
                        "tracking_combined_rmse_deg"
                    ],
                    "tracking_max_abs_error_deg": max(
                        run["tracking_max_abs_error_deg"]
                    ),
                    "command_force_peak_n": run["interaction_extended"][
                        "executed_command_force_peak_n"
                    ],
                    "physical_cuff_force_peak_n": run["interaction_extended"][
                        "physical_cuff_force_peak_n"
                    ],
                },
            }
        )
    return {
        "baseline_source": str(BASELINE_PATH),
        "baseline_rerun": False,
        "rows": rows,
    }


def _aggregate_latency(
    traces: dict[str, dict[str, np.ndarray]]
) -> dict[str, object]:
    mpc = np.concatenate(
        [np.asarray(trace["mpc_cycle_compute_ms"]) for trace in traces.values()]
    )
    full = np.concatenate(
        [
            np.asarray(trace["high_level_cycle_compute_ms"])
            for trace in traces.values()
        ]
    )

    def metrics(values: np.ndarray) -> dict[str, object]:
        return {
            "sample_count": len(values),
            "mean_ms": float(np.mean(values)),
            "p95_ms": float(np.percentile(values, 95.0)),
            "max_ms": float(np.max(values)),
            "deadline_misses_over_20ms": int(np.sum(values > 20.0)),
            "effective_hz_from_mean": float(1000.0 / np.mean(values)),
            "passes_hard_50hz_target": bool(
                np.percentile(values, 95.0) < 20.0
                and not np.any(values > 20.0)
            ),
        }

    return {
        "mpc_solve_including_joint_alpha_optimization": metrics(mpc),
        "full_high_level_estimator_plus_mpc_cycle": metrics(full),
        "deadline_definition": "strictly greater than 20 ms",
    }


def _plot(
    traces: dict[str, dict[str, np.ndarray]], output_path: Path
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12.2, 6.4))
    for row, name in enumerate(PILOT_TRAJECTORY_NAMES):
        trace = traces[name]
        time = np.asarray(trace["time_s"])
        axes[row, 0].plot(
            time,
            np.asarray(trace["reference_phase_time_s"]) / 23.0,
            color="#315f99",
        )
        axes[row, 0].axhline(1.0, color="black", linestyle=":", linewidth=0.8)
        axes[row, 1].step(
            np.asarray(trace["mpc_selection_time_s"]),
            np.asarray(trace["mpc_selected_alpha"]),
            where="post",
            color="#087f8c",
        )
        axes[row, 2].plot(
            np.asarray(trace["mpc_control_path_prediction_time_s"]),
            np.asarray(trace["mpc_control_path_predicted_command_force_n"]),
            label="winner predicted",
            color="#725cad",
            linewidth=1.0,
        )
        axes[row, 2].plot(
            np.asarray(trace["mpc_control_path_prediction_time_s"]),
            np.asarray(trace["mpc_control_path_executed_command_force_n"]),
            label="executed",
            color="#d1495b",
            linewidth=0.9,
            alpha=0.85,
        )
        axes[row, 2].axhline(200.0, color="black", linestyle=":", linewidth=0.8)
        axes[row, 0].set_ylabel(name.replace("_", " ") + "\nprogress")
        axes[row, 1].set_ylabel("alpha")
        axes[row, 1].set_ylim(0.47, 1.03)
        axes[row, 2].set_ylabel("command force [N]")
        for axis in axes[row]:
            axis.set_xlabel("wall time [s]")
            axis.grid(alpha=0.22)
    axes[0, 0].set_title("Reference progress")
    axes[0, 1].set_title("Joint-CEM alpha")
    axes[0, 2].set_title("Selected prediction vs execution")
    axes[0, 2].legend(fontsize=8)
    fig.suptitle("High-ROM progress-aware CEM pilot")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _report_section(payload: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "Two non-formal engineering runs used one batched 32-candidate CEM "
            "population to jointly sample the frozen action horizon and one alpha. "
            "The corrected fixed-clock evidence was read, not rerun."
        ),
        "",
        "| trajectory | completion | time | RMSE/max | alpha mean/min/max | below 1 | predicted/executed command peak | physical cuff RMS/P95/peak | moment RMS/peak | accel/jerk RMS | force prediction MAE/P95/max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in payload["runs"]:
        alpha = run["alpha"]
        interaction = run["interaction_extended"]
        smooth = run["smoothness"]
        prediction = run["force_prediction_accuracy"]
        lines.append(
            f"| {run['trajectory']} | {run['completion']} ({run['termination_reason']}) | "
            f"{run['completion_time_s']:.2f} s | "
            f"{run['tracking_combined_rmse_deg']:.3f}/"
            f"{max(run['tracking_max_abs_error_deg']):.3f} deg | "
            f"{alpha['mean']:.3f}/{alpha['minimum']:.3f}/{alpha['maximum']:.3f} | "
            f"{alpha['time_below_one_s']:.2f} s | "
            f"{interaction['predicted_command_force_peak_n']:.2f}/"
            f"{interaction['executed_command_force_peak_n']:.2f} N | "
            f"{interaction['physical_cuff_force_rms_n']:.2f}/"
            f"{interaction['physical_cuff_force_p95_n']:.2f}/"
            f"{interaction['physical_cuff_force_peak_n']:.2f} N | "
            f"{interaction['physical_cuff_moment_rms_nm']:.2f}/"
            f"{interaction['physical_cuff_moment_peak_nm']:.2f} Nm | "
            f"{smooth['acceleration_combined_rms_deg_s2']:.1f}/"
            f"{smooth['jerk_combined_rms_deg_s3']:.1f} | "
            f"{prediction['absolute_error_mean_n']:.2f}/"
            f"{prediction['absolute_error_p95_n']:.2f}/"
            f"{prediction['absolute_error_max_n']:.2f} N |"
        )
    latency = payload["aggregate_latency"]
    mpc = latency["mpc_solve_including_joint_alpha_optimization"]
    full = latency["full_high_level_estimator_plus_mpc_cycle"]
    lines.extend(
        [
            "",
            (
                f"Joint-alpha MPC solve latency mean/p95/max: {mpc['mean_ms']:.2f}/"
                f"{mpc['p95_ms']:.2f}/{mpc['max_ms']:.2f} ms; misses: "
                f"{mpc['deadline_misses_over_20ms']}; effective "
                f"{mpc['effective_hz_from_mean']:.1f} Hz."
            ),
            (
                f"Estimator+MPC high-level cycle mean/p95/max: {full['mean_ms']:.2f}/"
                f"{full['p95_ms']:.2f}/{full['max_ms']:.2f} ms; misses: "
                f"{full['deadline_misses_over_20ms']}."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite pilot output: {output}")
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix)
    if case.seed != 44104:
        raise RuntimeError("joint CEM pilot requires seed 44104")

    payload, traces = run_progress_aware_cem_pilot(case)
    payload["baseline_comparison"] = _baseline_comparison(payload, baseline)
    payload["aggregate_latency"] = _aggregate_latency(traces)
    payload["decision"] = {
        "both_paths_completed": all(run["completion"] for run in payload["runs"]),
        "both_paths_avoided_force_gate": all(
            run["events"]["force_gate_events"] == 0 for run in payload["runs"]
        ),
        "joint_alpha_mpc_50hz_pass": payload["aggregate_latency"][
            "mpc_solve_including_joint_alpha_optimization"
        ]["passes_hard_50hz_target"],
        "full_high_level_cycle_50hz_pass": payload["aggregate_latency"][
            "full_high_level_estimator_plus_mpc_cycle"
        ]["passes_hard_50hz_target"],
        "replace_outer_governor": False,
        "alpha_return_to_one_confirmed": all(
            run["alpha"]["returned_to_one_after_slowing"]
            for run in payload["runs"]
        ),
        "next_step": (
            "stop before tuning; diagnose no-feasible-candidate fallback and "
            "model-to-measured low-level force residual, then profile the 5 ms "
            "substep dynamics path before authorizing another pilot"
        ),
    }
    payload["provenance"] = {
        **_git_provenance(),
        "command": (
            "conda run -n mpc_learn env "
            "PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src "
            "python scripts/run_stage4_high_rom_progress_aware_cem_pilot.py"
        ),
    }

    output.mkdir(parents=True, exist_ok=False)
    (output / "progress_aware_cem_pilot.json").write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot(traces, output / "progress_alpha_force_prediction.png")

    report = REPORT_PATH.read_text(encoding="utf-8")
    if REPORT_MARKER in report:
        raise RuntimeError("report already contains joint CEM pilot section")
    REPORT_PATH.write_text(
        report.rstrip() + "\n\n" + _report_section(payload), encoding="utf-8"
    )
    print(json.dumps(json_ready(payload["decision"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
