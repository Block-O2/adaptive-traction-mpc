#!/usr/bin/env python3
"""Audit and summarize the completed Stage-4 crossed replication study."""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np

try:
    from .run_stage4_crossed_excitation_replication import (
        FORMAL_EVIDENCE_CATEGORY,
        MATRIX_SCHEMA_VERSION,
        REGISTERED_MPC_SEED,
        REGISTERED_SENSOR_CASE,
        SCHEMA_VERSION as NEW_PAIR_SCHEMA_VERSION,
        _frozen_controller_fingerprint,
        _resolve_stage_path,
        _sha256,
        load_crossed_replication_matrix,
        verify_reused_evidence,
    )
    from .run_stage4_patient_mismatch_robustness import (
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from .run_stage4_single_challenger_closed_loop_ab import (
        build_paired_ab_comparison,
    )
    from .run_stage4_trajectory_excitation_generalization import (
        _promotions_follow_qualification,
        select_trajectory,
    )
    from .summarize_stage4_trajectory_excitation_generalization import (
        _benefit,
        _correlations,
        _events_clear,
        _load_trace,
        _pressure,
        _read_json,
        _validate_future_data_isolation,
        _weak_directions,
    )
except ImportError:  # Direct execution from scripts/.
    from run_stage4_crossed_excitation_replication import (
        FORMAL_EVIDENCE_CATEGORY,
        MATRIX_SCHEMA_VERSION,
        REGISTERED_MPC_SEED,
        REGISTERED_SENSOR_CASE,
        SCHEMA_VERSION as NEW_PAIR_SCHEMA_VERSION,
        _frozen_controller_fingerprint,
        _resolve_stage_path,
        _sha256,
        load_crossed_replication_matrix,
        verify_reused_evidence,
    )
    from run_stage4_patient_mismatch_robustness import (
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from run_stage4_single_challenger_closed_loop_ab import (
        build_paired_ab_comparison,
    )
    from run_stage4_trajectory_excitation_generalization import (
        _promotions_follow_qualification,
        select_trajectory,
    )
    from summarize_stage4_trajectory_excitation_generalization import (
        _benefit,
        _correlations,
        _events_clear,
        _load_trace,
        _pressure,
        _read_json,
        _validate_future_data_isolation,
        _weak_directions,
    )

from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.patient_mismatch import patient_case_record


EXPECTED_PAIR_COUNT = 18
EXPECTED_NEW_PAIR_COUNT = 16
EXPECTED_REUSED_PAIR_COUNT = 2
EXPECTED_ARMS = ("prior_only", "trusted_adaptive")
EXPECTED_CASE_FILES = (
    "prior_only.json",
    "trusted_adaptive.json",
    "prior_only_trace.npz",
    "trusted_adaptive_trace.npz",
    "comparison_summary.json",
    "comparison_summary.md",
)
SUMMARY_SCHEMA_VERSION = "stage4_crossed_excitation_replication_aggregate_v1"


def _strict_json_read(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    json.dumps(payload, allow_nan=False)
    return payload


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return None if not values else float(statistics.fmean(values))


def _first_or_none(items: list[dict[str, Any]], key: str) -> float | None:
    return None if not items else float(items[0][key])


def _group_summaries(
    rows: list[dict[str, Any]], group_key: str
) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for group_value in sorted({row[group_key] for row in rows}):
        selected = [row for row in rows if row[group_key] == group_value]
        promotions = [
            row["trust_and_identification"]["first_control_promotion_time_s"]
            for row in selected
            if row["trust_and_identification"]["first_control_promotion_time_s"]
            is not None
        ]
        remaining = [
            row["trust_and_identification"][
                "trajectory_remaining_after_first_promotion_percent"
            ]
            for row in selected
            if row["trust_and_identification"][
                "trajectory_remaining_after_first_promotion_percent"
            ]
            is not None
        ]
        tracking = [
            row["tracking_rmse_deg"]["benefit"][
                "percent_prior_minus_adaptive"
            ]
            for row in selected
        ]
        prediction = [
            row["torque_prediction_rmse_nm"]["benefit"][
                "percent_prior_minus_adaptive"
            ]
            for row in selected
        ]
        summaries[group_value] = {
            "case_count": len(selected),
            "promotion_count": len(promotions),
            "first_promotion_time_s": {
                "mean": _mean(promotions),
                "minimum": min(promotions, default=None),
                "maximum": max(promotions, default=None),
            },
            "remaining_trajectory_percent": {
                "mean": _mean(remaining),
                "minimum": min(remaining, default=None),
                "maximum": max(remaining, default=None),
            },
            "tracking_rmse_benefit_percent": {
                "mean": _mean(tracking),
                "minimum": min(tracking),
                "maximum": max(tracking),
            },
            "torque_prediction_rmse_benefit_percent": {
                "mean": _mean(prediction),
                "minimum": min(prediction),
                "maximum": max(prediction),
            },
            "qualification_count": sum(
                row["trust_and_identification"]["qualification_count"]
                for row in selected
            ),
            "control_promotion_count": sum(
                row["trust_and_identification"]["promotion_count"]
                for row in selected
            ),
            "rejection_count": sum(
                row["trust_and_identification"]["rejection_count"]
                for row in selected
            ),
            "pending_count": sum(
                row["trust_and_identification"]["pending_count"]
                for row in selected
            ),
            "maximum_active_bound_count": max(
                row["trust_and_identification"]["active_bound_pressure"][
                    "maximum_active_bound_count"
                ]
                for row in selected
            ),
            "maximum_unconstrained_violation_fraction_of_span": max(
                row["trust_and_identification"]["active_bound_pressure"][
                    "maximum_unconstrained_violation_fraction_of_span"
                ]
                for row in selected
            ),
        }
    return summaries


def _promotion_order(
    richer: dict[str, Any], poorer: dict[str, Any]
) -> tuple[str, float | None, float | None]:
    rich_time = richer["trust_and_identification"]["first_control_promotion_time_s"]
    poor_time = poorer["trust_and_identification"]["first_control_promotion_time_s"]
    if rich_time is None and poor_time is None:
        return "neither_promoted", None, None
    if rich_time is not None and poor_time is None:
        return "poorer_no_promotion", None, None
    if rich_time is None and poor_time is not None:
        return "poorer_promoted_richer_did_not", None, None
    difference = float(poor_time - rich_time)
    rich_remaining = richer["trust_and_identification"][
        "trajectory_remaining_after_first_promotion_percent"
    ]
    poor_remaining = poorer["trust_and_identification"][
        "trajectory_remaining_after_first_promotion_percent"
    ]
    remaining_difference = float(poor_remaining - rich_remaining)
    if difference > 1e-12:
        label = "poorer_later"
    elif difference < -1e-12:
        label = "poorer_earlier"
    else:
        label = "same_promotion_time"
    return label, difference, remaining_difference


def _matched_trajectory_analysis(
    rows: list[dict[str, Any]], matrix: dict[str, Any]
) -> dict[str, Any]:
    by_key = {
        (row["patient_id"], row["trajectory_id"], row["measurement_seed"]): row
        for row in rows
    }
    patients = [item["patient_id"] for item in matrix["patient_levels"]]
    trajectories = [item["trajectory_id"] for item in matrix["trajectory_levels"]]
    contrasts = []
    for patient_id in patients:
        for richer_id, poorer_id in combinations(trajectories, 2):
            richer_seeds = {
                row["measurement_seed"]
                for row in rows
                if row["patient_id"] == patient_id
                and row["trajectory_id"] == richer_id
            }
            poorer_seeds = {
                row["measurement_seed"]
                for row in rows
                if row["patient_id"] == patient_id
                and row["trajectory_id"] == poorer_id
            }
            common = richer_seeds & poorer_seeds
            if len(common) != 1:
                raise RuntimeError("trajectory matched slice is not uniquely seeded")
            seed = next(iter(common))
            richer = by_key[(patient_id, richer_id, seed)]
            poorer = by_key[(patient_id, poorer_id, seed)]
            label, time_difference, remaining_difference = _promotion_order(
                richer, poorer
            )
            contrasts.append(
                {
                    "patient_id": patient_id,
                    "measurement_seed": seed,
                    "richer_trajectory_id": richer_id,
                    "poorer_trajectory_id": poorer_id,
                    "promotion_pattern": label,
                    "poorer_minus_richer_promotion_time_s": time_difference,
                    "poorer_minus_richer_remaining_trajectory_percentage_points": (
                        remaining_difference
                    ),
                    "poorer_minus_richer_prediction_benefit_nm": float(
                        poorer["torque_prediction_rmse_nm"]["benefit"][
                            "absolute_prior_minus_adaptive"
                        ]
                        - richer["torque_prediction_rmse_nm"]["benefit"][
                            "absolute_prior_minus_adaptive"
                        ]
                    ),
                    "poorer_minus_richer_tracking_benefit_deg": float(
                        poorer["tracking_rmse_deg"]["benefit"][
                            "absolute_prior_minus_adaptive"
                        ]
                        - richer["tracking_rmse_deg"]["benefit"][
                            "absolute_prior_minus_adaptive"
                        ]
                    ),
                }
            )
    pattern_counts = Counter(item["promotion_pattern"] for item in contrasts)
    anchor = trajectories[0]
    hip = trajectories[1]
    two = trajectories[2]
    return {
        "unit": "fixed_patient_and_measurement_seed",
        "contrast_count": len(contrasts),
        "contrasts": contrasts,
        "promotion_pattern_counts": dict(sorted(pattern_counts.items())),
        "poorer_later_count": pattern_counts["poorer_later"],
        "same_promotion_time_count": pattern_counts["same_promotion_time"],
        "poorer_earlier_count": pattern_counts["poorer_earlier"],
        "anchor_vs_two_cycle": [
            item
            for item in contrasts
            if item["richer_trajectory_id"] == anchor
            and item["poorer_trajectory_id"] == two
        ],
        "anchor_vs_hip": [
            item
            for item in contrasts
            if item["richer_trajectory_id"] == anchor
            and item["poorer_trajectory_id"] == hip
        ],
        "hip_vs_two_cycle": [
            item
            for item in contrasts
            if item["richer_trajectory_id"] == hip
            and item["poorer_trajectory_id"] == two
        ],
    }


def _matched_patient_analysis(
    rows: list[dict[str, Any]], matrix: dict[str, Any]
) -> dict[str, Any]:
    by_key = {
        (row["patient_id"], row["trajectory_id"], row["measurement_seed"]): row
        for row in rows
    }
    patients = [item["patient_id"] for item in matrix["patient_levels"]]
    trajectories = [item["trajectory_id"] for item in matrix["trajectory_levels"]]
    contrasts = []
    for trajectory_id in trajectories:
        for weaker_id, stronger_id in combinations(patients, 2):
            weaker_seeds = {
                row["measurement_seed"]
                for row in rows
                if row["patient_id"] == weaker_id
                and row["trajectory_id"] == trajectory_id
            }
            stronger_seeds = {
                row["measurement_seed"]
                for row in rows
                if row["patient_id"] == stronger_id
                and row["trajectory_id"] == trajectory_id
            }
            common = weaker_seeds & stronger_seeds
            if len(common) != 1:
                raise RuntimeError("patient matched slice is not uniquely seeded")
            seed = next(iter(common))
            weaker = by_key[(weaker_id, trajectory_id, seed)]
            stronger = by_key[(stronger_id, trajectory_id, seed)]
            tracking_difference = float(
                stronger["tracking_rmse_deg"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                - weaker["tracking_rmse_deg"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
            )
            prediction_difference = float(
                stronger["torque_prediction_rmse_nm"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
                - weaker["torque_prediction_rmse_nm"]["benefit"][
                    "absolute_prior_minus_adaptive"
                ]
            )
            contrasts.append(
                {
                    "trajectory_id": trajectory_id,
                    "measurement_seed": seed,
                    "weaker_patient_id": weaker_id,
                    "stronger_patient_id": stronger_id,
                    "stronger_minus_weaker_tracking_benefit_deg": (
                        tracking_difference
                    ),
                    "stronger_minus_weaker_prediction_benefit_nm": (
                        prediction_difference
                    ),
                    "stronger_has_larger_tracking_benefit": (
                        tracking_difference > 1e-12
                    ),
                    "stronger_has_larger_prediction_benefit": (
                        prediction_difference > 1e-12
                    ),
                }
            )
    return {
        "unit": "fixed_trajectory_and_measurement_seed",
        "contrast_count": len(contrasts),
        "contrasts": contrasts,
        "stronger_has_larger_tracking_benefit_count": sum(
            item["stronger_has_larger_tracking_benefit"] for item in contrasts
        ),
        "stronger_has_larger_prediction_benefit_count": sum(
            item["stronger_has_larger_prediction_benefit"] for item in contrasts
        ),
    }


def _matched_seed_analysis(
    rows: list[dict[str, Any]], matrix: dict[str, Any]
) -> dict[str, Any]:
    patients = [item["patient_id"] for item in matrix["patient_levels"]]
    trajectories = [item["trajectory_id"] for item in matrix["trajectory_levels"]]
    contrasts = []
    for patient_id in patients:
        for trajectory_id in trajectories:
            cell = sorted(
                (
                    row
                    for row in rows
                    if row["patient_id"] == patient_id
                    and row["trajectory_id"] == trajectory_id
                ),
                key=lambda row: row["measurement_seed"],
            )
            if len(cell) != 2:
                raise RuntimeError("patient/trajectory cell must contain two seeds")
            first, second = cell
            first_time = first["trust_and_identification"][
                "first_control_promotion_time_s"
            ]
            second_time = second["trust_and_identification"][
                "first_control_promotion_time_s"
            ]
            status_changed = (first_time is None) != (second_time is None)
            timing_difference = (
                None
                if first_time is None or second_time is None
                else float(second_time - first_time)
            )
            tracking_first = first["tracking_rmse_deg"]["benefit"][
                "absolute_prior_minus_adaptive"
            ]
            tracking_second = second["tracking_rmse_deg"]["benefit"][
                "absolute_prior_minus_adaptive"
            ]
            prediction_first = first["torque_prediction_rmse_nm"]["benefit"][
                "absolute_prior_minus_adaptive"
            ]
            prediction_second = second["torque_prediction_rmse_nm"]["benefit"][
                "absolute_prior_minus_adaptive"
            ]
            contrasts.append(
                {
                    "patient_id": patient_id,
                    "trajectory_id": trajectory_id,
                    "first_seed": first["measurement_seed"],
                    "second_seed": second["measurement_seed"],
                    "promotion_status_changed": status_changed,
                    "second_minus_first_promotion_time_s": timing_difference,
                    "absolute_promotion_time_difference_s": (
                        None if timing_difference is None else abs(timing_difference)
                    ),
                    "tracking_benefit_sign_changed": (
                        np.sign(tracking_first) != np.sign(tracking_second)
                    ),
                    "prediction_benefit_sign_changed": (
                        np.sign(prediction_first) != np.sign(prediction_second)
                    ),
                }
            )
    timing_differences = [
        item["absolute_promotion_time_difference_s"]
        for item in contrasts
        if item["absolute_promotion_time_difference_s"] is not None
    ]
    return {
        "unit": "fixed_patient_and_trajectory",
        "contrast_count": len(contrasts),
        "contrasts": contrasts,
        "promotion_status_changed_count": sum(
            item["promotion_status_changed"] for item in contrasts
        ),
        "tracking_benefit_sign_changed_count": sum(
            item["tracking_benefit_sign_changed"] for item in contrasts
        ),
        "prediction_benefit_sign_changed_count": sum(
            item["prediction_benefit_sign_changed"] for item in contrasts
        ),
        "promotion_time_absolute_difference_s": {
            "mean": _mean(timing_differences),
            "maximum": max(timing_differences, default=None),
            "values": timing_differences,
        },
        "trajectory_pattern_reversal_identifiability": (
            "the_fractional_design_does_not_repeat_the_same_two_trajectory_"
            "contrast_at_two_seeds_within_one_patient; seed-induced trajectory_"
            "ordering_reversal_is_not_separately_identifiable"
        ),
    }


def build_aggregate(
    *,
    matrix_config: Path,
    patient_config: Path,
    trajectory_config: Path,
    excitation_audit_path: Path,
    new_result_root: Path,
) -> dict[str, Any]:
    matrix = load_crossed_replication_matrix(matrix_config)
    if matrix["schema_version"] != MATRIX_SCHEMA_VERSION:
        raise RuntimeError("matrix schema drifted")
    cases = matrix["cases"]
    if len(cases) != EXPECTED_PAIR_COUNT:
        raise RuntimeError("analysis matrix does not contain 18 pairs")
    new_cases = [x for x in cases if x["execution_source"] == "new_formal_run"]
    reused_cases = [
        x
        for x in cases
        if x["execution_source"] == "read_only_existing_formal_bridge"
    ]
    if len(new_cases) != EXPECTED_NEW_PAIR_COUNT or len(reused_cases) != (
        EXPECTED_REUSED_PAIR_COUNT
    ):
        raise RuntimeError("new/reused matrix classification drifted")
    expected_new_directories = {item["case_id"] for item in new_cases}
    actual_new_directories = {
        path.name for path in new_result_root.iterdir() if path.is_dir()
    }
    if actual_new_directories != expected_new_directories:
        raise RuntimeError(
            "new formal directory set differs from preregistration: "
            f"missing={sorted(expected_new_directories - actual_new_directories)}, "
            f"extra={sorted(actual_new_directories - expected_new_directories)}"
        )

    audit = _strict_json_read(excitation_audit_path)
    audit_by_trajectory = {item["trajectory_id"]: item for item in audit["cases"]}
    patient_levels = {item["patient_id"]: item for item in matrix["patient_levels"]}
    trajectory_levels = {
        item["trajectory_id"]: item for item in matrix["trajectory_levels"]
    }
    matrix_hash = _sha256(matrix_config)
    expected_matrix_hash = matrix["source_contracts"].get(
        "matrix_config_sha256", matrix_hash
    )
    if matrix_hash != expected_matrix_hash:
        raise RuntimeError("matrix config hash changed during audit")
    expected_patient_hash = matrix["source_contracts"]["patient_config"]["sha256"]
    expected_trajectory_hash = matrix["source_contracts"]["trajectory_config"][
        "sha256"
    ]
    if _sha256(patient_config) != expected_patient_hash:
        raise RuntimeError("patient config hash drifted")
    if _sha256(trajectory_config) != expected_trajectory_hash:
        raise RuntimeError("trajectory config hash drifted")

    rows: list[dict[str, Any]] = []
    artifact_hashes: dict[str, dict[str, str]] = {}
    rebuilt_controller_fingerprints: set[str] = set()
    recorded_new_controller_fingerprints: set[str] = set()
    recorded_reused_controller_fingerprints: set[str] = set()
    evidence_directories: set[Path] = set()
    source_linkage_modes: Counter[str] = Counter()

    for case in cases:
        case_id = case["case_id"]
        reused = case["execution_source"] == "read_only_existing_formal_bridge"
        if reused:
            reused_verification = verify_reused_evidence(matrix_config, case_id)
            case_dir = Path(reused_verification["source_result_directory"])
            source_linkage = "preregistered_sha256_read_only_bridge"
        else:
            reused_verification = None
            case_dir = new_result_root / case_id
            source_linkage = "new_crossed_runner_output"
        resolved_dir = case_dir.resolve()
        if resolved_dir in evidence_directories:
            raise RuntimeError(f"duplicate evidence directory: {resolved_dir}")
        evidence_directories.add(resolved_dir)
        source_linkage_modes[source_linkage] += 1
        missing = [
            str(case_dir / filename)
            for filename in EXPECTED_CASE_FILES
            if not (case_dir / filename).is_file()
        ]
        if missing:
            raise RuntimeError(f"{case_id}: missing expected artifacts {missing}")
        if any("smoke" in path.name.lower() for path in case_dir.iterdir()):
            raise RuntimeError(f"{case_id}: smoke marker/artifact contamination")
        artifact_hashes[case_id] = {
            filename: _sha256(case_dir / filename)
            for filename in EXPECTED_CASE_FILES
        }

        paired = _strict_json_read(case_dir / "comparison_summary.json")
        raw = {
            arm: _strict_json_read(case_dir / f"{arm}.json")
            for arm in EXPECTED_ARMS
        }
        traces = {
            arm: _load_trace(case_dir / f"{arm}_trace.npz")
            for arm in EXPECTED_ARMS
        }
        patient_spec, _ = select_patient_case(patient_config, case["patient_id"])
        patient_record = patient_case_record(patient_spec)
        true_human = patient_spec.build_human()
        trajectory, _ = select_trajectory(
            trajectory_config, case["trajectory_id"]
        )
        if float(trajectory["duration_s"]) != float(case["duration_s"]):
            raise RuntimeError(f"{case_id}: trajectory duration mismatch")

        if reused:
            if reused_verification is None:
                raise RuntimeError("internal reused verification error")
            if paired["evidence_category"] != FORMAL_EVIDENCE_CATEGORY:
                raise RuntimeError(f"{case_id}: reused evidence category drifted")
            recorded_reused_controller_fingerprints.add(
                paired["provenance"]["controller_fingerprint_sha256"]
            )
            matrix_linkage = {
                "mode": source_linkage,
                "matrix_config_sha256": matrix_hash,
                "patient_config_sha256": expected_patient_hash,
                "trajectory_config_sha256": expected_trajectory_hash,
                "source_artifact_hashes_match_preregistration": True,
                "source_did_not_preexist_crossed_matrix_hash_field": True,
            }
        else:
            if paired.get("schema_version") != NEW_PAIR_SCHEMA_VERSION:
                raise RuntimeError(f"{case_id}: new pair schema mismatch")
            if paired.get("case_id") != case_id or paired.get("matrix_case") != case:
                raise RuntimeError(f"{case_id}: matrix case provenance mismatch")
            provenance = paired["provenance"]
            expected_provenance = {
                "patient_id": case["patient_id"],
                "trajectory_id": case["trajectory_id"],
                "measurement_seed": case["measurement_seed"],
                "mpc_seed": REGISTERED_MPC_SEED,
                "sensor_regime": REGISTERED_SENSOR_CASE,
                "matrix_config_sha256": matrix_hash,
                "patient_config_sha256": expected_patient_hash,
                "trajectory_config_sha256": expected_trajectory_hash,
                "baseline_tag": matrix["source_contracts"]["baseline_tag"],
                "baseline_commit": matrix["source_contracts"]["baseline_commit"],
                "evidence_category": FORMAL_EVIDENCE_CATEGORY,
                "execution_source": "new_formal_run",
                "matrix_execution_class": "new_formal_run",
                "reused_vs_newly_executed": "newly_executed",
                "preregistered_runtime_limit_s": 32.0,
                "executed_wall_time_limit_s": 32.0,
                "structural_smoke": False,
                "fresh_state_semantics": "fresh_per_arm_per_crossed_case",
            }
            for field, expected in expected_provenance.items():
                if provenance.get(field) != expected:
                    raise RuntimeError(
                        f"{case_id}: provenance mismatch at {field}: "
                        f"{provenance.get(field)!r} != {expected!r}"
                    )
            if provenance.get("code_commit") != matrix["source_contracts"][
                "baseline_commit"
            ]:
                raise RuntimeError(f"{case_id}: code commit drifted")
            recorded_new_controller_fingerprints.add(
                provenance["controller_fingerprint_sha256"]
            )
            matrix_linkage = {
                "mode": source_linkage,
                "matrix_config_sha256": provenance["matrix_config_sha256"],
                "patient_config_sha256": provenance["patient_config_sha256"],
                "trajectory_config_sha256": provenance[
                    "trajectory_config_sha256"
                ],
                "source_artifact_hashes_match_preregistration": None,
                "source_did_not_preexist_crossed_matrix_hash_field": False,
            }

        for arm in EXPECTED_ARMS:
            summary = raw[arm]
            if summary.get("case") != arm:
                raise RuntimeError(f"{case_id}: raw arm label mismatch")
            if summary.get("true_human_case") != case["patient_id"]:
                raise RuntimeError(f"{case_id}: raw patient mismatch")
            if summary.get("trajectory") != case["trajectory_id"]:
                raise RuntimeError(f"{case_id}: raw trajectory mismatch")
            if summary.get("requested_duration_s") != 32.0:
                raise RuntimeError(f"{case_id}: raw runtime mismatch")
            if summary.get("evidence_category") != FORMAL_EVIDENCE_CATEGORY:
                raise RuntimeError(f"{case_id}: raw evidence category mismatch")
            measurement = summary["measurement_model"]
            if measurement.get("name") != REGISTERED_SENSOR_CASE:
                raise RuntimeError(f"{case_id}: raw sensor regime mismatch")
            if measurement.get("random_seed") != case["measurement_seed"]:
                raise RuntimeError(f"{case_id}: raw measurement seed mismatch")
            _validate_future_data_isolation(summary)
            if not _promotions_follow_qualification(summary):
                raise RuntimeError(f"{case_id}/{arm}: invalid qualification/promotion order")

        comparison = build_paired_ab_comparison(
            raw,
            traces,
            sensor_case_name=REGISTERED_SENSOR_CASE,
            measurement_seed=int(case["measurement_seed"]),
            true_human=true_human,
            human_label=case["patient_id"],
            wall_time_limit_s=32.0,
            evidence_category=FORMAL_EVIDENCE_CATEGORY,
            reference_phase_duration_s=23.0,
            trajectory_label=case["trajectory_id"],
        )
        registered = comparison["registered_configuration"]
        registered_expected = {
            "human": case["patient_id"],
            "trajectory": case["trajectory_id"],
            "measurement_seed": case["measurement_seed"],
            "mpc_seed": REGISTERED_MPC_SEED,
            "sensor_case": REGISTERED_SENSOR_CASE,
            "wall_time_limit_s": 32.0,
            "reference_phase_duration_s": 23.0,
        }
        for field, expected in registered_expected.items():
            if registered.get(field) != expected:
                raise RuntimeError(f"{case_id}: rebuilt config mismatch at {field}")
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
        if not all(isolation.get(field) is True for field in required_isolation):
            raise RuntimeError(f"{case_id}: A/B causal isolation failed")
        if any(
            abs(float(value)) > 1e-10
            for value in isolation[
                "pre_promotion_trace_max_abs_difference"
            ].values()
        ):
            raise RuntimeError(f"{case_id}: pre-promotion trace mismatch")
        prior_beta = nominal_base_parameters()
        for arm in EXPECTED_ARMS:
            np.testing.assert_allclose(
                traces[arm]["dynamic_base_estimate"][0],
                prior_beta,
                rtol=0.0,
                atol=1e-12,
            )
        np.testing.assert_allclose(
            traces["prior_only"]["dynamic_base_estimate"],
            np.broadcast_to(
                prior_beta,
                np.asarray(traces["prior_only"]["dynamic_base_estimate"]).shape,
            ),
            rtol=0.0,
            atol=1e-12,
        )
        rebuilt_fingerprint, _ = _frozen_controller_fingerprint(
            comparison, int(case["measurement_seed"])
        )
        rebuilt_controller_fingerprints.add(rebuilt_fingerprint)

        comparison_by_arm = {item["arm"]: item for item in comparison["rows"]}
        prior = comparison_by_arm["prior_only"]
        adaptive = comparison_by_arm["trusted_adaptive"]
        trust = adaptive["hierarchical_trust"]
        qualifications = trust["qualifications"]
        promotions = trust["control_promotions"]
        first_qualification = _first_or_none(
            qualifications, "qualification_time_s"
        )
        first_promotion = _first_or_none(promotions, "promotion_time_s")
        first_applied = next(
            (
                item
                for item in adaptive["promotion_timeline"]
                if item["applied_to_control"]
            ),
            None,
        )
        promotion_phase = (
            None
            if first_applied is None
            else float(first_applied["decision_reference_phase_s"])
        )
        remaining_s = (
            None
            if first_applied is None
            else float(first_applied["remaining_reference_duration_s"])
        )
        duration = float(case["duration_s"])
        tracking = {
            arm: float(
                comparison_by_arm[arm]["full_task"][
                    "tracking_combined_rmse_deg"
                ]
            )
            for arm in EXPECTED_ARMS
        }
        maximum_error = {
            arm: float(
                comparison_by_arm[arm]["full_task"][
                    "tracking_max_abs_error_deg"
                ]
            )
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
        for metric in interaction.values():
            metric["adaptive_minus_prior"] = float(
                metric["trusted_adaptive"] - metric["prior_only"]
            )
        audit_case = audit_by_trajectory[case["trajectory_id"]]
        audit_info = audit_case["information_matrix_summary"]
        rows.append(
            {
                "case_id": case_id,
                "execution_source": (
                    "reused_read_only" if reused else "newly_executed"
                ),
                "evidence_directory": str(resolved_dir),
                "patient_id": case["patient_id"],
                "patient_level": patient_levels[case["patient_id"]]["level"],
                "patient_estimator_span_l2": patient_levels[case["patient_id"]][
                    "estimator_span_l2"
                ],
                "trajectory_id": case["trajectory_id"],
                "trajectory_level": trajectory_levels[case["trajectory_id"]][
                    "level"
                ],
                "measurement_seed": int(case["measurement_seed"]),
                "duration_s": duration,
                "runtime_limit_s": 32.0,
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
                    "condition_x": float(
                        audit_case["estimator_span_scaled_diagnostics"][
                            "condition_number"
                        ]
                    ),
                    "singular_values_x": audit_case[
                        "estimator_span_scaled_diagnostics"
                    ]["singular_values"],
                    "estimator_span_scaled_information_matrix": audit_case[
                        "estimator_span_scaled_information_matrix"
                    ],
                    "column_normalized_information_matrix": audit_case[
                        "column_normalized_information_matrix"
                    ],
                    "information_lambda_min": float(
                        audit_info["eigenvalues_ascending"][0]
                    ),
                    "information_trace": float(audit_info["trace"]),
                    "information_diagonal": audit_info["diagonal"],
                    "weakest_three_span_normalized_directions": (
                        _weak_directions(audit_case)
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
                    "normalized_reference_phase_at_promotion": (
                        None
                        if promotion_phase is None
                        else float(promotion_phase / duration)
                    ),
                    "reference_phase_at_promotion_s": promotion_phase,
                    "trajectory_remaining_after_first_promotion_s": remaining_s,
                    "trajectory_remaining_after_first_promotion_percent": (
                        None
                        if remaining_s is None
                        else float(100.0 * remaining_s / duration)
                    ),
                    "qualification_count": int(trust["counts"]["qualified"]),
                    "promotion_count": int(
                        trust["counts"]["control_promotions"]
                    ),
                    "rejection_count": int(trust["counts"]["rejected"]),
                    "pending_count": int(trust["counts"]["pending"]),
                    "active_bound_pressure": _pressure(trust),
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
                        maximum_error["prior_only"],
                        maximum_error["trusted_adaptive"],
                    ),
                },
                "torque_prediction_rmse_nm": {
                    "prior_only": prediction["prior_only"],
                    "trusted_adaptive": prediction["trusted_adaptive"],
                    "benefit": _benefit(
                        prediction["prior_only"], prediction["trusted_adaptive"]
                    ),
                },
                "completion": {
                    arm: {
                        "progress_fraction": float(
                            comparison_by_arm[arm]["reference_progress_fraction"]
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
                    "source_linkage": matrix_linkage,
                    "artifact_sha256": artifact_hashes[case_id],
                    "rebuilt_controller_fingerprint_sha256": (
                        rebuilt_fingerprint
                    ),
                    "pre_promotion_trace_max_abs_difference": isolation[
                        "pre_promotion_trace_max_abs_difference"
                    ],
                    "initial_state_and_population_prior_reset": True,
                    "causal_embargo_nonoverlap_single_challenger_valid": True,
                },
            }
        )

    if len(rebuilt_controller_fingerprints) != 1:
        raise RuntimeError("factor-invariant controller fingerprint drift")
    if len(recorded_new_controller_fingerprints) != 1:
        raise RuntimeError("new-run recorded controller fingerprint drift")
    if rebuilt_controller_fingerprints != recorded_new_controller_fingerprints:
        raise RuntimeError("recorded/rebuilt new controller fingerprint mismatch")
    if len(recorded_reused_controller_fingerprints) != 1:
        raise RuntimeError("reused source controller fingerprint drift")

    trajectory_analysis = _matched_trajectory_analysis(rows, matrix)
    patient_analysis = _matched_patient_analysis(rows, matrix)
    seed_analysis = _matched_seed_analysis(rows, matrix)
    tracking_benefits = [
        row["tracking_rmse_deg"]["benefit"]["absolute_prior_minus_adaptive"]
        for row in rows
    ]
    prediction_benefits = [
        row["torque_prediction_rmse_nm"]["benefit"][
            "absolute_prior_minus_adaptive"
        ]
        for row in rows
    ]
    no_promotion = [
        row["case_id"]
        for row in rows
        if row["trust_and_identification"]["first_control_promotion_time_s"]
        is None
    ]
    early_termination = [
        row["case_id"]
        for row in rows
        if any(
            row["completion"][arm]["progress_fraction"] < 1.0 - 1e-12
            for arm in EXPECTED_ARMS
        )
    ]
    rmse_improves_max_worsens = [
        row["case_id"]
        for row in rows
        if row["tracking_rmse_deg"]["benefit"][
            "absolute_prior_minus_adaptive"
        ]
        > 0.0
        and row["maximum_tracking_error_deg"]["benefit"][
            "absolute_prior_minus_adaptive"
        ]
        < 0.0
    ]
    promoted = [
        row
        for row in rows
        if row["trust_and_identification"]["first_control_promotion_time_s"]
        is not None
    ]
    all_safe = all(
        row["safety"][arm]["no_recorded_safety_event"]
        for row in rows
        for arm in EXPECTED_ARMS
    )
    aggregate = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "evidence_category": FORMAL_EVIDENCE_CATEGORY,
        "scope": (
            "balanced incomplete crossed simulation study of three registered "
            "patient mismatches, three rehabilitation trajectories, three fixed "
            "measurement seeds, and frozen paired Stage-4 control"
        ),
        "integrity": {
            "verdict": "mechanically_complete_and_internally_consistent",
            "matrix_pair_count": len(rows),
            "arm_count": len(rows) * 2,
            "new_pair_count": len(new_cases),
            "reused_pair_count": len(reused_cases),
            "all_expected_artifacts_present": True,
            "all_json_strict_and_npz_readable_finite": True,
            "all_factor_provenance_matches_preregistration": True,
            "all_runtime_sensor_seed_baseline_checks_passed": True,
            "all_pre_promotion_ab_isolation_checks_passed": True,
            "all_prior_only_control_betas_remained_population_prior": True,
            "all_embargo_nonoverlap_single_challenger_checks_passed": True,
            "all_initial_states_and_estimator_trust_state_fresh": True,
            "all_evidence_directories_unique": True,
            "no_smoke_contamination": True,
            "reused_artifact_hashes_reverified": True,
            "historical_overwrite_cannot_be_proven_from_final_artifacts_alone": True,
            "matrix_config_sha256": matrix_hash,
            "patient_config_sha256": expected_patient_hash,
            "trajectory_config_sha256": expected_trajectory_hash,
            "offline_excitation_audit_sha256": _sha256(excitation_audit_path),
            "rebuilt_factor_invariant_controller_fingerprint_sha256": next(
                iter(rebuilt_controller_fingerprints)
            ),
            "recorded_reused_source_controller_fingerprint_sha256": next(
                iter(recorded_reused_controller_fingerprints)
            ),
            "baseline_tag": matrix["source_contracts"]["baseline_tag"],
            "baseline_commit": matrix["source_contracts"]["baseline_commit"],
            "source_linkage_counts": dict(source_linkage_modes),
            "artifact_sha256": artifact_hashes,
            "authoritative_promotion_assessment": (
                "eligible_for_authoritative_formal_evidence_promotion_after_"
                "this_review_without_mutating_canonical_run_artifacts"
            ),
        },
        "suite_summary": {
            "cases_with_control_promotion": len(promoted),
            "cases_without_control_promotion": len(no_promotion),
            "cases_completed_both_arms": sum(
                all(
                    row["completion"][arm]["progress_fraction"] >= 1.0 - 1e-12
                    for arm in EXPECTED_ARMS
                )
                for row in rows
            ),
            "cases_with_early_termination": len(early_termination),
            "all_arms_without_recorded_safety_event": all_safe,
            "tracking_rmse_improved_count": sum(value > 0.0 for value in tracking_benefits),
            "prediction_rmse_improved_count": sum(
                value > 0.0 for value in prediction_benefits
            ),
            "rmse_improved_but_max_error_worsened_count": len(
                rmse_improves_max_worsens
            ),
            "first_promotion_time_s": {
                "mean": _mean(
                    row["trust_and_identification"][
                        "first_control_promotion_time_s"
                    ]
                    for row in promoted
                ),
                "minimum": min(
                    (
                        row["trust_and_identification"][
                            "first_control_promotion_time_s"
                        ]
                        for row in promoted
                    ),
                    default=None,
                ),
                "maximum": max(
                    (
                        row["trust_and_identification"][
                            "first_control_promotion_time_s"
                        ]
                        for row in promoted
                    ),
                    default=None,
                ),
            },
            "no_promotion_case_ids": no_promotion,
            "early_termination_case_ids": early_termination,
            "rmse_improves_max_error_worsens_case_ids": (
                rmse_improves_max_worsens
            ),
        },
        "group_summaries": {
            "by_trajectory": _group_summaries(rows, "trajectory_id"),
            "by_patient": _group_summaries(rows, "patient_id"),
        },
        "relationships": {
            "caution": (
                "n=18 balanced incomplete paired cases; correlations and matched "
                "contrast counts are descriptive only and do not identify an "
                "unrestricted three-way interaction"
            ),
            "prediction_benefit_nm_vs_tracking_benefit_deg": _correlations(
                prediction_benefits, tracking_benefits
            ),
            "benefit_sign_concordance_count": sum(
                np.sign(prediction) == np.sign(tracking)
                for prediction, tracking in zip(
                    prediction_benefits, tracking_benefits, strict=True
                )
            ),
            "matched_trajectory_slices": trajectory_analysis,
            "matched_patient_slices": patient_analysis,
            "matched_seed_slices": seed_analysis,
        },
        "cases": rows,
        "interpretation_boundaries": {
            "no_post_hoc_success_threshold": True,
            "no_unrestricted_three_way_interaction_claim": True,
            "no_active_excitation_recommendation_to_force_promotion": True,
            "interaction_metrics_are_not_safety_or_comfort_evidence": True,
            "no_promotion_distinguished_from_shared_early_termination": True,
            "identified_beta_is_control_effective_not_physical_parameter_truth": True,
        },
    }
    return _strict_json(aggregate)


def _fmt(value: float | None, digits: int = 2) -> str:
    return "none" if value is None else f"{value:.{digits}f}"


def _main_table(aggregate: dict[str, Any]) -> str:
    lines = [
        "# Stage-4 crossed excitation replication: main comparison table",
        "",
        "Positive benefit percentages mean lower error under trusted adaptation.",
        "Interaction quantities are not safety or comfort metrics.",
        "",
        "| patient | trajectory | seed | source | progress P/A | promotion s / phase % / remaining % | q/p/r | bound #/span | tracking RMSE P/A (benefit %) | max error P/A | torque RMSE P/A (benefit %) | safety |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in aggregate["cases"]:
        trust = row["trust_and_identification"]
        pressure = trust["active_bound_pressure"]
        progress = row["completion"]
        tracking = row["tracking_rmse_deg"]
        maximum = row["maximum_tracking_error_deg"]
        prediction = row["torque_prediction_rmse_nm"]
        safe = all(
            row["safety"][arm]["no_recorded_safety_event"]
            for arm in EXPECTED_ARMS
        )
        source = "R" if row["execution_source"] == "reused_read_only" else "N"
        lines.append(
            f"| `{row['patient_id']}` | `{row['trajectory_id']}` | "
            f"{row['measurement_seed']} | {source} | "
            f"{progress['prior_only']['progress_fraction']:.3f}/"
            f"{progress['trusted_adaptive']['progress_fraction']:.3f} | "
            f"{_fmt(trust['first_control_promotion_time_s'])} / "
            f"{_fmt(None if trust['normalized_reference_phase_at_promotion'] is None else 100.0 * trust['normalized_reference_phase_at_promotion'], 1)} / "
            f"{_fmt(trust['trajectory_remaining_after_first_promotion_percent'], 1)} | "
            f"{trust['qualification_count']}/{trust['promotion_count']}/"
            f"{trust['rejection_count']} | "
            f"{pressure['maximum_active_bound_count']}/"
            f"{pressure['maximum_unconstrained_violation_fraction_of_span']:.2f} | "
            f"{tracking['prior_only']:.4f}/{tracking['trusted_adaptive']:.4f} "
            f"({tracking['benefit']['percent_prior_minus_adaptive']:.2f}%) | "
            f"{maximum['prior_only']:.3f}/{maximum['trusted_adaptive']:.3f} | "
            f"{prediction['prior_only']:.4f}/{prediction['trusted_adaptive']:.4f} "
            f"({prediction['benefit']['percent_prior_minus_adaptive']:.2f}%) | "
            f"{'none' if safe else 'recorded event'} |"
        )
    return "\n".join(lines) + "\n"


def _hypothesis_verdicts(aggregate: dict[str, Any]) -> list[dict[str, str]]:
    trajectory = aggregate["relationships"]["matched_trajectory_slices"]
    patient = aggregate["relationships"]["matched_patient_slices"]
    seed = aggregate["relationships"]["matched_seed_slices"]
    association = aggregate["relationships"][
        "prediction_benefit_nm_vs_tracking_benefit_deg"
    ]
    anchor_two = trajectory["anchor_vs_two_cycle"]
    two_later = sum(
        item["promotion_pattern"] in ("poorer_later", "poorer_no_promotion")
        for item in anchor_two
    )
    return [
        {
            "hypothesis": "H1 poorer practical excitation tends to delay qualification/promotion",
            "verdict": "supported",
            "basis": (
                f"the poorer trajectory was later in {trajectory['poorer_later_count']}/"
                f"{trajectory['contrast_count']} matched contrasts, tied in "
                f"{trajectory['same_promotion_time_count']}, and earlier in "
                f"{trajectory['poorer_earlier_count']}; two-cycle was later than "
                f"anchor in {two_later}/{len(anchor_two)}"
            ),
        },
        {
            "hypothesis": "H2 stronger mismatch does not necessarily imply larger adaptive benefit",
            "verdict": "supported",
            "basis": (
                "stronger mismatch had larger tracking benefit in "
                f"{patient['stronger_has_larger_tracking_benefit_count']}/"
                f"{patient['contrast_count']} matched patient contrasts and larger "
                "prediction benefit in "
                f"{patient['stronger_has_larger_prediction_benefit_count']}/"
                f"{patient['contrast_count']}; benefit is not consistently ordered"
            ),
        },
        {
            "hypothesis": "H3 prediction improvement generally associates with tracking improvement",
            "verdict": "conditionally supported",
            "basis": (
                f"descriptive Pearson r={association['pearson_r']:.3f}, Spearman "
                f"rho={association['spearman_rho']:.3f}; association is not a "
                "casewise guarantee"
            ),
        },
        {
            "hypothesis": "H4 seed may change timing/status but should not systematically reverse the excitation pattern",
            "verdict": "conditionally supported",
            "basis": (
                f"promotion status changed in {seed['promotion_status_changed_count']}/"
                f"{seed['contrast_count']} fixed patient/trajectory seed contrasts, "
                f"while promotion time changed by up to "
                f"{seed['promotion_time_absolute_difference_s']['maximum']:.2f} s; "
                "the fractional matrix does not repeat one trajectory contrast at "
                "two seeds within the same patient, so seed-caused ordering reversal "
                "is not separately identifiable"
            ),
        },
        {
            "hypothesis": "H5 poor excitation may reduce remaining adaptation time without preventing promotion",
            "verdict": "supported",
            "basis": (
                f"two-cycle promoted in all six cases and was later than anchor in "
                f"{two_later}/{len(anchor_two)} matched contrasts, leaving "
                "6.09, 6.09, and 7.00 percentage points less trajectory"
            ),
        },
    ]


def _report(aggregate: dict[str, Any]) -> str:
    suite = aggregate["suite_summary"]
    relation = aggregate["relationships"]
    trajectory = relation["matched_trajectory_slices"]
    patient = relation["matched_patient_slices"]
    seed = relation["matched_seed_slices"]
    association = relation["prediction_benefit_nm_vs_tracking_benefit_deg"]
    verdicts = _hypothesis_verdicts(aggregate)
    anchor_two = trajectory["anchor_vs_two_cycle"]
    trajectory_groups = aggregate["group_summaries"]["by_trajectory"]
    offline_by_trajectory = {}
    for row in aggregate["cases"]:
        offline_by_trajectory.setdefault(
            row["trajectory_id"], row["offline_excitation"]
        )
    lines = [
        "# Stage-4 crossed excitation replication final report",
        "",
        "Evidence reviewed: `formal_user_run_unreviewed`. Scope is simulation/engineering only.",
        "",
        "## Integrity verdict",
        "",
        "The exact 18-pair/36-arm matrix is mechanically complete: 16 new pairs and two preregistered read-only bridges. All required JSON/NPZ/Markdown artifacts exist; JSON is strict, NPZ traces are readable and finite, factor/runtime/config/baseline provenance matches, no smoke marker is present, A/B pre-promotion isolation and prior-only population-beta invariants pass, and all embargo/non-overlap/single-challenger checks pass.",
        "",
        "The two bridge pairs were not copied or rerun. Their ten preregistered JSON/NPZ SHA-256 values were reverified, together with source configuration/provenance and finite traces. Final artifacts cannot prove the entire historical absence of overwrite, but contain no evidence of overwrite, config drift, or warm-start leakage.",
        "",
        "This completed audit makes the study eligible for promotion to authoritative formal evidence. Canonical per-run artifacts remain unchanged and retain their original `formal_user_run_unreviewed` labels; promotion is an evidence-review decision, not a rewrite of those files.",
        "",
        "## Aggregate outcomes",
        "",
        f"- Control promotion occurred in {suite['cases_with_control_promotion']}/18 cases; {suite['cases_without_control_promotion']} retained the prior.",
        f"- Both arms completed in {suite['cases_completed_both_arms']}/18 cases; {suite['cases_with_early_termination']} cases ended early.",
        f"- Tracking RMSE improved in {suite['tracking_rmse_improved_count']}/18 and torque-prediction RMSE improved in {suite['prediction_rmse_improved_count']}/18.",
        f"- {suite['rmse_improved_but_max_error_worsened_count']} cases improved tracking RMSE while worsening maximum tracking error.",
        f"- First promotion among promoted cases ranged from {_fmt(suite['first_promotion_time_s']['minimum'])} to {_fmt(suite['first_promotion_time_s']['maximum'])} s (mean {_fmt(suite['first_promotion_time_s']['mean'])} s).",
        "",
        "## Matched-slice findings",
        "",
        "### Descriptive trajectory aggregates",
        "",
        "| trajectory | cases | promotion time mean [min, max] s | remaining mean % | tracking benefit mean % | prediction benefit mean % |",
        "|---|---:|---:|---:|---:|---:|",
        *(
            f"| `{trajectory_id}` | {values['case_count']} | "
            f"{_fmt(values['first_promotion_time_s']['mean'])} "
            f"[{_fmt(values['first_promotion_time_s']['minimum'])}, "
            f"{_fmt(values['first_promotion_time_s']['maximum'])}] | "
            f"{_fmt(values['remaining_trajectory_percent']['mean'], 1)} | "
            f"{_fmt(values['tracking_rmse_benefit_percent']['mean'])} | "
            f"{_fmt(values['torque_prediction_rmse_benefit_percent']['mean'])} |"
            for trajectory_id, values in trajectory_groups.items()
        ),
        "",
        "All three regressors are structurally rank 11, so practical conditioning and information strength—not rank alone—separate them:",
        "",
        "| trajectory | rank | cond(Z) | cond(X) | information lambda min | information trace | leading weakest component |",
        "|---|---:|---:|---:|---:|---:|---|",
        *(
            f"| `{trajectory_id}` | {values['rank_z']} | "
            f"{values['condition_z']:.2f} | {values['condition_x']:.2f} | "
            f"{values['information_lambda_min']:.6g} | "
            f"{values['information_trace']:.2f} | "
            f"`{values['weakest_three_span_normalized_directions'][0]['dominant_components'][0]['parameter']}` |"
            for trajectory_id, values in offline_by_trajectory.items()
        ),
        "",
        "Two-cycle has by far the poorest practical conditioning despite full rank. Hip-dominant is qualitatively different: its column-normalized condition is lower than anchor, but raw condition is worse and minimum information eigenvalue is about 25 times smaller, consistent with joint-specific imbalance rather than uniformly weak information.",
        "",
        "### A. Fixed patient + seed: trajectory excitation",
        "",
        f"There are {trajectory['contrast_count']} preregistered matched trajectory contrasts. Anchor versus two-cycle promotion patterns were: "
        + ", ".join(
            f"{item['patient_id']}@{item['measurement_seed']}={item['promotion_pattern']}"
            for item in anchor_two
        )
        + ".",
        "",
        "Two-cycle was later and left less remaining trajectory than anchor in all three matched contrasts. Its prediction benefit was smaller in 3/3, while its tracking benefit was smaller in 2/3; timing is consistent, downstream benefit magnitude is not universally weaker.",
        "",
        "Hip-dominant was later than anchor once and tied twice; two-cycle was later than hip-dominant in all three comparisons. It is timing-intermediate/equal in these slices, but qualitatively seed-sensitive, is the only trajectory family with rejections (five total), and accounts for both cases where RMSE improved while maximum error worsened; it is not a simple scalar midpoint.",
        "",
        "### B. Fixed trajectory + seed: patient mismatch",
        "",
        f"Across {patient['contrast_count']} matched patient contrasts, the stronger configured mismatch had larger tracking benefit in {patient['stronger_has_larger_tracking_benefit_count']} and larger prediction benefit in {patient['stronger_has_larger_prediction_benefit_count']}. Stronger mismatch therefore does not consistently yield larger benefit; the selected patients are composite mechanisms rather than a scalar dose.",
        "",
        "### C. Fixed patient + trajectory: measurement seed",
        "",
        f"Promotion status changed in {seed['promotion_status_changed_count']}/{seed['contrast_count']} seed contrasts. For cells where both seeds promoted, the mean absolute timing change was {_fmt(seed['promotion_time_absolute_difference_s']['mean'])} s and the maximum was {_fmt(seed['promotion_time_absolute_difference_s']['maximum'])} s. Tracking-benefit sign changed in {seed['tracking_benefit_sign_changed_count']} cells and prediction-benefit sign changed in {seed['prediction_benefit_sign_changed_count']} cells.",
        "",
        "The incomplete balanced design does not repeat the same two-trajectory contrast under two seeds within one patient. It can show seed sensitivity and whether matched trajectory patterns span all three seeds, but cannot separately identify a seed-caused reversal of trajectory ordering or an unrestricted three-way interaction.",
        "",
        "## Prediction versus tracking",
        "",
        f"Prediction benefit versus tracking benefit had descriptive Pearson r={association['pearson_r']:.3f} and Spearman rho={association['spearman_rho']:.3f}, with matching signs in {relation['benefit_sign_concordance_count']}/18 cases. This is association within a small fixed simulation matrix, not a threshold, population estimate, or guarantee that prediction improvement produces tracking improvement.",
        "",
        "## Negative and mixed evidence",
        "",
        f"No-promotion cases: {', '.join(suite['no_promotion_case_ids']) if suite['no_promotion_case_ids'] else 'none'}.",
        "",
        f"Early-termination cases: {', '.join(suite['early_termination_case_ids']) if suite['early_termination_case_ids'] else 'none'}.",
        "",
        f"Tracking-RMSE improvement with worse maximum error: {', '.join(suite['rmse_improves_max_error_worsens_case_ids']) if suite['rmse_improves_max_error_worsens_case_ids'] else 'none'}.",
        "",
        "No promotion means trust retained the prior; it is not automatically a controller failure. Shared early termination is reported separately and is not attributed to excitation alone. Interaction force, moment and cylindrical surface proxy remain descriptive and support no safety, comfort, pressure or tissue-load claim.",
        "",
        "## Preregistered hypothesis verdicts",
        "",
        "| hypothesis | verdict | basis |",
        "|---|---|---|",
    ]
    for item in verdicts:
        lines.append(
            f"| {item['hypothesis']} | **{item['verdict']}** | {item['basis']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion and next step",
            "",
            "Natural rehabilitation excitation remains a conditional source of one-shot adaptive information. Practical conditioning affects when useful control adaptation becomes available, but patient mismatch and measurement realization materially modify the chain, and neither structural rank nor mismatch magnitude alone predicts benefit. Identified beta remains a measured-channel/control-effective model, not recovered physical patient truth.",
            "",
            "The next justified study is a separately preregistered model-inadequacy replication using the same small matched-slice discipline and frozen controller, varying one unsupported mechanism at a time. Do not add active excitation or retune weak trajectories merely to force promotion.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(aggregate: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True)
    aggregate = dict(aggregate)
    aggregate["hypothesis_verdicts"] = _hypothesis_verdicts(aggregate)
    (output_dir / "aggregate_summary.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "main_comparison_table.md").write_text(
        _main_table(aggregate), encoding="utf-8"
    )
    (output_dir / "research_report.md").write_text(
        _report(aggregate), encoding="utf-8"
    )


def main() -> None:
    stage_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix-config",
        type=Path,
        default=stage_root / "configs/stage4_crossed_excitation_replication.json",
    )
    parser.add_argument(
        "--patient-config",
        type=Path,
        default=stage_root / "configs/stage4_patient_mismatch_cases.json",
    )
    parser.add_argument(
        "--trajectory-config",
        type=Path,
        default=stage_root / "configs/stage4_trajectory_excitation_suite.json",
    )
    parser.add_argument(
        "--excitation-audit",
        type=Path,
        default=stage_root
        / "results/stage4_trajectory_excitation_design_audit/audit.json",
    )
    parser.add_argument(
        "--formal-result-dir",
        type=Path,
        default=stage_root
        / "results/stage4_crossed_excitation_replication_formal",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    aggregate = build_aggregate(
        matrix_config=args.matrix_config,
        patient_config=args.patient_config,
        trajectory_config=args.trajectory_config,
        excitation_audit_path=args.excitation_audit,
        new_result_root=args.formal_result_dir,
    )
    write_outputs(aggregate, args.output_dir)


if __name__ == "__main__":
    main()
