#!/usr/bin/env python3
"""Run the bounded two-path Stage-4 force-feasibility recovery pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.force_recovery_pilot import (
    PILOT_DURATION_S,
    PILOT_TRAJECTORY_NAMES,
    run_force_recovery_pilot,
)
from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = STAGE_ROOT / "results" / "high_rom_feasibility"
DEFAULT_OUTPUT = RESULT_ROOT / "force_feasibility_recovery_pilot"
DEFAULT_MATRIX = (
    STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
)
REPORT_PATH = RESULT_ROOT / "high_rom_feasibility_report.md"
REPORT_MARKER = "## Force-feasibility recovery High-ROM pilot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    return parser.parse_args()


def _git_provenance() -> dict[str, object]:
    repository = STAGE_ROOT.parents[1]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"code_commit": commit, "working_tree_dirty": bool(dirty)}


def _fixed_baselines(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        run["trajectory"]: run
        for run in payload["runs"]
        if run["controller"] == "fixed_mpc_prior_only"
        and run["trajectory"] in PILOT_TRAJECTORY_NAMES
    }


def _plot(traces: dict[str, dict[str, np.ndarray]], output: Path) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(12.0, 6.5), sharex="row")
    for row, name in enumerate(PILOT_TRAJECTORY_NAMES):
        trace = traces[name]
        time = np.asarray(trace["time_s"], dtype=float)
        phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
        alpha = np.asarray(trace["reference_speed_scale"], dtype=float)
        mode = np.asarray(trace["force_recovery_mode_code"], dtype=float)
        command_time = np.asarray(trace["commanded_force_time_s"], dtype=float)
        command_force = np.asarray(
            trace["commanded_translational_force_norm_n"], dtype=float
        )
        axes[row, 0].plot(time, phase / PILOT_DURATION_S, color="#2563eb")
        axes[row, 0].axhline(1.0, color="black", linestyle=":", linewidth=0.8)
        axes[row, 1].plot(time, alpha, color="#047857", label="alpha")
        axes[row, 1].step(
            time,
            mode / 4.0,
            where="post",
            color="#7c3aed",
            alpha=0.45,
            label="mode code / 4",
        )
        axes[row, 2].plot(command_time, command_force, color="#b45309")
        axes[row, 2].axhline(200.0, color="#b91c1c", linestyle=":")
        axes[row, 0].set_ylabel(name.replace("_", " ") + "\nprogress")
        axes[row, 1].set_ylabel("alpha / mode")
        axes[row, 2].set_ylabel("executed command force [N]")
        axes[row, 1].legend(loc="best", fontsize=7)
        for axis in axes[row]:
            axis.grid(alpha=0.22)
            axis.set_xlabel("wall time [s]")
    axes[0, 0].set_title("Reference progress")
    axes[0, 1].set_title("Recovery speed and state")
    axes[0, 2].set_title("Final executable low-level force")
    figure.suptitle("Stage-4 High-ROM force-feasibility recovery")
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def _report_section(payload: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "A two-run, one-seed engineering pilot added only a Stage-4 execution "
            "supervisor around the frozen Fixed MPC. It previews the exact 5 ms "
            "low-level force, rejects an unsafe first action, freezes path progress, "
            "and retains the independent 200 N runtime gate."
        ),
        "",
        "| trajectory | complete | class | time | HOLD count/duration | alpha mean/min | tracking RMSE/max | command peak/margin | cuff RMS/P95/peak | moment peak | accel/jerk RMS | latency p95/max | events |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in payload["runs"]:
        speed = run["speed_and_hold"]
        interaction = run["interaction_extended"]
        smooth = run["smoothness"]
        latency = run["latency"]["full_high_level_cycle"]
        events = run["events"]
        lines.append(
            f"| {run['trajectory']} | {run['completion']} "
            f"({run['termination_reason']}) | {run['recovery_classification']} | "
            f"{run['completion_time_s']:.2f} s | "
            f"{speed['hold_event_count']}/{speed['hold_total_duration_s']:.2f} s | "
            f"{speed['alpha_mean']:.3f}/{speed['alpha_minimum']:.3f} | "
            f"{run['tracking_combined_rmse_deg']:.3f}/"
            f"{max(run['tracking_max_abs_error_deg']):.3f} deg | "
            f"{interaction['executed_command_force_peak_n']:.2f}/"
            f"{interaction['executed_command_force_margin_n']:.2f} N | "
            f"{interaction['physical_cuff_force_rms_n']:.2f}/"
            f"{interaction['physical_cuff_force_p95_n']:.2f}/"
            f"{interaction['physical_cuff_force_peak_n']:.2f} N | "
            f"{interaction['physical_cuff_moment_peak_nm']:.2f} Nm | "
            f"{smooth['acceleration_combined_rms_deg_s2']:.1f}/"
            f"{smooth['jerk_combined_rms_deg_s3']:.1f} | "
            f"{latency['p95_ms']:.2f}/{latency['max_ms']:.2f} ms | "
            f"force={events['force_gate_events']}, ROM={events['rom_event_samples']}, "
            f"solver={events['mpc_solver_failures']}, robot="
            f"{run['robot']['joint_position_limit_samples']} |"
        )
    lines.extend(
        [
            "",
            (
                "The settle criterion is common to both paths: frozen-reference q-error "
                "norm <=2 deg, dq norm <=5 deg/s, executable HOLD command <=195 N, "
                "continuously for 0.10 s. Recovery uses a coarse bracket plus bisection "
                "to 0.001 alpha and ramps upward at the already used 0.25/s rate."
            ),
            "",
            (
                "All rejected command attempts remain diagnostic values; only commands "
                "that pass both the allocator and exact total-force checks are applied."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite recovery pilot: {output}")
    corrected = (
        RESULT_ROOT
        / "post_jacobian_corrected_pilot/high_rom_dynamic_pilot_corrected.json"
    )
    if not corrected.exists():
        raise FileNotFoundError("corrected fixed-clock baselines are required")
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix)
    if case.seed != 44104:
        raise RuntimeError("force recovery pilot requires seed 44104")

    payload, traces = run_force_recovery_pilot(case)
    baselines = _fixed_baselines(corrected)
    payload["fixed_clock_baseline_source"] = str(corrected)
    payload["baseline_comparison"] = {
        run["trajectory"]: {
            "fixed_clock_completion": baselines[run["trajectory"]]["completion"],
            "fixed_clock_termination_reason": baselines[run["trajectory"]][
                "termination_reason"
            ],
            "fixed_clock_stop_time_s": baselines[run["trajectory"]][
                "completed_duration_s"
            ],
            "fixed_clock_command_peak_n": baselines[run["trajectory"]][
                "commanded_force_gate"
            ]["peak_attempt_n"],
            "recovery_completion": run["completion"],
            "recovery_termination_reason": run["termination_reason"],
            "recovery_completion_time_s": run["completion_time_s"],
            "recovery_executed_command_peak_n": run["interaction_extended"][
                "executed_command_force_peak_n"
            ],
        }
        for run in payload["runs"]
    }
    payload["provenance"] = {
        **_git_provenance(),
        "command": (
            "PYTHONPATH=stages/stage4_adaptive_control/src:"
            "stages/stage3_full3d/src conda run -n mpc_learn python "
            "stages/stage4_adaptive_control/scripts/"
            "run_stage4_high_rom_force_recovery_pilot.py"
        ),
    }

    output.mkdir(parents=True, exist_ok=False)
    result_path = output / "force_feasibility_recovery_pilot.json"
    result_path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _plot(traces, output / "recovery_alpha_hold_force.png")

    report = REPORT_PATH.read_text(encoding="utf-8")
    if REPORT_MARKER in report:
        raise RuntimeError("report already contains force recovery section")
    REPORT_PATH.write_text(
        report.rstrip() + "\n\n" + _report_section(payload), encoding="utf-8"
    )
    print(
        json.dumps(
            json_ready(
                {
                    run["trajectory"]: {
                        "completion": run["completion"],
                        "termination_reason": run["termination_reason"],
                        "classification": run["recovery_classification"],
                        "completion_time_s": run["completion_time_s"],
                        "command_peak_n": run["interaction_extended"][
                            "executed_command_force_peak_n"
                        ],
                    }
                    for run in payload["runs"]
                }
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
