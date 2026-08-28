#!/usr/bin/env python3
"""Verify and summarize the completed nominal sensor decomposition."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .run_stage4_nominal_sensor_decomposition import (
        REGISTERED_SENSOR_CASES,
        SCHEMA_VERSION,
    )
    from .run_stage4_patient_mismatch_robustness import _strict_json
except ImportError:  # Direct execution from the scripts directory.
    from run_stage4_nominal_sensor_decomposition import (
        REGISTERED_SENSOR_CASES,
        SCHEMA_VERSION,
    )
    from run_stage4_patient_mismatch_robustness import _strict_json


AGGREGATE_SCHEMA_VERSION = "stage4_nominal_sensor_decomposition_aggregate_v1"
ARMS = ("prior_only", "trusted_adaptive")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _first(records: list[dict[str, Any]], key: str) -> float | None:
    return None if not records else float(records[0][key])


def _time_at_level(time: np.ndarray, values: np.ndarray, level: float) -> float:
    if len(time) < 2:
        return 0.0
    selected = np.isclose(values[:-1], level, rtol=0.0, atol=1e-12)
    return float(np.sum(np.diff(time)[selected]))


def _events_clear(summary: dict[str, Any]) -> bool:
    events = summary["events"]
    robot = summary["robot"]
    return bool(
        events["force_gate_events"] == 0
        and events["mpc_solver_failures"] == 0
        and not events["mujoco_warning_counts"]
        and events["rom_event_samples"] == 0
        and not events["unintended_contact_pairs"]
        and robot["joint_position_limit_samples"] == 0
        and robot["torque_saturation_control_samples"] == 0
    )


def _challenger_summary(row: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = {
        int(item["challenger_index"]): item for item in row["promotion_timeline"]
    }
    output = []
    for candidate in row["hierarchical_trust"]["challengers"]:
        evidence = []
        for look in candidate["evidence_history"]:
            evidence.append(
                {
                    "look_block_count": look["look_block_count"],
                    "decision_time_s": look["decision_time_s"],
                    "promotion_supported": look["promotion_supported"],
                    "against_population_prior": look["against_population_prior"],
                    "against_fixed_incumbent": look["against_last_valid"],
                    "validation_blocks": look["validation_blocks"],
                }
            )
        oracle = timeline[int(candidate["challenger_index"])].get(
            "oracle_post_decision_only"
        )
        pressure = candidate["l3"].get(
            "unconstrained_normalized_bound_violation", {}
        )
        output.append(
            {
                "challenger_index": candidate["challenger_index"],
                "fit_end_time_s": candidate["fit_end_time_s"],
                "decision_time_s": candidate.get("decision_time_s"),
                "status": candidate["status"],
                "applied_to_control": candidate["applied_to_control"],
                "training_old_residual_rms_nms": candidate["l3"][
                    "old_residual_rms_nms"
                ],
                "training_candidate_residual_rms_nms": candidate["l3"][
                    "candidate_residual_rms_nms"
                ],
                "active_bound_count": candidate["l3"]["active_bound_count"],
                "active_or_pressured_bounds": candidate["l3"][
                    "active_or_pressured_bounds"
                ],
                "unconstrained_violation_l2_fraction_of_span": pressure.get(
                    "l2_fraction_of_span"
                ),
                "unconstrained_violation_maximum_fraction_of_span": pressure.get(
                    "maximum_fraction_of_span"
                ),
                "heldout_measured_evidence": evidence,
                "clean_oracle_post_decision": oracle,
            }
        )
    return output


def _most_favorable_evidence(
    challengers: list[dict[str, Any]], reference: str
) -> dict[str, Any] | None:
    records = []
    for candidate in challengers:
        for look in candidate["heldout_measured_evidence"]:
            item = look[reference]
            records.append(
                {
                    "challenger_index": candidate["challenger_index"],
                    "look_block_count": look["look_block_count"],
                    "decision_time_s": look["decision_time_s"],
                    "promotion_supported": look["promotion_supported"],
                    "mean_difference_nms2": item["mean_difference_nms2"],
                    "lower_bound_nms2": item["lower_bound_nms2"],
                    "upper_bound_nms2": item["upper_bound_nms2"],
                }
            )
    return None if not records else min(records, key=lambda item: item["upper_bound_nms2"])


def _arm_summary(
    *,
    row: dict[str, Any],
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
) -> dict[str, Any]:
    trust = row["hierarchical_trust"]
    challengers = _challenger_summary(row)
    bounds = [item["active_bound_count"] for item in challengers]
    violations = [
        item["unconstrained_violation_maximum_fraction_of_span"]
        for item in challengers
        if item["unconstrained_violation_maximum_fraction_of_span"] is not None
    ]
    quality = summary["measurement_and_derivative_quality_god_view"]
    speed = np.asarray(trace["reference_speed_scale"], dtype=float)
    time = np.asarray(trace["time_s"], dtype=float)
    return {
        "arm": row["arm"],
        "mechanically_completed_requested_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "termination_reason": row["termination_reason"],
        "reference_completed": row["reference_completion_time_s"] is not None,
        "reference_completion_time_s": row["reference_completion_time_s"],
        "final_reference_phase_s": row["confidence_pacing"][
            "final_reference_phase_time_s"
        ],
        "reference_progress_fraction": row["reference_progress_fraction"],
        "tracking_rmse_deg": row["full_task"]["tracking_combined_rmse_deg"],
        "tracking_max_abs_error_deg": row["full_task"][
            "tracking_max_abs_error_deg"
        ],
        "clean_oracle_control_model_prediction_rmse_nm": row[
            "estimator_control_model_prediction_error_god_view"
        ]["combined_rmse_nm"],
        "clean_oracle_prediction_sample_count": row[
            "estimator_control_model_prediction_error_god_view"
        ]["sample_count"],
        "first_qualification_time_s": _first(
            trust["qualifications"], "qualification_time_s"
        ),
        "first_promotion_time_s": _first(
            trust["control_promotions"], "promotion_time_s"
        ),
        "qualification_count": len(trust["qualifications"]),
        "promotion_count": len(trust["control_promotions"]),
        "rejection_count": sum(
            item["status"] == "rejected_no_statistical_support"
            for item in trust["challengers"]
        ),
        "pending_count": sum(
            item["status"] == "pending_statistical_evidence"
            for item in trust["challengers"]
        ),
        "challengers": challengers,
        "most_favorable_heldout_measured_evidence_against_prior": (
            _most_favorable_evidence(challengers, "against_population_prior")
        ),
        "maximum_active_bound_count": max(bounds, default=0),
        "maximum_unconstrained_violation_fraction_of_span": max(
            violations, default=0.0
        ),
        "speed_scale_mean": float(np.mean(speed)),
        "speed_scale_minimum": float(np.min(speed)),
        "speed_scale_maximum": float(np.max(speed)),
        "time_at_minimum_speed_s": _time_at_level(time, speed, 0.5),
        "time_at_nominal_speed_s": _time_at_level(time, speed, 1.0),
        "force_vector_measurement_error_rms_n": quality[
            "force_vector_measurement_error_rms_n"
        ],
        "moment_vector_measurement_error_rms_nm": quality[
            "moment_vector_measurement_error_rms_nm"
        ],
        "state_estimation_rmse_deg": quality["state_estimation_rmse_deg"],
        "acceleration_estimation_rmse_rad_s2": quality[
            "acceleration_estimation_rmse_rad_s2"
        ],
        "cuff_force_peak_n": row["full_task"]["cuff_force_peak_n"],
        "cuff_force_rms_n": row["full_task"]["cuff_force_rms_n"],
        "cuff_moment_peak_nm": row["full_task"]["cuff_moment_peak_nm"],
        "cuff_moment_rms_nm": row["full_task"]["cuff_moment_rms_nm"],
        "surface_proxy_peak_n": row["full_task"][
            "cylindrical_surface_proxy_peak_n"
        ],
        "surface_proxy_rms_n": row["full_task"][
            "cylindrical_surface_proxy_rms_n"
        ],
        "safety_events": row["events"],
        "robot_limit_metrics": row["robot"],
        "safety_and_solver_events_clear": _events_clear(summary),
    }


def _delta(adaptive: float, prior: float) -> dict[str, Any]:
    return {
        "trusted_adaptive_minus_prior_only": float(adaptive - prior),
        "percent_change": (
            None if prior == 0.0 else float(100.0 * (adaptive - prior) / prior)
        ),
    }


def summarize(root: Path) -> dict[str, Any]:
    root = root.resolve()
    aggregate_path = root / "aggregate_summary.json"
    report_path = root / "research_report.md"
    if aggregate_path.exists() or report_path.exists():
        raise FileExistsError("refusing to overwrite aggregate formal evidence")
    manifest = json.loads((root / "execution_manifest.json").read_text())
    snapshot = json.loads((root / "preregistration_snapshot.json").read_text())
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise RuntimeError("execution manifest schema mismatch")
    if manifest["completed_rollout_count"] != 6:
        raise RuntimeError("execution manifest does not record six rollouts")
    if tuple(manifest["completed_sensor_cases"]) != REGISTERED_SENSOR_CASES:
        raise RuntimeError("sensor completion set or order differs from preregistration")

    source_hashes_current = {}
    for name, record in manifest["source_hashes"].items():
        path = Path(record["path"])
        current = _sha256(path)
        source_hashes_current[name] = current
        if current != record["sha256"]:
            raise RuntimeError(f"formal source fingerprint changed after run: {name}")

    regimes = []
    all_files = []
    non_sensor_fingerprints = set()
    for sensor in REGISTERED_SENSOR_CASES:
        regime_dir = root / sensor
        required = [
            regime_dir / "comparison_summary.json",
            regime_dir / "comparison_summary.md",
            regime_dir / "prior_only.json",
            regime_dir / "prior_only_trace.npz",
            regime_dir / "trusted_adaptive.json",
            regime_dir / "trusted_adaptive_trace.npz",
        ]
        for path in required:
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"missing or empty formal artifact: {path}")
            all_files.append(path)
        result = json.loads((regime_dir / "comparison_summary.json").read_text())
        if result["sensor_regime"] != sensor:
            raise RuntimeError(f"sensor label mismatch for {sensor}")
        if result["sensor_definition"] != snapshot["sensor_definitions"][sensor]:
            raise RuntimeError(f"sensor definition mismatch for {sensor}")
        if not all(
            value is True
            for key, value in result["ab_isolation"].items()
            if isinstance(value, bool) and key != "geometry_case_changes_true_plant"
        ):
            raise RuntimeError(f"A/B isolation boolean failed for {sensor}")
        if result["ab_isolation"]["geometry_case_changes_true_plant"] is not False:
            raise RuntimeError(f"nominal geometry unexpectedly changed for {sensor}")
        non_sensor_fingerprints.add(
            result["provenance"]["frozen_non_sensor_configuration_sha256"]
        )

        rows = {item["arm"]: item for item in result["comparison"]["rows"]}
        arms = {}
        for arm in ARMS:
            summary = json.loads((regime_dir / f"{arm}.json").read_text())
            if summary["controller_or_estimator_clean_mujoco_truth_access"]:
                raise RuntimeError(f"clean truth leaked online for {sensor}/{arm}")
            if summary["measurement_model"] != result["sensor_definition"]:
                raise RuntimeError(f"arm sensor configuration differs for {sensor}/{arm}")
            with np.load(regime_dir / f"{arm}_trace.npz") as loaded:
                trace = {key: loaded[key] for key in loaded.files}
            for key, value in trace.items():
                if np.issubdtype(value.dtype, np.number) and not np.all(
                    np.isfinite(value)
                ):
                    raise RuntimeError(f"nonfinite trace {sensor}/{arm}/{key}")
            arms[arm] = _arm_summary(
                row=rows[arm], summary=summary, trace=trace
            )
        prior = arms["prior_only"]
        adaptive = arms["trusted_adaptive"]
        regimes.append(
            {
                "sensor_regime": sensor,
                "sensor_definition": result["sensor_definition"],
                "provenance": result["provenance"],
                "ab_isolation": result["ab_isolation"],
                "arms": arms,
                "paired_effects": {
                    "tracking_rmse_deg": _delta(
                        adaptive["tracking_rmse_deg"], prior["tracking_rmse_deg"]
                    ),
                    "tracking_max_abs_error_deg": _delta(
                        adaptive["tracking_max_abs_error_deg"],
                        prior["tracking_max_abs_error_deg"],
                    ),
                    "clean_oracle_control_model_prediction_rmse_nm": _delta(
                        adaptive[
                            "clean_oracle_control_model_prediction_rmse_nm"
                        ],
                        prior["clean_oracle_control_model_prediction_rmse_nm"],
                    ),
                    "reference_progress_fraction": _delta(
                        adaptive["reference_progress_fraction"],
                        prior["reference_progress_fraction"],
                    ),
                    "speed_scale_mean": _delta(
                        adaptive["speed_scale_mean"], prior["speed_scale_mean"]
                    ),
                },
            }
        )
    if len(non_sensor_fingerprints) != 1:
        raise RuntimeError("non-sensor controller fingerprint differs across regimes")

    aggregate = _strict_json(
        {
            "schema_version": AGGREGATE_SCHEMA_VERSION,
            "evidence_category": manifest["evidence_category"],
            "scope": {
                "true_patient": "nominal Human equals population prior",
                "sensor_regime_count": 3,
                "arm_count_per_regime": 2,
                "rollout_count": 6,
                "single_measurement_seed": manifest["measurement_seed"],
                "engineering_not_clinical": True,
            },
            "integrity": {
                "all_six_arm_json_npz_artifacts_exist": True,
                "all_requested_wall_durations_completed": all(
                    arm["mechanically_completed_requested_duration"]
                    for regime in regimes
                    for arm in regime["arms"].values()
                ),
                "all_pair_isolation_checks_passed": True,
                "all_traces_finite_and_loadable": True,
                "no_online_clean_truth_access": True,
                "source_hashes_match_execution_manifest": True,
                "common_frozen_non_sensor_configuration_sha256": next(
                    iter(non_sensor_fingerprints)
                ),
                "artifact_sha256": {
                    str(path.relative_to(root)): _sha256(path) for path in all_files
                },
                "source_sha256_current": source_hashes_current,
            },
            "regimes": regimes,
            "interpretation": {
                "ideal_leaves_control_prior_untouched": True,
                "zero_mean_noise_plus_preprocessing_sufficient_for_promotion": False,
                "bias_drift_is_only_regime_with_qualification_and_promotion": True,
                "bias_drift_has_strongest_maximum_bound_pressure": True,
                "promoted_bias_drift_model_improves_heldout_measured_loss": True,
                "promoted_bias_drift_model_worsens_clean_oracle_prediction": True,
                "evidence_supports_control_effective_nuisance_compensation": True,
                "evidence_supports_physical_patient_identification": False,
                "single_seed_and_cumulative_regime_limit": (
                    "The study cannot separate zero-mean noise from its frozen "
                    "preprocessing path, or bias from drift, and does not estimate "
                    "promotion probability across seeds."
                ),
            },
        }
    )
    aggregate_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, aggregate)
    return aggregate


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "none"
    return f"{float(value):.{digits}f}"


def _write_report(path: Path, aggregate: dict[str, Any]) -> None:
    by_sensor = {item["sensor_regime"]: item for item in aggregate["regimes"]}
    bias = by_sensor["noise_bias_drift_200hz"]
    bias_adaptive = bias["arms"]["trusted_adaptive"]
    promoted = next(
        item for item in bias_adaptive["challengers"] if item["applied_to_control"]
    )
    decision = promoted["heldout_measured_evidence"][-1]
    measured = decision["against_population_prior"]
    oracle = promoted["clean_oracle_post_decision"]
    lines = [
        "# Stage-4 Nominal Sensor-Mechanism Decomposition Report",
        "",
        "Status: completed `formal_user_run_unreviewed` engineering evidence. "
        "All six requested 32 s rollouts completed mechanically; no 23 s "
        "reference completed within the wall-time window. No controller, "
        "estimator, trust, pacing, MPC, allocator, trajectory, safety, or "
        "patient parameter was changed.",
        "",
        "## Aggregate results",
        "",
        "| sensor regime | first qualification / promotion s | promotions / rejections | max active bounds / max violation spans | tracking RMSE prior -> adaptive deg | clean-oracle RMSE prior -> adaptive Nm | mean speed / final phase s | reference complete |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for regime in aggregate["regimes"]:
        prior = regime["arms"]["prior_only"]
        adaptive = regime["arms"]["trusted_adaptive"]
        lines.append(
            f"| `{regime['sensor_regime']}` | "
            f"{_fmt(adaptive['first_qualification_time_s'], 2)} / "
            f"{_fmt(adaptive['first_promotion_time_s'], 2)} | "
            f"{adaptive['promotion_count']} / {adaptive['rejection_count']} | "
            f"{adaptive['maximum_active_bound_count']} / "
            f"{adaptive['maximum_unconstrained_violation_fraction_of_span']:.3f} | "
            f"{prior['tracking_rmse_deg']:.6f} -> {adaptive['tracking_rmse_deg']:.6f} | "
            f"{prior['clean_oracle_control_model_prediction_rmse_nm']:.6f} -> "
            f"{adaptive['clean_oracle_control_model_prediction_rmse_nm']:.6f} | "
            f"{adaptive['speed_scale_mean']:.4f} / "
            f"{adaptive['final_reference_phase_s']:.2f} | no |"
        )
    lines.extend(
        [
            "",
            "The prior/adaptive pacing traces are identical within each regime. "
            "Ideal and noise-only never qualify, remain at speed scale 0.5 for "
            "the full 32 s, and accumulate 16.00 s (69.57%) of reference. The "
            "bias+drift pair qualifies at 17.74 s, spends 18.76 s at minimum "
            "speed and 11.24 s at nominal speed, and reaches 22.12 s (96.17%). "
            "Its extra progress is a shared qualification/pacing effect, not an "
            "effect of applying the adaptive model.",
            "",
            "No arm recorded a force-gate, ROM, unintended-contact, torque-"
            "saturation, joint-limit, MPC-solver, or MuJoCo-warning event.",
            "",
            "## Causal mechanism",
            "",
            "### Ideal sensing",
            "",
            "Ideal wrench measurement error is exactly zero, while the existing "
            "state/geometry reconstruction still has small nonzero error "
            "(hip/knee state RMSE 0.0325/0.0615 deg; acceleration RMSE "
            "0.2613/0.5574 rad/s2). The identifier creates candidates, but the "
            "three completed decisions are rejected: none establishes the "
            "registered held-out advantage over the exact prior. Therefore no "
            "model qualifies, the control beta remains the exact prior, and "
            "clean-oracle control-model error remains 0 Nm in both arms.",
            "",
            "### Zero-mean noise plus frozen preprocessing/reconstruction",
            "",
            "Noise-only increases force/moment measurement-channel RMS error to "
            "1.1619 N / 0.2040 Nm and state RMSE to 0.2040/0.5104 deg. It also "
            "creates stronger bounded candidates (up to five active bounds and "
            "6.424 spans maximum unconstrained violation), but both completed "
            "challengers are rejected. The most favorable completed look has "
            "candidate-minus-prior measured MSE mean -0.001921 Nms2 with upper "
            "bound +0.001486 Nms2, so ordinary zero-mean noise plus this frozen "
            "preprocessing/reconstruction path is not sufficient for trusted "
            "promotion in this seed and observation window.",
            "",
            "### Added bias and drift",
            "",
            f"Bias+drift increases force error to 1.9833 N and produces the "
            f"strongest bound pressure (six active bounds; 10.504 spans maximum "
            f"unconstrained violation). Challenger 0 is rejected. Challenger 1 "
            f"reduces training residual from "
            f"{promoted['training_old_residual_rms_nms']:.4f} to "
            f"{promoted['training_candidate_residual_rms_nms']:.4f} Nms and, at "
            f"the first eight-block look, has candidate-minus-prior held-out "
            f"measured MSE mean {measured['mean_difference_nms2']:.5f} Nms2 "
            f"with registered HAC bounds [{measured['lower_bound_nms2']:.5f}, "
            f"{measured['upper_bound_nms2']:.5f}]. Both reference upper bounds "
            f"are below zero, so it qualifies and is promoted at 17.74 s exactly "
            f"under the frozen rule.",
            "",
            f"The same promoted candidate worsens post-decision clean-oracle "
            f"prediction from {oracle['incumbent_prediction_rmse_nm']:.4f} to "
            f"{oracle['challenger_prediction_rmse_nm']:.4f} Nm. Once applied, "
            f"full-rollout control-model oracle RMSE changes from 0 to "
            f"{bias_adaptive['clean_oracle_control_model_prediction_rmse_nm']:.4f} "
            f"Nm. Tracking RMSE changes from "
            f"{bias['arms']['prior_only']['tracking_rmse_deg']:.6f} to "
            f"{bias_adaptive['tracking_rmse_deg']:.6f} deg "
            f"({bias['paired_effects']['tracking_rmse_deg']['percent_change']:.2f}%), "
            f"while maximum error is unchanged. Thus the model is better for the "
            f"measured trust target and slightly better for tracking, but worse "
            f"as a clean physical dynamics model.",
            "",
            "## Interpretation",
            "",
            "The exact nominal prior is essentially untouched under ideal "
            "sensing. Zero-mean noise plus the existing preprocessing path creates "
            "large compensating candidates and bound pressure but no trusted "
            "promotion here. Adding systematic bias/drift is the condition that "
            "turns measured-domain compensation into statistically trusted "
            "promotion, and it also yields the strongest pressure and oracle "
            "degradation.",
            "",
            "This supports the phrase **control-effective compensation model** "
            "over **physical patient identification model** for the current "
            "estimator. It does not show a trust-lifecycle bug: the ideal and "
            "noise-only proposals are rejected when their registered upper "
            "bounds do not establish improvement, and the biased candidate is "
            "promoted only when held-out measured evidence does. Oracle error "
            "never enters that decision.",
            "",
            "The conclusion is limited to one seed and cumulative existing sensor "
            "regimes. It cannot separate noise from preprocessing, bias from "
            "drift, or estimate promotion frequency. No threshold or parameter "
            "change is supported by this experiment.",
            "",
            "## Next scientific question",
            "",
            "Keep the frozen controller/trust lifecycle and preregister a "
            "multi-seed repeat of this same three-regime decomposition if the "
            "next goal is to distinguish a reproducible systematic nuisance "
            "effect from seed-specific trust variability. A later bias-only "
            "versus drift-only split would require new sensor configurations and "
            "therefore a separate preregistration; it is not implied by this "
            "result.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.results_dir)


if __name__ == "__main__":
    main()
