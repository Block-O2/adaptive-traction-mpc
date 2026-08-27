#!/usr/bin/env python3
"""Offline numerical audit of the Stage-4 dynamics trust bound gate."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.dynamics_failure_audit import replay_dynamics_candidates
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.integral_identifier import IntegralDynamicIdentifierConfig


MODES = ("existing_cem", "cem_plus_smooth_local_refinement")
BOUND_TOLERANCES = (0.0, 1e-12, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5)
PRESSURE_LEVELS = (0.0, 1e-6, 1e-4, 1e-3, 1e-2, 5e-2, 1e-1)


def _attempt_phase(attempts: list[dict[str, Any]], time_s: float | None) -> float | None:
    if time_s is None:
        return None
    return min(attempts, key=lambda item: abs(item["wall_time_s"] - time_s))[
        "reference_phase_s"
    ]


def _tolerance_summary(result: dict[str, Any]) -> dict[str, Any]:
    attempts = result["attempts"]
    accepted = [item for item in attempts if item["accepted"]]
    trust = result["reconstructed_trustworthy_time_s"]
    return {
        "accepted_count": len(accepted),
        "rejected_count": len(attempts) - len(accepted),
        "trustworthy_time_s": trust,
        "trustworthy_reference_phase_s": _attempt_phase(attempts, trust),
        "accepted_attempt_indices": [item["attempt_index"] for item in accepted],
        "accepted_reference_phases_s": [
            item["reference_phase_s"] for item in accepted
        ],
    }


def _maximum_pressure(attempt: dict[str, Any]) -> float:
    return max(
        (
            item["unconstrained_violation_fraction_of_span"]
            for item in attempt["bound_components"]
        ),
        default=0.0,
    )


def _passes_non_bound_gates(attempt: dict[str, Any]) -> bool:
    reasons = set(attempt["reason"].split(","))
    reasons.discard("accepted")
    reasons.discard("bound_hit")
    return not reasons


def _rule_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    attempts = result["attempts"]
    prior_error = result[
        "registered_full_trajectory_population_prior_prediction_error"
    ]["combined_rmse_nm"]
    viable = [item for item in attempts if _passes_non_bound_gates(item)]
    pressure_counts = []
    for level in PRESSURE_LEVELS:
        selected = [item for item in viable if _maximum_pressure(item) <= level]
        pressure_counts.append(
            {
                "maximum_normalized_unconstrained_violation": level,
                "candidate_count": len(selected),
                "first_wall_time_s": None if not selected else selected[0]["wall_time_s"],
                "first_reference_phase_s": (
                    None if not selected else selected[0]["reference_phase_s"]
                ),
            }
        )
    oracle_reliable_boundary = [
        item
        for item in viable
        if _maximum_pressure(item) > 0.0
        and item["positive_definite_mass_matrix"]
        and item[
            "registered_full_trajectory_generalized_torque_prediction_error"
        ]["combined_rmse_nm"]
        <= prior_error
    ]
    return {
        "population_prior_registered_trajectory_prediction_rmse_nm": prior_error,
        "non_bound_gate_viable_candidate_count": len(viable),
        "maximum_unconstrained_violation_fraction_of_span": {
            "minimum": float(min((_maximum_pressure(item) for item in attempts), default=np.nan)),
            "median": float(np.median([_maximum_pressure(item) for item in attempts])),
            "maximum": float(max((_maximum_pressure(item) for item in attempts), default=np.nan)),
        },
        "candidate_level_rule_a_pressure_scan": pressure_counts,
        "oracle_rule_b_boundary_candidates": {
            "definition": (
                "boundary-required, all current non-bound gates pass, positive-definite, "
                "and registered-true full-trajectory torque RMSE no worse than prior"
            ),
            "count": len(oracle_reliable_boundary),
            "first_wall_time_s": (
                None if not oracle_reliable_boundary else oracle_reliable_boundary[0]["wall_time_s"]
            ),
            "first_reference_phase_s": (
                None
                if not oracle_reliable_boundary
                else oracle_reliable_boundary[0]["reference_phase_s"]
            ),
            "attempt_indices": [item["attempt_index"] for item in oracle_reliable_boundary],
            "warning": "Uses registered true beta and is therefore diagnostic, not deployable.",
        },
    }


def _write_candidates(output_dir: Path, modes: dict[str, Any]) -> None:
    names = modes[MODES[0]]["parameter_names"]
    fields = [
        "mode",
        "attempt_index",
        "wall_time_s",
        "reference_phase_s",
        "accepted",
        "reason",
        "current_bound_hit",
        "rank",
        "rrqr_rank",
        "condition_number",
        "candidate_residual_rms_nms",
        "old_residual_rms_nms",
        "positive_definite_mass_matrix",
        "maximum_unconstrained_violation_fraction_of_span",
        "active_or_pressured_bounds",
        "distance_to_prior_span_normalized_l2",
        "distance_to_true_span_normalized_l2",
        "observed_history_torque_rmse_nm",
        "registered_full_trajectory_torque_rmse_nm",
        *[f"unconstrained_{name}" for name in names],
        *[f"constrained_{name}" for name in names],
    ]
    with (output_dir / "dynamics_candidates.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for mode, result in modes.items():
            for attempt in result["attempts"]:
                row: dict[str, Any] = {
                    "mode": mode,
                    "attempt_index": attempt["attempt_index"],
                    "wall_time_s": attempt["wall_time_s"],
                    "reference_phase_s": attempt["reference_phase_s"],
                    "accepted": attempt["accepted"],
                    "reason": attempt["reason"],
                    "current_bound_hit": attempt["bound_hit"],
                    "rank": attempt["rank"],
                    "rrqr_rank": attempt["rrqr_rank"],
                    "condition_number": attempt["condition_number"],
                    "candidate_residual_rms_nms": attempt[
                        "candidate_residual_rms_nms"
                    ],
                    "old_residual_rms_nms": attempt["old_residual_rms_nms"],
                    "positive_definite_mass_matrix": attempt[
                        "positive_definite_mass_matrix"
                    ],
                    "maximum_unconstrained_violation_fraction_of_span": _maximum_pressure(
                        attempt
                    ),
                    "active_or_pressured_bounds": ";".join(
                        f'{item["name"]}:{item["direction"]}:'
                        f'{item["unconstrained_violation_fraction_of_span"]:.12g}:'
                        f'{item["constrained_distance_to_bound"]:.12g}'
                        for item in attempt["bound_components"]
                    ),
                    "distance_to_prior_span_normalized_l2": attempt[
                        "distance_to_population_prior"
                    ]["span_normalized_l2"],
                    "distance_to_true_span_normalized_l2": attempt[
                        "distance_to_registered_true_beta"
                    ]["span_normalized_l2"],
                    "observed_history_torque_rmse_nm": attempt[
                        "candidate_generalized_torque_prediction_error"
                    ]["combined_rmse_nm"],
                    "registered_full_trajectory_torque_rmse_nm": attempt[
                        "registered_full_trajectory_generalized_torque_prediction_error"
                    ]["combined_rmse_nm"],
                }
                row.update(
                    {
                        f"unconstrained_{name}": value
                        for name, value in zip(
                            names,
                            attempt["unconstrained_candidate_beta"],
                            strict=True,
                        )
                    }
                )
                row.update(
                    {
                        f"constrained_{name}": value
                        for name, value in zip(
                            names, attempt["candidate_beta"], strict=True
                        )
                    }
                )
                writer.writerow(row)


def _write_summary(output_dir: Path, audit: dict[str, Any]) -> None:
    lines = [
        "# Stage-4 dynamics trust-rule numerical audit",
        "",
        "Saved traces were replayed offline. Production estimator logic, bounds, and tolerance were not modified.",
        "",
        "## Bound-detection tolerance sweep",
        "",
        "| atol | mode | accepted | trust wall/phase (s) | accepted attempts |",
        "|---:|---|---:|---:|---|",
    ]
    for tolerance in BOUND_TOLERANCES:
        key = f"{tolerance:.0e}"
        for mode in MODES:
            row = audit["bound_detection_tolerance_sweep"][key][mode]
            trust = (
                "-"
                if row["trustworthy_time_s"] is None
                else f'{row["trustworthy_time_s"]:.3f}/'
                f'{row["trustworthy_reference_phase_s"]:.3f}'
            )
            lines.append(
                f'| {key} | {mode} | {row["accepted_count"]} | {trust} | '
                f'{row["accepted_attempt_indices"]} |'
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The tolerance sweep reproduces the current raw-unit distance test only. "
            "It is a sensitivity diagnosis, not a proposed scientific acceptance rule.",
        ]
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

    true_human, metadata = registered_cold_start_perturbed_human()
    traces: dict[str, dict[str, np.ndarray]] = {}
    geometry_trust: dict[str, float] = {}
    source_summary: dict[str, Any] = {}
    for mode in MODES:
        summary = json.loads(
            (args.source_dir / f"{mode}.json").read_text(encoding="utf-8")
        )
        with np.load(args.source_dir / f"{mode}_trace.npz") as stored:
            traces[mode] = {name: stored[name] for name in stored.files}
        geometry_trust[mode] = float(
            summary["geometry_identifier"]["trustworthy_time_s"]
        )
        source_summary[mode] = {
            "recorded_accepted_updates": summary["dynamic_identifier"][
                "accepted_updates"
            ],
            "recorded_rejected_updates": summary["dynamic_identifier"][
                "rejected_updates"
            ],
            "recorded_trustworthy_time_s": summary["dynamic_identifier"][
                "trustworthy_time_s"
            ],
        }

    production_replay = {
        mode: replay_dynamics_candidates(
            traces[mode],
            geometry_trusted_time_s=geometry_trust[mode],
            true_human=true_human,
        )
        for mode in MODES
    }
    tolerance_sweep: dict[str, Any] = {}
    for tolerance in BOUND_TOLERANCES:
        tolerance_sweep[f"{tolerance:.0e}"] = {
            mode: _tolerance_summary(
                replay_dynamics_candidates(
                    traces[mode],
                    geometry_trusted_time_s=geometry_trust[mode],
                    true_human=true_human,
                    bound_detection_atol=tolerance,
                )
            )
            for mode in MODES
        }

    audit = {
        "evidence_category": "offline_diagnostic",
        "formal_experiment": False,
        "source_dir": str(args.source_dir),
        "registered_true_human": metadata,
        "source_summary": source_summary,
        "production_bound_detection_atol": 1e-7,
        "production_replay": production_replay,
        "bound_detection_tolerance_sweep": tolerance_sweep,
        "rule_diagnostics": {
            mode: _rule_diagnostics(production_replay[mode]) for mode in MODES
        },
        "current_identifier_config": vars(IntegralDynamicIdentifierConfig()),
        "production_source_changed": False,
        "production_tolerance_changed": False,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_candidates(args.output_dir, production_replay)
    _write_summary(args.output_dir, audit)


if __name__ == "__main__":
    main()
