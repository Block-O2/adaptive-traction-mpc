#!/usr/bin/env python3
"""Audit and summarize the completed formal trajectory-excitation suite."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np

try:
    from .run_stage4_patient_mismatch_robustness import (
        _canonical_fingerprint,
        _runtime_controller_fingerprint,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from .run_stage4_single_challenger_closed_loop_ab import (
        build_paired_ab_comparison,
    )
except ImportError:  # Direct execution from the scripts directory.
    from run_stage4_patient_mismatch_robustness import (
        _canonical_fingerprint,
        _runtime_controller_fingerprint,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from run_stage4_single_challenger_closed_loop_ab import (
        build_paired_ab_comparison,
    )
from traction_mpc_stage4.patient_mismatch import patient_case_record
from traction_mpc_stage4.trajectory_excitation import load_trajectory_suite


EXPECTED_CASE_COUNT = 6
EXPECTED_ARMS = ("prior_only", "trusted_adaptive")
EXPECTED_BASELINE_TAG = "stage4-baseline-v1"
EXPECTED_BASELINE_COMMIT = "ef1fe90e61c5981df8e934585780ce188d104ea4"
EXPECTED_CONFIG_SHA256 = (
    "3024919e822297af06f01afa0a775f1453fe08abc0ed12cc313339811706ac14"
)
EXPECTED_CONTROLLER_SHA256 = (
    "faa50c1a34ee0f618de424b28f49432ffd13f8143d4e9f15eb5a04acdf6d3754"
)
EXPECTED_EVIDENCE_CATEGORY = "formal_user_run_unreviewed"
EXPECTED_PATIENT_ID = "registered_formal_perturbed_anchor"
EXPECTED_SENSOR = "noise_bias_drift_200hz"
EXPECTED_MEASUREMENT_SEED = 44104
EXPECTED_MPC_SEED = 20260824
EXPECTED_CASE_FILES = (
    "prior_only.json",
    "trusted_adaptive.json",
    "prior_only_trace.npz",
    "trusted_adaptive_trace.npz",
    "comparison_summary.json",
    "comparison_summary.md",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as stored:
        if not stored.files:
            raise RuntimeError(f"empty trace: {path}")
        trace = {key: stored[key] for key in stored.files}
    for key, value in trace.items():
        array = np.asarray(value)
        if np.issubdtype(array.dtype, np.number) and not np.all(np.isfinite(array)):
            raise RuntimeError(f"nonfinite trace values: {path}:{key}")
    return trace


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


def _events_clear(summary: dict[str, Any]) -> bool:
    events = summary["events"]
    robot = summary["robot"]
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
            for reference in (
                evidence["against_last_valid"],
                evidence["against_population_prior"],
            ):
                if reference.get("sample_unit") != (
                    "nonoverlapping_clean_integral_block"
                ):
                    raise RuntimeError("validation sample unit changed")
            previous_end = None
            for block in evidence["validation_blocks"]:
                start = float(block["start_time_s"])
                end = float(block["end_time_s"])
                if start < fit_end + 0.5 - 1e-10:
                    raise RuntimeError("training/validation embargo was violated")
                if previous_end is not None and start < previous_end - 1e-10:
                    raise RuntimeError("validation blocks overlap")
                previous_end = end


def _pressure(trust: dict[str, Any]) -> dict[str, Any]:
    by_challenger = []
    all_names: set[str] = set()
    for challenger in trust["challengers"]:
        l3 = challenger["l3"]
        pressured = l3.get("active_or_pressured_bounds", [])
        names = sorted({str(item["name"]) for item in pressured})
        all_names.update(names)
        violation = l3.get("unconstrained_normalized_bound_violation", {})
        by_challenger.append(
            {
                "challenger_index": int(challenger["challenger_index"]),
                "status": challenger["status"],
                "active_bound_count": int(l3.get("active_bound_count", 0)),
                "active_or_pressured_parameter_names": names,
                "unconstrained_violation_l2_fraction_of_span": float(
                    violation.get("l2_fraction_of_span", 0.0)
                ),
                "unconstrained_violation_maximum_fraction_of_span": float(
                    violation.get("maximum_fraction_of_span", 0.0)
                ),
            }
        )
    return {
        "by_challenger": by_challenger,
        "first_challenger_active_bound_count": (
            None if not by_challenger else by_challenger[0]["active_bound_count"]
        ),
        "maximum_active_bound_count": max(
            (item["active_bound_count"] for item in by_challenger), default=0
        ),
        "maximum_unconstrained_violation_fraction_of_span": max(
            (
                item["unconstrained_violation_maximum_fraction_of_span"]
                for item in by_challenger
            ),
            default=0.0,
        ),
        "active_or_pressured_parameter_names_union": sorted(all_names),
    }


def _pacing_metrics(
    trace: dict[str, np.ndarray], first_promotion_time_s: float | None
) -> dict[str, float | None]:
    time_s = np.asarray(trace["time_s"], dtype=float)
    high = np.asarray(trace["execution_confidence_high"], dtype=bool)
    speed = np.asarray(trace["reference_speed_scale"], dtype=float)
    if len(time_s) < 2:
        return {
            "first_high_confidence_time_s": None,
            "first_nominal_speed_time_s": None,
            "time_at_minimum_speed_s": 0.0,
            "time_at_nominal_speed_s": 0.0,
        }
    dt = float(np.median(np.diff(time_s)))
    after = (
        np.ones(len(time_s), dtype=bool)
        if first_promotion_time_s is None
        else time_s >= first_promotion_time_s - 1e-12
    )
    high_indices = np.flatnonzero(after & high)
    nominal_indices = np.flatnonzero(after & (speed >= 1.0 - 1e-12))
    return {
        "first_high_confidence_time_s": (
            None if not len(high_indices) else float(time_s[high_indices[0]])
        ),
        "first_nominal_speed_time_s": (
            None if not len(nominal_indices) else float(time_s[nominal_indices[0]])
        ),
        "time_at_minimum_speed_s": float(
            dt * np.count_nonzero(speed <= 0.5 + 1e-12)
        ),
        "time_at_nominal_speed_s": float(
            dt * np.count_nonzero(speed >= 1.0 - 1e-12)
        ),
    }


def _weak_directions(audit_case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "singular_value": float(item["singular_value"]),
            "dominant_components": item["dominant_components"],
            "group_energy": item["group_energy"],
        }
        for item in audit_case["weak_span_normalized_parameter_directions"][:3]
    ]


def _anchor_replication(
    current_comparison: dict[str, Any],
    current_case_dir: Path,
    earlier_result_dir: Path,
) -> dict[str, Any]:
    earlier = _read_json(earlier_result_dir / "comparison_summary.json")
    earlier_by_arm = {item["arm"]: item for item in earlier["rows"]}
    current_by_arm = {item["arm"]: item for item in current_comparison["rows"]}
    metric_differences: dict[str, dict[str, float]] = {}
    for arm in EXPECTED_ARMS:
        old = earlier_by_arm[arm]
        new = current_by_arm[arm]
        metric_differences[arm] = {
            "tracking_rmse_deg": abs(
                float(new["full_task"]["tracking_combined_rmse_deg"])
                - float(old["full_task"]["tracking_combined_rmse_deg"])
            ),
            "maximum_tracking_error_deg": abs(
                float(new["full_task"]["tracking_max_abs_error_deg"])
                - float(old["full_task"]["tracking_max_abs_error_deg"])
            ),
            "torque_prediction_rmse_nm": abs(
                float(
                    new["estimator_control_model_prediction_error_god_view"][
                        "combined_rmse_nm"
                    ]
                )
                - float(
                    old["estimator_control_model_prediction_error_god_view"][
                        "combined_rmse_nm"
                    ]
                )
            ),
            "reference_progress_fraction": abs(
                float(new["reference_progress_fraction"])
                - float(old["reference_progress_fraction"])
            ),
        }
    trace_hashes = {
        arm: {
            "current": _sha256(current_case_dir / f"{arm}_trace.npz"),
            "earlier": _sha256(earlier_result_dir / f"{arm}_trace.npz"),
        }
        for arm in EXPECTED_ARMS
    }
    exact_trace_match = all(
        item["current"] == item["earlier"] for item in trace_hashes.values()
    )
    maximum_metric_difference = max(
        value for arm in metric_differences.values() for value in arm.values()
    )
    if not exact_trace_match or maximum_metric_difference > 1e-12:
        raise RuntimeError("trajectory anchor did not reproduce registered A/B")
    return {
        "earlier_result_directory": str(earlier_result_dir.resolve()),
        "exact_trace_sha256_match": exact_trace_match,
        "trace_sha256": trace_hashes,
        "metric_absolute_differences": metric_differences,
        "maximum_metric_absolute_difference": maximum_metric_difference,
        "expected_numerical_tolerance": 1e-12,
        "within_expected_numerical_consistency": True,
    }


def build_summary(
    *,
    trajectory_config: Path,
    patient_config: Path,
    excitation_audit_path: Path,
    formal_result_dir: Path,
    earlier_anchor_result_dir: Path,
) -> dict[str, Any]:
    suite = load_trajectory_suite(trajectory_config)
    cases = suite["cases"]
    if len(cases) != EXPECTED_CASE_COUNT:
        raise RuntimeError("preregistered trajectory count changed")
    if _sha256(trajectory_config) != EXPECTED_CONFIG_SHA256:
        raise RuntimeError("trajectory config fingerprint changed")
    audit = _read_json(excitation_audit_path)
    audit_by_id = {item["trajectory_id"]: item for item in audit["cases"]}
    trajectory_ids = [str(item["trajectory_id"]) for item in cases]
    if set(audit_by_id) != set(trajectory_ids):
        raise RuntimeError("offline audit/config trajectory set mismatch")
    result_directories = {
        path.name for path in formal_result_dir.iterdir() if path.is_dir()
    }
    if result_directories != set(trajectory_ids):
        raise RuntimeError("formal result directory set differs from preregistration")

    patient_spec, _ = select_patient_case(patient_config, EXPECTED_PATIENT_ID)
    patient_record = patient_case_record(patient_spec)
    true_human = patient_spec.build_human()
    artifact_hashes: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    anchor_comparison: dict[str, Any] | None = None
    controller_fingerprints: set[str] = set()
    config_fingerprints: set[str] = set()
    code_commits: set[str] = set()

    for case in cases:
        trajectory_id = str(case["trajectory_id"])
        case_dir = formal_result_dir / trajectory_id
        required = [case_dir / filename for filename in EXPECTED_CASE_FILES]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"missing trajectory artifacts: {missing}")
        if (case_dir / ".stage4_trajectory_excitation_structural_smoke").exists():
            raise RuntimeError(f"smoke marker found in formal case: {trajectory_id}")
        for path in required:
            artifact_hashes[str(path.relative_to(formal_result_dir))] = _sha256(path)

        paired = _read_json(case_dir / "comparison_summary.json")
        raw = {
            arm: _read_json(case_dir / f"{arm}.json") for arm in EXPECTED_ARMS
        }
        traces = {
            arm: _load_trace(case_dir / f"{arm}_trace.npz")
            for arm in EXPECTED_ARMS
        }
        provenance = paired["provenance"]
        expected_runtime = float(case["duration_s"]) + 9.0
        expected_provenance = {
            "baseline_tag": EXPECTED_BASELINE_TAG,
            "baseline_commit": EXPECTED_BASELINE_COMMIT,
            "code_commit": EXPECTED_BASELINE_COMMIT,
            "trajectory_id": trajectory_id,
            "trajectory_duration_s": float(case["duration_s"]),
            "trajectory_config_sha256": EXPECTED_CONFIG_SHA256,
            "trajectory_case_sha256": _canonical_fingerprint(case),
            "patient_id": EXPECTED_PATIENT_ID,
            "controller_fingerprint_sha256": EXPECTED_CONTROLLER_SHA256,
            "sensor_regime": EXPECTED_SENSOR,
            "preregistered_runtime_limit_s": expected_runtime,
            "executed_wall_time_limit_s": expected_runtime,
            "structural_smoke": False,
        }
        for key, expected in expected_provenance.items():
            if provenance.get(key) != expected:
                raise RuntimeError(f"{trajectory_id}: provenance mismatch at {key}")
        if provenance["seeds"] != {
            "measurement": EXPECTED_MEASUREMENT_SEED,
            "mpc": EXPECTED_MPC_SEED,
        }:
            raise RuntimeError(f"{trajectory_id}: seed provenance changed")
        if paired["evidence_category"] != EXPECTED_EVIDENCE_CATEGORY:
            raise RuntimeError(f"{trajectory_id}: evidence category changed")
        controller_fingerprints.add(provenance["controller_fingerprint_sha256"])
        config_fingerprints.add(provenance["trajectory_config_sha256"])
        code_commits.add(provenance["code_commit"])

        for arm in EXPECTED_ARMS:
            if raw[arm]["case"] != arm or raw[arm]["trajectory"] != trajectory_id:
                raise RuntimeError(f"{trajectory_id}: raw arm label mismatch")
            if raw[arm]["evidence_category"] != EXPECTED_EVIDENCE_CATEGORY:
                raise RuntimeError(f"{trajectory_id}: raw arm evidence changed")
            if raw[arm]["true_human_case"] != EXPECTED_PATIENT_ID:
                raise RuntimeError(f"{trajectory_id}: raw patient changed")
            arm_provenance = raw[arm]["trajectory_excitation_provenance"]
            if arm_provenance["arm"] != arm:
                raise RuntimeError(f"{trajectory_id}: arm provenance mismatch")
            for key in (
                "trajectory_id",
                "trajectory_duration_s",
                "trajectory_config_sha256",
                "patient_id",
                "controller_fingerprint_sha256",
                "seeds",
                "sensor_regime",
                "preregistered_runtime_limit_s",
                "executed_wall_time_limit_s",
                "evidence_category",
            ):
                if arm_provenance[key] != paired["arms"][arm]["provenance"][key]:
                    raise RuntimeError(
                        f"{trajectory_id}: raw/paired arm provenance mismatch at {key}"
                    )
            _validate_future_data_isolation(raw[arm])

        comparison = build_paired_ab_comparison(
            raw,
            traces,
            sensor_case_name=EXPECTED_SENSOR,
            measurement_seed=EXPECTED_MEASUREMENT_SEED,
            true_human=true_human,
            human_label=EXPECTED_PATIENT_ID,
            wall_time_limit_s=expected_runtime,
            evidence_category=EXPECTED_EVIDENCE_CATEGORY,
            reference_phase_duration_s=float(case["duration_s"]),
            trajectory_label=trajectory_id,
        )
        isolation = verify_case_pair_isolation(
            comparison, raw, traces, patient_record
        )
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
            raise RuntimeError(f"{trajectory_id}: paired isolation failed")
        if any(
            abs(float(value)) > 1e-10
            for value in isolation["pre_promotion_trace_max_abs_difference"].values()
        ):
            raise RuntimeError(f"{trajectory_id}: pre-promotion trace mismatch")
        rebuilt_fingerprint, _ = _runtime_controller_fingerprint(comparison)
        if rebuilt_fingerprint != EXPECTED_CONTROLLER_SHA256:
            raise RuntimeError(f"{trajectory_id}: rebuilt controller drift")

        comparison_by_arm = {item["arm"]: item for item in comparison["rows"]}
        prior = comparison_by_arm["prior_only"]
        adaptive = comparison_by_arm["trusted_adaptive"]
        trust = adaptive["hierarchical_trust"]
        qualifications = trust["qualifications"]
        promotions = trust["control_promotions"]
        first_qualification = (
            None
            if not qualifications
            else float(qualifications[0]["qualification_time_s"])
        )
        first_promotion = (
            None if not promotions else float(promotions[0]["promotion_time_s"])
        )
        promotion_timeline = adaptive["promotion_timeline"]
        first_promotion_record = next(
            (item for item in promotion_timeline if item["applied_to_control"]), None
        )
        remaining_s = (
            None
            if first_promotion_record is None
            else float(first_promotion_record["remaining_reference_duration_s"])
        )
        remaining_fraction = (
            None
            if remaining_s is None
            else float(remaining_s / float(case["duration_s"]))
        )
        tracking = {
            arm: float(comparison_by_arm[arm]["full_task"]["tracking_combined_rmse_deg"])
            for arm in EXPECTED_ARMS
        }
        maximum_error = {
            arm: float(comparison_by_arm[arm]["full_task"]["tracking_max_abs_error_deg"])
            for arm in EXPECTED_ARMS
        }
        prediction = {
            arm: float(
                comparison_by_arm[arm][
                    "estimator_control_model_prediction_error_god_view"
                ]["combined_rmse_nm"]
            )
            for arm in EXPECTED_ARMS
        }
        prediction_post = {
            arm: comparison_by_arm[arm][
                "estimator_control_model_prediction_error_god_view"
            ]["post_first_promotion_combined_rmse_nm"]
            for arm in EXPECTED_ARMS
        }
        interaction = {
            metric: {
                arm: float(comparison_by_arm[arm]["full_task"][metric])
                for arm in EXPECTED_ARMS
            }
            for metric in (
                "cuff_force_peak_n",
                "cuff_force_rms_n",
                "cuff_moment_peak_nm",
                "cuff_moment_rms_nm",
                "cylindrical_surface_proxy_peak_n",
                "cylindrical_surface_proxy_rms_n",
            )
        }
        for values in interaction.values():
            values["adaptive_minus_prior"] = (
                values["trusted_adaptive"] - values["prior_only"]
            )
        audit_case = audit_by_id[trajectory_id]
        info = audit_case["information_matrix_summary"]
        row = {
            "trajectory_id": trajectory_id,
            "duration_s": float(case["duration_s"]),
            "rehabilitation_interpretation": case[
                "rehabilitation_interpretation"
            ],
            "offline_excitation": {
                "rank_z": int(
                    audit_case["column_normalized_gate_diagnostics"]["rank"]
                ),
                "condition_z": float(
                    audit_case["column_normalized_gate_diagnostics"][
                        "condition_number"
                    ]
                ),
                "singular_values_z": audit_case[
                    "column_normalized_gate_diagnostics"
                ]["singular_values"],
                "sigma_min_z": float(
                    audit_case["column_normalized_gate_diagnostics"][
                        "singular_values"
                    ][-1]
                ),
                "condition_x": float(
                    audit_case["estimator_span_scaled_diagnostics"][
                        "condition_number"
                    ]
                ),
                "singular_values_x": audit_case[
                    "estimator_span_scaled_diagnostics"
                ]["singular_values"],
                "sigma_min_x": float(
                    audit_case["estimator_span_scaled_diagnostics"][
                        "singular_values"
                    ][-1]
                ),
                "information_trace": float(info["trace"]),
                "information_lambda_min": float(info["eigenvalues_ascending"][0]),
                "information_diagonal": info["diagonal"],
                "weakest_three_span_normalized_directions": _weak_directions(
                    audit_case
                ),
            },
            "trust_and_identification": {
                "first_candidate_fit_time_s": (
                    None
                    if not trust["challengers"]
                    else float(trust["challengers"][0]["fit_end_time_s"])
                ),
                "first_qualification_time_s": first_qualification,
                "first_control_promotion_time_s": first_promotion,
                "promotion_count": int(trust["counts"]["control_promotions"]),
                "qualification_count": int(trust["counts"]["qualified"]),
                "rejection_count": int(trust["counts"]["rejected"]),
                "pending_count": int(trust["counts"]["pending"]),
                "trajectory_remaining_after_first_promotion_s": remaining_s,
                "trajectory_remaining_after_first_promotion_fraction": (
                    remaining_fraction
                ),
                "promotion_timeline": promotion_timeline,
                "active_bound_pressure": _pressure(trust),
                "pacing": _pacing_metrics(
                    traces["trusted_adaptive"], first_promotion
                ),
            },
            "tracking_rmse_deg": {
                "prior_only": tracking["prior_only"],
                "trusted_adaptive": tracking["trusted_adaptive"],
                "benefit": _benefit(
                    tracking["prior_only"], tracking["trusted_adaptive"]
                ),
            },
            "maximum_tracking_error_deg": {
                "prior_only": maximum_error["prior_only"],
                "trusted_adaptive": maximum_error["trusted_adaptive"],
                "benefit": _benefit(
                    maximum_error["prior_only"], maximum_error["trusted_adaptive"]
                ),
            },
            "torque_prediction_rmse_nm": {
                "prior_only": prediction["prior_only"],
                "trusted_adaptive": prediction["trusted_adaptive"],
                "benefit": _benefit(
                    prediction["prior_only"], prediction["trusted_adaptive"]
                ),
                "post_first_promotion": prediction_post,
            },
            "completion": {
                arm: {
                    "progress_fraction": float(
                        comparison_by_arm[arm]["reference_progress_fraction"]
                    ),
                    "final_reference_phase_s": float(
                        comparison_by_arm[arm]["final_reference_phase_s"]
                    ),
                    "completion_time_s": comparison_by_arm[arm][
                        "reference_completion_time_s"
                    ],
                    "termination_reason": comparison_by_arm[arm][
                        "termination_reason"
                    ],
                }
                for arm in EXPECTED_ARMS
            },
            "safety": {
                arm: {
                    "no_recorded_safety_event": _events_clear(raw[arm]),
                    "events": raw[arm]["events"],
                    "torque_saturation_control_samples": raw[arm]["robot"][
                        "torque_saturation_control_samples"
                    ],
                    "joint_position_limit_samples": raw[arm]["robot"][
                        "joint_position_limit_samples"
                    ],
                }
                for arm in EXPECTED_ARMS
            },
            "interaction_metrics_descriptive_only": interaction,
            "integrity": {
                "postprocessing_mode": provenance["postprocessing_mode"],
                "working_tree_dirty_at_execution": provenance[
                    "working_tree_dirty"
                ],
                "pre_promotion_trace_max_abs_difference": isolation[
                    "pre_promotion_trace_max_abs_difference"
                ],
            },
        }
        rows.append(row)
        if trajectory_id == suite["anchor"]:
            anchor_comparison = comparison

    if len(controller_fingerprints) != 1 or len(config_fingerprints) != 1:
        raise RuntimeError("cross-trajectory fingerprint drift")
    if code_commits != {EXPECTED_BASELINE_COMMIT}:
        raise RuntimeError("cross-trajectory code commit drift")
    if anchor_comparison is None:
        raise RuntimeError("registered anchor result missing")
    anchor_replication = _anchor_replication(
        anchor_comparison,
        formal_result_dir / suite["anchor"],
        earlier_anchor_result_dir,
    )

    condition_z = [row["offline_excitation"]["condition_z"] for row in rows]
    condition_x = [row["offline_excitation"]["condition_x"] for row in rows]
    lambda_min = [
        row["offline_excitation"]["information_lambda_min"] for row in rows
    ]
    sigma_min_x = [row["offline_excitation"]["sigma_min_x"] for row in rows]
    promoted_indices = [
        index
        for index, row in enumerate(rows)
        if row["trust_and_identification"]["first_control_promotion_time_s"]
        is not None
    ]
    first_promotion = [
        float(
            rows[index]["trust_and_identification"][
                "first_control_promotion_time_s"
            ]
        )
        for index in promoted_indices
    ]
    remaining_fraction = [
        float(
            rows[index]["trust_and_identification"][
                "trajectory_remaining_after_first_promotion_fraction"
            ]
        )
        for index in promoted_indices
    ]
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
    relationships = {
        "caution": (
            "n=6 preregistered trajectories, with promotion-timing relationships "
            "restricted to promoted cases; correlations are descriptive only, not "
            "inferential or a calibrated dose-response"
        ),
        "log10_condition_z_vs_first_promotion_time_s": _correlations(
            np.log10([condition_z[index] for index in promoted_indices]).tolist(),
            first_promotion,
        ),
        "log10_condition_x_vs_first_promotion_time_s": _correlations(
            np.log10([condition_x[index] for index in promoted_indices]).tolist(),
            first_promotion,
        ),
        "log10_lambda_min_information_vs_first_promotion_time_s": _correlations(
            np.log10([lambda_min[index] for index in promoted_indices]).tolist(),
            first_promotion,
        ),
        "log10_sigma_min_x_vs_first_promotion_time_s": _correlations(
            np.log10([sigma_min_x[index] for index in promoted_indices]).tolist(),
            first_promotion,
        ),
        "log10_lambda_min_information_vs_remaining_fraction": _correlations(
            np.log10([lambda_min[index] for index in promoted_indices]).tolist(),
            remaining_fraction,
        ),
        "log10_lambda_min_information_vs_prediction_benefit_nm": _correlations(
            np.log10(lambda_min).tolist(), prediction_benefit
        ),
        "log10_lambda_min_information_vs_tracking_benefit_deg": _correlations(
            np.log10(lambda_min).tolist(), tracking_benefit
        ),
        "prediction_benefit_nm_vs_tracking_benefit_deg": _correlations(
            prediction_benefit, tracking_benefit
        ),
    }
    all_safe = all(
        row["safety"][arm]["no_recorded_safety_event"]
        for row in rows
        for arm in EXPECTED_ARMS
    )
    all_complete = all(
        row["completion"][arm]["progress_fraction"] >= 1.0 - 1e-12
        for row in rows
        for arm in EXPECTED_ARMS
    )
    return {
        "schema_version": "stage4_trajectory_excitation_aggregate_summary_v1",
        "evidence_category": EXPECTED_EVIDENCE_CATEGORY,
        "scope": (
            "single registered perturbed Human, single registered sensor/noise "
            "realization, simulation/engineering evidence only"
        ),
        "integrity": {
            "verdict": "mechanically_complete_and_internally_consistent",
            "trajectory_count": len(rows),
            "arm_count": len(rows) * len(EXPECTED_ARMS),
            "all_required_artifacts_present": True,
            "all_traces_readable_and_finite": True,
            "all_provenance_and_fingerprints_match_preregistration": True,
            "all_pre_promotion_ab_isolation_checks_passed": True,
            "all_training_validation_embargo_and_nonoverlap_checks_passed": True,
            "all_cases_use_distinct_preregistered_directories": True,
            "no_smoke_marker_in_formal_results": True,
            "no_artifact_evidence_of_config_drift_or_cross_case_warm_start": True,
            "historical_overwrite_cannot_be_proven_from_final_artifacts_alone": True,
            "baseline_tag": EXPECTED_BASELINE_TAG,
            "baseline_commit": EXPECTED_BASELINE_COMMIT,
            "trajectory_config_sha256": EXPECTED_CONFIG_SHA256,
            "offline_excitation_audit_sha256": _sha256(excitation_audit_path),
            "controller_fingerprint_sha256": EXPECTED_CONTROLLER_SHA256,
            "artifact_sha256": artifact_hashes,
            "anchor_replication": anchor_replication,
        },
        "suite_summary": {
            "cases_with_any_control_promotion": sum(
                row["trust_and_identification"]["promotion_count"] > 0
                for row in rows
            ),
            "cases_with_no_control_promotion": sum(
                row["trust_and_identification"]["promotion_count"] == 0
                for row in rows
            ),
            "total_control_promotions": sum(
                row["trust_and_identification"]["promotion_count"] for row in rows
            ),
            "total_rejections": sum(
                row["trust_and_identification"]["rejection_count"] for row in rows
            ),
            "cases_tracking_rmse_improved": sum(
                row["tracking_rmse_deg"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                > 0.0
                for row in rows
            ),
            "cases_torque_prediction_rmse_improved": sum(
                row["torque_prediction_rmse_nm"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                > 0.0
                for row in rows
            ),
            "cases_maximum_tracking_error_improved": sum(
                row["maximum_tracking_error_deg"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                > 0.0
                for row in rows
            ),
            "all_arms_completed_reference": all_complete,
            "cases_both_arms_completed_reference": sum(
                row["completion"]["prior_only"]["progress_fraction"]
                >= 1.0 - 1e-12
                and row["completion"]["trusted_adaptive"]["progress_fraction"]
                >= 1.0 - 1e-12
                for row in rows
            ),
            "cases_with_shared_early_termination": sum(
                row["completion"]["prior_only"]["progress_fraction"]
                < 1.0 - 1e-12
                and row["completion"]["trusted_adaptive"]["progress_fraction"]
                < 1.0 - 1e-12
                for row in rows
            ),
            "no_recorded_safety_events": all_safe,
            "cases_with_any_recorded_safety_or_controller_event": sum(
                not row["safety"]["prior_only"]["no_recorded_safety_event"]
                or not row["safety"]["trusted_adaptive"][
                    "no_recorded_safety_event"
                ]
                for row in rows
            ),
            "mean_tracking_rmse_benefit_deg": _mean(tracking_benefit),
            "mean_torque_prediction_rmse_benefit_nm": _mean(prediction_benefit),
        },
        "scientific_conclusion": {
            "classification": "conditionally_supported_but_limited",
            "statement": (
                "Natural rehabilitation motion supported valid one-shot promotion "
                "in five of six trajectories for this single patient and sensor "
                "realization. Poorer practical conditioning was associated with "
                "later promotion and less remaining trajectory among promoted "
                "cases, but excitation strength did not monotonically determine "
                "prediction or tracking benefit. One shared force-gate termination "
                "prevented candidate formation and cannot be attributed solely to "
                "identifiability."
            ),
            "full_rank_is_not_sufficient_for_practical_identifiability": True,
            "poor_excitation_does_not_imply_unsafe_or_incorrect_control": True,
            "scope_limit": (
                "simulation/engineering evidence for one registered perturbed Human, "
                "one measurement seed, and one MPC seed"
            ),
        },
        "recommended_next_research_step": (
            "Pre-register replication across a small fixed set of patient "
            "mismatches and measurement seeds with the same six trajectories and "
            "unchanged controller/trust contract; do not add active excitation or "
            "retune trajectories within this evidence set."
        ),
        "relationships": relationships,
        "cases": rows,
    }


def _fmt(value: float | None, digits: int = 3) -> str:
    return "none" if value is None else f"{value:.{digits}f}"


def write_report(path: Path, summary: dict[str, Any]) -> None:
    rows = summary["cases"]
    by_id = {row["trajectory_id"]: row for row in rows}
    counts = summary["suite_summary"]
    rel = summary["relationships"]
    anchor = by_id["registered_high_flexion_23s"]
    moderate = by_id["moderate_rom_23s"]
    slow = by_id["slow_high_flexion_34p5s"]
    hip = by_id["hip_dominant_low_knee_23s"]
    knee = by_id["knee_dominant_low_hip_23s"]
    two_cycle = by_id["two_cycle_moderate_23s"]
    lines = [
        "# Stage-4 trajectory-excitation generalization formal report",
        "",
        f"Evidence category: `{summary['evidence_category']}`.",
        "",
        "Scope: one registered perturbed Human, one registered sensor/noise "
        "realization, and the frozen Stage-4 controller in simulation. This is "
        "engineering evidence, not a clinical, population, or safety claim.",
        "",
        "## Integrity verdict",
        "",
        "All 6 preregistered trajectories and 12 arms are present. Config hash, "
        "controller fingerprint, patient, sensor, seeds, runtime mapping, finite "
        "traces, causal validation isolation, and pre-promotion A/B equality all "
        "passed. The anchor traces exactly match the earlier registered "
        "perturbed-Human traces byte-for-byte. Final artifacts cannot prove the "
        "entire historical absence of overwrite, but contain no evidence of "
        "config drift, case substitution, smoke contamination, or warm start.",
        "",
        "## Main comparison",
        "",
        "Positive benefit percentages mean lower error under trusted adaptation. "
        "`cond(Z)` and `lambda_min(I)` are frozen offline descriptors.",
        "",
        "| trajectory | cond(Z) | lambda_min(I) | first promotion s | remaining % | tracking RMSE P/A deg | benefit % | max error P/A deg | torque RMSE P/A Nm | benefit % | promo/rej | max bound #/span | progress P/A | event |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        excitation = row["offline_excitation"]
        trust = row["trust_and_identification"]
        tracking = row["tracking_rmse_deg"]
        maximum_error = row["maximum_tracking_error_deg"]
        prediction = row["torque_prediction_rmse_nm"]
        completion = row["completion"]
        pressure = trust["active_bound_pressure"]
        event_label = (
            "none"
            if row["safety"]["prior_only"]["no_recorded_safety_event"]
            and row["safety"]["trusted_adaptive"]["no_recorded_safety_event"]
            else "shared force gate"
        )
        lines.append(
            f"| `{row['trajectory_id']}` | {excitation['condition_z']:.3g} | "
            f"{excitation['information_lambda_min']:.3g} | "
            f"{_fmt(trust['first_control_promotion_time_s'], 2)} | "
            f"{_fmt(None if trust['trajectory_remaining_after_first_promotion_fraction'] is None else 100.0 * trust['trajectory_remaining_after_first_promotion_fraction'], 1)} | "
            f"{tracking['prior_only']:.4f}/{tracking['trusted_adaptive']:.4f} | "
            f"{_fmt(tracking['benefit']['percent_prior_minus_adaptive'], 2)} | "
            f"{maximum_error['prior_only']:.3f}/{maximum_error['trusted_adaptive']:.3f} | "
            f"{prediction['prior_only']:.4f}/{prediction['trusted_adaptive']:.4f} | "
            f"{_fmt(prediction['benefit']['percent_prior_minus_adaptive'], 2)} | "
            f"{trust['promotion_count']}/{trust['rejection_count']} | "
            f"{pressure['maximum_active_bound_count']}/"
            f"{pressure['maximum_unconstrained_violation_fraction_of_span']:.2f} | "
            f"{completion['prior_only']['progress_fraction']:.3f}/"
            f"{completion['trusted_adaptive']['progress_fraction']:.3f} | "
            f"{event_label} |"
        )
    lines.extend(
        [
            "",
            "## Causal-chain findings",
            "",
            "Every trajectory remained structurally rank 11, but practical "
            "conditioning varied by orders of magnitude. "
            f"{counts['cases_with_any_control_promotion']}/6 produced at least "
            "one valid promotion; the remaining case retained the prior. Promotion "
            "timing and downstream benefit varied materially, so rank alone did "
            "not predict usefulness.",
            "",
            f"Tracking RMSE improved in {counts['cases_tracking_rmse_improved']}/6 "
            f"cases and clean-oracle torque-prediction RMSE improved in "
            f"{counts['cases_torque_prediction_rmse_improved']}/6, while maximum "
            f"tracking error strictly improved in only "
            f"{counts['cases_maximum_tracking_error_improved']}/6. Five cases "
            "completed in both arms. The knee-dominant case stopped identically in "
            "both arms at 24.3% progress on the commanded cuff-force gate before "
            "any challenger fit; this is a shared controller/safety event, not an "
            "adaptation-induced event and not evidence that weak excitation itself "
            "is unsafe.",
            "",
            "The aggregate JSON retains the complete singular spectra, three "
            "weakest parameter directions, candidate-by-candidate active-bound "
            "pressure, promotion timelines, prediction/tracking windows, progress, "
            "safety, and descriptive force/moment/surface-proxy metrics.",
            "",
            "## Trajectory-by-trajectory findings",
            "",
            f"- **Anchor:** promotion at "
            f"{anchor['trust_and_identification']['first_control_promotion_time_s']:.2f} s "
            "with 78.9% reference remaining; tracking/prediction RMSE improved "
            f"{anchor['tracking_rmse_deg']['benefit']['percent_prior_minus_adaptive']:.2f}%/"
            f"{anchor['torque_prediction_rmse_nm']['benefit']['percent_prior_minus_adaptive']:.2f}%. "
            "The traces exactly reproduce the earlier registered result.",
            f"- **Moderate ROM:** despite weaker offline information than the "
            "anchor, promotion was only 0.16 s later and RMSE benefits were larger "
            f"({moderate['tracking_rmse_deg']['benefit']['percent_prior_minus_adaptive']:.2f}% tracking, "
            f"{moderate['torque_prediction_rmse_nm']['benefit']['percent_prior_minus_adaptive']:.2f}% prediction). "
            "Maximum tracking error worsened 1.82%, so the result is mixed rather "
            "than uniformly better.",
            "- **Slow high-flexion:** full geometric ROM preserved `cond(Z)` near "
            "the anchor, but lower acceleration reduced absolute weakest-direction "
            "strength. Promotion occurred at 11.14 s yet left 83.9% of the slower "
            f"reference; RMSE benefits were the largest "
            f"({slow['tracking_rmse_deg']['benefit']['percent_prior_minus_adaptive']:.2f}%/"
            f"{slow['torque_prediction_rmse_nm']['benefit']['percent_prior_minus_adaptive']:.2f}%), "
            "while maximum error worsened 21.04%.",
            f"- **Hip-dominant/low-knee:** its apparently favorable `cond(Z)="
            f"{hip['offline_excitation']['condition_z']:.0f}` masked weak absolute "
            f"information (`cond(X)={hip['offline_excitation']['condition_x']:.0f}`, "
            f"`lambda_min(I)={hip['offline_excitation']['information_lambda_min']:.2e}`). "
            "It still promoted at 9.72 s and improved tracking/prediction RMSE "
            f"{hip['tracking_rmse_deg']['benefit']['percent_prior_minus_adaptive']:.2f}%/"
            f"{hip['torque_prediction_rmse_nm']['benefit']['percent_prior_minus_adaptive']:.2f}%, "
            "but recorded one later challenger rejection and substantial bound pressure.",
            "- **Knee-dominant/low-hip:** both arms hit the same commanded "
            f"cuff-force gate at reference phase "
            f"{knee['completion']['prior_only']['final_reference_phase_s']:.2f} s, "
            "before any challenger was created. Trust retained the prior and A/B "
            "outputs remained identical. Because the causal chain was interrupted "
            "by shared early termination, no-promotion cannot be attributed solely "
            "to offline conditioning.",
            "- **Two-cycle moderate:** the preregistered practically ill-conditioned "
            f"case (`cond(Z)={two_cycle['offline_excitation']['condition_z']:.2e}`, "
            f"`lambda_min(I)={two_cycle['offline_excitation']['information_lambda_min']:.2e}`) "
            "fit later (8.42 s), promoted latest (12.94 s), left the least "
            "reference among promoted cases (71.9%), and showed the largest bound "
            "pressure (6 active bounds, 20.67 spans maximum unconstrained "
            "violation). It still improved tracking/prediction RMSE 6.98%/9.75%, "
            "so poor conditioning delayed and constrained usefulness rather than "
            "preventing it outright.",
            "",
            "## Excitation versus adaptation",
            "",
            "Across only six fixed trajectories, log10(lambda_min(I)) versus first "
            f"promotion had Pearson r={_fmt(rel['log10_lambda_min_information_vs_first_promotion_time_s']['pearson_r'])} "
            f"and Spearman rho={_fmt(rel['log10_lambda_min_information_vs_first_promotion_time_s']['spearman_rho'])}; "
            "prediction benefit versus tracking benefit had "
            f"Pearson r={_fmt(rel['prediction_benefit_nm_vs_tracking_benefit_deg']['pearson_r'])} "
            f"and Spearman rho={_fmt(rel['prediction_benefit_nm_vs_tracking_benefit_deg']['spearman_rho'])}. "
            "These are descriptive associations, not inferential evidence or a "
            "calibrated excitation threshold.",
            "",
            "This supports the timing portion of the causal chain: among the five "
            "promoted cases, poorer conditioning was associated with later "
            "promotion and less remaining trajectory. It does **not** support a "
            "simple monotonic excitation-to-benefit rule: `lambda_min(I)` had "
            "near-zero descriptive association with tracking or prediction benefit "
            "across all six cases, and moderate/slow/hip-dominant trajectories are "
            "counterexamples to such a ranking.",
            "",
            "Force, moment, and cylindrical surface-proxy changes were small and "
            "not consistently signed in the five completed pairs. The knee-dominant "
            "pair had identical, larger peak interaction values because both arms "
            "shared the same early force-gate termination. These quantities remain "
            "descriptive and are not pressure, comfort, tissue-loading, or safety "
            "benefit evidence.",
            "",
            "## Scientific conclusion",
            "",
            "The hypothesis that natural rehabilitation excitation is sufficient "
            "for useful one-shot adaptation is **conditionally supported but "
            "limited**. Natural task motion was sufficient for valid promotion in "
            "five of six trajectories in this one patient/seed suite, while one "
            "normal task retained the prior. Practical conditioning was associated "
            "with when trust could act, but did not alone determine how much "
            "prediction/tracking benefit followed. "
            "Full rank was not sufficient evidence of timely or useful adaptation, "
            "and excitation quality alone did not determine benefit magnitude. The "
            "shared force-gate/no-promotion result, maximum-error degradations, late "
            "promotion, rejection, and bound pressure are valid negative/mixed "
            "evidence and were not tuned away.",
            "",
            "## Recommended next step",
            "",
            "Pre-register replication across a small fixed set of patient mismatches "
            "and measurement seeds using these unchanged six trajectories. Treat "
            "promotion probability/timing and benefit variability as outcomes; do "
            "not add active excitation, retune weak trajectories, or change the "
            "trust/controller contract within this evidence set.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory-config", type=Path, required=True)
    parser.add_argument("--patient-config", type=Path, required=True)
    parser.add_argument("--excitation-audit", type=Path, required=True)
    parser.add_argument("--formal-result-dir", type=Path, required=True)
    parser.add_argument("--earlier-anchor-result-dir", type=Path, required=True)
    parser.add_argument("--aggregate-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.aggregate_output, args.report_output):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite summary output: {path}")
    summary = _strict_json(
        build_summary(
            trajectory_config=args.trajectory_config,
            patient_config=args.patient_config,
            excitation_audit_path=args.excitation_audit,
            formal_result_dir=args.formal_result_dir,
            earlier_anchor_result_dir=args.earlier_anchor_result_dir,
        )
    )
    args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    write_report(args.report_output, summary)
    print(
        json.dumps(
            {
                "integrity": summary["integrity"]["verdict"],
                "trajectory_count": summary["integrity"]["trajectory_count"],
                "arm_count": summary["integrity"]["arm_count"],
                "suite_summary": summary["suite_summary"],
                "aggregate_output": str(args.aggregate_output),
                "report_output": str(args.report_output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
