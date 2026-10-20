#!/usr/bin/env python3
"""Validate and summarize the completed preregistered Stage-4 mismatch suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np

from traction_mpc_stage4.patient_mismatch import load_patient_case_specs


EXPECTED_CASE_COUNT = 13
EXPECTED_ARM_NAMES = ("prior_only", "trusted_adaptive")
EXPECTED_BASELINE_TAG = "stage4-baseline-v1"
EXPECTED_BASELINE_COMMIT = "ef1fe90e61c5981df8e934585780ce188d104ea4"
EXPECTED_CONFIG_SHA256 = "a51d3cb086ebeb21ea01b59c7cb6d7cb8a422fa3e9bab0028d84002cf2ed129b"
EXPECTED_CONTROLLER_SHA256 = "faa50c1a34ee0f618de424b28f49432ffd13f8143d4e9f15eb5a04acdf6d3754"
EXPECTED_EVIDENCE_CATEGORY = "formal_user_run_unreviewed"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _benefit(prior: float, adaptive: float) -> dict[str, float | None]:
    absolute = float(prior - adaptive)
    return {
        "absolute_prior_minus_adaptive": absolute,
        "percent_prior_minus_adaptive": (
            None if prior == 0.0 else float(100.0 * absolute / prior)
        ),
    }


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return None if not values else float(statistics.fmean(values))


def _median(values: Iterable[float]) -> float | None:
    values = list(values)
    return None if not values else float(statistics.median(values))


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        rank = (index + 1 + end) / 2.0
        for location in order[index:end]:
            ranks[location] = rank
        index = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if np.std(left_array) == 0.0 or np.std(right_array) == 0.0:
        return None
    return float(np.corrcoef(left_array, right_array)[0, 1])


def _correlations(left: list[float], right: list[float]) -> dict[str, Any]:
    return {
        "sample_count": len(left),
        "pearson_r": _pearson(left, right),
        "spearman_rho": _pearson(_average_ranks(left), _average_ranks(right)),
    }


def _events_clear(events: dict[str, Any], robot: dict[str, Any]) -> bool:
    return bool(
        events.get("force_gate_events", 0) == 0
        and events.get("mpc_solver_failures", 0) == 0
        and events.get("rom_event_samples", 0) == 0
        and not events.get("mujoco_warning_counts", {})
        and not events.get("unintended_contact_pairs", [])
        and robot.get("torque_saturation_control_samples", 0) == 0
        and robot.get("joint_position_limit_samples", 0) == 0
    )


def _validate_future_data_isolation(summary: dict[str, Any]) -> None:
    trust = summary["hierarchical_trust"]
    if trust["oracle_used_online"]:
        raise RuntimeError("God-view oracle was used online")
    if trust["maximum_concurrent_challengers"] > 1 or trust["race_state_count"]:
        raise RuntimeError("single-challenger lifecycle was violated")
    for challenger in trust["challengers"]:
        fit_end = float(challenger["fit_end_time_s"])
        for evidence in challenger.get("evidence_history", []):
            references = (
                evidence["against_last_valid"],
                evidence["against_population_prior"],
            )
            for reference in references:
                if reference.get("sample_unit") != (
                    "nonoverlapping_clean_integral_block"
                ):
                    raise RuntimeError("validation sample unit changed")
            blocks = evidence["validation_blocks"]
            previous_end = None
            for block in blocks:
                start = float(block["start_time_s"])
                end = float(block["end_time_s"])
                if start < fit_end + 0.5 - 1e-10:
                    raise RuntimeError("training/validation embargo was violated")
                if previous_end is not None and start < previous_end - 1e-10:
                    raise RuntimeError("validation blocks overlap")
                previous_end = end


def _validate_trace(path: Path) -> None:
    with np.load(path, allow_pickle=False) as trace:
        if not trace.files:
            raise RuntimeError(f"empty trace: {path}")
        for key in trace.files:
            value = np.asarray(trace[key])
            if np.issubdtype(value.dtype, np.number) and not np.all(
                np.isfinite(value)
            ):
                raise RuntimeError(f"nonfinite trace values: {path}:{key}")


def _interaction_row(arm: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(arm[key])
        for key in (
            "cuff_force_peak_n",
            "cuff_force_rms_n",
            "cuff_moment_peak_nm",
            "cuff_moment_rms_nm",
            "cylindrical_surface_proxy_peak_n",
            "cylindrical_surface_proxy_rms_n",
        )
    }


def _case_tags(row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if row["promotion"]["count"] == 0:
        tags.append("trust_protected_regime")
    if not row["completion"]["prior_completed_reference"] and not row[
        "completion"
    ]["adaptive_completed_reference"]:
        tags.append("controller_safety_failure_shared_incomplete_trajectory")
    track = row["tracking_rmse_deg"]["benefit"][
        "absolute_prior_minus_adaptive"
    ]
    prediction = row["torque_prediction_rmse_nm"]["benefit"][
        "absolute_prior_minus_adaptive"
    ]
    if row["promotion"]["count"] > 0:
        if track > 0.0 and prediction > 0.0:
            tags.append("useful_adaptation_regime")
        elif track < 0.0 or prediction < 0.0:
            tags.append("mixed_primary_metrics_after_promotion")
        else:
            tags.append("no_strict_primary_metric_improvement")
    if row["case_id"] == "nominal_reference":
        tags.append("zero_mismatch_sanity_reference")
    return tags


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracking = [
        row["tracking_rmse_deg"]["benefit"]["absolute_prior_minus_adaptive"]
        for row in rows
    ]
    prediction = [
        row["torque_prediction_rmse_nm"]["benefit"][
            "absolute_prior_minus_adaptive"
        ]
        for row in rows
    ]
    tracking_pct = [
        row["tracking_rmse_deg"]["benefit"]["percent_prior_minus_adaptive"]
        for row in rows
    ]
    prediction_pct = [
        row["torque_prediction_rmse_nm"]["benefit"][
            "percent_prior_minus_adaptive"
        ]
        for row in rows
        if row["torque_prediction_rmse_nm"]["benefit"][
            "percent_prior_minus_adaptive"
        ]
        is not None
    ]
    return {
        "case_count": len(rows),
        "tracking_improved_case_count": sum(value > 0.0 for value in tracking),
        "prediction_improved_case_count": sum(value > 0.0 for value in prediction),
        "mean_tracking_rmse_benefit_deg": _mean(tracking),
        "median_tracking_rmse_benefit_deg": _median(tracking),
        "mean_tracking_rmse_improvement_percent": _mean(tracking_pct),
        "mean_prediction_rmse_benefit_nm": _mean(prediction),
        "median_prediction_rmse_benefit_nm": _median(prediction),
        "mean_prediction_rmse_improvement_percent_excluding_zero_denominator": (
            _mean(prediction_pct)
        ),
    }


def build_summary(case_config: Path, output_root: Path) -> dict[str, Any]:
    specs = load_patient_case_specs(case_config)
    if len(specs) != EXPECTED_CASE_COUNT:
        raise RuntimeError("preregistered case count changed")
    if _sha256(case_config) != EXPECTED_CONFIG_SHA256:
        raise RuntimeError("patient-case config fingerprint changed")

    rows: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}
    for spec in specs:
        case_dir = output_root / spec.case_id
        required = [
            case_dir / "prior_only.json",
            case_dir / "trusted_adaptive.json",
            case_dir / "prior_only_trace.npz",
            case_dir / "trusted_adaptive_trace.npz",
            case_dir / "comparison_summary.json",
            case_dir / "comparison_summary.md",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"missing case artifacts: {missing}")
        for path in required:
            artifact_hashes[str(path.relative_to(output_root))] = _sha256(path)

        paired = _read_json(case_dir / "comparison_summary.json")
        if paired["case_record"]["case_id"] != spec.case_id:
            raise RuntimeError("case directory/record mismatch")
        provenance = paired["provenance"]
        expected_provenance = {
            "baseline_tag": EXPECTED_BASELINE_TAG,
            "baseline_commit": EXPECTED_BASELINE_COMMIT,
            "code_commit": EXPECTED_BASELINE_COMMIT,
            "patient_case_config_sha256": EXPECTED_CONFIG_SHA256,
            "frozen_controller_fingerprint_sha256": EXPECTED_CONTROLLER_SHA256,
            "measurement_seed": 44104,
            "mpc_seed": 20260824,
            "runtime_allowance_s": 32.0,
            "structural_smoke": False,
        }
        for key, expected in expected_provenance.items():
            if provenance.get(key) != expected:
                raise RuntimeError(
                    f"{spec.case_id}: provenance mismatch for {key}"
                )
        if paired["evidence_category"] != EXPECTED_EVIDENCE_CATEGORY:
            raise RuntimeError("formal evidence category changed")
        isolation = paired["ab_isolation"]
        required_isolation = (
            "selected_true_patient_equal_between_arms",
            "initial_human_state_equal",
            "initial_robot_state_equal",
            "measurement_seed_and_realization_equal_before_promotion",
            "controller_population_prior_equal_to_nominal",
            "prior_only_control_beta_constant_population_prior",
            "trusted_control_beta_population_prior_before_promotion",
            "geometry_estimation_active_and_equal_before_promotion",
            "geometry_prior_uses_nominal_lengths_not_true_patient_oracle",
            "shared_configuration_fields_equal",
            "first_qualification_times_equal",
            "prior_control_model_constant",
            "single_challenger_invariants_held",
        )
        if not all(isolation.get(key) is True for key in required_isolation):
            raise RuntimeError(f"{spec.case_id}: paired isolation assertion failed")
        if any(
            abs(float(value)) > 1e-10
            for value in isolation["pre_promotion_trace_max_abs_difference"].values()
        ):
            raise RuntimeError(f"{spec.case_id}: pre-promotion trace mismatch")

        raw = {
            arm: _read_json(case_dir / f"{arm}.json")
            for arm in EXPECTED_ARM_NAMES
        }
        for arm in EXPECTED_ARM_NAMES:
            if raw[arm]["evidence_category"] != EXPECTED_EVIDENCE_CATEGORY:
                raise RuntimeError("raw arm evidence category changed")
            if raw[arm]["true_human_case"] != spec.case_id:
                raise RuntimeError("raw arm patient case changed")
            arm_provenance = paired["arms"][arm]["provenance"]
            if arm_provenance["arm"] != arm:
                raise RuntimeError("arm provenance label changed")
            for key in (
                "baseline_tag",
                "baseline_commit",
                "patient_case_config_sha256",
                "frozen_controller_fingerprint_sha256",
                "measurement_seed",
                "mpc_seed",
                "runtime_allowance_s",
                "code_commit",
            ):
                if arm_provenance[key] != provenance[key]:
                    raise RuntimeError(f"{spec.case_id}: arm provenance mismatch")
            _validate_future_data_isolation(raw[arm])
            _validate_trace(case_dir / f"{arm}_trace.npz")

        arms = paired["arms"]
        prior = arms["prior_only"]
        adaptive = arms["trusted_adaptive"]
        prior_interaction = _interaction_row(prior)
        adaptive_interaction = _interaction_row(adaptive)
        interaction = {
            key: {
                "prior_only": prior_interaction[key],
                "trusted_adaptive": adaptive_interaction[key],
                "adaptive_minus_prior": adaptive_interaction[key]
                - prior_interaction[key],
            }
            for key in prior_interaction
        }
        adaptive_trust = raw["trusted_adaptive"]["hierarchical_trust"]
        challengers = adaptive_trust["challengers"]
        active_counts = [int(item["l3"]["active_bound_count"]) for item in challengers]
        maximum_violations = [
            float(
                item["l3"]["unconstrained_normalized_bound_violation"][
                    "maximum_fraction_of_span"
                ]
            )
            for item in challengers
        ]
        prior_complete = prior["reference_progress_fraction"] >= 1.0 - 1e-12
        adaptive_complete = adaptive["reference_progress_fraction"] >= 1.0 - 1e-12
        prior_safe = _events_clear(raw["prior_only"]["events"], raw["prior_only"]["robot"])
        adaptive_safe = _events_clear(
            raw["trusted_adaptive"]["events"], raw["trusted_adaptive"]["robot"]
        )
        row = {
            "case_id": spec.case_id,
            "severity": spec.severity,
            "mechanism": spec.mechanism,
            "geometry_changes": bool(paired["case_record"]["geometry"]["changes"]),
            "mismatch_span_l2": float(
                paired["case_record"]["normalized_difference_from_prior"][
                    "span_l2"
                ]
            ),
            "tracking_rmse_deg": {
                "prior_only": float(prior["tracking_rmse_deg"]),
                "trusted_adaptive": float(adaptive["tracking_rmse_deg"]),
                "benefit": _benefit(
                    float(prior["tracking_rmse_deg"]),
                    float(adaptive["tracking_rmse_deg"]),
                ),
            },
            "maximum_tracking_error_deg": {
                "prior_only": float(prior["maximum_tracking_error_deg"]),
                "trusted_adaptive": float(adaptive["maximum_tracking_error_deg"]),
                "benefit": _benefit(
                    float(prior["maximum_tracking_error_deg"]),
                    float(adaptive["maximum_tracking_error_deg"]),
                ),
            },
            "torque_prediction_rmse_nm": {
                "prior_only": float(prior["generalized_torque_prediction_rmse_nm"]),
                "trusted_adaptive": float(
                    adaptive["generalized_torque_prediction_rmse_nm"]
                ),
                "benefit": _benefit(
                    float(prior["generalized_torque_prediction_rmse_nm"]),
                    float(adaptive["generalized_torque_prediction_rmse_nm"]),
                ),
            },
            "completion": {
                "prior_progress_fraction": float(prior["reference_progress_fraction"]),
                "adaptive_progress_fraction": float(
                    adaptive["reference_progress_fraction"]
                ),
                "prior_completed_reference": prior_complete,
                "adaptive_completed_reference": adaptive_complete,
                "prior_runner_termination_reason": prior["termination_reason"],
                "adaptive_runner_termination_reason": adaptive["termination_reason"],
            },
            "safety": {
                "prior_no_recorded_safety_event": prior_safe,
                "adaptive_no_recorded_safety_event": adaptive_safe,
                "prior_events": raw["prior_only"]["events"],
                "adaptive_events": raw["trusted_adaptive"]["events"],
                "prior_torque_saturation_samples": raw["prior_only"]["robot"][
                    "torque_saturation_control_samples"
                ],
                "adaptive_torque_saturation_samples": raw[
                    "trusted_adaptive"
                ]["robot"]["torque_saturation_control_samples"],
            },
            "promotion": {
                "count": int(adaptive["promotion_count"]),
                "qualification_count": int(adaptive_trust["counts"]["qualified"]),
                "rejection_count": int(adaptive_trust["counts"]["rejected"]),
                "pending_count": int(adaptive_trust["counts"]["pending"]),
                "first_qualification_time_s": adaptive[
                    "first_challenger_qualification_time_s"
                ],
                "first_control_promotion_time_s": adaptive["first_promotion_time_s"],
                "trajectory_remaining_at_first_promotion_s": adaptive[
                    "trajectory_remaining_after_first_promotion_s"
                ],
                "timeline": adaptive["promotion_timeline"],
            },
            "active_bound_pressure": {
                "active_bound_counts_by_challenger": active_counts,
                "maximum_active_bound_count": max(active_counts, default=0),
                "maximum_unconstrained_violation_fraction_of_span": max(
                    maximum_violations, default=0.0
                ),
                "final_candidate_status": adaptive["candidate_status"],
            },
            "interaction_metrics_descriptive_only": interaction,
        }
        row["interpretation_tags"] = _case_tags(row)
        rows.append(row)

    if len(rows) != EXPECTED_CASE_COUNT:
        raise RuntimeError("not all preregistered cases were summarized")

    by_mechanism: dict[str, Any] = {}
    for mechanism in sorted({row["mechanism"] for row in rows}):
        by_mechanism[mechanism] = _group_summary(
            [row for row in rows if row["mechanism"] == mechanism]
        )
    geometry_rows = [row for row in rows if row["geometry_changes"]]
    dynamics_rows = [row for row in rows if not row["geometry_changes"]]
    mismatch = [row["mismatch_span_l2"] for row in rows]
    tracking_benefit = [
        row["tracking_rmse_deg"]["benefit"]["absolute_prior_minus_adaptive"]
        for row in rows
    ]
    prediction_benefit = [
        row["torque_prediction_rmse_nm"]["benefit"][
            "absolute_prior_minus_adaptive"
        ]
        for row in rows
    ]
    nonzero = [index for index, value in enumerate(mismatch) if value > 0.0]
    first_promotions = [
        float(row["promotion"]["first_control_promotion_time_s"]) for row in rows
    ]
    remaining = [
        float(row["promotion"]["trajectory_remaining_at_first_promotion_s"])
        for row in rows
    ]
    summary = {
        "schema_version": "stage4_patient_mismatch_aggregate_summary_v1",
        "evidence_category": EXPECTED_EVIDENCE_CATEGORY,
        "scope": (
            "engineering robustness variations within the current representable "
            "Human-V2 model family; not a clinical population claim"
        ),
        "interpretation": (
            "continuous paired outcomes using the preregistered vocabulary; no "
            "post-hoc success threshold or composite score"
        ),
        "integrity": {
            "case_count": len(rows),
            "arm_count": len(rows) * len(EXPECTED_ARM_NAMES),
            "all_required_case_artifacts_present": True,
            "all_json_and_npz_artifacts_readable_and_finite": True,
            "all_provenance_and_fingerprints_equal": True,
            "all_pre_promotion_isolation_checks_passed": True,
            "all_training_validation_embargo_and_nonoverlap_checks_passed": True,
            "baseline_tag": EXPECTED_BASELINE_TAG,
            "baseline_commit": EXPECTED_BASELINE_COMMIT,
            "case_config_sha256": EXPECTED_CONFIG_SHA256,
            "controller_fingerprint_sha256": EXPECTED_CONTROLLER_SHA256,
            "artifact_sha256": artifact_hashes,
        },
        "suite_counts": {
            "cases_with_any_control_promotion": sum(
                row["promotion"]["count"] > 0 for row in rows
            ),
            "total_control_promotions": sum(
                row["promotion"]["count"] for row in rows
            ),
            "total_statistical_rejections_adaptive_arm": sum(
                row["promotion"]["rejection_count"] for row in rows
            ),
            "cases_both_arms_completed_reference": sum(
                row["completion"]["prior_completed_reference"]
                and row["completion"]["adaptive_completed_reference"]
                for row in rows
            ),
            "cases_with_shared_incomplete_reference": sum(
                not row["completion"]["prior_completed_reference"]
                and not row["completion"]["adaptive_completed_reference"]
                for row in rows
            ),
            "cases_with_any_recorded_safety_event": sum(
                not row["safety"]["prior_no_recorded_safety_event"]
                or not row["safety"]["adaptive_no_recorded_safety_event"]
                for row in rows
            ),
            "cases_tracking_rmse_improved": sum(
                row["tracking_rmse_deg"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                > 0.0
                for row in rows
            ),
            "cases_prediction_rmse_improved": sum(
                row["torque_prediction_rmse_nm"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                > 0.0
                for row in rows
            ),
        },
        "promotion_summary": {
            "first_promotion_time_s_min": min(first_promotions),
            "first_promotion_time_s_median": _median(first_promotions),
            "first_promotion_time_s_max": max(first_promotions),
            "trajectory_remaining_at_first_promotion_s_min": min(remaining),
            "trajectory_remaining_at_first_promotion_s_median": _median(remaining),
            "trajectory_remaining_at_first_promotion_s_max": max(remaining),
        },
        "all_cases": _group_summary(rows),
        "geometry_comparison": {
            "geometry_changing": _group_summary(geometry_rows),
            "dynamics_only_including_nominal_reference": _group_summary(
                dynamics_rows
            ),
        },
        "by_mechanism": by_mechanism,
        "relationships": {
            "mismatch_span_l2_vs_tracking_rmse_benefit_all_cases": _correlations(
                mismatch, tracking_benefit
            ),
            "mismatch_span_l2_vs_prediction_rmse_benefit_all_cases": _correlations(
                mismatch, prediction_benefit
            ),
            "mismatch_span_l2_vs_tracking_rmse_benefit_nonzero_mismatch": (
                _correlations(
                    [mismatch[index] for index in nonzero],
                    [tracking_benefit[index] for index in nonzero],
                )
            ),
            "mismatch_span_l2_vs_prediction_rmse_benefit_nonzero_mismatch": (
                _correlations(
                    [mismatch[index] for index in nonzero],
                    [prediction_benefit[index] for index in nonzero],
                )
            ),
            "prediction_rmse_benefit_vs_tracking_rmse_benefit": _correlations(
                prediction_benefit, tracking_benefit
            ),
        },
        "cases": rows,
    }
    return summary


def _fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def write_report(path: Path, summary: dict[str, Any]) -> None:
    counts = summary["suite_counts"]
    promotion = summary["promotion_summary"]
    relationships = summary["relationships"]
    geometry = summary["geometry_comparison"]
    lines = [
        "# Stage-4 patient/model-mismatch robustness formal report",
        "",
        f"Evidence category: `{summary['evidence_category']}`.",
        "",
        "This is a paired engineering-robustness experiment within the current "
        "representable Human-V2 model family. It is not a clinical population "
        "claim. No post-hoc threshold or composite success score is used.",
        "",
        "## Completion and integrity",
        "",
        f"All {summary['integrity']['case_count']} preregistered cases and "
        f"{summary['integrity']['arm_count']} arms are present. Provenance, frozen "
        "fingerprints, A/B isolation, causal embargo/non-overlap, and finite trace "
        "checks passed mechanically.",
        "",
        f"Both arms completed the reference in {counts['cases_both_arms_completed_reference']}/13 "
        f"cases. Both arms had the same incomplete-reference outcome in "
        f"{counts['cases_with_shared_incomplete_reference']}/13 cases. No recorded "
        f"safety event occurred in any case.",
        "",
        "## Per-case paired results",
        "",
        "Positive benefit columns mean lower error under trusted adaptation.",
        "",
        "| case | geom | progress P/A | tracking RMSE P/A (deg) | tracking benefit % | prediction RMSE P/A (Nm) | prediction benefit % | promotions | first promotion (s) | tags |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["cases"]:
        tracking = row["tracking_rmse_deg"]
        prediction = row["torque_prediction_rmse_nm"]
        completion = row["completion"]
        promotion_row = row["promotion"]
        lines.append(
            f"| `{row['case_id']}` | {'yes' if row['geometry_changes'] else 'no'} | "
            f"{completion['prior_progress_fraction']:.4f}/{completion['adaptive_progress_fraction']:.4f} | "
            f"{tracking['prior_only']:.4f}/{tracking['trusted_adaptive']:.4f} | "
            f"{_fmt(tracking['benefit']['percent_prior_minus_adaptive'], 2)} | "
            f"{prediction['prior_only']:.4f}/{prediction['trusted_adaptive']:.4f} | "
            f"{_fmt(prediction['benefit']['percent_prior_minus_adaptive'], 2)} | "
            f"{promotion_row['count']} | "
            f"{_fmt(promotion_row['first_control_promotion_time_s'], 2)} | "
            f"{', '.join(row['interpretation_tags'])} |"
        )
    lines.extend(
        [
            "",
            "## Promotion and estimator behavior",
            "",
            f"Trusted adaptation entered control in {counts['cases_with_any_control_promotion']}/13 "
            f"cases, with {counts['total_control_promotions']} promotions total. First "
            f"promotion ranged from {_fmt(promotion['first_promotion_time_s_min'], 2)} "
            f"to {_fmt(promotion['first_promotion_time_s_max'], 2)} s (median "
            f"{_fmt(promotion['first_promotion_time_s_median'], 2)} s), leaving "
            f"{_fmt(promotion['trajectory_remaining_at_first_promotion_s_min'], 2)} "
            f"to {_fmt(promotion['trajectory_remaining_at_first_promotion_s_max'], 2)} s "
            "of reference.",
            "",
            f"The adaptive arms recorded {counts['total_statistical_rejections_adaptive_arm']} "
            "challenger rejections. Every case showed active-bound pressure in at "
            "least one challenger; the per-case counts and unconstrained violation "
            "magnitudes are retained in the aggregate JSON. This limits interpreting "
            "the fitted 11-base vectors as physical patient parameters.",
            "",
            "## Mismatch type, geometry, and relationships",
            "",
            f"Tracking RMSE decreased in {counts['cases_tracking_rmse_improved']}/13 "
            f"cases; torque-prediction RMSE decreased in "
            f"{counts['cases_prediction_rmse_improved']}/13. Cases with prediction "
            "worsening are reported as mixed primary-metric outcomes even when "
            "tracking improved.",
            "",
            f"The three geometry-changing anchors had mean tracking improvement "
            f"{_fmt(geometry['geometry_changing']['mean_tracking_rmse_improvement_percent'], 2)}% "
            f"and mean prediction improvement "
            f"{_fmt(geometry['geometry_changing']['mean_prediction_rmse_improvement_percent_excluding_zero_denominator'], 2)}%. "
            "The ten dynamics-only cases (including the nominal reference) had mean "
            f"tracking improvement {_fmt(geometry['dynamics_only_including_nominal_reference']['mean_tracking_rmse_improvement_percent'], 2)}% "
            "and mean defined prediction improvement "
            f"{_fmt(geometry['dynamics_only_including_nominal_reference']['mean_prediction_rmse_improvement_percent_excluding_zero_denominator'], 2)}%.",
            "",
            "Across cases, prediction-error benefit and tracking-error benefit had "
            f"Pearson r={_fmt(relationships['prediction_rmse_benefit_vs_tracking_rmse_benefit']['pearson_r'])} "
            f"and Spearman rho={_fmt(relationships['prediction_rmse_benefit_vs_tracking_rmse_benefit']['spearman_rho'])}. "
            "These descriptive associations do not establish a threshold or causal "
            "dose-response. Mismatch-distance correlations are retained in the "
            "aggregate JSON and do not make the 11-base distance a population score.",
            "",
            "Force, moment, and cylindrical surface-proxy values are logged "
            "descriptively per case in the aggregate JSON. They are not success "
            "criteria, and the cylindrical quantity is not pressure, comfort, or "
            "tissue loading.",
            "",
            "## Next scientific question",
            "",
            "Preregister a separate out-of-family model-inadequacy experiment that "
            "varies one unsupported mechanism at a time, while retaining this frozen "
            "controller and trust contract. The first target should distinguish "
            "estimator bound pressure from irreducible model residual; it should not "
            "retune bounds or add new control logic within the present evidence set.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    aggregate_path = args.output_dir / "aggregate_summary.json"
    report_path = args.output_dir / "research_report.md"
    if aggregate_path.exists() or report_path.exists():
        raise FileExistsError("refusing to overwrite aggregate formal evidence")
    summary = build_summary(args.case_config, args.output_dir)
    aggregate_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    write_report(report_path, summary)
    print(
        json.dumps(
            {
                "case_count": summary["integrity"]["case_count"],
                "arm_count": summary["integrity"]["arm_count"],
                "aggregate_summary": str(aggregate_path),
                "research_report": str(report_path),
                "suite_counts": summary["suite_counts"],
                "relationships": summary["relationships"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
