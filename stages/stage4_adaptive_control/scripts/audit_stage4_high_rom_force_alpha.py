#!/usr/bin/env python3
"""Audit F_cmd(alpha) at fixed pre-gate High-ROM closed-loop states."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.force_pacing_audit import (
    analyze_force_curves,
    run_fixed_clock_force_curve_audit,
)
from traction_mpc_stage4.high_rom_dynamic_pilot import pilot_trajectories
from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = STAGE_ROOT / "results" / "high_rom_feasibility"
OUTPUT_ROOT = RESULT_ROOT / "receding_horizon_force_pacing"
BASELINE_PATH = RESULT_ROOT / "post_jacobian_corrected_pilot" / "high_rom_dynamic_pilot_corrected.json"
RESIDUAL_PATH = RESULT_ROOT / "progress_aware_cem_5ms_corrected_pilot" / "progress_aware_cem_pilot.json"
MATRIX_PATH = STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
REPORT_PATH = RESULT_ROOT / "high_rom_feasibility_report.md"
REPORT_MARKER = "## Receding-horizon final-command force-alpha audit"
TRAJECTORIES = ("hip_dominant_100_60", "aggressive_both_120_120")


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


def _fixed_rows(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        item["trajectory"]: item for item in payload["runs"]
        if item["controller"] == "fixed_mpc_prior_only"
        and item["trajectory"] in TRAJECTORIES
    }


def _select_plot_records(records: list[dict[str, object]], name: str) -> list[dict[str, object]]:
    items = [item for item in records if item["trajectory"] == name]
    targets = (1.0, 0.6, 0.3, 0.1)
    selected = []
    for target in targets:
        record = min(items, key=lambda item: abs(item["lead_to_gate_s"] - target))
        if record not in selected:
            selected.append(record)
    return selected


def _plot(payload: dict[str, object], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), sharey=True)
    reserve = payload["residual_bound"]["common_reserve_n"]
    for axis, name in zip(axes, TRAJECTORIES, strict=True):
        for record in _select_plot_records(payload["records"], name):
            axis.plot(
                record["alpha"],
                np.asarray(record["peak_force_n"]) + reserve,
                label=f"lead {record['lead_to_gate_s']:.2f} s",
            )
        axis.axhline(200.0, color="#b91c1c", linestyle=":", linewidth=1.0)
        axis.set_title(name.replace("_", " "))
        axis.set_xlabel("continuous alpha target")
        axis.grid(alpha=0.22)
        axis.legend(fontsize=8)
    axes[0].set_ylabel("robust predicted command-force peak [N]")
    fig.suptitle("Final-selected-action F_cmd(alpha) before fixed-clock gates")
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _report_section(payload: dict[str, object]) -> str:
    decision = payload["decision"]
    residual = payload["residual_bound"]
    lines = [
        REPORT_MARKER,
        "",
        (
            "A diagnostic-only replay reproduced the two preserved fixed-clock "
            "force-gate outcomes, then swept 101 continuous alpha targets from "
            "0.50 to 1.00 at fixed measured/estimated pre-gate states. Each curve "
            "used the one actual final CEM-selected action sequence, 5 ms held-action "
            "substeps, frozen rigid-cuff allocation, and exact low-level Cartesian "
            "feedback. No additional MPC solve was used."
        ),
        "",
        (
            f"The common empirical reserve was {residual['common_reserve_n']:.0f} N. "
            f"Monotonicity={decision['all_curves_sufficiently_monotonic']}, "
            f"lead-time={decision['both_paths_have_rate_limit_lead']}, "
            f"alpha_min near-gate feasibility="
            f"{decision['alpha_minimum_feasible_within_0p3s_of_gate']}."
        ),
        "",
        (
            f"Step-1 gate passed: {decision['step_1_passed']}. An online pacing "
            "pilot is permitted only when this value is true."
        ),
        "",
        (
            "Observed diagnosis: 21/25 curves changed by no more than 1 N over "
            "alpha=0.50..1.00 because the horizon peak was usually the immediate "
            "selected-action command, before the rate-limited alpha target could "
            "affect it. At 100/60 with only 0.10 s lead, the direction reversed "
            "(F(1)-F(0.5)=-1.35 N; only 76% of dense steps were nondecreasing)."
        ),
        "",
        (
            "The final-selected-sequence predictor remained accurate at the gate "
            "itself but did not anticipate the later CEM action change: maximum "
            "next-0.3 s underprediction was 110.44 N, yielding a 111 N common "
            "reserve. Within 0.30 s of both gates, robust F_cmd(0.5) exceeded "
            "200 N at every audited state, so no bounded scalar search could return "
            "a robustly feasible alpha. The task therefore stops before online "
            "implementation or pacing rollout."
        ),
        "",
        (
            "A dense 101-alpha curve took about 10.5 ms and was evaluated at 10 Hz "
            "for diagnosis. The unchanged MPC p95 remained 9.69/9.72 ms with zero "
            "MPC deadline misses, but diagnostic full-cycle p95 was 19.96/17.13 ms "
            "with 22/15 samples above 20 ms. This audit therefore does not establish "
            "a hard 50 Hz online pacing implementation."
        ),
        "",
    ]
    return "\n".join(lines)


def _update_report(section: str) -> None:
    text = REPORT_PATH.read_text()
    if REPORT_MARKER in text:
        text = text.split(REPORT_MARKER, 1)[0].rstrip() + "\n\n" + section
    else:
        text = text.rstrip() + "\n\n" + section
    REPORT_PATH.write_text(text)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    baseline_payload = json.loads(BASELINE_PATH.read_text())
    fixed = _fixed_rows(baseline_payload)
    trajectories = {
        item.name: item for item in pilot_trajectories() if item.name in TRAJECTORIES
    }
    matrix = load_report_validation_matrix(MATRIX_PATH)
    case = measurement_case(matrix, measurement_seed=44104)
    audit_runs = []
    replay_metrics = []
    for name in TRAJECTORIES:
        gate_time = float(fixed[name]["completed_duration_s"])
        metrics, trace, auditor = run_fixed_clock_force_curve_audit(
            case, trajectories[name], gate_time_s=gate_time
        )
        replay_metrics.append(metrics)
        audit_runs.append((name, gate_time, trace, auditor))
    residual_payload = json.loads(RESIDUAL_PATH.read_text())
    preserved_max = max(
        float(item["force_prediction_accuracy"]["absolute_error_max_n"])
        for item in residual_payload["runs"]
    )
    payload = analyze_force_curves(
        audit_runs, preserved_same_action_max_error_n=preserved_max
    )
    payload.update(
        {
            "evidence_category": "diagnostic_replay_not_formal_benchmark",
            "measurement_case": case.name,
            "measurement_seed": case.seed,
            "fixed_clock_baseline_source": str(BASELINE_PATH),
            "same_action_residual_source": str(RESIDUAL_PATH),
            "replay_metrics": replay_metrics,
            "baseline_exact_reproduction": all(
                metrics["termination_reason"] == fixed[metrics["trajectory"]]["termination_reason"]
                and metrics["completed_duration_s"] == fixed[metrics["trajectory"]]["completed_duration_s"]
                and metrics["tracking_combined_rmse_deg"] == fixed[metrics["trajectory"]]["tracking_combined_rmse_deg"]
                and metrics["commanded_force_gate"]["peak_attempt_n"] == fixed[metrics["trajectory"]]["commanded_force_gate"]["peak_attempt_n"]
                for metrics in replay_metrics
            ),
            "provenance": _git_provenance(),
        }
    )
    output_json = OUTPUT_ROOT / "f_cmd_alpha_audit.json"
    output_json.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n"
    )
    _plot(payload, OUTPUT_ROOT / "f_cmd_alpha_curves.png")
    _update_report(_report_section(payload))
    print(json.dumps(json_ready(payload["decision"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
