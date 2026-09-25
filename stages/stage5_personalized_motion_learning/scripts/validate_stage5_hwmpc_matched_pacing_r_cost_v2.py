#!/usr/bin/env python3
"""Clean matched-pacing cuff-interaction study on the frozen V2 r domain."""

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
from scipy.stats import spearmanr

from validate_stage5_human_waypoint_shadow import _jsonable
from validate_stage5_human_waypoint_trajectory_diversity import (
    _path_distance,
    _sequence_metrics,
)
from validate_stage5_hwmpc_matched_pacing_r_cost import _fixed_models
from validate_stage5_hwmpc_matched_pacing_scheduler import _run_profile


SCHEMA = "stage5_hwmpc_matched_pacing_r_cost_validation_v2"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_matched_pacing_r_cost_v2.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contract_valid(case: dict[str, Any]) -> bool:
    return bool(
        case["completed"]
        and case["matched_pacing_contract_passed"]
        and case["safety_contract_passed"]
    )


def _fit_r_squared(design: np.ndarray, outcome: np.ndarray) -> tuple[np.ndarray, float]:
    coefficients = np.linalg.lstsq(design, outcome, rcond=None)[0]
    fitted = design @ coefficients
    total = float(np.sum((outcome - np.mean(outcome)) ** 2))
    residual = float(np.sum((outcome - fitted) ** 2))
    r_squared = 1.0 if total <= 1.0e-15 else 1.0 - residual / total
    return coefficients, r_squared


def classify_conclusion(
    *,
    contract_valid: bool,
    relative_range: float,
    useful_relative_range: float,
    path_distance_deg: float,
    minimum_path_distance_deg: float,
    repeatability_passed: bool,
    numerical_separation: bool,
    absolute_spearman_rho: float,
    minimum_absolute_spearman_rho: float,
) -> str:
    if not contract_valid:
        return "RC2-D — EXECUTION CONTRACT INVALIDATES THE COMPARISON"
    path_passed = path_distance_deg >= minimum_path_distance_deg
    if relative_range >= useful_relative_range and path_passed and repeatability_passed:
        return "RC2-A — USEFUL MATCHED-PACING PATH/COST SEPARATION CONFIRMED"
    if (
        relative_range > 0.0
        and relative_range < useful_relative_range
        and path_passed
        and repeatability_passed
        and numerical_separation
        and absolute_spearman_rho >= minimum_absolute_spearman_rho
    ):
        return "RC2-B — PATH EFFECT IS CONSISTENT BUT SMALL"
    return "RC2-C — NO MEANINGFUL PATH/COST SEPARATION"


def _run_one(
    *,
    r_value: float,
    order_seed: int,
    config: dict[str, Any],
    truth_human: Any,
    control_human_model: Any,
    control_model_version: str,
) -> dict[str, Any]:
    case = _run_profile(
        profile={"name": f"clean_cost_r{r_value:+.3f}_seed{order_seed}", "r": r_value},
        config=config,
        truth_human=truth_human,
        control_human_model=control_human_model,
        control_model_version=control_model_version,
    )
    case["order_seed"] = int(order_seed)
    case["boundary_contract_valid"] = _contract_valid(case)
    case["mean_measured_cuff_force_n"] = float(
        case["cumulative_measured_cuff_force_n_s"] / 4.9
    )
    case["q_tracking_rmse_deg"] = case["metrics"]["estimated_q_tracking_rmse_deg"]
    case["dq_tracking_rmse_deg_s"] = case["metrics"][
        "estimated_dq_tracking_rmse_deg_s"
    ]
    case["trajectory_metrics"] = _sequence_metrics(case, r_value)
    return case


def _profile_summaries(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for r_value in sorted({float(case["coordination_r"]) for case in cases}):
        selected = [case for case in cases if case["coordination_r"] == r_value]
        force = np.asarray(
            [case["cumulative_measured_cuff_force_n_s"] for case in selected]
        )
        q_rmse = np.asarray([case["q_tracking_rmse_deg"] for case in selected])
        dq_rmse = np.asarray([case["dq_tracking_rmse_deg_s"] for case in selected])
        representative = selected[0]
        rows.append(
            {
                "coordination_r": r_value,
                "replicate_count": len(selected),
                "all_replicates_contract_valid": all(
                    _contract_valid(case) for case in selected
                ),
                "classification_consistent": len(
                    {_contract_valid(case) for case in selected}
                )
                == 1,
                "force_integral_mean_n_s": float(np.mean(force)),
                "force_integral_min_n_s": float(np.min(force)),
                "force_integral_max_n_s": float(np.max(force)),
                "force_integral_range_n_s": float(np.ptp(force)),
                "mean_cuff_force_n": float(
                    np.mean([case["mean_measured_cuff_force_n"] for case in selected])
                ),
                "peak_cuff_force_n": float(
                    np.max([case["peak_measured_cuff_force_n"] for case in selected])
                ),
                "peak_cuff_moment_nm": float(
                    np.max([case["peak_measured_cuff_moment_nm"] for case in selected])
                ),
                "q_tracking_rmse_deg": np.mean(q_rmse, axis=0),
                "dq_tracking_rmse_deg_s": np.mean(dq_rmse, axis=0),
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
                "maximum_robot_torque_fraction": representative[
                    "maximum_robot_torque_fraction"
                ],
                "shank_bed_contact_sample_count": representative[
                    "shank_bed_contact_sample_count"
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
                "representative_trajectory": representative["trajectory_metrics"],
            }
        )
    return rows


def _effect_analysis(
    summaries: list[dict[str, Any]], analysis_contract: dict[str, Any]
) -> dict[str, Any]:
    r_values = np.asarray([row["coordination_r"] for row in summaries], dtype=float)
    force = np.asarray([row["force_integral_mean_n_s"] for row in summaries])
    balanced_index = int(np.flatnonzero(np.isclose(r_values, 0.0))[0])
    balanced_force = float(force[balanced_index])
    force_range = float(np.ptp(force))
    relative_range = float(force_range / balanced_force)
    maximum_within_range = float(max(row["force_integral_range_n_s"] for row in summaries))
    repeatability_ratio = (
        0.0 if force_range <= 1.0e-15 else maximum_within_range / force_range
    )
    linear_design = np.column_stack((np.ones(len(r_values)), r_values))
    linear_coefficients, linear_r_squared = _fit_r_squared(linear_design, force)
    quadratic_design = np.column_stack(
        (np.ones(len(r_values)), r_values, r_values**2)
    )
    quadratic_coefficients, quadratic_r_squared = _fit_r_squared(
        quadratic_design, force
    )
    spearman = spearmanr(r_values, force)
    differences = np.diff(force)
    monotonic_decreasing = bool(np.all(differences < -1.0e-12))
    monotonic_increasing = bool(np.all(differences > 1.0e-12))
    effects_vs_balanced = [
        {
            "coordination_r": float(r_value),
            "delta_J_F_n_s": float(value - balanced_force),
            "percent_delta_vs_r0": float(100.0 * (value - balanced_force) / balanced_force),
        }
        for r_value, value in zip(r_values, force)
    ]

    endpoint_distances = {}
    endpoint_rows = (summaries[0], summaries[-1])
    for phase in ("OUTBOUND", "RETURN"):
        endpoint_distances[phase] = _path_distance(
            endpoint_rows[0]["representative_trajectory"]["realized_paths"][phase],
            endpoint_rows[1]["representative_trajectory"]["realized_paths"][phase],
        )
    mean_endpoint_path_distance = float(
        np.mean([row["rms_distance_deg"] for row in endpoint_distances.values()])
    )
    balanced_trajectory = summaries[balanced_index]["representative_trajectory"]
    path_vs_balanced = []
    for row in summaries:
        per_phase = {
            phase: _path_distance(
                balanced_trajectory["realized_paths"][phase],
                row["representative_trajectory"]["realized_paths"][phase],
            )
            for phase in ("OUTBOUND", "RETURN")
        }
        path_vs_balanced.append(
            {
                "coordination_r": row["coordination_r"],
                "per_phase": per_phase,
                "mean_phase_rms_distance_deg": float(
                    np.mean([item["rms_distance_deg"] for item in per_phase.values()])
                ),
            }
        )

    minimum_index = int(np.argmin(force))
    minimum_row = summaries[minimum_index]
    balanced_row = summaries[balanced_index]
    degradation = {
        "minimum_J_F_r": minimum_row["coordination_r"],
        "q_tracking_rmse_delta_deg": (
            np.asarray(minimum_row["q_tracking_rmse_deg"])
            - np.asarray(balanced_row["q_tracking_rmse_deg"])
        ),
        "dq_tracking_rmse_delta_deg_s": (
            np.asarray(minimum_row["dq_tracking_rmse_deg_s"])
            - np.asarray(balanced_row["dq_tracking_rmse_deg_s"])
        ),
        "terminal_max_abs_q_error_delta_deg": float(
            np.max(np.abs(minimum_row["terminal_q_error_deg"]))
            - np.max(np.abs(balanced_row["terminal_q_error_deg"]))
        ),
        "terminal_max_abs_dq_delta_deg_s": float(
            np.max(np.abs(minimum_row["terminal_dq_deg_s"]))
            - np.max(np.abs(balanced_row["terminal_dq_deg_s"]))
        ),
        "minimum_clearance_delta_mm": float(
            minimum_row["minimum_truth_shank_clearance_mm"]
            - balanced_row["minimum_truth_shank_clearance_mm"]
        ),
        "maximum_torque_fraction_delta": float(
            minimum_row["maximum_robot_torque_fraction"]
            - balanced_row["maximum_robot_torque_fraction"]
        ),
    }
    numerical_separation = bool(
        force_range > max(1.0e-9, 3.0 * maximum_within_range)
    )
    repeatability_passed = bool(
        repeatability_ratio
        <= analysis_contract["maximum_within_r_range_fraction_of_between_r_range"]
    )
    return {
        "J_F_range_n_s": force_range,
        "J_F_range_percent_vs_r0": 100.0 * relative_range,
        "J_F_min_n_s": float(np.min(force)),
        "J_F_max_n_s": float(np.max(force)),
        "balanced_r0_J_F_n_s": balanced_force,
        "effect_vs_r0": effects_vs_balanced,
        "monotonic_decreasing": monotonic_decreasing,
        "monotonic_increasing": monotonic_increasing,
        "spearman_rho": float(spearman.statistic),
        "spearman_pvalue_descriptive": float(spearman.pvalue),
        "linear_intercept_n_s": float(linear_coefficients[0]),
        "linear_slope_n_s_per_r": float(linear_coefficients[1]),
        "linear_r_squared": linear_r_squared,
        "quadratic_coefficients_intercept_linear_quadratic": quadratic_coefficients,
        "quadratic_r_squared": quadratic_r_squared,
        "quadratic_incremental_r_squared": quadratic_r_squared - linear_r_squared,
        "maximum_within_r_repeat_range_n_s": maximum_within_range,
        "within_to_between_range_ratio": repeatability_ratio,
        "repeatability_passed": repeatability_passed,
        "numerical_separation_above_repeatability_scale": numerical_separation,
        "endpoint_path_distance": endpoint_distances,
        "mean_endpoint_phase_rms_path_distance_deg": mean_endpoint_path_distance,
        "path_distance_vs_balanced": path_vs_balanced,
        "minimum_J_F_execution_tradeoff_vs_r0": degradation,
        "repeatability_interpretation": (
            "order-only deterministic repeats; equality is reproducibility, not "
            "stochastic robustness"
        ),
    }


def _plot(summaries: list[dict[str, Any]], effect: dict[str, Any], path: Path) -> None:
    colors = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(summaries)))
    figure, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    for color, row in zip(colors, summaries, strict=True):
        for phase, linestyle in (("OUTBOUND", "-"), ("RETURN", "--")):
            q = np.degrees(
                np.asarray(
                    row["representative_trajectory"]["realized_paths"][phase]["q_rad"]
                )
            )
            axes[0].plot(q[:, 0], q[:, 1], color=color, linestyle=linestyle)
        axes[0].plot([], [], color=color, label=f"r={row['coordination_r']:+.2f}")
    axes[0].set(
        title="Matched-pacing realized q1-q2 paths",
        xlabel="q1 [deg]",
        ylabel="q2 [deg]",
    )
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)

    r_values = np.asarray([row["coordination_r"] for row in summaries])
    force = np.asarray([row["force_integral_mean_n_s"] for row in summaries])
    axes[1].plot(r_values, force, marker="o", color="black", label="J_F")
    linear = effect["linear_intercept_n_s"] + effect["linear_slope_n_s_per_r"] * r_values
    quadratic_coefficients = np.asarray(
        effect["quadratic_coefficients_intercept_linear_quadratic"]
    )
    quadratic = (
        quadratic_coefficients[0]
        + quadratic_coefficients[1] * r_values
        + quadratic_coefficients[2] * r_values**2
    )
    axes[1].plot(r_values, linear, linestyle="--", label="linear fit")
    axes[1].plot(r_values, quadratic, linestyle=":", label="quadratic fit")
    axes[1].set(
        title="Primary outcome over fixed 4.9 s",
        xlabel="coordination r",
        ylabel="J_F [N s]",
    )
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    q_rmse = np.asarray([row["q_tracking_rmse_deg"] for row in summaries])
    axes[2].plot(r_values, q_rmse[:, 0], marker="o", label="q1 RMSE")
    axes[2].plot(r_values, q_rmse[:, 1], marker="o", label="q2 RMSE")
    clearance_axis = axes[2].twinx()
    clearance_axis.plot(
        r_values,
        [row["minimum_truth_shank_clearance_mm"] for row in summaries],
        color="tab:green",
        marker="s",
        linestyle="--",
        label="clearance",
    )
    axes[2].set(
        title="Tracking and clearance tradeoff",
        xlabel="coordination r",
        ylabel="q tracking RMSE [deg]",
    )
    clearance_axis.set_ylabel("minimum clearance [mm]", color="tab:green")
    axes[2].legend(loc="upper left")
    clearance_axis.legend(loc="upper right")
    axes[2].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_matched_pacing_r_cost_v2":
        raise ValueError("unexpected clean matched-pacing cost schema")
    if config.get("status") != "PREREGISTERED_BEFORE_CLEAN_COST_EXECUTION":
        raise ValueError("clean matched-pacing cost config must remain preregistered")
    domain_path = Path(config["frozen_domain_source"]["path"])
    if _sha256(domain_path) != config["frozen_domain_source"]["sha256"]:
        raise ValueError("frozen matched-pacing domain config hash changed")
    domain = json.loads(domain_path.read_text(encoding="utf-8"))
    points = list(config["coordination"]["preregistered_r_values"])
    if points != domain["next_clean_cost_study"]["representative_r_values"]:
        raise ValueError("cost-study points differ from frozen domain")
    if config["coordination"]["force_used_for_selection_or_adaptation"]:
        raise ValueError("force may not select or adapt r")
    truth_human, control_model, model_version = _fixed_models(config)

    cases = []
    for order_seed in config["repeatability"]["order_randomization_seeds"]:
        rng = np.random.default_rng(int(order_seed))
        for index in rng.permutation(len(points)):
            cases.append(
                _run_one(
                    r_value=float(points[int(index)]),
                    order_seed=int(order_seed),
                    config=config,
                    truth_human=truth_human,
                    control_human_model=control_model,
                    control_model_version=model_version,
                )
            )
    summaries = _profile_summaries(cases)
    effect = _effect_analysis(summaries, config["analysis_contract"])
    contract_valid = all(_contract_valid(case) for case in cases)
    analysis = config["analysis_contract"]
    decision = classify_conclusion(
        contract_valid=contract_valid,
        relative_range=effect["J_F_range_percent_vs_r0"] / 100.0,
        useful_relative_range=analysis["minimum_relative_J_F_range_for_RC2_A"],
        path_distance_deg=effect["mean_endpoint_phase_rms_path_distance_deg"],
        minimum_path_distance_deg=analysis[
            "minimum_mean_phase_rms_path_distance_deg_for_useful_path_separation"
        ],
        repeatability_passed=effect["repeatability_passed"],
        numerical_separation=effect["numerical_separation_above_repeatability_scale"],
        absolute_spearman_rho=abs(effect["spearman_rho"]),
        minimum_absolute_spearman_rho=analysis[
            "minimum_absolute_spearman_rho_for_consistent_small_effect"
        ],
    )
    if decision.startswith("RC2-A"):
        next_step = {
            "learning_justified": True,
            "design_only": (
                "learn a bounded Human-waypoint/r policy over the frozen interval "
                "using J_F as an offline trajectory-level target, with the unchanged "
                "V2 feasibility contract retained outside learning"
            ),
            "implemented": False,
        }
    else:
        next_step = {
            "learning_justified": False,
            "reason": (
                "the fixed-Human deterministic J_F effect does not meet the frozen "
                "5% useful-separation criterion"
            ),
            "single_next_scientific_question": (
                "Does the small matched-pacing coordination effect persist above "
                "measurement and Human/interface variability across supported "
                "personalized Human conditions?"
            ),
            "implemented": False,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "matched_pacing_r_cost_v2.png"
    _plot(summaries, effect, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": config["evidence_category"],
            "decision": decision,
            "config": config,
            "fixed_model_version": model_version,
            "cases": cases,
            "profile_summary": summaries,
            "primary_analysis": effect,
            "criteria_observed": {
                "all_execution_contracts_valid": contract_valid,
                "relative_J_F_range_meets_5_percent_useful_threshold": bool(
                    effect["J_F_range_percent_vs_r0"]
                    >= 100.0 * analysis["minimum_relative_J_F_range_for_RC2_A"]
                ),
                "path_separation_passed": bool(
                    effect["mean_endpoint_phase_rms_path_distance_deg"]
                    >= analysis[
                        "minimum_mean_phase_rms_path_distance_deg_for_useful_path_separation"
                    ]
                ),
                "repeatability_passed": effect["repeatability_passed"],
                "monotonicity_consistency_passed": bool(
                    abs(effect["spearman_rho"])
                    >= analysis[
                        "minimum_absolute_spearman_rho_for_consistent_small_effect"
                    ]
                ),
            },
            "learning_decision": next_step,
            "scope_invariants": config["scope"],
            "plot": str(plot_path),
        }
    )
    result_path = output_dir / "matched_pacing_r_cost_v2.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            _jsonable({
                "decision": decision,
                "criteria_observed": payload["criteria_observed"],
                "primary_analysis": effect,
                "profiles": [
                    {
                        "r": row["coordination_r"],
                        "J_F_n_s": row["force_integral_mean_n_s"],
                        "mean_force_n": row["mean_cuff_force_n"],
                        "q_rmse_deg": row["q_tracking_rmse_deg"],
                        "clearance_mm": row["minimum_truth_shank_clearance_mm"],
                    }
                    for row in summaries
                ],
                "output_dir": str(output_dir),
            }),
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
