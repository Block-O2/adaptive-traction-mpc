#!/usr/bin/env python3
"""Run the bounded High-ROM fixed-clock versus speed-governor pilot."""

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
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
)
from traction_mpc_stage4.speed_governor_pilot import (
    PILOT_DURATION_S,
    PILOT_TRAJECTORY_NAMES,
    run_predictive_speed_governor_pilot,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = STAGE_ROOT / "results" / "high_rom_feasibility"
DEFAULT_OUTPUT = RESULT_ROOT / "predictive_speed_governor_pilot"
DEFAULT_MATRIX = STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
REPORT_PATH = RESULT_ROOT / "high_rom_feasibility_report.md"
REPORT_MARKER = "## Predictive speed-governor High-ROM pilot"


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


def _plot(
    traces: dict[str, dict[str, np.ndarray]], output_path: Path
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 6.2), sharex=False)
    labels = {
        "fixed_nominal": "fixed clock",
        "predictive_speed_governor": "governor",
    }
    colors = {"fixed_nominal": "#687386", "predictive_speed_governor": "#087f8c"}
    for row, trajectory in enumerate(PILOT_TRAJECTORY_NAMES):
        for mode in labels:
            trace = traces[f"{trajectory}__{mode}"]
            time = np.asarray(trace["time_s"])
            axes[row, 0].plot(
                time,
                np.asarray(trace["reference_phase_time_s"]) / PILOT_DURATION_S,
                label=labels[mode],
                color=colors[mode],
            )
            axes[row, 1].plot(
                time,
                np.asarray(trace["force_speed_scale"]),
                label=labels[mode],
                color=colors[mode],
            )
            axes[row, 2].plot(
                np.asarray(trace["commanded_force_time_s"]),
                np.asarray(trace["commanded_translational_force_norm_n"]),
                label=labels[mode],
                color=colors[mode],
            )
        axes[row, 0].set_ylabel(trajectory.replace("_", " ") + "\nreference progress")
        axes[row, 0].axhline(1.0, color="black", linewidth=0.8, linestyle=":")
        axes[row, 1].set_ylabel("alpha")
        axes[row, 1].set_ylim(0.45, 1.04)
        axes[row, 2].set_ylabel("command force [N]")
        axes[row, 2].axhline(195.0, color="#d97706", linewidth=0.9, linestyle="--")
        axes[row, 2].axhline(200.0, color="#b91c1c", linewidth=0.9, linestyle=":")
        for axis in axes[row]:
            axis.grid(alpha=0.22)
            axis.set_xlabel("wall time [s]")
    axes[0, 0].legend(loc="best", fontsize=8)
    axes[0, 0].set_title("Reference progress")
    axes[0, 1].set_title("Applied phase-rate scale")
    axes[0, 2].set_title("Total commanded translational force")
    fig.suptitle("High-ROM Fixed MPC: fixed clock versus predictive speed governor")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _report_section(payload: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "A small non-formal pilot compared the unchanged Fixed MPC under the "
            "nominal reference clock and an outer-loop predictive phase-rate governor. "
            "The governor is separate from trust confidence and retains the original "
            "MPC, population prior, allocator, geometry, and 200 N hard gate."
        ),
        "",
        "| trajectory | clock | completed | wall / phase | alpha mean/min | tracking RMSE/max | command P95/peak | physical force RMS/P95/peak | moment RMS/peak | accel/jerk RMS | events |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in payload["runs"]:
        speed = run["speed"]
        interaction = run["interaction_extended"]
        smooth = run["smoothness"]
        events = run["events"]
        lines.append(
            f"| {run['trajectory']} | {run['clock_mode']} | {run['completion']} "
            f"({run['termination_reason']}) | {speed['completed_wall_time_s']:.2f} / "
            f"{speed['completed_reference_phase_s']:.2f} s | "
            f"{speed['mean_alpha']:.3f}/{speed['minimum_alpha']:.3f} | "
            f"{run['tracking_combined_rmse_deg']:.3f}/"
            f"{max(run['tracking_max_abs_error_deg']):.3f} deg | "
            f"{interaction['commanded_force_p95_n']:.2f}/"
            f"{interaction['commanded_force_peak_or_gate_attempt_n']:.2f} N | "
            f"{interaction['physical_cuff_force_rms_n']:.2f}/"
            f"{interaction['physical_cuff_force_p95_n']:.2f}/"
            f"{interaction['physical_cuff_force_peak_n']:.2f} N | "
            f"{interaction['physical_cuff_moment_rms_nm']:.2f}/"
            f"{interaction['physical_cuff_moment_peak_nm']:.2f} Nm | "
            f"{smooth['acceleration_combined_rms_deg_s2']:.1f}/"
            f"{smooth['jerk_combined_rms_deg_s3']:.1f} | "
            f"force={events['force_gate_events']}, ROM={events['rom_event_samples']}, "
            f"solver={events['mpc_solver_failures']}, contacts="
            f"{len(events['unintended_contact_pairs'])} |"
        )
    lines.extend(
        [
            "",
            (
                "The planning threshold is 195 N (5 N inside the unchanged hard "
                "gate); candidate alpha values are common to both paths and the "
                "existing Stage-4 0.50 minimum plus existing rate limits are reused."
            ),
            "",
            (
                "Observed result: neither governed path completed. The seed-sequence "
                "forecast stayed below 195 N until the same control update that crossed "
                "the hard gate, so applied alpha remained 1.0 throughout both runs. "
                "This pilot therefore shows no speed, smoothness, interaction, or "
                "completion benefit from the current predictor."
            ),
            "",
            (
                "Next experiment: run an instrumented diagnostic-only replay of the "
                "frozen pre-gate segment and compare "
                "the seed forecast, selected MPC sequence, and realized next-step command "
                "before authorizing any horizon, margin, or controller change."
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
    corrected = RESULT_ROOT / "post_jacobian_corrected_pilot" / "high_rom_dynamic_pilot_corrected.json"
    if not corrected.exists():
        raise FileNotFoundError("corrected post-Jacobian pilot evidence is required")
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix)
    if case.seed != 44104:
        raise RuntimeError("frozen pilot requires measurement seed 44104")

    payload, traces = run_predictive_speed_governor_pilot(case)
    payload["provenance"] = {
        **_git_provenance(),
        "command": (
            "conda run -n mpc_learn env "
            "PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src "
            "python "
            "scripts/run_stage4_high_rom_speed_governor_pilot.py"
        ),
        "corrected_fixed_baseline_preserved_at": str(corrected),
    }

    output.mkdir(parents=True, exist_ok=False)
    result_path = output / "predictive_speed_governor_pilot.json"
    result_path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot(traces, output / "reference_progress_alpha_force.png")

    report = REPORT_PATH.read_text(encoding="utf-8")
    if REPORT_MARKER in report:
        raise RuntimeError("report already contains predictive governor section")
    REPORT_PATH.write_text(
        report.rstrip() + "\n\n" + _report_section(payload),
        encoding="utf-8",
    )
    print(json.dumps(json_ready(payload["paired_comparisons"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
