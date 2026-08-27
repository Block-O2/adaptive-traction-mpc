#!/usr/bin/env python3
"""Replay the non-default single incumbent--challenger L4 prototype."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.oracle_chain_audit import audit_saved_sensor_case
from traction_mpc_stage4.reference import cold_start_teaching_reference
from traction_mpc_stage4.statistical_trust import (
    PRIMARY_STATISTICAL_L4,
    SENSITIVITY_STATISTICAL_L4,
    audit_statistical_trust_case,
)


def _write_candidate_csv(
    output_dir: Path, settings: dict[str, dict[str, Any]]
) -> None:
    fields = [
        "setting",
        "case",
        "challenger_index",
        "fit_end_time_s",
        "reference_epoch",
        "parameter_identification_status",
        "active_bound_count",
        "rank",
        "rrqr_rank",
        "condition_number",
        "control_model_status",
        "decision_time_s",
        "decision_reason",
        "decision_block_count",
        "validation_duration_s",
        "valid_measurements_accumulated_during_validation",
        "look_count",
        "final_delta_prior_mean_nms2",
        "final_delta_prior_upper_nms2",
        "final_delta_last_mean_nms2",
        "final_delta_last_upper_nms2",
        "oracle_improvement_vs_last_valid_nm",
        "proposed_model_distance_to_truth_span_l2",
        "reference_model_distance_to_truth_span_l2",
    ]
    with (output_dir / "candidate_decisions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for setting_name, setting in settings.items():
            for case_name, case in setting["cases"].items():
                for candidate in case["challengers"]:
                    evidence = (
                        candidate["evidence_history"][-1]
                        if candidate["evidence_history"]
                        else None
                    )
                    writer.writerow(
                        {
                            "setting": setting_name,
                            "case": case_name,
                            "challenger_index": candidate["challenger_index"],
                            "fit_end_time_s": candidate["fit_end_time_s"],
                            "reference_epoch": candidate["reference_epoch"],
                            "parameter_identification_status": candidate[
                                "parameter_identification_status"
                            ],
                            "active_bound_count": candidate["l3"][
                                "active_bound_count"
                            ],
                            "rank": candidate["l3"]["rank"],
                            "rrqr_rank": candidate["l3"]["rrqr_rank"],
                            "condition_number": candidate["l3"][
                                "condition_number"
                            ],
                            "control_model_status": candidate[
                                "control_model_status"
                            ],
                            "decision_time_s": candidate.get("decision_time_s"),
                            "decision_reason": candidate.get("decision_reason"),
                            "decision_block_count": candidate.get(
                                "decision_block_count"
                            ),
                            "validation_duration_s": candidate.get(
                                "validation_duration_s"
                            ),
                            "valid_measurements_accumulated_during_validation": (
                                candidate.get(
                                    "valid_measurements_accumulated_during_validation"
                                )
                            ),
                            "look_count": len(candidate["evidence_history"]),
                            "final_delta_prior_mean_nms2": (
                                evidence["against_population_prior"][
                                    "mean_difference_nms2"
                                ]
                                if evidence
                                else None
                            ),
                            "final_delta_prior_upper_nms2": (
                                evidence["against_population_prior"][
                                    "upper_bound_nms2"
                                ]
                                if evidence
                                else None
                            ),
                            "final_delta_last_mean_nms2": (
                                evidence["against_last_valid"][
                                    "mean_difference_nms2"
                                ]
                                if evidence
                                else None
                            ),
                            "final_delta_last_upper_nms2": (
                                evidence["against_last_valid"][
                                    "upper_bound_nms2"
                                ]
                                if evidence
                                else None
                            ),
                            "oracle_improvement_vs_last_valid_nm": candidate.get(
                                "oracle_improvement_vs_last_valid_nm"
                            ),
                            "proposed_model_distance_to_truth_span_l2": candidate.get(
                                "proposed_model_distance_to_truth_span_l2"
                            ),
                            "reference_model_distance_to_truth_span_l2": candidate.get(
                                "reference_model_distance_to_truth_span_l2"
                            ),
                        }
                    )


def _write_summary(
    output_dir: Path, settings: dict[str, dict[str, Any]]
) -> None:
    lines = [
        "# Stage-4 single incumbent--challenger L4 offline audit",
        "",
        "No setting is production-default. Oracle data was appended only after each online-style decision.",
        "",
        "## Primary pre-registered setting",
        "",
        f"Anytime familywise alpha: {PRIMARY_STATISTICAL_L4.familywise_alpha}; "
        "challenger spending: alpha_j=alpha/[j(j+1)]; "
        f"looks: {PRIMARY_STATISTICAL_L4.scheduled_looks}; "
        "two fixed references per look.",
        "",
        "| case | challengers P/R/Pending | first promotion s/phase | decided validation durations s | longest no-promotion s | promoted oracle worse | rejected oracle better | prior->final oracle Nm | beta truth prior->final |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    primary = settings[PRIMARY_STATISTICAL_L4.name]
    for case_name, case in primary["cases"].items():
        counts = case["counts"]
        starvation = case["starvation"]
        selection = case["oracle_selection_audit"]
        first = starvation["first_promotion_time_s"]
        phase = starvation["first_promotion_reference_phase_fraction"]
        full = case["full_trace_oracle_prediction"]
        durations = [
            item["validation_duration_s"]
            for item in case["challengers"]
            if "validation_duration_s" in item
        ]
        lines.append(
            f'| {case_name} | {counts["challenger_count"]} '
            f'{counts["promoted"]}/{counts["statistically_rejected"]}/'
            f'{counts["pending"]} | '
            f'{f"{first:.3f}/{phase:.3f}" if first is not None else "none"} | '
            f'{",".join(f"{value:.3f}" for value in durations) or "none"} | '
            f'{starvation["longest_no_promotion_interval_s"]:.3f} | '
            f'{case["compensation_diagnostic"]["promoted_with_oracle_worsening_count"]} | '
            f'{selection["statistically_rejected"]["oracle_improved_count"]} | '
            f'{full["population_prior_error_nm"]:.3f}->{full["final_retained_error_nm"]:.3f} | '
            f'{case["population_prior_distance_to_truth_span_l2"]:.3f}->'
            f'{case["final_retained_distance_to_truth_span_l2"]:.3f} |'
        )
    lines.extend(
        [
            "",
            "## Pre-declared sensitivity settings",
            "",
            "| setting | case | challengers P/R/Pending | first promotion s | promoted oracle worse |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for setting_name, setting in settings.items():
        if setting_name == PRIMARY_STATISTICAL_L4.name:
            continue
        for case_name, case in setting["cases"].items():
            counts = case["counts"]
            first = case["starvation"]["first_promotion_time_s"]
            lines.append(
                f'| {setting_name} | {case_name} | {counts["challenger_count"]} '
                f'{counts["promoted"]}/'
                f'{counts["statistically_rejected"]}/'
                f'{counts["pending"]} | '
                f'{f"{first:.3f}" if first is not None else "none"} | '
                f'{case["compensation_diagnostic"]["promoted_with_oracle_worsening_count"]} |'
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

    human, _ = registered_cold_start_perturbed_human()
    true_beta = nominal_base_parameters(human)
    initial_q = cold_start_teaching_reference(0.0).q_rad
    replay_details = {}
    terminations = {}
    for case in sensor_realism_cases():
        _, replay_details[case.name] = audit_saved_sensor_case(
            args.source_dir, case
        )
        source = json.loads(
            (args.source_dir / f"{case.name}.json").read_text(encoding="utf-8")
        )
        terminations[case.name] = {
            "termination_reason": source["termination_reason"],
            "completed_duration_s": source["completed_duration_s"],
        }

    configurations = (PRIMARY_STATISTICAL_L4, *SENSITIVITY_STATISTICAL_L4)
    settings: dict[str, dict[str, Any]] = {}
    for configuration in configurations:
        cases = {}
        for case in sensor_realism_cases():
            cases[case.name] = audit_statistical_trust_case(
                case=case,
                details=replay_details[case.name],
                initial_q_prior_rad=initial_q,
                true_beta=true_beta,
                statistical_config=configuration,
            )
        settings[configuration.name] = {
            "predeclared_before_oracle_audit": True,
            "selected_by_oracle_outcome": False,
            "cases": cases,
        }

    audit = {
        "evidence_category": "offline_single_challenger_statistical_prototype_and_oracle_diagnostic",
        "formal_experiment": False,
        "production_default": False,
        "primary_setting_selected_before_replay": PRIMARY_STATISTICAL_L4.name,
        "sensitivity_settings_are_diagnostic_not_model_selection": True,
        "oracle_scope": "post_decision_only",
        "new_closed_loop_rollouts_run": False,
        "production_estimator_controller_settings_changed": False,
        "source_dir": str(args.source_dir),
        "source_terminations": terminations,
        "settings": settings,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_candidate_csv(args.output_dir, settings)
    _write_summary(args.output_dir, settings)


if __name__ == "__main__":
    main()
