#!/usr/bin/env python3
"""Reconstruct every dynamics-ID attempt for baseline and ungated hybrid traces."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.dynamics_failure_audit import replay_dynamics_candidates
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human


MODES = ("existing_cem", "cem_plus_smooth_local_refinement")


def _mode_summary(mode_result: dict[str, Any]) -> dict[str, Any]:
    attempts = mode_result["attempts"]
    bound_counts = Counter(
        component["name"]
        for attempt in attempts
        for component in attempt["bound_components"]
        if component["constrained_hit"]
    )
    reason_counts = Counter(
        reason
        for attempt in attempts
        for reason in attempt["reason"].split(",")
        if reason != "accepted"
    )
    accepted = [item for item in attempts if item["accepted"]]
    return {
        "attempt_count": len(attempts),
        "accepted_count": len(accepted),
        "rejected_count": len(attempts) - len(accepted),
        "first_accepted_wall_time_s": (
            None if not accepted else accepted[0]["wall_time_s"]
        ),
        "first_accepted_reference_phase_s": (
            None if not accepted else accepted[0]["reference_phase_s"]
        ),
        "reason_counts": dict(reason_counts),
        "bound_hit_component_counts": dict(bound_counts),
        "condition_number": {
            "minimum": float(min(item["condition_number"] for item in attempts)),
            "maximum": float(max(item["condition_number"] for item in attempts)),
        },
        "candidate_residual_rms_nms": {
            "minimum": float(
                min(item["candidate_residual_rms_nms"] for item in attempts)
            ),
            "maximum": float(
                max(item["candidate_residual_rms_nms"] for item in attempts)
            ),
        },
    }


def _write_summary(output_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Stage 4 dynamics-estimator bound-hit diagnosis",
        "",
        "Offline reconstruction from the saved registered A/B traces. Estimator logic, bounds, and gates are unchanged.",
        "",
        "| mode | attempts | accepted | first trust wall/phase | bound-hit components | rejection reasons |",
        "|---|---:|---:|---:|---|---|",
    ]
    for mode in MODES:
        row = result["summary"][mode]
        trust = (
            "-"
            if row["first_accepted_wall_time_s"] is None
            else f'{row["first_accepted_wall_time_s"]:.3f}/'
            f'{row["first_accepted_reference_phase_s"]:.3f} s'
        )
        lines.append(
            f'| {mode} | {row["attempt_count"]} | {row["accepted_count"]} | '
            f'{trust} | {row["bound_hit_component_counts"]} | '
            f'{row["reason_counts"]} |'
        )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _write_candidate_csv(output_dir: Path, result: dict[str, Any]) -> None:
    parameter_names = result["modes"][MODES[0]]["parameter_names"]
    fieldnames = [
        "mode",
        "attempt_index",
        "wall_time_s",
        "reference_phase_s",
        "accepted",
        "reason",
        "rank",
        "rrqr_rank",
        "condition_number",
        "candidate_residual_rms_nms",
        "old_residual_rms_nms",
        *[f"beta_{name}" for name in parameter_names],
        "bound_hit_components",
        "unconstrained_bound_pressure",
        "distance_to_prior_span_normalized_l2",
        "distance_to_true_span_normalized_l2",
        "generalized_torque_prediction_combined_rmse_nm",
    ]
    with (output_dir / "dynamics_candidates.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for mode in MODES:
            for attempt in result["modes"][mode]["attempts"]:
                hit = [
                    item for item in attempt["bound_components"] if item["constrained_hit"]
                ]
                pressure = [
                    item
                    for item in attempt["bound_components"]
                    if item["unconstrained_violation"] > 0.0
                ]
                row: dict[str, Any] = {
                    key: attempt[key]
                    for key in (
                        "attempt_index",
                        "wall_time_s",
                        "reference_phase_s",
                        "accepted",
                        "reason",
                        "rank",
                        "rrqr_rank",
                        "condition_number",
                        "candidate_residual_rms_nms",
                        "old_residual_rms_nms",
                    )
                }
                row["mode"] = mode
                row.update(
                    {
                        f"beta_{name}": value
                        for name, value in zip(
                            parameter_names, attempt["candidate_beta"], strict=True
                        )
                    }
                )
                row["bound_hit_components"] = ";".join(
                    f'{item["name"]}:{item["direction"]}' for item in hit
                )
                row["unconstrained_bound_pressure"] = ";".join(
                    f'{item["name"]}:{item["direction"]}:'
                    f'{item["unconstrained_violation"]:.12g}:'
                    f'{item["unconstrained_violation_fraction_of_span"]:.12g}'
                    for item in pressure
                )
                row["distance_to_prior_span_normalized_l2"] = attempt[
                    "distance_to_population_prior"
                ]["span_normalized_l2"]
                row["distance_to_true_span_normalized_l2"] = attempt[
                    "distance_to_registered_true_beta"
                ]["span_normalized_l2"]
                row["generalized_torque_prediction_combined_rmse_nm"] = attempt[
                    "candidate_generalized_torque_prediction_error"
                ]["combined_rmse_nm"]
                writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summarize-existing", action="store_true")
    args = parser.parse_args()
    if args.summarize_existing:
        result = json.loads(
            (args.output_dir / "audit.json").read_text(encoding="utf-8")
        )
        _write_summary(args.output_dir, result)
        _write_candidate_csv(args.output_dir, result)
        return
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    true_human, metadata = registered_cold_start_perturbed_human()
    modes: dict[str, Any] = {}
    source_summaries: dict[str, Any] = {}
    for mode in MODES:
        source_summary = json.loads(
            (args.source_dir / f"{mode}.json").read_text(encoding="utf-8")
        )
        with np.load(args.source_dir / f"{mode}_trace.npz") as stored:
            trace = {name: stored[name] for name in stored.files}
        modes[mode] = replay_dynamics_candidates(
            trace,
            geometry_trusted_time_s=float(
                source_summary["geometry_identifier"]["trustworthy_time_s"]
            ),
            true_human=true_human,
        )
        source_summaries[mode] = {
            "recorded_dynamic_accepted_updates": source_summary[
                "dynamic_identifier"
            ]["accepted_updates"],
            "recorded_dynamic_rejected_updates": source_summary[
                "dynamic_identifier"
            ]["rejected_updates"],
            "recorded_dynamic_trustworthy_time_s": source_summary[
                "dynamic_identifier"
            ]["trustworthy_time_s"],
        }
    result = {
        "evidence_category": "stage4_hybrid_dynamics_estimator_failure_audit",
        "formal_experiment": False,
        "source_dir": str(args.source_dir),
        "registered_true_human": metadata,
        "source_summary": source_summaries,
        "modes": modes,
        "summary": {mode: _mode_summary(modes[mode]) for mode in MODES},
        "estimator_logic_changed": False,
        "estimator_bounds_or_gates_changed": False,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_summary(args.output_dir, result)
    _write_candidate_csv(args.output_dir, result)


if __name__ == "__main__":
    main()
