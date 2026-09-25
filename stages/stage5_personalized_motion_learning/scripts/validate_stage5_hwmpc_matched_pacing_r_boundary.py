#!/usr/bin/env python3
"""Find the positive-r matched-pacing boundary with the frozen V2 scheduler."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from validate_stage5_human_waypoint_shadow import _jsonable
from validate_stage5_hwmpc_matched_pacing_r_cost import _fixed_models
from validate_stage5_hwmpc_matched_pacing_scheduler import _run_profile


SCHEMA = "stage5_hwmpc_matched_pacing_r_boundary_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_matched_pacing_r_boundary_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contract_valid(case: dict[str, Any]) -> bool:
    return bool(
        case["completed"]
        and case["matched_pacing_contract_passed"]
        and case["safety_contract_passed"]
    )


def refinement_grid(lower: float, upper: float, step: float) -> list[float]:
    """Return the preregistered strict-interior grid without endpoint duplication."""

    if not np.isfinite(lower) or not np.isfinite(upper) or not np.isfinite(step):
        raise ValueError("refinement bounds and step must be finite")
    if lower >= upper or step <= 0.0:
        raise ValueError("refinement bounds and step are invalid")
    count = int(round((upper - lower) / step))
    if count < 1 or not np.isclose(
        lower + count * step, upper, atol=1.0e-12, rtol=0.0
    ):
        raise ValueError("coarse bracket must be divisible by refinement step")
    return [round(lower + index * step, 12) for index in range(1, count)]


def _run_r(
    *,
    r_value: float,
    stage: str,
    replicate_index: int,
    config: dict[str, Any],
    truth_human: Any,
    control_human_model: Any,
    control_model_version: str,
) -> dict[str, Any]:
    case = _run_profile(
        profile={"name": f"{stage}_r{r_value:+.3f}_rep{replicate_index}", "r": r_value},
        config=config,
        truth_human=truth_human,
        control_human_model=control_human_model,
        control_model_version=control_model_version,
    )
    case["search_stage"] = stage
    case["replicate_index"] = int(replicate_index)
    case["boundary_contract_valid"] = contract_valid(case)
    return case


def _first_cases_by_r(cases: list[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    selected: dict[float, dict[str, Any]] = {}
    for case in cases:
        selected.setdefault(float(case["coordination_r"]), case)
    return selected


def _coarse_bracket(cases: list[dict[str, Any]]) -> tuple[float, float, bool]:
    selected = _first_cases_by_r(cases)
    ordered = sorted(selected)
    statuses = [contract_valid(selected[value]) for value in ordered]
    nonmonotonic = any(
        (not left_status) and right_status
        for left_status, right_status in zip(statuses[:-1], statuses[1:])
    )
    transitions = [
        (left, right)
        for left, right in zip(ordered[:-1], ordered[1:])
        if contract_valid(selected[left]) and not contract_valid(selected[right])
    ]
    if len(transitions) != 1:
        raise ValueError("coarse grid did not produce one passing-to-failing bracket")
    return transitions[0][0], transitions[0][1], nonmonotonic


def _summaries(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for r_value in sorted({float(case["coordination_r"]) for case in cases}):
        selected = [case for case in cases if case["coordination_r"] == r_value]
        representative = selected[0]
        terminal_speed = [
            float(np.max(np.abs(case["terminal_dq_deg_s"]))) for case in selected
        ]
        summaries.append(
            {
                "coordination_r": r_value,
                "replicate_count": len(selected),
                "search_stages": [case["search_stage"] for case in selected],
                "all_replicates_contract_valid": all(
                    contract_valid(case) for case in selected
                ),
                "any_replicate_contract_valid": any(
                    contract_valid(case) for case in selected
                ),
                "classification_consistent": len(
                    {contract_valid(case) for case in selected}
                )
                == 1,
                "terminal_max_abs_dq_deg_s": terminal_speed,
                "terminal_max_abs_dq_range_deg_s": float(np.ptp(terminal_speed)),
                "terminal_q_error_deg": representative["terminal_q_error_deg"],
                "terminal_dq_deg_s": representative["terminal_dq_deg_s"],
                "scheduled_peak_abs_20ms_acceleration_deg_s2": representative[
                    "scheduled_peak_abs_20ms_acceleration_deg_s2"
                ],
                "realized_peak_abs_20ms_acceleration_deg_s2": representative[
                    "realized_peak_abs_20ms_acceleration_deg_s2"
                ],
                "minimum_truth_shank_clearance_mm": representative[
                    "minimum_truth_shank_clearance_mm"
                ],
                "shank_bed_contact_sample_count": representative[
                    "shank_bed_contact_sample_count"
                ],
                "cumulative_measured_cuff_force_n_s": representative[
                    "cumulative_measured_cuff_force_n_s"
                ],
                "peak_measured_cuff_force_n": representative[
                    "peak_measured_cuff_force_n"
                ],
                "peak_measured_cuff_moment_nm": representative[
                    "peak_measured_cuff_moment_nm"
                ],
                "maximum_robot_torque_fraction": representative[
                    "maximum_robot_torque_fraction"
                ],
                "human_motion_violation_count": representative[
                    "human_motion_violation_count"
                ],
                "safety_filter_intervention_count": representative[
                    "safety_filter_intervention_count"
                ],
                "brake_cycle_count": representative["brake_cycle_count"],
                "force_gate_event_count": representative["force_gate_event_count"],
                "torque_clip_event_count": representative["torque_clip_event_count"],
                "actual_phase_durations_s": representative[
                    "actual_phase_durations_s"
                ],
            }
        )
    return summaries


def _clean_cost_design(r_min: float, r_max: float) -> dict[str, Any]:
    equally_spaced = np.linspace(r_min, r_max, 6)
    representative = sorted(
        {round(float(value), 6) for value in equally_spaced} | {0.0}
    )
    return {
        "status": "DESIGNED_NOT_EXECUTED",
        "matched_pacing_interval": [r_min, r_max],
        "representative_r_values": representative,
        "selection_basis": (
            "six equal interval coordinates plus exact balanced r=0; selected "
            "without cuff-force outcomes"
        ),
        "scheduler": "unchanged boundary-conditioned matched-pacing V2",
        "phase_durations_s": {"OUTBOUND": 2.2, "HOLD": 0.5, "RETURN": 2.2},
        "fixed_human_model": True,
        "primary_future_observation": "cumulative measured cuff-force norm integral",
        "force_based_control_or_selection": False,
        "value_imitation_or_rl": False,
    }


def _plot(summaries: list[dict[str, Any]], path: Path) -> None:
    r_values = np.asarray([row["coordination_r"] for row in summaries])
    valid = np.asarray([row["all_replicates_contract_valid"] for row in summaries])
    colors = np.where(valid, "tab:green", "tab:red")
    figure, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    axes[0].scatter(
        r_values,
        [max(abs(value) for value in row["terminal_dq_deg_s"]) for row in summaries],
        c=colors,
    )
    axes[0].axhline(2.0, color="black", linestyle=":")
    axes[0].set(
        title="RETURN terminal velocity criterion",
        xlabel="coordination r",
        ylabel="max |dq| [deg/s]",
    )
    axes[0].grid(True, alpha=0.3)

    axes[1].scatter(
        r_values,
        [row["minimum_truth_shank_clearance_mm"] for row in summaries],
        c=colors,
    )
    axes[1].axhline(0.0, color="black", linestyle=":")
    axes[1].set(
        title="Minimum shank-table clearance",
        xlabel="coordination r",
        ylabel="clearance [mm]",
    )
    axes[1].grid(True, alpha=0.3)

    scheduled = np.asarray(
        [row["scheduled_peak_abs_20ms_acceleration_deg_s2"] for row in summaries]
    )
    realized = np.asarray(
        [row["realized_peak_abs_20ms_acceleration_deg_s2"] for row in summaries]
    )
    axes[2].plot(r_values, scheduled[:, 0], label="scheduled hip")
    axes[2].plot(r_values, scheduled[:, 1], label="scheduled knee")
    axes[2].plot(r_values, realized[:, 0], linestyle="--", label="realized hip")
    axes[2].plot(r_values, realized[:, 1], linestyle="--", label="realized knee")
    axes[2].axhline(300.0, color="tab:blue", linestyle=":")
    axes[2].axhline(600.0, color="tab:orange", linestyle=":")
    axes[2].set(
        title="20 ms motion acceleration",
        xlabel="coordination r",
        ylabel="deg/s^2",
    )
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_matched_pacing_r_boundary_v1":
        raise ValueError("unexpected matched-pacing r-boundary schema")
    if config.get("status") != "PREREGISTERED_BEFORE_BOUNDARY_EXECUTION":
        raise ValueError("r-boundary config must remain preregistered")
    source = Path(config["scheduler_source"]["artifact"])
    if _sha256(source) != config["scheduler_source"]["sha256"]:
        raise ValueError("frozen V2 scheduler source artifact hash changed")
    if config["search"]["classification_uses_force"]:
        raise ValueError("boundary classification may not use cuff force")
    truth_human, control_model, model_version = _fixed_models(config)

    cases: list[dict[str, Any]] = []
    for r_value in config["search"]["lower_bound_reconfirmation"]:
        cases.append(
            _run_r(
                r_value=float(r_value),
                stage="lower_reconfirmation",
                replicate_index=0,
                config=config,
                truth_human=truth_human,
                control_human_model=control_model,
                control_model_version=model_version,
            )
        )
    for r_value in config["search"]["interior_reconfirmation"]:
        cases.append(
            _run_r(
                r_value=float(r_value),
                stage="interior_reconfirmation",
                replicate_index=0,
                config=config,
                truth_human=truth_human,
                control_human_model=control_model,
                control_model_version=model_version,
            )
        )

    coarse_cases = []
    for r_value in config["search"]["positive_coarse_grid"]:
        case = _run_r(
            r_value=float(r_value),
            stage="positive_coarse",
            replicate_index=0,
            config=config,
            truth_human=truth_human,
            control_human_model=control_model,
            control_model_version=model_version,
        )
        coarse_cases.append(case)
        cases.append(case)
    coarse_lower, coarse_upper, coarse_nonmonotonic = _coarse_bracket(coarse_cases)

    refined_values = refinement_grid(
        coarse_lower,
        coarse_upper,
        float(config["search"]["refinement_step"]),
    )
    for r_value in refined_values:
        cases.append(
            _run_r(
                r_value=r_value,
                stage="positive_refinement",
                replicate_index=0,
                config=config,
                truth_human=truth_human,
                control_human_model=control_model,
                control_model_version=model_version,
            )
        )

    primary = _first_cases_by_r(cases)
    positive_values = sorted(value for value in primary if value >= 0.4 - 1.0e-12)
    valid_positive = [value for value in positive_values if contract_valid(primary[value])]
    r_max = max(valid_positive) if valid_positive else None
    next_failure = (
        None
        if r_max is None
        else min(
            (
                value
                for value in positive_values
                if value > r_max and not contract_valid(primary[value])
            ),
            default=None,
        )
    )
    repeat_count = int(config["search"]["boundary_total_repeat_count"])
    if r_max is not None and next_failure is not None:
        for replicate_index in range(1, repeat_count):
            for r_value, stage in (
                (r_max, "boundary_pass_repeat"),
                (next_failure, "boundary_fail_repeat"),
            ):
                cases.append(
                    _run_r(
                        r_value=r_value,
                        stage=stage,
                        replicate_index=replicate_index,
                        config=config,
                        truth_human=truth_human,
                        control_human_model=control_model,
                        control_model_version=model_version,
                    )
                )

    summaries = _summaries(cases)
    summary_by_r = {row["coordination_r"]: row for row in summaries}
    lower = float(config["search"]["lower_bound_reconfirmation"][0])
    lower_valid = summary_by_r[lower]["all_replicates_contract_valid"]
    classification_consistent = all(
        row["classification_consistent"] for row in summaries
    )
    ordered_positive = [row for row in summaries if row["coordination_r"] >= 0.4]
    positive_statuses = [row["all_replicates_contract_valid"] for row in ordered_positive]
    monotonic = not any(
        (not left) and right
        for left, right in zip(positive_statuses[:-1], positive_statuses[1:])
    )
    step = float(config["search"]["refinement_step"])
    adjacent_bracket = bool(
        r_max is not None
        and next_failure is not None
        and np.isclose(next_failure - r_max, step, atol=1.0e-12, rtol=0.0)
    )
    repeated_boundary = bool(
        r_max is not None
        and next_failure is not None
        and summary_by_r[r_max]["replicate_count"] == repeat_count
        and summary_by_r[next_failure]["replicate_count"] == repeat_count
        and summary_by_r[r_max]["all_replicates_contract_valid"]
        and not summary_by_r[next_failure]["any_replicate_contract_valid"]
    )
    if (
        lower_valid
        and r_max is not None
        and adjacent_bracket
        and repeated_boundary
        and classification_consistent
        and monotonic
        and not coarse_nonmonotonic
    ):
        decision = "RB-A — MATCHED-PACING r INTERVAL VALIDATED"
    elif r_max is not None:
        decision = "RB-B — BOUNDARY REMAINS AMBIGUOUS / TOO SENSITIVE"
    else:
        decision = "RB-C — NO USEFUL FIXED-PACING INTERVAL BEYOND CURRENT INTERIOR POINTS"

    frozen_interval = None if decision.startswith("RB-B") or decision.startswith("RB-C") else [lower, r_max]
    cost_design = (
        None if frozen_interval is None else _clean_cost_design(lower, float(r_max))
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "matched_pacing_r_boundary.png"
    _plot(summaries, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": config["evidence_category"],
            "decision": decision,
            "config": config,
            "fixed_model_version": model_version,
            "tested_cases": cases,
            "point_summary": summaries,
            "boundary_analysis": {
                "coarse_bracket": [coarse_lower, coarse_upper],
                "refinement_values": refined_values,
                "r_min_matched_pacing": lower if lower_valid else None,
                "r_max_matched_pacing": r_max,
                "first_failing_r_above_boundary": next_failure,
                "boundary_resolution_r": step,
                "older_free_pacing_support_interval": config[
                    "older_free_pacing_support_interval"
                ],
                "frozen_matched_pacing_interval": frozen_interval,
                "classification_monotonic": monotonic,
                "classification_consistent_on_repeats": classification_consistent,
                "adjacent_pass_fail_bracket_observed": adjacent_bracket,
                "boundary_pass_fail_repeated": repeated_boundary,
                "force_used_for_boundary_selection": False,
                "interpretation": (
                    "largest validated grid point under this exact deterministic "
                    "V2 contract; not a continuous mathematical feasibility proof"
                ),
            },
            "next_clean_matched_pacing_cost_study": cost_design,
            "scope_invariants": config["scope"],
            "plot": str(plot_path),
        }
    )
    result_path = output_dir / "matched_pacing_r_boundary.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": decision,
                "boundary_analysis": payload["boundary_analysis"],
                "points": [
                    {
                        "r": row["coordination_r"],
                        "valid": row["all_replicates_contract_valid"],
                        "terminal_dq_deg_s": row["terminal_dq_deg_s"],
                        "clearance_mm": row["minimum_truth_shank_clearance_mm"],
                    }
                    for row in summaries
                ],
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.config, arguments.output_dir)


if __name__ == "__main__":
    main()
