#!/usr/bin/env python3
"""Run one preregistered trajectory through the frozen paired Stage-4 path.

Formal execution remains user-only.  ``--smoke-duration-s`` creates explicitly
non-scientific structural evidence and never changes the preregistered runtime
recorded in provenance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.patient_mismatch import patient_case_record
from traction_mpc_stage4.trajectory_excitation import (
    load_trajectory_suite,
    trajectory_case,
    trajectory_joint_reference,
    trajectory_reference,
    trajectory_waypoints as build_trajectory_waypoints,
)

try:
    from .run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        REGISTERED_MEASUREMENT_SEED,
        REGISTERED_MPC_SEED,
        REGISTERED_SENSOR_CASE,
        _canonical_fingerprint,
        _git_provenance,
        _runtime_controller_fingerprint,
        _sha256_bytes,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from .run_stage4_single_challenger_closed_loop_ab import (
        build_paired_ab_comparison,
        run_paired_ab,
    )
except ImportError:  # Direct execution from the scripts directory.
    from run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        REGISTERED_MEASUREMENT_SEED,
        REGISTERED_MPC_SEED,
        REGISTERED_SENSOR_CASE,
        _canonical_fingerprint,
        _git_provenance,
        _runtime_controller_fingerprint,
        _sha256_bytes,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from run_stage4_single_challenger_closed_loop_ab import (
        build_paired_ab_comparison,
        run_paired_ab,
    )


RESULT_SCHEMA_VERSION = "stage4_trajectory_excitation_paired_result_v1"
REGISTERED_PATIENT_ID = "registered_formal_perturbed_anchor"
RUNTIME_ALLOWANCE_S = 9.0
SMOKE_EVIDENCE_CATEGORY = "trajectory_excitation_structural_smoke_non_scientific"
FORMAL_EVIDENCE_CATEGORY = "formal_user_run_unreviewed"
RAW_ARM_EVIDENCE_CATEGORY = "stage4_sensor_realism_engineering_rollout"
SMOKE_MARKER = ".stage4_trajectory_excitation_structural_smoke"
DEFAULT_TRAJECTORY_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_trajectory_excitation_suite.json"
)
DEFAULT_PATIENT_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_patient_mismatch_cases.json"
)


def select_trajectory(
    config_path: Path, trajectory_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    suite = load_trajectory_suite(config_path)
    return trajectory_case(trajectory_id, suite), suite


def preregistered_runtime_limit_s(case: dict[str, Any]) -> float:
    return float(case["duration_s"]) + RUNTIME_ALLOWANCE_S


def _reference_validation(case: dict[str, Any]) -> dict[str, Any]:
    waypoints = build_trajectory_waypoints(case)
    duration = float(case["duration_s"])
    times = {0.0, duration}
    for start, end in zip(waypoints[:-1], waypoints[1:], strict=True):
        times.add(float(start.time_s))
        times.add(float(end.time_s))
        times.add(0.5 * (float(start.time_s) + float(end.time_s)))
    sample_times = sorted(times)
    samples = []
    for time_s in sample_times:
        q, dq, ddq = trajectory_joint_reference(case, time_s)
        samples.append(
            {
                "time_s": time_s,
                "q_rad": q.tolist(),
                "dq_rad_s": dq.tolist(),
                "ddq_rad_s2": ddq.tolist(),
            }
        )
    for waypoint in waypoints:
        q, _, _ = trajectory_joint_reference(case, waypoint.time_s)
        np.testing.assert_allclose(
            q,
            np.radians(waypoint.q_deg),
            rtol=0.0,
            atol=1e-12,
        )
    start = trajectory_joint_reference(case, 0.0)
    end = trajectory_joint_reference(case, duration)
    np.testing.assert_allclose(start[0], end[0], rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(start[1], 0.0, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(start[2], 0.0, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(end[1], 0.0, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(end[2], 0.0, rtol=0.0, atol=1e-12)
    if not np.isclose(float(waypoints[-1].time_s), duration):
        raise RuntimeError("trajectory duration differs from final derived waypoint")
    return {
        "sample_definition": "all_derived_waypoints_and_segment_midpoints",
        "samples": samples,
        "reference_definition_sha256": _canonical_fingerprint(samples),
        "start_end_posture_equal": True,
        "start_end_derivatives_zero": True,
        "waypoint_values_match_preregistered_definition": True,
    }


def _trace_is_finite(trace: dict[str, np.ndarray]) -> bool:
    for value in trace.values():
        array = np.asarray(value)
        if np.issubdtype(array.dtype, np.number) and not np.all(np.isfinite(array)):
            return False
    return True


def _promotions_follow_qualification(summary: dict[str, Any]) -> bool:
    trust = summary["hierarchical_trust"]
    applied_qualifications = [
        item for item in trust["qualifications"] if item["applied_to_control"]
    ]
    qualifications = {
        int(item["challenger_index"]): float(item["qualification_time_s"])
        for item in applied_qualifications
    }
    promotions = trust["control_promotions"]
    if len(qualifications) != len(applied_qualifications):
        return False
    for promotion in promotions:
        challenger_index = int(promotion["challenger_index"])
        qualification_time_s = qualifications.get(challenger_index)
        if qualification_time_s is None:
            return False
        if float(promotion["promotion_time_s"]) < qualification_time_s - 1e-12:
            return False
    return True


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# Trajectory paired A/B: {payload['trajectory']['trajectory_id']}",
        "",
        f"Evidence category: `{payload['evidence_category']}`.",
        "",
        (
            "This is structural smoke only. Scientific interpretation is prohibited."
            if payload["provenance"]["structural_smoke"]
            else "Formal user-run evidence; scientific review is still required."
        ),
        "",
        f"Preregistered runtime: {payload['trajectory']['preregistered_runtime_limit_s']} s; "
        f"executed smoke duration: {payload['provenance']['executed_wall_time_limit_s']} s.",
        "",
        "| arm | termination | finite trace | promotions |",
        "|---|---|:---:|---:|",
    ]
    for arm in ("prior_only", "trusted_adaptive"):
        record = payload["arms"][arm]
        lines.append(
            f"| {arm} | {record['termination_reason']} | "
            f"{record['finite_trace']} | {record['control_promotion_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _finalize_trajectory_outputs(
    *,
    trajectory_config: Path,
    case: dict[str, Any],
    suite: dict[str, Any],
    patient_record: dict[str, Any],
    trajectory_output_dir: Path,
    comparison: dict[str, Any],
    summaries: dict[str, dict[str, Any]],
    traces: dict[str, dict[str, np.ndarray]],
    structural_smoke: bool,
    executed_wall_time_limit_s: float,
    postprocessing_mode: str,
    recovered_input_sha256: dict[str, str] | None = None,
) -> dict[str, Any]:
    trajectory_id = str(case["trajectory_id"])
    reference_duration_s = float(case["duration_s"])
    formal_runtime_limit_s = preregistered_runtime_limit_s(case)
    evidence_category = (
        SMOKE_EVIDENCE_CATEGORY if structural_smoke else FORMAL_EVIDENCE_CATEGORY
    )
    registered = comparison["registered_configuration"]
    expected_fields = {
        "sensor_case": REGISTERED_SENSOR_CASE,
        "measurement_seed": REGISTERED_MEASUREMENT_SEED,
        "mpc_seed": REGISTERED_MPC_SEED,
        "wall_time_limit_s": executed_wall_time_limit_s,
        "reference_phase_duration_s": reference_duration_s,
        "human": REGISTERED_PATIENT_ID,
        "trajectory": trajectory_id,
    }
    for field, expected in expected_fields.items():
        if registered[field] != expected:
            raise RuntimeError(
                f"paired runner configuration mismatch at {field}: "
                f"{registered[field]!r} != {expected!r}"
            )

    isolation = verify_case_pair_isolation(
        comparison, summaries, traces, patient_record
    )
    controller_fingerprint, controller_payload = _runtime_controller_fingerprint(
        comparison
    )
    prior_beta = nominal_base_parameters()
    if not np.allclose(
        traces["prior_only"]["dynamic_base_estimate"],
        prior_beta,
        rtol=0.0,
        atol=1e-12,
    ):
        raise RuntimeError("prior-only arm applied a patient-specific beta")
    if not all(_trace_is_finite(trace) for trace in traces.values()):
        raise RuntimeError("nonfinite value in trajectory trace")
    if not _promotions_follow_qualification(summaries["trusted_adaptive"]):
        raise RuntimeError("trusted-adaptive promotion preceded qualification")

    trajectory_config_sha256 = _sha256_bytes(trajectory_config.read_bytes())
    trajectory_case_sha256 = _canonical_fingerprint(case)
    repo_root = Path(__file__).resolve().parents[3]
    provenance = {
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": BASELINE_COMMIT,
        "trajectory_id": trajectory_id,
        "trajectory_duration_s": reference_duration_s,
        "trajectory_config_path": str(trajectory_config.resolve()),
        "trajectory_config_sha256": trajectory_config_sha256,
        "trajectory_case_sha256": trajectory_case_sha256,
        "trajectory_config_schema": suite["schema_version"],
        "preregistered_trajectory_count": len(suite["cases"]),
        "patient_id": REGISTERED_PATIENT_ID,
        "controller_fingerprint_sha256": controller_fingerprint,
        "controller_fingerprint_payload": controller_payload,
        "seeds": {
            "measurement": REGISTERED_MEASUREMENT_SEED,
            "mpc": REGISTERED_MPC_SEED,
        },
        "sensor_regime": REGISTERED_SENSOR_CASE,
        "preregistered_runtime_limit_s": formal_runtime_limit_s,
        "executed_wall_time_limit_s": executed_wall_time_limit_s,
        "runtime_rule": "trajectory_duration_s_plus_9.0_s",
        "evidence_category": evidence_category,
        "structural_smoke": structural_smoke,
        "estimator_trust_initialization": "fresh_per_arm_per_trajectory",
        "postprocessing_mode": postprocessing_mode,
        **_git_provenance(repo_root),
    }
    if recovered_input_sha256 is not None:
        provenance["recovered_input_sha256"] = recovered_input_sha256

    arms: dict[str, Any] = {}
    for arm in ("prior_only", "trusted_adaptive"):
        trust = summaries[arm]["hierarchical_trust"]
        arm_provenance = {
            "trajectory_id": trajectory_id,
            "trajectory_duration_s": reference_duration_s,
            "trajectory_config_sha256": trajectory_config_sha256,
            "patient_id": REGISTERED_PATIENT_ID,
            "controller_fingerprint_sha256": controller_fingerprint,
            "seeds": provenance["seeds"],
            "sensor_regime": REGISTERED_SENSOR_CASE,
            "preregistered_runtime_limit_s": formal_runtime_limit_s,
            "executed_wall_time_limit_s": executed_wall_time_limit_s,
            "arm": arm,
            "evidence_category": evidence_category,
            "postprocessing_mode": postprocessing_mode,
        }
        summaries[arm]["evidence_category"] = evidence_category
        summaries[arm]["trajectory_excitation_provenance"] = arm_provenance
        arms[arm] = {
            "provenance": arm_provenance,
            "termination_reason": summaries[arm]["termination_reason"],
            "mechanically_completed_requested_duration": summaries[arm][
                "mechanically_completed_requested_duration"
            ],
            "finite_trace": True,
            "control_promotion_count": int(trust["counts"]["control_promotions"]),
            "qualified_count": int(trust["counts"]["qualified"]),
            "trusted_adaptation_entered_control": bool(
                trust["counts"]["control_promotions"]
            ),
            "initial_control_beta": traces[arm]["dynamic_base_estimate"][0].tolist(),
            "final_control_beta": traces[arm]["dynamic_base_estimate"][-1].tolist(),
            "promotion_only_after_valid_qualification": (
                _promotions_follow_qualification(summaries[arm])
            ),
        }

    result = _strict_json(
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "evidence_category": evidence_category,
            "scientific_interpretation_permitted": not structural_smoke,
            "trajectory": {
                "trajectory_id": trajectory_id,
                "construction": case["construction"],
                "trajectory_duration_s": reference_duration_s,
                "preregistered_runtime_limit_s": formal_runtime_limit_s,
                "runtime_rule": "trajectory_duration_s_plus_9.0_s",
            },
            "patient": {
                "patient_id": REGISTERED_PATIENT_ID,
                "case_record": patient_record,
            },
            "provenance": provenance,
            "reference_validation": _reference_validation(case),
            "registered_configuration": registered,
            "ab_isolation": isolation,
            "arms": arms,
            "comparison": comparison["trusted_adaptive_minus_prior_only"],
        }
    )

    trajectory_output_dir.mkdir(parents=True, exist_ok=True)
    for arm in ("prior_only", "trusted_adaptive"):
        (trajectory_output_dir / f"{arm}.json").write_text(
            json.dumps(
                _strict_json(summaries[arm]),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    (trajectory_output_dir / "comparison_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(trajectory_output_dir / "comparison_summary.md", result)
    if structural_smoke:
        (trajectory_output_dir / SMOKE_MARKER).write_text(
            "structural smoke only; scientific interpretation prohibited\n",
            encoding="utf-8",
        )
    return result


def run_selected_trajectory(
    *,
    trajectory_config: Path,
    trajectory_id: str,
    patient_config: Path,
    output_root: Path,
    smoke_duration_s: float | None = None,
) -> dict[str, Any]:
    structural_smoke = smoke_duration_s is not None
    if structural_smoke and not 0.0 < float(smoke_duration_s) <= 0.5:
        raise ValueError("structural smoke duration must lie in (0, 0.5] seconds")

    case, suite = select_trajectory(trajectory_config, trajectory_id)
    trajectory_output_dir = output_root / trajectory_id
    if trajectory_output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {trajectory_output_dir}")

    patient_spec, _ = select_patient_case(patient_config, REGISTERED_PATIENT_ID)
    patient_record = patient_case_record(patient_spec)
    true_human = patient_spec.build_human()
    reference_duration_s = float(case["duration_s"])
    formal_runtime_limit_s = preregistered_runtime_limit_s(case)
    executed_wall_time_limit_s = (
        float(smoke_duration_s) if structural_smoke else formal_runtime_limit_s
    )
    evidence_category = (
        SMOKE_EVIDENCE_CATEGORY if structural_smoke else FORMAL_EVIDENCE_CATEGORY
    )
    waypoints = build_trajectory_waypoints(case)

    def selected_reference(time_s: float) -> Any:
        return trajectory_reference(case, time_s)

    true_metadata = {
        "case": REGISTERED_PATIENT_ID,
        "patient_case_id": REGISTERED_PATIENT_ID,
        "variation_spec": patient_record["variation_spec"],
        "raw_human_parameters": patient_record["raw_human_parameters"],
    }
    comparison, summaries, traces = run_paired_ab(
        trajectory_output_dir,
        sensor_case_name=REGISTERED_SENSOR_CASE,
        measurement_seed=REGISTERED_MEASUREMENT_SEED,
        true_human=true_human,
        true_metadata=true_metadata,
        human_label=REGISTERED_PATIENT_ID,
        wall_time_limit_s=executed_wall_time_limit_s,
        evidence_category=evidence_category,
        write_comparison_outputs=False,
        reference_fn=selected_reference,
        reference_phase_duration_s=reference_duration_s,
        trajectory_label=trajectory_id,
        trajectory_waypoints=waypoints,
    )
    return _finalize_trajectory_outputs(
        trajectory_config=trajectory_config,
        case=case,
        suite=suite,
        patient_record=patient_record,
        trajectory_output_dir=trajectory_output_dir,
        comparison=comparison,
        summaries=summaries,
        traces=traces,
        structural_smoke=structural_smoke,
        executed_wall_time_limit_s=executed_wall_time_limit_s,
        postprocessing_mode="fresh_run",
    )


def finalize_saved_trajectory(
    *,
    trajectory_config: Path,
    trajectory_id: str,
    patient_config: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Finish postprocessing from complete saved arms without rerunning control."""

    case, suite = select_trajectory(trajectory_config, trajectory_id)
    trajectory_output_dir = output_root / trajectory_id
    if not trajectory_output_dir.is_dir():
        raise FileNotFoundError(
            f"saved trajectory directory does not exist: {trajectory_output_dir}"
        )
    if (trajectory_output_dir / SMOKE_MARKER).exists():
        raise RuntimeError("formal recovery refuses a structural-smoke directory")
    for filename in ("comparison_summary.json", "comparison_summary.md"):
        if (trajectory_output_dir / filename).exists():
            raise FileExistsError(
                f"refusing to overwrite completed output {trajectory_output_dir / filename}"
            )

    required_files = tuple(
        filename
        for arm in ("prior_only", "trusted_adaptive")
        for filename in (f"{arm}.json", f"{arm}_trace.npz")
    )
    missing = [
        filename
        for filename in required_files
        if not (trajectory_output_dir / filename).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"incomplete saved trajectory outputs: {missing}")
    recovered_input_sha256 = {
        filename: _sha256_bytes((trajectory_output_dir / filename).read_bytes())
        for filename in required_files
    }

    summaries = {
        arm: json.loads(
            (trajectory_output_dir / f"{arm}.json").read_text(encoding="utf-8")
        )
        for arm in ("prior_only", "trusted_adaptive")
    }
    traces: dict[str, dict[str, np.ndarray]] = {}
    for arm in ("prior_only", "trusted_adaptive"):
        with np.load(
            trajectory_output_dir / f"{arm}_trace.npz", allow_pickle=False
        ) as stored:
            traces[arm] = {key: stored[key] for key in stored.files}

    formal_runtime_limit_s = preregistered_runtime_limit_s(case)
    for arm, summary in summaries.items():
        expected = {
            "case": arm,
            "trajectory": trajectory_id,
            "requested_duration_s": formal_runtime_limit_s,
            "true_human_case": REGISTERED_PATIENT_ID,
            "evidence_category": RAW_ARM_EVIDENCE_CATEGORY,
        }
        for field, value in expected.items():
            if summary.get(field) != value:
                raise RuntimeError(
                    f"saved {arm} summary mismatch at {field}: "
                    f"{summary.get(field)!r} != {value!r}"
                )

    patient_spec, _ = select_patient_case(patient_config, REGISTERED_PATIENT_ID)
    patient_record = patient_case_record(patient_spec)
    true_human = patient_spec.build_human()
    comparison = build_paired_ab_comparison(
        summaries,
        traces,
        sensor_case_name=REGISTERED_SENSOR_CASE,
        measurement_seed=REGISTERED_MEASUREMENT_SEED,
        true_human=true_human,
        human_label=REGISTERED_PATIENT_ID,
        wall_time_limit_s=formal_runtime_limit_s,
        evidence_category=FORMAL_EVIDENCE_CATEGORY,
        reference_phase_duration_s=float(case["duration_s"]),
        trajectory_label=trajectory_id,
    )
    return _finalize_trajectory_outputs(
        trajectory_config=trajectory_config,
        case=case,
        suite=suite,
        patient_record=patient_record,
        trajectory_output_dir=trajectory_output_dir,
        comparison=comparison,
        summaries=summaries,
        traces=traces,
        structural_smoke=False,
        executed_wall_time_limit_s=formal_runtime_limit_s,
        postprocessing_mode="saved_outputs_recovery_no_rerun",
        recovered_input_sha256=recovered_input_sha256,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trajectory-config", type=Path, default=DEFAULT_TRAJECTORY_CONFIG
    )
    parser.add_argument("--trajectory-id", required=True)
    parser.add_argument("--patient-config", type=Path, default=DEFAULT_PATIENT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--smoke-duration-s", type=float)
    parser.add_argument("--finalize-existing", action="store_true")
    args = parser.parse_args()
    if args.finalize_existing:
        if args.smoke_duration_s is not None:
            raise ValueError("saved-output recovery cannot be combined with smoke")
        finalize_saved_trajectory(
            trajectory_config=args.trajectory_config,
            trajectory_id=args.trajectory_id,
            patient_config=args.patient_config,
            output_root=args.output_dir,
        )
        return
    run_selected_trajectory(
        trajectory_config=args.trajectory_config,
        trajectory_id=args.trajectory_id,
        patient_config=args.patient_config,
        output_root=args.output_dir,
        smoke_duration_s=args.smoke_duration_s,
    )


if __name__ == "__main__":
    main()
