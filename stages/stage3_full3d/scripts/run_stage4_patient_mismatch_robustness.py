#!/usr/bin/env python3
"""Run one preregistered patient case through the frozen paired Stage-4 A/B path."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, CONTROL_SUBSTEPS, SIMULATION_DT_S
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from traction_mpc_stage4.patient_mismatch import (
    CASE_RESULT_REQUIRED_FIELDS,
    FROZEN_SHARED_AB_CONTRACT,
    RESULT_SCHEMA_VERSION,
    PatientCaseSpec,
    load_patient_case_specs,
    patient_case_record,
)
from traction_mpc_stage4.reference import COLD_START_TEACHING_DURATION_S

try:
    from .run_stage4_single_challenger_closed_loop_ab import run_paired_ab
except ImportError:  # Direct execution from the scripts directory.
    from run_stage4_single_challenger_closed_loop_ab import run_paired_ab


BASELINE_TAG = "stage4-baseline-v1"
BASELINE_COMMIT = "ef1fe90e61c5981df8e934585780ce188d104ea4"
REGISTERED_SENSOR_CASE = "noise_bias_drift_200hz"
REGISTERED_MEASUREMENT_SEED = 44104
REGISTERED_MPC_SEED = 20260824
FORMAL_WALL_LIMIT_S = 32.0
SMOKE_EVIDENCE_CATEGORY = "structural_smoke_non_scientific"
FORMAL_EVIDENCE_CATEGORY = "formal_user_run_unreviewed"
SMOKE_MARKER = ".stage4_patient_mismatch_structural_smoke"


def select_patient_case(
    case_config: Path, case_id: str
) -> tuple[PatientCaseSpec, tuple[PatientCaseSpec, ...]]:
    specs = load_patient_case_specs(case_config)
    selected = [item for item in specs if item.case_id == case_id]
    if len(selected) != 1:
        available = ", ".join(item.case_id for item in specs)
        raise ValueError(f"unknown patient case {case_id!r}; available: {available}")
    return selected[0], specs


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _strict_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _strict_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return _strict_json(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _git_provenance(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        dirty = bool(run("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        return {"code_commit": None, "working_tree_dirty": None}
    return {"code_commit": commit, "working_tree_dirty": dirty}


def _prepare_case_output_directory(
    case_output_dir: Path,
    *,
    structural_smoke: bool,
    debug_allow_existing_output: bool,
) -> None:
    if not case_output_dir.exists():
        return
    marker = case_output_dir / SMOKE_MARKER
    if not (
        structural_smoke
        and debug_allow_existing_output
        and marker.is_file()
    ):
        raise FileExistsError(f"refusing to overwrite {case_output_dir}")


def _first_time(records: list[dict[str, Any]], key: str) -> float | None:
    return None if not records else float(records[0][key])


def _span_distance(beta: np.ndarray, true_beta: np.ndarray) -> float:
    span = AccumulatedIntegralBaseDynamicIdentifier().span
    return float(np.linalg.norm((np.asarray(beta) - true_beta) / span))


def _candidate_bound_pressure(summary: dict[str, Any]) -> dict[str, Any]:
    challengers = summary["hierarchical_trust"]["challengers"]
    if challengers:
        l3 = challengers[-1]["l3"]
        violation = l3.get("unconstrained_normalized_bound_violation", {})
        return {
            "available": True,
            "active_bound_count": int(l3.get("active_bound_count", 0)),
            "active_or_pressured_bounds": l3.get(
                "active_or_pressured_bounds", []
            ),
            "unconstrained_violation_l2_fraction_of_span": violation.get(
                "l2_fraction_of_span"
            ),
            "unconstrained_violation_maximum_fraction_of_span": violation.get(
                "maximum_fraction_of_span"
            ),
        }
    last = summary["dynamic_identifier"]["last_attempt"]
    return {
        "available": False,
        "reason": "no_challenger_created",
        "latest_identifier_attempted": bool(last.get("attempted", False)),
        "latest_identifier_bound_hit": bool(last.get("bound_hit", False)),
    }


def _arm_result(
    arm: str,
    row: dict[str, Any],
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    *,
    true_beta: np.ndarray,
    prior_to_true_distance: float,
    arm_provenance: dict[str, Any],
) -> dict[str, Any]:
    trust = summary["hierarchical_trust"]
    qualifications = trust["qualifications"]
    promotions = trust["control_promotions"]
    challengers = trust["challengers"]
    applied_timeline = [
        item for item in row["promotion_timeline"] if item["applied_to_control"]
    ]
    final_control_beta = np.asarray(trace["dynamic_base_estimate"][-1], dtype=float)
    challenger_distance = (
        None
        if not challengers
        else _span_distance(
            np.asarray(challengers[-1]["proposed_model_beta"], dtype=float),
            true_beta,
        )
    )
    full = row["full_task"]
    prediction = row["estimator_control_model_prediction_error_god_view"]
    result = {
        "arm": arm,
        "tracking_rmse_deg": full.get("tracking_combined_rmse_deg"),
        "maximum_tracking_error_deg": full.get("tracking_max_abs_error_deg"),
        "reference_progress_fraction": row["reference_progress_fraction"],
        "reference_completion_time_s": row["reference_completion_time_s"],
        "termination_reason": row["termination_reason"],
        "safety_events": summary["events"],
        "generalized_torque_prediction_rmse_nm": prediction.get(
            "combined_rmse_nm"
        ),
        "generalized_torque_prediction_sample_count": prediction.get(
            "sample_count", 0
        ),
        "first_challenger_qualification_time_s": _first_time(
            qualifications, "qualification_time_s"
        ),
        "first_promotion_time_s": _first_time(promotions, "promotion_time_s"),
        "promotion_count": len(promotions),
        "promotion_timeline": row["promotion_timeline"],
        "trajectory_remaining_after_first_promotion_s": (
            None
            if not applied_timeline
            else applied_timeline[0].get("remaining_reference_duration_s")
        ),
        "candidate_status": (
            "not_created" if not challengers else challengers[-1]["status"]
        ),
        "active_bound_pressure": _candidate_bound_pressure(summary),
        "trusted_adaptation_entered_control": bool(promotions),
        "cuff_force_peak_n": full.get("cuff_force_peak_n"),
        "cuff_force_rms_n": full.get("cuff_force_rms_n"),
        "cuff_moment_peak_nm": full.get("cuff_moment_peak_nm"),
        "cuff_moment_rms_nm": full.get("cuff_moment_rms_nm"),
        "cylindrical_surface_proxy_peak_n": full.get(
            "cylindrical_surface_proxy_peak_n"
        ),
        "cylindrical_surface_proxy_rms_n": full.get(
            "cylindrical_surface_proxy_rms_n"
        ),
        "prior_to_true_beta_span_l2": prior_to_true_distance,
        "incumbent_to_true_beta_span_l2": _span_distance(
            final_control_beta, true_beta
        ),
        "challenger_to_true_beta_span_l2": challenger_distance,
        "provenance": arm_provenance,
    }
    missing = set(CASE_RESULT_REQUIRED_FIELDS["arm"]) - set(result)
    if missing:
        raise RuntimeError(f"arm result schema missing fields: {sorted(missing)}")
    return result


def _assert_trace_equal(
    prior: dict[str, np.ndarray],
    adaptive: dict[str, np.ndarray],
    key: str,
    mask: np.ndarray,
) -> float:
    left = np.asarray(prior[key])[mask]
    right = np.asarray(adaptive[key])[mask]
    if left.shape != right.shape:
        raise RuntimeError(f"pre-promotion A/B shape differs at {key}")
    if np.issubdtype(left.dtype, np.bool_):
        if not np.array_equal(left, right):
            raise RuntimeError(f"pre-promotion A/B trace differs at {key}")
        return 0.0
    maximum = float(np.max(np.abs(left - right))) if left.size else 0.0
    if not np.allclose(left, right, rtol=0.0, atol=1e-10):
        raise RuntimeError(f"pre-promotion A/B trace differs at {key}")
    return maximum


def verify_case_pair_isolation(
    comparison: dict[str, Any],
    summaries: dict[str, dict[str, Any]],
    traces: dict[str, dict[str, np.ndarray]],
    case_record: dict[str, Any],
) -> dict[str, Any]:
    prior_summary = summaries["prior_only"]
    adaptive_summary = summaries["trusted_adaptive"]
    prior_trace = traces["prior_only"]
    adaptive_trace = traces["trusted_adaptive"]
    true_beta = np.asarray(case_record["beta_11"], dtype=float)
    population_prior = nominal_base_parameters(HUMAN)

    for summary in (prior_summary, adaptive_summary):
        np.testing.assert_allclose(
            summary["dynamic_identifier"]["true_base_parameters_god_view"],
            true_beta,
            rtol=0.0,
            atol=1e-12,
        )
        if summary["true_human_case"] != case_record["case_id"]:
            raise RuntimeError("true patient label differs from selected case")
        if summary["controller_or_estimator_clean_mujoco_truth_access"]:
            raise RuntimeError("controller or estimator received clean MuJoCo truth")

    if prior_summary["measurement_model"] != adaptive_summary["measurement_model"]:
        raise RuntimeError("A/B measurement models differ")
    if prior_summary["measurement_routing"] != adaptive_summary["measurement_routing"]:
        raise RuntimeError("A/B measurement routing differs")
    if prior_summary["mpc"]["objective_contract"] != adaptive_summary["mpc"][
        "objective_contract"
    ]:
        raise RuntimeError("A/B MPC objective contracts differ")
    if prior_summary["reference_execution"]["config"] != adaptive_summary[
        "reference_execution"
    ]["config"]:
        raise RuntimeError("A/B pacing configurations differ")

    prior_trust = prior_summary["hierarchical_trust"]
    adaptive_trust = adaptive_summary["hierarchical_trust"]
    if prior_trust["apply_qualified_model_to_control"] is not False:
        raise RuntimeError("prior_only may not apply a qualified dynamics model")
    if adaptive_trust["apply_qualified_model_to_control"] is not True:
        raise RuntimeError("trusted_adaptive lost frozen promotion semantics")
    if prior_trust["statistical_config"] != adaptive_trust["statistical_config"]:
        raise RuntimeError("A/B statistical trust configurations differ")

    for trace in (prior_trace, adaptive_trace):
        np.testing.assert_allclose(
            trace["dynamic_base_estimate"][0],
            population_prior,
            rtol=0.0,
            atol=1e-12,
        )
    np.testing.assert_allclose(
        prior_trace["dynamic_base_estimate"],
        np.broadcast_to(
            population_prior, np.asarray(prior_trace["dynamic_base_estimate"]).shape
        ),
        rtol=0.0,
        atol=1e-12,
    )

    prior_time = np.asarray(prior_trace["time_s"])
    adaptive_time = np.asarray(adaptive_trace["time_s"])
    split_time = comparison["shared_pre_post_split_wall_time_s"]
    if split_time is None:
        prior_mask = np.ones(len(prior_time), dtype=bool)
        adaptive_mask = np.ones(len(adaptive_time), dtype=bool)
    else:
        prior_mask = prior_time < float(split_time) - 1e-12
        adaptive_mask = adaptive_time < float(split_time) - 1e-12
    if not np.array_equal(prior_time[prior_mask], adaptive_time[adaptive_mask]):
        raise RuntimeError("pre-promotion A/B time grids differ")
    if len(prior_mask) != len(adaptive_mask) or not np.array_equal(
        prior_mask, adaptive_mask
    ):
        raise RuntimeError("pre-promotion A/B masks differ")

    prior_control_time = np.asarray(prior_trace["control_time_s"])
    adaptive_control_time = np.asarray(adaptive_trace["control_time_s"])
    if split_time is None:
        prior_control_mask = np.ones(len(prior_control_time), dtype=bool)
        adaptive_control_mask = np.ones(len(adaptive_control_time), dtype=bool)
    else:
        prior_control_mask = prior_control_time < float(split_time) - 1e-12
        adaptive_control_mask = adaptive_control_time < float(split_time) - 1e-12
    if not np.array_equal(
        prior_control_time[prior_control_mask],
        adaptive_control_time[adaptive_control_mask],
    ):
        raise RuntimeError("pre-promotion A/B control time grids differ")
    if len(prior_control_mask) != len(adaptive_control_mask) or not np.array_equal(
        prior_control_mask, adaptive_control_mask
    ):
        raise RuntimeError("pre-promotion A/B control masks differ")

    equality_keys = (
        "human_q_deg_god_view",
        "human_q_ref_deg",
        "estimated_human_q_deg",
        "estimated_human_dq_deg_s",
        "robot_q_rad",
        "robot_dq_rad_s",
        "desired_human_action_nm",
        "allocated_wrench_world",
        "geometry_estimate",
        "dynamic_base_estimate",
        "reference_phase_time_s",
        "reference_speed_scale",
    )
    trace_differences = {
        key: _assert_trace_equal(prior_trace, adaptive_trace, key, prior_mask)
        for key in equality_keys
    }
    control_rate_equality_keys = (
        "measurement_new_sample",
        "measured_cuff_force_world_n",
        "measured_cuff_moment_world_nm",
    )
    trace_differences.update(
        {
            key: _assert_trace_equal(
                prior_trace, adaptive_trace, key, prior_control_mask
            )
            for key in control_rate_equality_keys
        }
    )
    np.testing.assert_allclose(
        adaptive_trace["dynamic_base_estimate"][adaptive_mask],
        np.broadcast_to(
            population_prior,
            np.asarray(adaptive_trace["dynamic_base_estimate"])[adaptive_mask].shape,
        ),
        rtol=0.0,
        atol=1e-12,
    )

    initial_geometry = np.asarray(prior_trace["geometry_estimate"][0], dtype=float)
    np.testing.assert_allclose(
        initial_geometry[2], HUMAN.thigh_length_m, rtol=0.0, atol=1e-12
    )
    np.testing.assert_allclose(
        np.linalg.norm(initial_geometry[3:5]),
        HUMAN.sleeve_center_m,
        rtol=0.0,
        atol=1e-12,
    )
    true_raw = case_record["raw_human_parameters"]
    geometry_changed = bool(case_record["geometry"]["changes"])
    if geometry_changed and (
        math.isclose(true_raw["thigh_length_m"], HUMAN.thigh_length_m)
        and math.isclose(true_raw["sleeve_center_m"], HUMAN.sleeve_center_m)
    ):
        raise RuntimeError("case says geometry changed but true geometry is nominal")

    return {
        **comparison["mechanical_ab_isolation"],
        "selected_true_patient_equal_between_arms": True,
        "initial_human_state_equal": trace_differences["human_q_deg_god_view"]
        == 0.0,
        "initial_robot_state_equal": trace_differences["robot_q_rad"] == 0.0,
        "measurement_seed_and_realization_equal_before_promotion": (
            trace_differences["measurement_new_sample"] == 0.0
            and trace_differences["measured_cuff_force_world_n"] == 0.0
            and trace_differences["measured_cuff_moment_world_nm"] == 0.0
        ),
        "controller_population_prior_equal_to_nominal": True,
        "prior_only_control_beta_constant_population_prior": True,
        "trusted_control_beta_population_prior_before_promotion": True,
        "geometry_estimation_active_and_equal_before_promotion": (
            trace_differences["geometry_estimate"] == 0.0
        ),
        "geometry_prior_uses_nominal_lengths_not_true_patient_oracle": True,
        "geometry_case_changes_true_plant": geometry_changed,
        "pre_promotion_trace_max_abs_difference": trace_differences,
    }


def _runtime_controller_fingerprint(
    comparison: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    config = comparison["registered_configuration"]
    payload = {
        "preregistered_contract": FROZEN_SHARED_AB_CONTRACT,
        "measurement_model": config["measurement_model"],
        "measurement_routing": config["measurement_routing"],
        "mpc_objective_contract": config["mpc_objective_contract"],
        "confidence_pacing_config": config["confidence_pacing_config"],
        "statistical_trust_config": config["statistical_trust_config"],
        "plant_integrator": {
            "simulation_dt_s": SIMULATION_DT_S,
            "control_dt_s": CONTROL_DT_S,
            "control_substeps": CONTROL_SUBSTEPS,
        },
    }
    return _canonical_fingerprint(payload), payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# Patient-mismatch paired A/B: {payload['case_record']['case_id']}",
        "",
        f"Evidence category: `{payload['evidence_category']}`.",
        "",
        "This artifact contains no post-hoc success threshold or interpretation.",
        "",
        "| arm | termination | progress | tracking RMSE deg | max error deg | promotions |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for arm in ("prior_only", "trusted_adaptive"):
        row = payload["arms"][arm]
        lines.append(
            f"| {arm} | {row['termination_reason']} | "
            f"{row['reference_progress_fraction']:.6g} | "
            f"{row['tracking_rmse_deg']:.6g} | "
            f"{row['maximum_tracking_error_deg']:.6g} | "
            f"{row['promotion_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_selected_patient_case(
    *,
    case_config: Path,
    case_id: str,
    output_root: Path,
    smoke_duration_s: float | None = None,
    debug_allow_existing_output: bool = False,
) -> dict[str, Any]:
    structural_smoke = smoke_duration_s is not None
    if structural_smoke and not 0.0 < float(smoke_duration_s) <= 0.5:
        raise ValueError("structural smoke duration must lie in (0, 0.5] seconds")
    if debug_allow_existing_output and not structural_smoke:
        raise ValueError("existing-output override is restricted to structural smoke")

    spec, all_specs = select_patient_case(case_config, case_id)
    case_output_dir = output_root / spec.case_id
    _prepare_case_output_directory(
        case_output_dir,
        structural_smoke=structural_smoke,
        debug_allow_existing_output=debug_allow_existing_output,
    )
    record = patient_case_record(spec)
    true_human = spec.build_human()
    duration_s = float(smoke_duration_s) if structural_smoke else FORMAL_WALL_LIMIT_S
    evidence_category = (
        SMOKE_EVIDENCE_CATEGORY if structural_smoke else FORMAL_EVIDENCE_CATEGORY
    )
    true_metadata = {
        "case": spec.case_id,
        "patient_case_id": spec.case_id,
        "variation_spec": record["variation_spec"],
        "raw_human_parameters": record["raw_human_parameters"],
    }
    comparison, summaries, traces = run_paired_ab(
        case_output_dir,
        true_human=true_human,
        true_metadata=true_metadata,
        human_label=spec.case_id,
        wall_time_limit_s=duration_s,
        evidence_category=evidence_category,
        write_comparison_outputs=False,
    )
    isolation = verify_case_pair_isolation(comparison, summaries, traces, record)
    controller_fingerprint, controller_payload = _runtime_controller_fingerprint(
        comparison
    )
    config_bytes = case_config.read_bytes()
    repo_root = Path(__file__).resolve().parents[3]
    git = _git_provenance(repo_root)
    provenance = {
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": BASELINE_COMMIT,
        "patient_case_config_path": str(case_config.resolve()),
        "patient_case_config_sha256": _sha256_bytes(config_bytes),
        "patient_case_config_schema": "stage4_patient_mismatch_cases_v1",
        "preregistered_case_count": len(all_specs),
        "frozen_controller_fingerprint_sha256": controller_fingerprint,
        "frozen_controller_fingerprint_payload": controller_payload,
        "measurement_seed": REGISTERED_MEASUREMENT_SEED,
        "mpc_seed": REGISTERED_MPC_SEED,
        "sensor_regime": REGISTERED_SENSOR_CASE,
        "trajectory_id": "stage4_population_prior_cold_start_high_flexion_23s",
        "reference_duration_s": COLD_START_TEACHING_DURATION_S,
        "runtime_allowance_s": duration_s,
        "structural_smoke": structural_smoke,
        **git,
    }
    rows = {item["arm"]: item for item in comparison["rows"]}
    true_beta = np.asarray(record["beta_11"], dtype=float)
    prior_distance = float(
        record["normalized_difference_from_prior"]["span_l2"]
    )
    arm_provenance = {
        arm: {
            "patient_case_id": spec.case_id,
            "arm": arm,
            "evidence_category": evidence_category,
            "baseline_tag": BASELINE_TAG,
            "baseline_commit": BASELINE_COMMIT,
            "patient_case_config_sha256": provenance[
                "patient_case_config_sha256"
            ],
            "measurement_seed": REGISTERED_MEASUREMENT_SEED,
            "mpc_seed": REGISTERED_MPC_SEED,
            "sensor_regime": REGISTERED_SENSOR_CASE,
            "trajectory_id": (
                "stage4_population_prior_cold_start_high_flexion_23s"
            ),
            "runtime_allowance_s": duration_s,
            "frozen_controller_fingerprint_sha256": controller_fingerprint,
            "code_commit": provenance["code_commit"],
            "working_tree_dirty": provenance["working_tree_dirty"],
        }
        for arm in ("prior_only", "trusted_adaptive")
    }
    arms = {
        arm: _arm_result(
            arm,
            rows[arm],
            summaries[arm],
            traces[arm],
            true_beta=true_beta,
            prior_to_true_distance=prior_distance,
            arm_provenance=arm_provenance[arm],
        )
        for arm in ("prior_only", "trusted_adaptive")
    }
    for arm in ("prior_only", "trusted_adaptive"):
        summaries[arm]["evidence_category"] = evidence_category
        summaries[arm]["paired_ab_provenance"] = arm_provenance[arm]
        (case_output_dir / f"{arm}.json").write_text(
            json.dumps(
                _strict_json(summaries[arm]),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    result = _strict_json(
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "evidence_category": evidence_category,
            "case_record": record,
            "provenance": provenance,
            "shared_ab_contract": FROZEN_SHARED_AB_CONTRACT,
            "ab_isolation": isolation,
            "arms": arms,
            "comparison": comparison["trusted_adaptive_minus_prior_only"],
        }
    )
    missing = set(CASE_RESULT_REQUIRED_FIELDS["top_level"]) - set(result)
    if missing:
        raise RuntimeError(f"pair result schema missing fields: {sorted(missing)}")
    case_output_dir.mkdir(parents=True, exist_ok=True)
    (case_output_dir / "comparison_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(case_output_dir / "comparison_summary.md", result)
    if structural_smoke:
        (case_output_dir / SMOKE_MARKER).write_text(
            "noncanonical structural smoke; no scientific interpretation\n",
            encoding="utf-8",
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-config",
        type=Path,
        default=Path("configs/stage4_patient_mismatch_cases.json"),
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--smoke-duration-s", type=float)
    parser.add_argument("--debug-allow-existing-output", action="store_true")
    args = parser.parse_args()
    run_selected_patient_case(
        case_config=args.case_config,
        case_id=args.case_id,
        output_root=args.output_dir,
        smoke_duration_s=args.smoke_duration_s,
        debug_allow_existing_output=args.debug_allow_existing_output,
    )


if __name__ == "__main__":
    main()
