#!/usr/bin/env python3
"""Run a frozen V2 reduced-plant development or formal campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any

import numpy as np
import scipy

from traction_mpc_stage3 import executable_command as stage3_executable_command
from traction_mpc_stage3 import frames as stage3_frames
from traction_mpc_stage3 import human as stage3_human
from traction_mpc_stage3 import reference as stage3_reference
from traction_mpc_stage4 import estimator_v2 as stage4_estimator_v2
from traction_mpc_stage4 import human_model as stage4_human_model
from traction_mpc_stage4 import mpc as stage4_mpc
from traction_mpc_stage5.architecture_recovery_v2 import effective_model
from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark
from traction_mpc_stage5.full3d_adaptive_integration_v1 import (
    time_contract as full3d_time_contract,
)
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    make_benchmark_case,
    run_closed_loop_case,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def validate_expected_git_status(
    config: dict[str, Any], git_status: str
) -> str:
    """Fail closed when a campaign seals the expected working-tree state."""

    actual = hashlib.sha256(git_status.encode("utf-8")).hexdigest()
    expected = config.get("expected_git_status_sha256")
    if expected is not None and actual != expected:
        raise RuntimeError(
            "live git status hash does not match sealed expected_git_status_sha256"
        )
    return actual


def validate_expected_source_seal(config: dict[str, Any]) -> dict[str, Any] | None:
    """Fail closed on preregistered file hashes before case generation."""

    seal_value = config.get("expected_source_seal_path")
    if seal_value is None:
        return None
    seal_path = Path(seal_value).resolve()
    seal = json.loads(seal_path.read_text())
    expected_files = seal.get("files")
    if not isinstance(expected_files, dict) or not expected_files:
        raise ValueError("expected source seal must contain a nonempty files map")
    actual_files: dict[str, str] = {}
    for file_value, expected_sha256 in expected_files.items():
        path = Path(file_value).resolve()
        actual_sha256 = _sha256(path)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(f"pre-run source seal mismatch: {file_value}")
        actual_files[str(file_value)] = actual_sha256
    return {
        "seal_path": str(seal_path),
        "seal_sha256": _sha256(seal_path),
        "files": actual_files,
    }


def _manifest(paths: list[Path]) -> dict[str, str]:
    return {str(path.resolve()): _sha256(path) for path in paths}


def _strict_json_value(value: Any) -> Any:
    """Map non-finite diagnostics to JSON null without dropping their keys."""

    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _strict_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_json_value(item) for item in value]
    return value


def _maximum_or_none(values: list[float]) -> float | None:
    return None if not values else float(np.max(values))


def _generation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cases: dict[tuple[int, int], dict[str, Any] | None] = {}
    for row in rows:
        key = (int(row["seed"]), int(row["task_seed"]))
        record = row.get("setup_evaluation_only")
        if key not in cases or cases[key] is None:
            cases[key] = record if isinstance(record, dict) else None
    accepted = [record for record in cases.values() if record is not None]
    proposal_draw_count = sum(
        int(record.get("generation_attempt", 0)) + 1 for record in accepted
    )
    rejection_causes: dict[str, int] = {}
    for record in accepted:
        for name, count in record.get("generation_rejection_counts", {}).items():
            rejection_causes[name] = rejection_causes.get(name, 0) + int(count)
    per_profile_rom_cell: dict[str, dict[str, Any]] = {}
    representative_rows: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        representative_rows.setdefault(
            (int(row["seed"]), int(row["task_seed"])), row
        )
    for row in representative_rows.values():
        cell_name = (
            f"{row.get('task_id', 'generation_failed')}::"
            f"{'high_rom' if row.get('high_rom_case', False) else 'standard'}"
        )
        cell = per_profile_rom_cell.setdefault(
            cell_name,
            {
                "configured_case_count": 0,
                "generated_case_count": 0,
                "proposal_draw_count": 0,
                "rejection_causes": {},
            },
        )
        cell["configured_case_count"] += 1
        record = row.get("setup_evaluation_only")
        if isinstance(record, dict):
            cell["generated_case_count"] += 1
            cell["proposal_draw_count"] += int(record.get("generation_attempt", 0)) + 1
            for name, count in record.get("generation_rejection_counts", {}).items():
                cell["rejection_causes"][name] = (
                    cell["rejection_causes"].get(name, 0) + int(count)
                )
    for cell in per_profile_rom_cell.values():
        cell["realized_acceptance_fraction"] = (
            cell["generated_case_count"] / cell["proposal_draw_count"]
            if cell["proposal_draw_count"]
            else None
        )
    return {
        "configured_case_count": len(cases),
        "generated_case_count": len(accepted),
        "generation_failure_count": len(cases) - len(accepted),
        "proposal_draw_count_for_generated_cases": proposal_draw_count,
        "realized_acceptance_fraction_for_generated_cases": (
            len(accepted) / proposal_draw_count if proposal_draw_count else None
        ),
        "generation_attempt_max": (
            max(int(record.get("generation_attempt", 0)) for record in accepted)
            if accepted
            else None
        ),
        "rejection_causes_before_acceptance": rejection_causes,
        "per_profile_rom_cell": per_profile_rom_cell,
        "conditional_distribution_note": (
            "setup proposals are rejection-sampled while each task draw remains "
            "fixed; accepted setup and task are therefore jointly conditional"
        ),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, dict[str, Any]] = {}
    for arm in sorted({str(row["arm"]) for row in rows}):
        selected = [row for row in rows if row["arm"] == arm]
        numeric = [row for row in selected if "q_tracking_rmse_deg" in row]
        full_horizon = [
            row for row in numeric if bool(row.get("full_horizon_executed", False))
        ]
        case_keys = [
            (int(row["seed"]), int(row["task_seed"])) for row in selected
        ]
        by_arm[arm] = {
            "case_count": len(selected),
            "unique_case_key_count": len(set(case_keys)),
            "case_keys": [list(key) for key in sorted(case_keys)],
            "tracking_metric_count": len(numeric),
            "full_horizon_metric_count": len(full_horizon),
            "clearance_evaluated_count": sum(
                bool(row.get("clearance_evaluation_enabled", False))
                for row in selected
            ),
            "completed_count": sum(bool(row.get("completed")) for row in selected),
            "completion_rate": float(
                np.mean([bool(row.get("completed")) for row in selected])
            ),
            "tracking_rmse_deg_mean": float(
                np.mean([row["q_tracking_rmse_deg"] for row in numeric])
            ) if numeric else None,
            "tracking_rmse_deg_median": float(
                np.median([row["q_tracking_rmse_deg"] for row in numeric])
            ) if numeric else None,
            "tracking_rmse_deg_p95": float(
                np.percentile(
                    [row["q_tracking_rmse_deg"] for row in numeric],
                    95,
                    method="linear",
                )
            ) if numeric else None,
            "hold_entry_0p5s_q_tracking_rmse_deg_median": float(
                np.median(
                    [
                        row["hold_entry_0p5s_q_tracking_rmse_deg"]
                        for row in numeric
                        if row.get("hold_entry_0p5s_q_tracking_rmse_deg") is not None
                    ]
                )
            ) if any(
                row.get("hold_entry_0p5s_q_tracking_rmse_deg") is not None
                for row in numeric
            ) else None,
            "return_entry_0p5s_q_tracking_rmse_deg_median": float(
                np.median(
                    [
                        row["return_entry_0p5s_q_tracking_rmse_deg"]
                        for row in numeric
                        if row.get("return_entry_0p5s_q_tracking_rmse_deg") is not None
                    ]
                )
            ) if any(
                row.get("return_entry_0p5s_q_tracking_rmse_deg") is not None
                for row in numeric
            ) else None,
            "full_horizon_tracking_rmse_deg_median": float(
                np.median([row["q_tracking_rmse_deg"] for row in full_horizon])
            ) if full_horizon else None,
            "full_horizon_tracking_rmse_deg_p95": float(
                np.percentile(
                    [row["q_tracking_rmse_deg"] for row in full_horizon],
                    95,
                    method="linear",
                )
            ) if full_horizon else None,
            "full_episode_force_exposure_n_s_mean": float(
                np.mean(
                    [
                        row["full_episode_force_exposure_n_s"]
                        for row in numeric
                        if "full_episode_force_exposure_n_s" in row
                    ]
                )
            ) if any("full_episode_force_exposure_n_s" in row for row in numeric) else None,
            "full_episode_force_exposure_n_s_max": _maximum_or_none(
                [
                    float(row["full_episode_force_exposure_n_s"])
                    for row in numeric
                    if "full_episode_force_exposure_n_s" in row
                ]
            ),
            "full_episode_moment_exposure_nm_s_mean": float(
                np.mean(
                    [
                        row["full_episode_moment_exposure_nm_s"]
                        for row in numeric
                        if "full_episode_moment_exposure_nm_s" in row
                    ]
                )
            ) if any("full_episode_moment_exposure_nm_s" in row for row in numeric) else None,
            "full_episode_moment_exposure_nm_s_max": _maximum_or_none(
                [
                    float(row["full_episode_moment_exposure_nm_s"])
                    for row in numeric
                    if "full_episode_moment_exposure_nm_s" in row
                ]
            ),
            "runner_wall_time_s_mean": float(
                np.mean(
                    [row["runner_wall_time_s"] for row in selected if "runner_wall_time_s" in row]
                )
            ) if any("runner_wall_time_s" in row for row in selected) else None,
            "runner_wall_time_s_p95": float(
                np.percentile(
                    [row["runner_wall_time_s"] for row in selected if "runner_wall_time_s" in row],
                    95,
                    method="linear",
                )
            ) if any("runner_wall_time_s" in row for row in selected) else None,
            "tracking_max_abs_deg_max": float(
                np.max([row["q_tracking_max_abs_deg"] for row in numeric])
            ) if numeric else None,
            "force_peak_n_max": float(
                np.max([row["force_peak_n"] for row in numeric])
            ) if numeric else None,
            "moment_peak_nm_max": float(
                np.max([row["moment_peak_nm"] for row in numeric])
            ) if numeric else None,
            "rom_violation_samples": int(
                sum(int(row.get("rom_violation_samples", 0)) for row in selected)
            ),
            "solver_failure_count": int(
                sum(int(row.get("solver_failure_count", 0)) for row in selected)
            ),
            "safety_abort_count": int(
                sum(int(row.get("safety_abort_count", 0)) for row in selected)
            ),
            "estimated_rom_supervisor_abort_count": int(
                sum(
                    int(row.get("estimated_rom_supervisor_abort_count", 0))
                    for row in selected
                )
            ),
            "probe_rom_violation_count": int(
                sum(bool(row.get("probe_rom_violation", False)) for row in selected)
            ),
            "probe_clearance_violation_count": int(
                sum(
                    bool(row.get("probe_clearance_violation", False))
                    for row in selected
                )
            ),
            "table_clearance_violation_samples": int(
                sum(
                    int(row.get("table_clearance_violation_samples", 0))
                    for row in selected
                )
            ),
            "post_probe_constructed_reference_clearance_violation_count": int(
                sum(
                    bool(
                        row.get(
                            "post_probe_constructed_reference_clearance_violation_evaluation_only",
                            False,
                        )
                    )
                    for row in selected
                )
            ),
            "post_probe_constructed_reference_clearance_evaluated_count": int(
                sum(
                    "post_probe_constructed_reference_min_clearance_m_evaluation_only"
                    in row
                    and row[
                        "post_probe_constructed_reference_min_clearance_m_evaluation_only"
                    ]
                    is not None
                    for row in selected
                )
            ),
            "probe_consistency_abort_count": int(
                sum(
                    int(row.get("probe_consistency_abort_count", 0))
                    for row in selected
                )
            ),
            "probe_settle_timeout_count": int(
                sum(
                    int(row.get("probe_settle_timeout_count", 0))
                    for row in selected
                )
            ),
            "probe_force_peak_n_max": _maximum_or_none(
                [
                    float(row["probe_force_peak_n"])
                    for row in selected
                    if "probe_force_peak_n" in row
                ]
            ),
            "probe_moment_peak_nm_max": _maximum_or_none(
                [
                    float(row["probe_moment_peak_nm"])
                    for row in selected
                    if "probe_moment_peak_nm" in row
                ]
            ),
            "geometry_fit_rejection_count": sum(
                str(row.get("termination_reason", "")).startswith(
                    "geometry_fit_rejected"
                )
                for row in selected
            ),
        }
        task_force = by_arm[arm]["force_peak_n_max"]
        task_moment = by_arm[arm]["moment_peak_nm_max"]
        by_arm[arm]["full_episode_force_peak_n_max"] = _maximum_or_none(
            [
                value
                for value in (by_arm[arm]["probe_force_peak_n_max"], task_force)
                if value is not None
            ]
        )
        by_arm[arm]["full_episode_moment_peak_nm_max"] = _maximum_or_none(
            [
                value
                for value in (by_arm[arm]["probe_moment_peak_nm_max"], task_moment)
                if value is not None
            ]
        )
    return {
        "tracking_percentile_method": "numpy_linear",
        "missing_metric_policy": "formal adaptive/oracle gate fails unless every expected row has tracking metrics",
        "case_generation": _generation_summary(rows),
        "by_arm": by_arm,
    }


def validate_config(config: dict[str, Any]) -> None:
    environment = config.get("environment_contract", {})
    hidden = config.get("hidden_generation", {})
    if environment.get("scenario") == "lying_bed_contact_free_clearance":
        required = (
            "bed_height_m",
            "shank_radius_m",
            "minimum_reference_clearance_m",
        )
        missing = [name for name in required if hidden.get(name) is None]
        if missing:
            raise ValueError(
                "lying-bed campaign requires fail-closed mechanics fields: "
                + ", ".join(missing)
            )
    if "state_residual_velocity_scale_rad_s" in config:
        configured = float(config["state_residual_velocity_scale_rad_s"])
        frozen = float(
            functional_benchmark.STATE_RESIDUAL_VELOCITY_SCALE_RAD_S
        )
        if configured != frozen:
            raise ValueError(
                "state_residual_velocity_scale_rad_s must equal frozen source constant"
            )


def evaluate_gates(
    summary: dict[str, Any],
    gates: dict[str, Any] | None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if gates is None:
        return None
    candidate_arm = str(gates.get("candidate_arm", "adaptive"))
    arm = summary["by_arm"][candidate_arm]
    fixed = summary["by_arm"]["fixed_nominal"]
    oracle = summary["by_arm"]["oracle"]
    no_adapt = summary["by_arm"]["no_dynamics_adaptation"]
    wrong_geometry = summary["by_arm"]["wrong_geometry_adaptive_dynamics"]
    commissioning_only = summary["by_arm"].get("commissioning_only_dynamics")
    expected_cases = int(gates["expected_case_count_per_arm"])
    matrix_complete = all(
        summary["by_arm"].get(name, {}).get("case_count") == expected_cases
        and summary["by_arm"].get(name, {}).get("unique_case_key_count")
        == expected_cases
        for name in gates["expected_arms"]
    )
    if matrix_complete:
        expected_keys = summary["by_arm"][gates["expected_arms"][0]]["case_keys"]
        matrix_complete = all(
            summary["by_arm"][name]["case_keys"] == expected_keys
            for name in gates["expected_arms"]
        )
    adaptive_median = arm["full_horizon_tracking_rmse_deg_median"]
    adaptive_p95 = arm["full_horizon_tracking_rmse_deg_p95"]
    fixed_median = fixed["full_horizon_tracking_rmse_deg_median"]
    no_adapt_median = no_adapt["full_horizon_tracking_rmse_deg_median"]
    wrong_geometry_median = wrong_geometry[
        "full_horizon_tracking_rmse_deg_median"
    ]
    oracle_median = oracle["full_horizon_tracking_rmse_deg_median"]
    checks = {
        "complete_paired_matrix": matrix_complete,
        "adaptive_exact_case_count": arm["case_count"] == expected_cases,
        "adaptive_complete_metrics": arm["tracking_metric_count"] == expected_cases,
        "adaptive_full_horizon_metrics": (
            arm["full_horizon_metric_count"] == expected_cases
        ),
        "adaptive_clearance_evaluated": (
            arm["clearance_evaluated_count"] == expected_cases
        ),
        "adaptive_completion_rate": (
            arm["completion_rate"] >= gates["adaptive_completion_rate_minimum"]
        ),
        "adaptive_tracking_median": adaptive_median is not None
        and (
            adaptive_median
            <= gates["adaptive_tracking_rmse_deg_median_maximum"]
        ),
        "adaptive_tracking_p95": (
            adaptive_p95 is not None
            and adaptive_p95 <= gates["adaptive_tracking_rmse_deg_p95_maximum"]
        ),
        "adaptive_full_episode_force": (
            arm["full_episode_force_peak_n_max"] is not None
            and arm["full_episode_force_peak_n_max"]
            <= gates["force_peak_n_maximum"]
        ),
        "adaptive_full_episode_moment": (
            arm["full_episode_moment_peak_nm_max"] is not None
            and arm["full_episode_moment_peak_nm_max"]
            <= gates["moment_peak_nm_maximum"]
        ),
        "adaptive_task_rom": arm["rom_violation_samples"] == 0,
        "adaptive_probe_rom": arm["probe_rom_violation_count"] == 0,
        "adaptive_probe_clearance": (
            arm["probe_clearance_violation_count"] == 0
        ),
        "adaptive_task_clearance": (
            arm["table_clearance_violation_samples"] == 0
        ),
        "adaptive_post_probe_constructed_reference_clearance": (
            arm[
                "post_probe_constructed_reference_clearance_evaluated_count"
            ]
            == expected_cases
            and
            arm[
                "post_probe_constructed_reference_clearance_violation_count"
            ]
            == 0
        ),
        "adaptive_probe_consistency": (
            arm["probe_consistency_abort_count"] == 0
        ),
        "adaptive_probe_settle_timeout": (
            arm["probe_settle_timeout_count"] == 0
        ),
        "adaptive_solver": arm["solver_failure_count"] == 0,
        "adaptive_safety_abort": arm["safety_abort_count"] == 0,
        "adaptive_beats_fixed": (
            fixed["full_horizon_metric_count"] == expected_cases
            and fixed_median is not None
            and adaptive_median is not None
            and adaptive_median
            <= fixed_median
            * (1.0 - gates["adaptive_vs_fixed_median_improvement_fraction_minimum"])
        )
        or (
            fixed["completion_rate"]
            <= arm["completion_rate"]
            - gates.get("adaptive_vs_fixed_completion_rate_margin_minimum", 1.0)
        ),
        "adaptive_beats_no_dynamics_adaptation": (
            no_adapt["full_horizon_metric_count"] == expected_cases
            and no_adapt_median is not None
            and adaptive_median is not None
            and adaptive_median
            <= no_adapt_median
            * (
                1.0
                - gates[
                    "adaptive_vs_no_dynamics_median_improvement_fraction_minimum"
                ]
            )
        )
        or (
            no_adapt["completion_rate"]
            <= arm["completion_rate"]
            - gates[
                "adaptive_vs_no_dynamics_completion_rate_margin_minimum"
            ]
        ),
        "adaptive_beats_wrong_geometry": (
            "adaptive_vs_wrong_geometry_median_improvement_fraction_minimum"
            in gates
            and "adaptive_vs_wrong_geometry_completion_rate_margin_minimum"
            in gates
            and (
                (
                    wrong_geometry["full_horizon_metric_count"]
                    == expected_cases
                    and wrong_geometry_median is not None
                    and adaptive_median is not None
                    and adaptive_median
                    <= wrong_geometry_median
                    * (
                        1.0
                        - gates[
                            "adaptive_vs_wrong_geometry_median_improvement_fraction_minimum"
                        ]
                    )
                )
                or (
                    wrong_geometry["completion_rate"]
                    <= arm["completion_rate"]
                    - gates[
                        "adaptive_vs_wrong_geometry_completion_rate_margin_minimum"
                    ]
                )
            )
        ),
        "adaptive_beats_commissioning_only": (
            commissioning_only is None
            or (
                (
                    commissioning_only["full_horizon_metric_count"]
                    == expected_cases
                    and commissioning_only[
                        "full_horizon_tracking_rmse_deg_median"
                    ]
                    is not None
                    and adaptive_median is not None
                    and adaptive_median
                    <= commissioning_only[
                        "full_horizon_tracking_rmse_deg_median"
                    ]
                    * (
                        1.0
                        - gates[
                            "adaptive_vs_commissioning_median_improvement_fraction_minimum"
                        ]
                    )
                )
                or (
                    commissioning_only["completion_rate"]
                    <= arm["completion_rate"]
                    - gates[
                        "adaptive_vs_commissioning_completion_rate_margin_minimum"
                    ]
                )
            )
        ),
        "adaptive_oracle_gap": (
            oracle_median is not None
            and adaptive_median is not None
            and
            adaptive_median
            - oracle_median
            <= gates["adaptive_minus_oracle_median_gap_deg_maximum"]
        ),
        "oracle_exact_case_count": oracle["case_count"] == expected_cases,
        "oracle_complete_metrics": oracle["tracking_metric_count"] == expected_cases,
        "oracle_full_horizon_metrics": (
            oracle["full_horizon_metric_count"] == expected_cases
        ),
        "oracle_clearance_evaluated": (
            oracle["clearance_evaluated_count"] == expected_cases
        ),
        "oracle_completion": oracle["completion_rate"] == 1.0,
        "oracle_task_rom": oracle["rom_violation_samples"] == 0,
        "oracle_probe_rom": oracle["probe_rom_violation_count"] == 0,
        "oracle_probe_clearance": (
            oracle["probe_clearance_violation_count"] == 0
        ),
        "oracle_task_clearance": (
            oracle["table_clearance_violation_samples"] == 0
        ),
        "oracle_post_probe_constructed_reference_clearance": (
            oracle[
                "post_probe_constructed_reference_clearance_evaluated_count"
            ]
            == expected_cases
            and
            oracle[
                "post_probe_constructed_reference_clearance_violation_count"
            ]
            == 0
        ),
        "oracle_probe_consistency": (
            oracle["probe_consistency_abort_count"] == 0
        ),
        "oracle_probe_settle_timeout": (
            oracle["probe_settle_timeout_count"] == 0
        ),
        "oracle_solver": oracle["solver_failure_count"] == 0,
        "oracle_safety_abort": oracle["safety_abort_count"] == 0,
        "oracle_full_episode_force": (
            oracle["full_episode_force_peak_n_max"] is not None
            and oracle["full_episode_force_peak_n_max"]
            <= gates["force_peak_n_maximum"]
        ),
        "oracle_full_episode_moment": (
            oracle["full_episode_moment_peak_nm_max"] is not None
            and oracle["full_episode_moment_peak_nm_max"]
            <= gates["moment_peak_nm_maximum"]
        ),
    }
    if candidate_arm == "adaptive_state_residual":
        if rows is None:
            raise ValueError(
                "state-residual formal gate evaluation requires raw rows"
            )
        candidate_rows = [
            row for row in rows if row.get("arm") == candidate_arm
        ]
        telemetry_keys = (
            "task_residual_bias_peak_abs_nm",
            "task_residual_bias_max_step_nm",
            "task_residual_bias_total_variation_l1_nm",
            "task_residual_bias_sign_reversal_count",
            "task_state_residual_weight_peak_l2_nm",
            "task_state_residual_weight_max_component_step_nm",
            "task_state_residual_weight_total_variation_l1_nm",
            "task_state_residual_coefficient_projection_hit_count",
            "task_state_residual_observed_output_cap_hit_count",
            "task_state_residual_prediction_dynamics_component_evaluation_count",
            "task_state_residual_prediction_dynamics_component_cap_hit_count",
            "task_state_residual_chosen_rollout_component_evaluation_count",
            "task_state_residual_chosen_rollout_component_cap_hit_count",
        )
        checks.update(
            {
                "adaptive_state_residual_integrity_row_count": len(candidate_rows)
                == expected_cases,
                "adaptive_state_residual_telemetry_finite": len(candidate_rows)
                == expected_cases
                and all(
                    all(
                        key in row
                        and isinstance(row[key], (int, float))
                        and np.isfinite(float(row[key]))
                        for key in telemetry_keys
                    )
                    for row in candidate_rows
                ),
                "adaptive_state_residual_telemetry_exercised": len(candidate_rows)
                == expected_cases
                and all(
                    int(
                        row.get(
                            "task_state_residual_prediction_dynamics_component_evaluation_count",
                            0,
                        )
                    )
                    > 0
                    and int(
                        row.get(
                            "task_state_residual_chosen_rollout_component_evaluation_count",
                            0,
                        )
                    )
                    > 0
                    for row in candidate_rows
                ),
                "adaptive_state_residual_finite_bounded": len(candidate_rows)
                == expected_cases
                and all(
                    bool(row.get("task_state_residual_weights_finite", False))
                    and bool(
                        row.get(
                            "task_state_residual_weights_within_l2_projection_limit",
                            False,
                        )
                    )
                    and bool(row.get("task_residual_bias_finite", False))
                    and bool(row.get("task_residual_bias_within_limit", False))
                    and float(
                        row.get("task_residual_bias_peak_abs_nm", np.inf)
                    )
                    <= float(gates["residual_output_abs_nm_maximum"])
                    + 1.0e-12
                    for row in candidate_rows
                ),
                "adaptive_state_residual_feature_contract": len(candidate_rows)
                == expected_cases
                and all(
                    row.get("task_residual_bias_representation")
                    == "bounded_linear_state_nlms_v1"
                    and row.get("task_state_residual_feature_names")
                    == [
                        "constant",
                        "q1_rom",
                        "q2_rom",
                        "dq1_bounded",
                        "dq2_bounded",
                    ]
                    and float(
                        row.get(
                            "task_state_residual_velocity_scale_rad_s", np.nan
                        )
                    )
                    == float(gates["state_residual_velocity_scale_rad_s"])
                    and bool(row.get("task_beta_updates_enabled_for_arm", False))
                    for row in candidate_rows
                ),
                "adaptive_state_residual_truth_firewall": len(candidate_rows)
                == expected_cases
                and all(
                    not bool(
                        row.get("truth_firewall", {}).get(
                            "deployable_truth_consumed", True
                        )
                    )
                    for row in candidate_rows
                ),
            }
        )
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "criteria_frozen_before_results": True,
        "candidate_arm": candidate_arm,
    }


def evaluate_ablation_gates(
    summary: dict[str, Any], gates: dict[str, Any] | None
) -> dict[str, Any] | None:
    if gates is None:
        return None
    expected = int(gates["expected_case_count_per_arm"])
    arm_names = list(gates["expected_arms"])
    continual = summary["by_arm"]["adaptive"]
    commissioning = summary["by_arm"]["commissioning_only_dynamics"]
    no_dynamics = summary["by_arm"]["no_dynamics_adaptation"]
    matrix_complete = all(
        summary["by_arm"].get(name, {}).get("case_count") == expected
        and summary["by_arm"].get(name, {}).get("unique_case_key_count") == expected
        for name in arm_names
    )
    if matrix_complete:
        expected_keys = summary["by_arm"][arm_names[0]]["case_keys"]
        matrix_complete = all(
            summary["by_arm"][name]["case_keys"] == expected_keys
            for name in arm_names
        )
    continual_median = continual["full_horizon_tracking_rmse_deg_median"]
    commissioning_median = commissioning[
        "full_horizon_tracking_rmse_deg_median"
    ]
    no_dynamics_median = no_dynamics["full_horizon_tracking_rmse_deg_median"]

    def beneficial_against(
        comparator: dict[str, Any], comparator_median: float | None,
        *, median_fraction: float, completion_margin: float,
    ) -> bool:
        return (
            comparator["full_horizon_metric_count"] == expected
            and continual_median is not None
            and comparator_median is not None
            and continual_median
            <= comparator_median * (1.0 - median_fraction)
        ) or (
            comparator["completion_rate"]
            <= continual["completion_rate"] - completion_margin
        )

    checks = {
        "complete_paired_matrix": matrix_complete,
        "continual_completion": continual["completion_rate"] == 1.0,
        "continual_full_horizon": continual["full_horizon_metric_count"] == expected,
        "continual_clearance_evaluated": continual["clearance_evaluated_count"] == expected,
        "continual_post_probe_reference_evaluated": continual[
            "post_probe_constructed_reference_clearance_evaluated_count"
        ] == expected,
        "continual_post_probe_reference_clearance": continual[
            "post_probe_constructed_reference_clearance_violation_count"
        ] == 0,
        "continual_probe_clearance": continual["probe_clearance_violation_count"] == 0,
        "continual_task_clearance": continual["table_clearance_violation_samples"] == 0,
        "continual_probe_rom": continual["probe_rom_violation_count"] == 0,
        "continual_task_rom": continual["rom_violation_samples"] == 0,
        "continual_probe_consistency": continual["probe_consistency_abort_count"] == 0,
        "continual_probe_settle_timeout": continual["probe_settle_timeout_count"] == 0,
        "continual_solver": continual["solver_failure_count"] == 0,
        "continual_safety": continual["safety_abort_count"] == 0,
        "continual_force": continual["full_episode_force_peak_n_max"] <= gates["force_peak_n_maximum"],
        "continual_moment": continual["full_episode_moment_peak_nm_max"] <= gates["moment_peak_nm_maximum"],
        "continual_benefits_over_commissioning_only": beneficial_against(
            commissioning,
            commissioning_median,
            median_fraction=float(gates["continual_vs_commissioning_median_improvement_fraction_minimum"]),
            completion_margin=float(gates["continual_vs_commissioning_completion_rate_margin_minimum"]),
        ),
        "continual_benefits_over_no_dynamics": beneficial_against(
            no_dynamics,
            no_dynamics_median,
            median_fraction=float(gates["continual_vs_no_dynamics_median_improvement_fraction_minimum"]),
            completion_margin=float(gates["continual_vs_no_dynamics_completion_rate_margin_minimum"]),
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "criteria_frozen_before_results": True,
    }


def evaluate_state_residual_development_gates(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    gates: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Evaluate the frozen four-arm state-residual development contract."""

    if gates is None:
        return None
    expected = int(gates["expected_case_count_per_arm"])
    arm_names = list(gates["expected_arms"])
    candidate = summary["by_arm"]["adaptive_state_residual"]
    baseline = summary["by_arm"]["adaptive"]
    commissioning = summary["by_arm"]["commissioning_only_dynamics"]
    oracle = summary["by_arm"]["oracle"]
    matrix_complete = all(
        summary["by_arm"].get(name, {}).get("case_count") == expected
        and summary["by_arm"].get(name, {}).get("unique_case_key_count") == expected
        for name in arm_names
    )
    if matrix_complete:
        expected_keys = summary["by_arm"][arm_names[0]]["case_keys"]
        matrix_complete = all(
            summary["by_arm"][name]["case_keys"] == expected_keys
            for name in arm_names
        )

    candidate_rows = [
        row for row in rows if row.get("arm") == "adaptive_state_residual"
    ]
    telemetry_keys = (
        "task_residual_bias_peak_abs_nm",
        "task_residual_bias_max_step_nm",
        "task_residual_bias_total_variation_l1_nm",
        "task_residual_bias_sign_reversal_count",
        "task_state_residual_weight_peak_l2_nm",
        "task_state_residual_weight_max_component_step_nm",
        "task_state_residual_weight_total_variation_l1_nm",
        "task_state_residual_coefficient_projection_hit_count",
        "task_state_residual_observed_output_cap_hit_count",
        "task_state_residual_prediction_dynamics_component_evaluation_count",
        "task_state_residual_prediction_dynamics_component_cap_hit_count",
        "task_state_residual_chosen_rollout_component_evaluation_count",
        "task_state_residual_chosen_rollout_component_cap_hit_count",
    )
    telemetry_complete_finite = len(candidate_rows) == expected and all(
        all(
            key in row
            and isinstance(row[key], (int, float))
            and np.isfinite(float(row[key]))
            for key in telemetry_keys
        )
        for row in candidate_rows
    )
    telemetry_exercised = len(candidate_rows) == expected and all(
        int(
            row.get(
                "task_state_residual_prediction_dynamics_component_evaluation_count",
                0,
            )
        )
        > 0
        and int(
            row.get(
                "task_state_residual_chosen_rollout_component_evaluation_count",
                0,
            )
        )
        > 0
        for row in candidate_rows
    )
    weights_and_outputs_bounded = len(candidate_rows) == expected and all(
        bool(row.get("task_state_residual_weights_finite", False))
        and bool(
            row.get(
                "task_state_residual_weights_within_l2_projection_limit",
                False,
            )
        )
        and bool(row.get("task_residual_bias_finite", False))
        and bool(row.get("task_residual_bias_within_limit", False))
        and float(row.get("task_residual_bias_peak_abs_nm", np.inf))
        <= float(gates["residual_output_abs_nm_maximum"]) + 1.0e-12
        for row in candidate_rows
    )
    feature_contract = len(candidate_rows) == expected and all(
        row.get("task_state_residual_feature_names")
        == ["constant", "q1_rom", "q2_rom", "dq1_bounded", "dq2_bounded"]
        and float(row.get("task_state_residual_velocity_scale_rad_s", np.nan))
        == float(gates["state_residual_velocity_scale_rad_s"])
        and bool(row.get("task_beta_updates_enabled_for_arm", False))
        for row in candidate_rows
    )
    truth_firewall = len(candidate_rows) == expected and all(
        not bool(row.get("truth_firewall", {}).get("deployable_truth_consumed", True))
        for row in candidate_rows
    )

    candidate_median = candidate["tracking_rmse_deg_median"]
    candidate_p95 = candidate["tracking_rmse_deg_p95"]
    baseline_median = baseline["tracking_rmse_deg_median"]
    baseline_p95 = baseline["tracking_rmse_deg_p95"]
    commissioning_median = commissioning["tracking_rmse_deg_median"]
    oracle_median = oracle["tracking_rmse_deg_median"]
    commission_benefit = (
        candidate["tracking_metric_count"] == expected
        and commissioning["tracking_metric_count"] == expected
        and candidate_median is not None
        and commissioning_median is not None
        and candidate_median
        <= commissioning_median
        * (
            1.0
            - float(
                gates[
                    "candidate_vs_commissioning_median_improvement_fraction_minimum"
                ]
            )
        )
    ) or (
        commissioning["completion_rate"]
        <= candidate["completion_rate"]
        - float(gates["candidate_vs_commissioning_completion_rate_margin_minimum"])
    )
    zero_events = all(
        candidate[key] == 0
        for key in (
            "rom_violation_samples",
            "probe_rom_violation_count",
            "probe_clearance_violation_count",
            "table_clearance_violation_samples",
            "post_probe_constructed_reference_clearance_violation_count",
            "probe_consistency_abort_count",
            "probe_settle_timeout_count",
            "solver_failure_count",
            "safety_abort_count",
            "estimated_rom_supervisor_abort_count",
        )
    )
    checks = {
        "complete_paired_matrix": matrix_complete,
        "candidate_tracking_full_denominator": candidate["tracking_metric_count"]
        == expected,
        "candidate_full_horizon_metrics": candidate["full_horizon_metric_count"]
        == expected,
        "baseline_tracking_full_denominator": baseline["tracking_metric_count"]
        == expected,
        "commissioning_tracking_full_denominator": commissioning[
            "tracking_metric_count"
        ]
        == expected,
        "oracle_tracking_full_denominator": oracle["tracking_metric_count"]
        == expected,
        "candidate_completion_not_below_v21": candidate["completion_rate"]
        >= baseline["completion_rate"],
        "candidate_median_strictly_lower_than_v21": candidate_median is not None
        and baseline_median is not None
        and candidate_median < baseline_median,
        "candidate_p95_no_worse_than_v21": candidate_p95 is not None
        and baseline_p95 is not None
        and candidate_p95 <= baseline_p95,
        "candidate_completion_absolute": candidate["completion_rate"]
        >= float(gates["candidate_completion_rate_minimum"]),
        "candidate_median_absolute": candidate_median is not None
        and candidate_median
        <= float(gates["candidate_tracking_rmse_deg_median_maximum"]),
        "candidate_p95_absolute": candidate_p95 is not None
        and candidate_p95
        <= float(gates["candidate_tracking_rmse_deg_p95_maximum"]),
        "candidate_force_absolute": candidate["full_episode_force_peak_n_max"]
        is not None
        and candidate["full_episode_force_peak_n_max"]
        <= float(gates["force_peak_n_maximum"]),
        "candidate_moment_absolute": candidate[
            "full_episode_moment_peak_nm_max"
        ]
        is not None
        and candidate["full_episode_moment_peak_nm_max"]
        <= float(gates["moment_peak_nm_maximum"]),
        "candidate_zero_events": zero_events,
        "candidate_clearance_evaluated": candidate["clearance_evaluated_count"]
        == expected,
        "candidate_post_probe_reference_evaluated": candidate[
            "post_probe_constructed_reference_clearance_evaluated_count"
        ]
        == expected,
        "candidate_beats_commissioning": commission_benefit,
        "candidate_oracle_gap": candidate_median is not None
        and oracle_median is not None
        and candidate_median - oracle_median
        <= float(gates["candidate_minus_oracle_median_gap_deg_maximum"]),
        "candidate_telemetry_complete_finite": telemetry_complete_finite,
        "candidate_telemetry_exercised": telemetry_exercised,
        "candidate_weights_and_outputs_bounded": weights_and_outputs_bounded,
        "candidate_feature_contract": feature_contract,
        "candidate_truth_firewall": truth_firewall,
        "oracle_full_horizon_metrics": oracle["full_horizon_metric_count"]
        == expected,
        "oracle_completion": oracle["completion_rate"] == 1.0,
        "oracle_clearance_evaluated": oracle["clearance_evaluated_count"]
        == expected,
        "oracle_post_probe_reference_evaluated": oracle[
            "post_probe_constructed_reference_clearance_evaluated_count"
        ]
        == expected,
        "oracle_zero_events": all(
            oracle[key] == 0
            for key in (
                "rom_violation_samples",
                "probe_rom_violation_count",
                "probe_clearance_violation_count",
                "table_clearance_violation_samples",
                "post_probe_constructed_reference_clearance_violation_count",
                "probe_consistency_abort_count",
                "probe_settle_timeout_count",
                "solver_failure_count",
                "safety_abort_count",
                "estimated_rom_supervisor_abort_count",
            )
        ),
        "oracle_force_absolute": oracle["full_episode_force_peak_n_max"]
        is not None
        and oracle["full_episode_force_peak_n_max"]
        <= float(gates["force_peak_n_maximum"]),
        "oracle_moment_absolute": oracle["full_episode_moment_peak_nm_max"]
        is not None
        and oracle["full_episode_moment_peak_nm_max"]
        <= float(gates["moment_peak_nm_maximum"]),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "criteria_frozen_before_results": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    wrapper_config = json.loads(args.config.read_text())
    base_config_path = wrapper_config.get("base_config_path")
    if base_config_path is not None:
        base_config_path = Path(base_config_path).resolve()
        config = json.loads(base_config_path.read_text())
        config.update(
            {
                key: value
                for key, value in wrapper_config.items()
                if key != "base_config_path"
            }
        )
    else:
        config = wrapper_config
    validate_config(config)
    pre_run_source_seal = validate_expected_source_seal(config)
    configured_case_keys = [
        (
            int(case.get("setup_seed", case.get("seed"))),
            int(
                case.get(
                    "task_seed",
                    int(case.get("setup_seed", case.get("seed"))) + 1_000_000,
                )
            ),
        )
        for case in config["cases"]
    ]
    if len(set(configured_case_keys)) != len(configured_case_keys):
        raise ValueError("campaign config contains duplicate (setup_seed, task_seed) cases")
    package_roots = [
        Path(stage3_human.__file__).resolve().parent,
        Path(stage4_mpc.__file__).resolve().parent,
        Path(functional_benchmark.__file__).resolve().parent,
    ]
    source_paths = [
        args.config,
        Path(__file__).resolve(),
        Path(full3d_time_contract.__file__).resolve(),
        *[path for root in package_roots for path in sorted(root.glob("*.py"))],
    ]
    if base_config_path is not None:
        source_paths.append(base_config_path)
    preregistration_values: list[str] = []
    if config.get("preregistration_path"):
        preregistration_values.append(str(config["preregistration_path"]))
    preregistration_values.extend(
        str(value) for value in config.get("preregistration_paths", [])
    )
    source_paths.extend(Path(value).resolve() for value in preregistration_values)
    if config.get("expected_source_seal_path"):
        source_paths.append(Path(config["expected_source_seal_path"]).resolve())
    source_paths = list(dict.fromkeys(path.resolve() for path in source_paths))
    manifest_before = _manifest(source_paths)
    git_status_before = _git(["status", "--short"])
    actual_status_sha256 = validate_expected_git_status(config, git_status_before)
    args.output_dir.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for case in config["cases"]:
        setup_seed = int(case.get("setup_seed", case.get("seed")))
        task_seed = int(case.get("task_seed", setup_seed + 1_000_000))
        try:
            setup, task = make_benchmark_case(
                setup_seed,
                task_seed=task_seed,
                high_rom=bool(case.get("high_rom", False)),
                task_profile=case.get("task_profile"),
                domain=config.get("hidden_generation"),
            )
        except Exception as error:
            for arm in config["arms"]:
                rows.append(
                    {
                        "schema": "architecture_recovery_v2.closed_loop_case.v1",
                        "arm": arm,
                        "seed": setup_seed,
                        "task_seed": task_seed,
                        "task_id": case.get("task_profile", "generation_failed"),
                        "high_rom_case": bool(case.get("high_rom", False)),
                        "completed": False,
                        "full_horizon_executed": False,
                        "clearance_evaluation_enabled": False,
                        "termination_reason": (
                            f"case_generation_exception:{type(error).__name__}"
                        ),
                        "exception_message": str(error),
                    }
                )
            continue
        for arm in config["arms"]:
            row_started = time.perf_counter()
            try:
                row = run_closed_loop_case(
                    setup,
                    task,
                    arm,
                    dt_s=float(config.get("control_dt_s", 0.02)),
                    probe_duration_s=float(config.get("probe_duration_s", 8.0)),
                    probe_control_dt_s=float(
                        config.get("probe_control_dt_s", 0.01)
                    ),
                    task_dynamics_history_window_samples=config.get(
                        "task_dynamics_history_window_samples"
                    ),
                    task_dynamics_smoothing_alpha=config.get(
                        "task_dynamics_smoothing_alpha"
                    ),
                    task_residual_bias_alpha=config.get(
                        "task_residual_bias_alpha"
                    ),
                    task_residual_bias_limit_nm=float(
                        config.get("task_residual_bias_limit_nm", 12.0)
                    ),
                    evaluation_time_contract=str(
                        config.get(
                            "evaluation_time_contract",
                            "historical_post_state_pre_reference_v1",
                        )
                    ),
                )
            except Exception as error:
                row = {
                    "schema": "architecture_recovery_v2.closed_loop_case.v1",
                    "arm": arm,
                    "seed": setup_seed,
                    "task_seed": task_seed,
                    "task_id": task.task_id,
                    "high_rom_case": task.high_rom,
                    "completed": False,
                    "full_horizon_executed": False,
                    "clearance_evaluation_enabled": False,
                    "termination_reason": f"runner_exception:{type(error).__name__}",
                    "exception_message": str(error),
                    "truth_firewall": {"deployable_truth_consumed": False},
                    "setup_evaluation_only": setup.evaluation_record(),
                    "task_input": task.record(),
                }
            row["runner_wall_time_s"] = time.perf_counter() - row_started
            rows.append(row)
            print(
                f"[{setup_seed}:{task_seed}/{arm}] completed={row.get('completed')} "
                f"rmse={row.get('q_tracking_rmse_deg')} "
                f"reason={row.get('termination_reason')}",
                flush=True,
            )
    summary = summarize(rows)
    gate_result = evaluate_gates(summary, config.get("gates"), rows)
    ablation_gate_result = evaluate_ablation_gates(
        summary, config.get("ablation_gates")
    )
    state_residual_gate_result = evaluate_state_residual_development_gates(
        summary, rows, config.get("state_residual_development_gates")
    )
    manifest_after = _manifest(source_paths)
    git_status_after = _git(["status", "--short"])
    payload = {
        "schema": "architecture_recovery_v2.functional_campaign.v1",
        "evidence_category": config["evidence_category"],
        "study_id": config["study_id"],
        "config_path": str(args.config),
        "config_sha256": _sha256(args.config),
        "base_config_path": (
            str(base_config_path) if base_config_path is not None else None
        ),
        "effective_config": config,
        "git_branch": _git(["branch", "--show-current"]),
        "git_head": _git(["rev-parse", "HEAD"]),
        "source_or_config_changed_during_run": manifest_before != manifest_after,
        "source_manifest_before": manifest_before,
        "source_manifest_after": manifest_after,
        "pre_run_source_seal": pre_run_source_seal,
        "git_status_before_sha256": hashlib.sha256(
            git_status_before.encode("utf-8")
        ).hexdigest(),
        "git_status_after_sha256": hashlib.sha256(
            git_status_after.encode("utf-8")
        ).hexdigest(),
        "git_status_changed_during_run": git_status_before != git_status_after,
        "git_status_before": git_status_before.splitlines(),
        "git_status_after": git_status_after.splitlines(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "conda_default_env": os.environ.get("CONDA_DEFAULT_ENV"),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "strict_json_nonfinite_policy": "nonfinite diagnostic values are encoded as null",
        "hidden_generation": config["hidden_generation"],
        "held_out_policy": config["held_out_policy"],
        "summary": summary,
        "gates": gate_result,
        "ablation_gates": ablation_gate_result,
        "state_residual_development_gates": state_residual_gate_result,
        "rows": rows,
    }
    (args.output_dir / "result.json").write_text(
        json.dumps(
            _strict_json_value(payload), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n"
    )
    snapshot_dir = args.output_dir / "source_snapshot"
    snapshot_dir.mkdir()
    snapshot_manifest: dict[str, str] = {}
    for index, source_path in enumerate(source_paths):
        target = snapshot_dir / f"{index:02d}_{source_path.name}"
        shutil.copy2(source_path, target)
        snapshot_manifest[str(target)] = _sha256(target)
    (args.output_dir / "source_snapshot_manifest.json").write_text(
        json.dumps(snapshot_manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    (args.output_dir / "git_status_before.txt").write_text(git_status_before + "\n")
    (args.output_dir / "git_status_after.txt").write_text(git_status_after + "\n")
    (args.output_dir / "command.txt").write_text(
        "PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:"
        "stages/stage5_personalized_motion_learning/src conda run -n mpc_learn "
        f"python {Path(__file__)} --config {args.config} --output-dir {args.output_dir}\n"
    )


if __name__ == "__main__":
    main()
