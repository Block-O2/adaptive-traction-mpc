#!/usr/bin/env python3
"""Run the offline Stage-4 measurement/estimator/control-prediction oracle audit."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.oracle_chain_audit import audit_saved_sensor_case


def _metric(case: dict[str, Any], path: tuple[str, ...]) -> float:
    value: Any = case
    for key in path:
        value = value[key]
    return float(value)


def _attribution(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    names = list(cases)
    rows = []
    for name in names:
        case = cases[name]
        rows.append(
            {
                "case": name,
                "duration_s": case["measurement"]["duration_s"],
                "measurement_age_ms": case["measurement"]["mean_age_ms"],
                "frontend_q_arrival_rmse_deg": _metric(
                    case,
                    ("measurement", "arrival_aligned", "human_q_deg", "combined_rmse"),
                ),
                "frontend_dq_arrival_rmse_deg_s": _metric(
                    case,
                    ("measurement", "arrival_aligned", "human_dq_deg_s", "combined_rmse"),
                ),
                "force_arrival_rmse_n": _metric(
                    case,
                    ("measurement", "arrival_aligned", "cuff_force_n", "combined_rmse"),
                ),
                "moment_arrival_rmse_nm": _metric(
                    case,
                    ("measurement", "arrival_aligned", "cuff_moment_nm", "combined_rmse"),
                ),
                "estimated_q_arrival_rmse_deg": _metric(
                    case,
                    ("estimator", "geometry", "state_arrival_aligned_q_deg", "combined_rmse"),
                ),
                "estimated_dq_arrival_rmse_deg_s": _metric(
                    case,
                    ("estimator", "geometry", "state_arrival_aligned_dq_deg_s", "combined_rmse"),
                ),
                "parameter_distance_prior_span_l2": _metric(
                    case,
                    ("estimator", "dynamics", "population_prior_distance_to_truth_span_l2"),
                ),
                "parameter_distance_final_span_l2": _metric(
                    case,
                    ("estimator", "dynamics", "final_distance_to_truth_span_l2"),
                ),
                "E_meas_prior_nm": _metric(
                    case,
                    ("prediction", "population_prior", "E_meas_instantaneous", "combined_rmse_nm"),
                ),
                "E_meas_final_nm": _metric(
                    case,
                    ("prediction", "final_last_valid", "E_meas_instantaneous", "combined_rmse_nm"),
                ),
                "E_oracle_prior_nm": _metric(
                    case,
                    (
                        "prediction",
                        "population_prior",
                        "E_oracle_sample_aligned_full_chain",
                        "combined_rmse_nm",
                    ),
                ),
                "E_oracle_final_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "E_oracle_sample_aligned_full_chain",
                        "combined_rmse_nm",
                    ),
                ),
                "E_parameter_only_final_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "E_oracle_parameter_only",
                        "combined_rmse_nm",
                    ),
                ),
                "E_state_geometry_only_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "E_oracle_state_geometry_only_with_true_beta",
                        "combined_rmse_nm",
                    ),
                ),
                "measurement_target_to_oracle_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "measurement_target_to_oracle",
                        "combined_rmse_nm",
                    ),
                ),
                "measurement_target_true_geometry_to_oracle_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "measurement_target_true_geometry_to_oracle",
                        "combined_rmse_nm",
                    ),
                ),
                "oracle_wrench_true_geometry_to_oracle_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "oracle_wrench_target_true_geometry_to_oracle",
                        "combined_rmse_nm",
                    ),
                ),
                "estimated_geometry_generalized_input_error_nm": _metric(
                    case,
                    (
                        "prediction",
                        "final_last_valid",
                        "estimated_vs_true_geometry_generalized_input",
                        "combined_rmse_nm",
                    ),
                ),
            }
        )
    by_name = {item["case"]: item for item in rows}
    contrasts = {}
    pairs = (
        ("random_noise", "noise_200hz", "ideal_200hz"),
        ("bias_and_drift", "noise_bias_drift_200hz", "noise_200hz"),
        ("delay_plus_bias", "noise_bias_delay_200hz", "noise_bias_drift_200hz"),
        ("100hz_zoh_plus_combined", "noise_bias_delay_100hz", "noise_bias_delay_200hz"),
    )
    contrast_metrics = (
        "frontend_q_arrival_rmse_deg",
        "frontend_dq_arrival_rmse_deg_s",
        "force_arrival_rmse_n",
        "moment_arrival_rmse_nm",
        "E_meas_final_nm",
        "E_oracle_final_nm",
    )
    for label, changed, reference in pairs:
        contrasts[label] = {
            "changed_case": changed,
            "reference_case": reference,
            "absolute_metric_change": {
                metric: by_name[changed][metric] - by_name[reference][metric]
                for metric in contrast_metrics
            },
            "warning": (
                "Registered closed-loop trajectories differ and delayed cases terminate early; "
                "this is layer attribution evidence, not a matched-state causal decomposition."
            ),
        }
    return {"case_rows": rows, "registered_case_contrasts": contrasts}


def _write_measurement_csv(output_dir: Path, cases: dict[str, dict[str, Any]]) -> None:
    fields = [
        "case",
        "alignment",
        "quantity",
        "bias",
        "component_rmse",
        "combined_rmse",
        "peak_norm",
    ]
    with (output_dir / "measurement_oracle_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, case in cases.items():
            for alignment in ("aligned", "arrival_aligned"):
                for quantity, metrics in case["measurement"][alignment].items():
                    writer.writerow(
                        {
                            "case": name,
                            "alignment": alignment,
                            "quantity": quantity,
                            "bias": json.dumps(metrics["bias"]),
                            "component_rmse": json.dumps(metrics["component_rmse"]),
                            "combined_rmse": metrics["combined_rmse"],
                            "peak_norm": metrics["peak_norm"],
                        }
                    )


def _write_parameter_csv(output_dir: Path, cases: dict[str, dict[str, Any]]) -> None:
    fields = [
        "case",
        "name",
        "population_prior",
        "registered_true",
        "final_last_valid",
        "absolute_error",
        "normalized_error_fraction_of_span",
    ]
    with (output_dir / "parameter_oracle_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, case in cases.items():
            for parameter in case["estimator"]["dynamics"]["parameters"]:
                writer.writerow({"case": name, **parameter})


def _write_attempt_csv(output_dir: Path, cases: dict[str, dict[str, Any]]) -> None:
    fields = [
        "case",
        "attempt_index",
        "arrival_time_s",
        "sample_time_s",
        "accepted",
        "reason",
        "rank",
        "rrqr_rank",
        "condition_number",
        "candidate_residual_rms_nms",
        "bound_hit",
        "active_or_pressured_bounds",
        "candidate_distance_to_truth_span_l2",
        "last_valid_before_distance_to_truth_span_l2",
        "last_valid_after_distance_to_truth_span_l2",
        "accepted_update_movement",
        "candidate_E_meas_nm",
        "candidate_E_oracle_nm",
        "last_valid_after_E_meas_nm",
        "last_valid_after_E_oracle_nm",
        "measurement_fit_improves_without_oracle_improvement",
        "unconstrained_beta",
        "candidate_beta",
        "last_valid_after_beta",
    ]
    with (output_dir / "dynamics_attempt_oracle_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, case in cases.items():
            for attempt in case["estimator"]["dynamics"]["attempts"]:
                writer.writerow(
                    {
                        "case": name,
                        **{
                            key: attempt[key]
                            for key in fields
                            if key in attempt and key != "case"
                        },
                        "active_or_pressured_bounds": json.dumps(
                            attempt["active_or_pressured_bounds"]
                        ),
                        "candidate_E_meas_nm": attempt["candidate_prediction"][
                            "E_meas_instantaneous"
                        ]["combined_rmse_nm"],
                        "candidate_E_oracle_nm": attempt["candidate_prediction"][
                            "E_oracle_sample_aligned_full_chain"
                        ]["combined_rmse_nm"],
                        "last_valid_after_E_meas_nm": attempt[
                            "last_valid_after_prediction"
                        ]["E_meas_instantaneous"]["combined_rmse_nm"],
                        "last_valid_after_E_oracle_nm": attempt[
                            "last_valid_after_prediction"
                        ]["E_oracle_sample_aligned_full_chain"]["combined_rmse_nm"],
                        "measurement_fit_improves_without_oracle_improvement": attempt[
                            "candidate_measurement_fit_improves_without_oracle_improvement"
                        ],
                        "unconstrained_beta": json.dumps(attempt["unconstrained_beta"]),
                        "candidate_beta": json.dumps(attempt["candidate_beta"]),
                        "last_valid_after_beta": json.dumps(
                            attempt["last_valid_after_beta"]
                        ),
                    }
                )


def _write_summary(output_dir: Path, audit: dict[str, Any]) -> None:
    lines = [
        "# Stage-4 oracle chain audit",
        "",
        "Offline replay of saved registered trajectories. Oracle data did not enter the estimator.",
        "",
        "| case | age ms | frontend q RMSE deg | F RMSE N | geom state q RMSE deg | dyn A/R | final beta dist/span | E_meas prior->final Nm | E_oracle prior->final Nm |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audit["attribution"]["case_rows"]:
        dynamics = audit["cases"][row["case"]]["estimator"]["dynamics"]
        lines.append(
            f'| {row["case"]} | {row["measurement_age_ms"]:.2f} | '
            f'{row["frontend_q_arrival_rmse_deg"]:.3f} | '
            f'{row["force_arrival_rmse_n"]:.3f} | '
            f'{row["estimated_q_arrival_rmse_deg"]:.3f} | '
            f'{dynamics["accepted_updates"]}/{dynamics["rejected_updates"]} | '
            f'{row["parameter_distance_final_span_l2"]:.3f} | '
            f'{row["E_meas_prior_nm"]:.3f}->{row["E_meas_final_nm"]:.3f} | '
            f'{row["E_oracle_prior_nm"]:.3f}->{row["E_oracle_final_nm"]:.3f} |'
        )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    cases: dict[str, dict[str, Any]] = {}
    for case in sensor_realism_cases():
        summary, details = audit_saved_sensor_case(args.source_dir, case)
        source_summary = json.loads(
            (args.source_dir / f"{case.name}.json").read_text(encoding="utf-8")
        )
        summary["saved_rollout_termination"] = source_summary["termination_reason"]
        summary["saved_rollout_completed_duration_s"] = source_summary[
            "completed_duration_s"
        ]
        cases[case.name] = summary
        np.savez_compressed(args.output_dir / f"{case.name}_diagnostic.npz", **details)

    audit = {
        "evidence_category": "offline_oracle_diagnostic",
        "formal_experiment": False,
        "source_dir": str(args.source_dir),
        "oracle_scope": "diagnostic_only_never_entered_online_estimator_or_controller",
        "estimator_logic_changed": False,
        "controller_or_scientific_settings_changed": False,
        "new_controller_rollouts_run": False,
        "cases": cases,
        "attribution": _attribution(cases),
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_measurement_csv(args.output_dir, cases)
    _write_parameter_csv(args.output_dir, cases)
    _write_attempt_csv(args.output_dir, cases)
    _write_summary(args.output_dir, audit)


if __name__ == "__main__":
    main()
