#!/usr/bin/env python3
"""Build a reproducible Phase-1B-F fragility and conditioning audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import nominal_base_parameters


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distribution(rows: list[dict[str, Any]], feature: str) -> dict[str, float]:
    values = np.asarray([row["features"][feature] for row in rows], dtype=float)
    return {
        "mean": float(np.mean(values)),
        "p05": float(np.percentile(values, 5)),
        "p95": float(np.percentile(values, 95)),
    }


def correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or np.std(x) <= 1.0e-15 or np.std(y) <= 1.0e-15:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def trace_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prior = nominal_base_parameters()
    lower = 0.45 * prior
    upper = 1.65 * prior
    lower[7:9] = -0.30 * prior[5:7]
    upper[7:9] = 0.60 * prior[5:7]
    span = upper - lower
    all_finite = True
    all_in_bounds = True
    accepted_mass_margins: list[float] = []
    accepted_residual_excess: list[float] = []
    max_step_fraction = 0.0
    total_attempts = 0
    total_accepted = 0
    phases: dict[str, int] = {}
    mass_freeze_attempts = 0
    conditional_freeze_attempts = 0
    ranks: list[int] = []
    conditions: list[float] = []
    max_path_l1 = 0.0
    max_path_to_net_ratio = 0.0
    max_sign_reversals = 0
    max_frozen_set_transitions = 0

    for row in rows:
        previous = prior.copy()
        increments: list[np.ndarray] = []
        path_l1 = 0.0
        frozen_sets: list[tuple[str, ...]] = []
        for attempt in row["dynamics_update_trace"]:
            total_attempts += 1
            phases[attempt["phase"]] = phases.get(attempt["phase"], 0) + 1
            beta = np.asarray(attempt["applied_beta"], dtype=float)
            all_finite &= bool(np.all(np.isfinite(beta)))
            all_in_bounds &= bool(
                np.all(beta >= lower - 1.0e-12)
                and np.all(beta <= upper + 1.0e-12)
            )
            increment = (beta - previous) / span
            increments.append(increment)
            max_step_fraction = max(
                max_step_fraction, float(np.max(np.abs(increment)))
            )
            path_l1 += float(np.sum(np.abs(increment)))
            previous = beta
            frozen = tuple(attempt["frozen_conditional_parameter_names"])
            frozen_sets.append(frozen)
            conditional_freeze_attempts += int(bool(frozen))
            mass_freeze_attempts += int(
                bool(attempt["frozen_mass_margin_parameter_names"])
            )
            if attempt["rank"] is not None:
                ranks.append(int(attempt["rank"]))
            if attempt["condition_number"] is not None:
                conditions.append(float(attempt["condition_number"]))
            if attempt["accepted"]:
                total_accepted += 1
                accepted_mass_margins.append(
                    float(attempt["minimum_mass_matrix_eigenvalue"])
                )
                accepted_residual_excess.append(
                    float(attempt["trusted_candidate_residual_rms_nm"])
                    - float(attempt["old_residual_rms_nm"])
                )
        net_l1 = float(np.sum(np.abs((previous - prior) / span)))
        max_path_l1 = max(max_path_l1, path_l1)
        max_path_to_net_ratio = max(
            max_path_to_net_ratio,
            path_l1 / max(net_l1, 1.0e-12),
        )
        if increments:
            matrix = np.vstack(increments)
            for column in range(matrix.shape[1]):
                signs = np.sign(matrix[:, column])
                signs = signs[signs != 0.0]
                if len(signs) > 1:
                    max_sign_reversals = max(
                        max_sign_reversals,
                        int(np.sum(signs[1:] != signs[:-1])),
                    )
        max_frozen_set_transitions = max(
            max_frozen_set_transitions,
            sum(a != b for a, b in zip(frozen_sets, frozen_sets[1:])),
        )

    return {
        "row_count": len(rows),
        "attempt_count": total_attempts,
        "accepted_attempt_count": total_accepted,
        "attempt_count_by_phase": phases,
        "all_applied_beta_finite": all_finite,
        "all_applied_beta_within_registered_bounds": all_in_bounds,
        "accepted_minimum_mass_margin": min(accepted_mass_margins),
        "accepted_maximum_residual_excess_nm": max(accepted_residual_excess),
        "maximum_applied_step_fraction_of_span": max_step_fraction,
        "configured_step_cap_fraction_of_span": 0.03,
        "minimum_attempt_rank": min(ranks),
        "maximum_attempt_condition_number": max(conditions),
        "mass_margin_freeze_attempt_count": mass_freeze_attempts,
        "conditional_freeze_attempt_count": conditional_freeze_attempts,
        "maximum_normalized_beta_path_l1_per_row": max_path_l1,
        "maximum_path_to_net_l1_ratio_per_row": max_path_to_net_ratio,
        "maximum_parameter_increment_sign_reversals_per_row": max_sign_reversals,
        "maximum_conditional_frozen_set_transitions_per_row": (
            max_frozen_set_transitions
        ),
        "accepted_mass_floor_pass": min(accepted_mass_margins) >= 0.03,
        "accepted_residual_tolerance_pass": max(accepted_residual_excess) <= 0.02,
        "step_cap_pass": max_step_fraction <= 0.03 + 1.0e-12,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--ablation", type=Path, required=True)
    parser.add_argument("--domain", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    combined = json.loads(args.combined.read_text())
    ablation = json.loads(args.ablation.read_text())
    domain = json.loads(args.domain.read_text())

    adaptive = [row for row in combined["rows"] if row["arm"] == "adaptive"]
    continual = [row for row in ablation["rows"] if row["arm"] == "adaptive"]
    proposal_rows = domain["proposal_rows"]
    recertified = [
        row
        for row in proposal_rows
        if row["minimum_reference_clearance_m"] >= 0.025
        and row["static_force_ok"]
        and row["static_moment_ok"]
    ]
    features = sorted(proposal_rows[0]["features"])
    cell_counts: dict[str, dict[str, int]] = {}
    for profile in sorted({row["profile"] for row in proposal_rows}):
        cell_counts[profile] = {}
        for high_rom in (False, True):
            name = "high_rom" if high_rom else "standard"
            cell_counts[profile][name] = sum(
                row["profile"] == profile and row["high_rom"] == high_rom
                for row in recertified
            )

    geometry_magnitude = [
        math.sqrt(
            row["geometry_error_evaluation_only"]["hip_position_m"] ** 2
            + row["geometry_error_evaluation_only"]["thigh_length_m"] ** 2
            + row["geometry_error_evaluation_only"]["knee_to_cuff_m"] ** 2
        )
        for row in adaptive
    ]
    beta_error = [row["beta_error_span_l2_evaluation_only"] for row in adaptive]
    rmse = [row["q_tracking_rmse_deg"] for row in adaptive]
    high_rom_goals = [
        row["task_input"]["goal_q_deg"] for row in adaptive if row["high_rom_case"]
    ]

    result = {
        "schema": "architecture_recovery_v2.phase1bf.freeze_evidence_audit.v1",
        "evidence_category": "derived_development_audit",
        "inputs": {
            "combined": str(args.combined),
            "combined_sha256": sha256(args.combined),
            "ablation": str(args.ablation),
            "ablation_sha256": sha256(args.ablation),
            "domain": str(args.domain),
            "domain_sha256": sha256(args.domain),
        },
        "combined_gates_passed": bool(combined["gates"]["passed"]),
        "ablation_gates_passed": bool(ablation["ablation_gates"]["passed"]),
        "source_or_config_changed_during_inputs": bool(
            combined["source_or_config_changed_during_run"]
            or ablation["source_or_config_changed_during_run"]
        ),
        "git_status_changed_during_inputs": bool(
            combined["git_status_changed_during_run"]
            or ablation["git_status_changed_during_run"]
        ),
        "continual_adaptive_trace": trace_audit(continual),
        "geometry_absorption_diagnostic": {
            "case_count": len(adaptive),
            "geometry_error_vs_beta_error_pearson": correlation(
                geometry_magnitude, beta_error
            ),
            "geometry_error_vs_tracking_rmse_pearson": correlation(
                geometry_magnitude, rmse
            ),
            "interpretation_limit": (
                "small development sample; correlation is diagnostic, not proof of independence"
            ),
            "wrong_geometry_completion": combined["summary"]["by_arm"][
                "wrong_geometry_adaptive_dynamics"
            ]["completed_count"],
            "adaptive_completion": combined["summary"]["by_arm"]["adaptive"][
                "completed_count"
            ],
        },
        "mechanics": {
            "adaptive_post_probe_reference_min_clearance_m": min(
                row[
                    "post_probe_constructed_reference_min_clearance_m_evaluation_only"
                ]
                for row in adaptive
            ),
            "adaptive_probe_min_clearance_m": min(
                row["probe_min_clearance_m_evaluation_only"] for row in adaptive
            ),
            "adaptive_task_min_clearance_m": min(
                row["task_min_clearance_m_evaluation_only"] for row in adaptive
            ),
            "high_rom_goal_q1_deg_range": [
                min(goal[0] for goal in high_rom_goals),
                max(goal[0] for goal in high_rom_goals),
            ],
            "high_rom_goal_q2_deg_range": [
                min(goal[1] for goal in high_rom_goals),
                max(goal[1] for goal in high_rom_goals),
            ],
        },
        "derived_25mm_domain_recertification": {
            "source_configured_clearance_m": domain["config"]["mechanics_domain"][
                "minimum_reference_clearance_m"
            ],
            "derived_clearance_m": 0.025,
            "proposal_count": len(proposal_rows),
            "retained_count": len(recertified),
            "retained_fraction": len(recertified) / len(proposal_rows),
            "retained_count_by_profile_rom_cell": cell_counts,
            "feature_distributions": {
                feature: {
                    "all_proposals": distribution(proposal_rows, feature),
                    "recertified_25mm": distribution(recertified, feature),
                }
                for feature in features
            },
        },
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "audit.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "command.txt").write_text(
        " ".join(
            [
                "python",
                str(Path(__file__).resolve()),
                "--combined",
                str(args.combined),
                "--ablation",
                str(args.ablation),
                "--domain",
                str(args.domain),
                "--output-dir",
                str(args.output_dir),
            ]
        )
        + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
