#!/usr/bin/env python3
"""Offline Stage-4 hierarchical-trust and oracle selection-bias audit."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.hierarchical_trust import audit_hierarchical_trust_case
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.oracle_chain_audit import audit_saved_sensor_case
from traction_mpc_stage4.reference import cold_start_teaching_reference


def _write_candidate_csv(output_dir: Path, cases: dict[str, dict[str, Any]]) -> None:
    fields = [
        "case",
        "candidate_index",
        "fit_end_time_s",
        "validation_ready_time_s",
        "promotion_time_s",
        "parameter_identification_status",
        "control_model_status",
        "legacy_estimator_accepted",
        "legacy_estimator_reason",
        "rank",
        "rrqr_rank",
        "condition_number",
        "candidate_residual_rms_nms",
        "active_bound_count",
        "maximum_unconstrained_violation_fraction_of_span",
        "maximum_normalized_parameter_std",
        "validation_candidate_total_mse_nms2",
        "validation_prior_total_mse_nms2",
        "validation_last_valid_total_mse_nms2",
        "oracle_proposed_model_error_nm",
        "oracle_prior_error_nm",
        "oracle_last_valid_error_nm",
        "oracle_improvement_vs_last_valid_nm",
        "oracle_improvement_vs_prior_nm",
        "proposed_model_distance_to_truth_span_l2",
        "reference_model_distance_to_truth_span_l2",
        "truth_distance_change_from_last_valid_span_l2",
        "proposed_model_distance_to_prior_span_l2",
    ]
    with (output_dir / "candidate_audit.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, case in cases.items():
            for candidate in case["L3_L4_candidates"]:
                l3 = candidate["l3"]
                writer.writerow(
                    {
                        "case": name,
                        **{
                            key: candidate.get(key)
                            for key in fields
                            if key not in {"case"}
                        },
                        "rank": l3["rank"],
                        "rrqr_rank": l3["rrqr_rank"],
                        "condition_number": l3["condition_number"],
                        "candidate_residual_rms_nms": l3[
                            "candidate_residual_rms_nms"
                        ],
                        "active_bound_count": l3["active_bound_count"],
                        "maximum_unconstrained_violation_fraction_of_span": l3[
                            "unconstrained_normalized_bound_violation"
                        ]["maximum_fraction_of_span"],
                        "maximum_normalized_parameter_std": l3["uncertainty"][
                            "maximum_normalized_parameter_std"
                        ],
                    }
                )


def _write_summary(output_dir: Path, audit: dict[str, Any]) -> None:
    lines = [
        "# Stage-4 hierarchical trust offline audit",
        "",
        "The prototype is not production-default. Oracle data was appended only after each causal promotion decision.",
        "",
        "| case | L1 valid/invalid | L2 valid/invalid | candidates | promoted | valid unpromoted | pending | first promotion s | max no-promotion s | promoted/nonpromoted oracle median Nm | rejected-better pair probability | full-trace oracle prior->final Nm | final/prior truth distance |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, case in audit["cases"].items():
        starvation = case["starvation"]
        selection = case["selection_bias_oracle_audit"]
        promoted = selection["promoted"]
        rejected = selection["valid_nonpromoted"]
        first = starvation["first_promotion_time_s"]
        lines.append(
            f'| {name} | {case["L1"]["valid_count"]}/{case["L1"]["invalid_count"]} | '
            f'{case["L2"]["valid_count"]}/{case["L2"]["invalid_count"]} | '
            f'{starvation["valid_candidate_count"]} | {starvation["promoted_candidate_count"]} | '
            f'{starvation["valid_but_unpromoted_candidate_count"]} | '
            f'{starvation["pending_insufficient_future_validation_count"]} | '
            f'{f"{first:.3f}" if first is not None else "none"} | '
            f'{starvation["longest_no_promotion_interval_s"]:.3f} | '
            f'{promoted["oracle_error_median_nm"]:.3f}/{rejected["oracle_error_median_nm"]:.3f} | '
            f'{selection["cross_pair_probability_nonpromoted_has_greater_phase_matched_oracle_improvement"]:.3f} | '
            f'{case["full_trace_oracle_prediction"]["population_prior_error_nm"]:.3f}->'
            f'{case["full_trace_oracle_prediction"]["final_retained_error_nm"]:.3f} | '
            f'{case["final_distance_to_truth_span_l2"]:.3f}/'
            f'{case["population_prior_distance_to_truth_span_l2"]:.3f} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    human, _ = registered_cold_start_perturbed_human()
    true_beta = nominal_base_parameters(human)
    initial_q = cold_start_teaching_reference(0.0).q_rad
    cases: dict[str, dict[str, Any]] = {}
    source_terminations = {}
    for case in sensor_realism_cases():
        _, details = audit_saved_sensor_case(args.source_dir, case)
        cases[case.name] = audit_hierarchical_trust_case(
            case=case,
            details=details,
            initial_q_prior_rad=initial_q,
            true_beta=true_beta,
        )
        source = json.loads(
            (args.source_dir / f"{case.name}.json").read_text(encoding="utf-8")
        )
        source_terminations[case.name] = {
            "termination_reason": source["termination_reason"],
            "completed_duration_s": source["completed_duration_s"],
        }

    audit = {
        "evidence_category": "offline_prototype_and_oracle_diagnostic",
        "formal_experiment": False,
        "production_default": False,
        "oracle_scope": "post_decision_selection_bias_diagnostic_only",
        "source_dir": str(args.source_dir),
        "source_terminations": source_terminations,
        "estimator_formulation_bounds_controller_settings_changed": False,
        "new_closed_loop_rollouts_run": False,
        "cases": cases,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_candidate_csv(args.output_dir, cases)
    _write_summary(args.output_dir, audit)


if __name__ == "__main__":
    main()
