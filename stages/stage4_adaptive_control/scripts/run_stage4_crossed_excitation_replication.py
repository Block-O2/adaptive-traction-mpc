#!/usr/bin/env python3
"""Run or resolve one preregistered Stage-4 crossed-replication pair.

Formal execution remains user-only. Reused cells are hash/provenance verified
and returned as read-only evidence references; they can never enter the paired
execution path. ``--smoke-duration-s`` is structural and non-scientific.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, CONTROL_SUBSTEPS, SIMULATION_DT_S
from traction_mpc_stage4.artifact_paths import resolve_stage_artifact
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.patient_mismatch import patient_case_record
from traction_mpc_stage4.trajectory_excitation import trajectory_reference, trajectory_waypoints

try:
    from .run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        _canonical_fingerprint,
        _git_provenance,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from .run_stage4_single_challenger_closed_loop_ab import run_paired_ab
    from .run_stage4_trajectory_excitation_generalization import (
        _promotions_follow_qualification,
        _reference_validation,
        _trace_is_finite,
        select_trajectory,
    )
except ImportError:  # Direct execution from scripts/.
    from run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        _canonical_fingerprint,
        _git_provenance,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from run_stage4_single_challenger_closed_loop_ab import run_paired_ab
    from run_stage4_trajectory_excitation_generalization import (
        _promotions_follow_qualification,
        _reference_validation,
        _trace_is_finite,
        select_trajectory,
    )


SCHEMA_VERSION = "stage4_crossed_excitation_replication_pair_v1"
REUSED_SCHEMA_VERSION = "stage4_crossed_excitation_reused_evidence_v1"
MATRIX_SCHEMA_VERSION = "stage4_crossed_excitation_replication_v1"
SMOKE_EVIDENCE_CATEGORY = (
    "crossed_excitation_replication_structural_smoke_non_scientific"
)
FORMAL_EVIDENCE_CATEGORY = "formal_user_run_unreviewed"
REGISTERED_SENSOR_CASE = "noise_bias_drift_200hz"
REGISTERED_MPC_SEED = 20260824
SMOKE_MARKER = ".stage4_crossed_excitation_replication_structural_smoke"
DEFAULT_MATRIX_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_crossed_excitation_replication.json"
)
DEFAULT_PATIENT_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_patient_mismatch_cases.json"
)
DEFAULT_TRAJECTORY_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_trajectory_excitation_suite.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_stage_path(stage_root: Path, configured_path: str) -> Path:
    return resolve_stage_artifact(stage_root, configured_path)


def load_crossed_replication_matrix(matrix_config: Path) -> dict[str, Any]:
    """Load and mechanically validate the frozen 18-cell matrix."""

    matrix = json.loads(matrix_config.read_text(encoding="utf-8"))
    if matrix.get("schema_version") != MATRIX_SCHEMA_VERSION:
        raise ValueError("unexpected crossed-replication matrix schema")
    cases = matrix.get("cases", [])
    if len(cases) != 18 or len({item["case_id"] for item in cases}) != 18:
        raise ValueError("crossed-replication matrix must contain 18 unique pairs")
    sources = Counter(item["execution_source"] for item in cases)
    if sources != Counter(
        {"new_formal_run": 16, "read_only_existing_formal_bridge": 2}
    ):
        raise ValueError("crossed-replication new/reused classification drifted")
    if len({(x["patient_id"], x["trajectory_id"], x["measurement_seed"]) for x in cases}) != 18:
        raise ValueError("crossed-replication factor combinations must be unique")
    if any(float(item["duration_s"]) != 23.0 for item in cases):
        raise ValueError("crossed-replication trajectory duration drifted")
    if any(float(item["wall_time_limit_s"]) != 32.0 for item in cases):
        raise ValueError("crossed-replication runtime mapping drifted")

    stage_root = Path(__file__).resolve().parents[1]
    for source_name in (
        "patient_config",
        "trajectory_config",
        "offline_excitation_audit",
    ):
        source = matrix["source_contracts"][source_name]
        path = _resolve_stage_path(stage_root, source["path"])
        if _sha256(path) != source["sha256"]:
            raise RuntimeError(f"frozen source hash mismatch: {source_name}")
    return matrix


def select_crossed_case(
    matrix_config: Path, case_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    matrix = load_crossed_replication_matrix(matrix_config)
    matches = [item for item in matrix["cases"] if item["case_id"] == case_id]
    if len(matches) != 1:
        available = ", ".join(item["case_id"] for item in matrix["cases"])
        raise ValueError(f"unknown crossed-replication case {case_id!r}; available: {available}")
    return deepcopy(matches[0]), matrix


def output_path_for_case(output_root: Path, case: dict[str, Any]) -> Path:
    return output_root / str(case["case_id"])


def _verify_reused_summary_provenance(
    summary: dict[str, Any], case: dict[str, Any], matrix: dict[str, Any]
) -> None:
    provenance = summary["provenance"]
    expected = {
        "baseline_tag": matrix["source_contracts"]["baseline_tag"],
        "baseline_commit": matrix["source_contracts"]["baseline_commit"],
        "trajectory_id": case["trajectory_id"],
        "trajectory_duration_s": case["duration_s"],
        "trajectory_config_sha256": matrix["source_contracts"][
            "trajectory_config"
        ]["sha256"],
        "patient_id": case["patient_id"],
        "sensor_regime": matrix["fixed_contract"]["sensor_regime"],
        "preregistered_runtime_limit_s": case["wall_time_limit_s"],
        "evidence_category": FORMAL_EVIDENCE_CATEGORY,
        "structural_smoke": False,
    }
    for field, expected_value in expected.items():
        if provenance.get(field) != expected_value:
            raise RuntimeError(
                f"reused evidence provenance mismatch at {field}: "
                f"{provenance.get(field)!r} != {expected_value!r}"
            )
    if provenance.get("seeds") != {
        "measurement": case["measurement_seed"],
        "mpc": matrix["fixed_contract"]["mpc_seed"],
    }:
        raise RuntimeError("reused evidence seed provenance mismatch")
    registered = summary["registered_configuration"]
    registered_expected = {
        "human": case["patient_id"],
        "trajectory": case["trajectory_id"],
        "measurement_seed": case["measurement_seed"],
        "mpc_seed": matrix["fixed_contract"]["mpc_seed"],
        "sensor_case": matrix["fixed_contract"]["sensor_regime"],
        "wall_time_limit_s": case["wall_time_limit_s"],
        "reference_phase_duration_s": case["duration_s"],
    }
    for field, expected_value in registered_expected.items():
        if registered.get(field) != expected_value:
            raise RuntimeError(f"reused registered configuration mismatch at {field}")
    if summary.get("evidence_category") != FORMAL_EVIDENCE_CATEGORY:
        raise RuntimeError("reused evidence category mismatch")


def verify_reused_evidence(
    matrix_config: Path, case_id: str
) -> dict[str, Any]:
    """Verify and expose one preregistered read-only bridge without writing."""

    case, matrix = select_crossed_case(matrix_config, case_id)
    if case["execution_source"] != "read_only_existing_formal_bridge":
        raise ValueError(f"case {case_id!r} is not preregistered reused evidence")
    stage_root = Path(__file__).resolve().parents[1]
    source_dir = _resolve_stage_path(stage_root, case["source_result_directory"])
    registered_hashes = matrix["read_only_bridge_artifact_hashes"][case_id]
    observed_hashes: dict[str, str] = {}
    for filename, expected_hash in registered_hashes.items():
        path = source_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing reused evidence artifact {path}")
        observed_hashes[filename] = _sha256(path)
        if observed_hashes[filename] != expected_hash:
            raise RuntimeError(f"reused evidence hash mismatch: {path}")

    summary = json.loads(
        (source_dir / "comparison_summary.json").read_text(encoding="utf-8")
    )
    _verify_reused_summary_provenance(summary, case, matrix)
    finite_traces = True
    for arm in ("prior_only", "trusted_adaptive"):
        raw = json.loads((source_dir / f"{arm}.json").read_text(encoding="utf-8"))
        arm_provenance = raw.get("trajectory_excitation_provenance", {})
        if raw.get("case") != arm:
            raise RuntimeError(f"reused {arm} arm label mismatch")
        if raw.get("true_human_case") != case["patient_id"]:
            raise RuntimeError(f"reused {arm} patient label mismatch")
        if raw.get("trajectory") != case["trajectory_id"]:
            raise RuntimeError(f"reused {arm} trajectory label mismatch")
        if arm_provenance.get("seeds") != summary["provenance"]["seeds"]:
            raise RuntimeError(f"reused {arm} seed provenance mismatch")
        with np.load(source_dir / f"{arm}_trace.npz", allow_pickle=False) as stored:
            for key in stored.files:
                value = np.asarray(stored[key])
                if np.issubdtype(value.dtype, np.number) and not np.all(
                    np.isfinite(value)
                ):
                    finite_traces = False
    if not finite_traces:
        raise RuntimeError("reused evidence contains nonfinite trace values")
    return {
        "schema_version": REUSED_SCHEMA_VERSION,
        "case_id": case_id,
        "patient_id": case["patient_id"],
        "trajectory_id": case["trajectory_id"],
        "measurement_seed": case["measurement_seed"],
        "execution_source": "read_only_existing_formal_bridge",
        "reused_vs_newly_executed": "reused_read_only",
        "source_result_directory": str(source_dir.resolve()),
        "artifact_hashes_verified": True,
        "config_and_provenance_verified": True,
        "finite_traces_verified": True,
        "artifacts_sha256": observed_hashes,
        "matrix_config_sha256": _sha256(matrix_config),
        "patient_config_sha256": matrix["source_contracts"]["patient_config"][
            "sha256"
        ],
        "trajectory_config_sha256": matrix["source_contracts"][
            "trajectory_config"
        ]["sha256"],
        "controller_fingerprint": summary["provenance"][
            "controller_fingerprint_sha256"
        ],
        "baseline_tag": matrix["source_contracts"]["baseline_tag"],
        "baseline_commit": matrix["source_contracts"]["baseline_commit"],
        "evidence_category": FORMAL_EVIDENCE_CATEGORY,
        "executed_by_crossed_runner": False,
    }


def analysis_matrix_entries(
    matrix_config: Path, new_output_root: Path
) -> list[dict[str, Any]]:
    """Resolve all future aggregate inputs without executing a rollout."""

    matrix = load_crossed_replication_matrix(matrix_config)
    entries = []
    for case in matrix["cases"]:
        if case["execution_source"] == "read_only_existing_formal_bridge":
            entries.append(verify_reused_evidence(matrix_config, case["case_id"]))
        else:
            entries.append(
                {
                    "case_id": case["case_id"],
                    "patient_id": case["patient_id"],
                    "trajectory_id": case["trajectory_id"],
                    "measurement_seed": case["measurement_seed"],
                    "execution_source": "new_formal_run",
                    "reused_vs_newly_executed": "new_execution_required",
                    "expected_result_directory": str(
                        output_path_for_case(new_output_root, case).resolve()
                    ),
                }
            )
    return entries


def _frozen_controller_fingerprint(
    comparison: dict[str, Any], measurement_seed: int
) -> tuple[str, dict[str, Any]]:
    registered = comparison["registered_configuration"]
    measurement_model = deepcopy(registered["measurement_model"])
    runtime_seed = measurement_model.pop("random_seed")
    if runtime_seed != measurement_seed:
        raise RuntimeError("runtime measurement seed differs from selected matrix seed")
    payload = {
        "sensor_definition_without_allowed_seed": measurement_model,
        "measurement_routing": registered["measurement_routing"],
        "mpc_objective_contract": registered["mpc_objective_contract"],
        "confidence_pacing_config": registered["confidence_pacing_config"],
        "statistical_trust_config": registered["statistical_trust_config"],
        "estimator": registered["estimator"],
        "trust": registered["trust"],
        "allocator": registered["allocator"],
        "confidence_pacing": registered["confidence_pacing"],
        "mpc_controller_safety_changed": registered[
            "mpc_controller_safety_changed"
        ],
        "mpc_seed": registered["mpc_seed"],
        "plant_integrator": {
            "simulation_dt_s": SIMULATION_DT_S,
            "control_dt_s": CONTROL_DT_S,
            "control_substeps": CONTROL_SUBSTEPS,
        },
        "allowed_crossed_factors_excluded": [
            "patient_id",
            "trajectory_id",
            "measurement_seed",
        ],
        "smoke_or_formal_runtime_envelope_excluded": True,
    }
    return _canonical_fingerprint(payload), payload


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        f"# Crossed replication pair: {result['case_id']}",
        "",
        f"Evidence category: `{result['evidence_category']}`.",
        "",
        (
            "Structural smoke only; scientific interpretation is prohibited."
            if result["provenance"]["structural_smoke"]
            else "Formal user-run evidence; aggregate scientific review remains required."
        ),
        "",
        "| arm | termination | finite | qualifications | promotions | rejections |",
        "|---|---|:---:|---:|---:|---:|",
    ]
    for arm in ("prior_only", "trusted_adaptive"):
        item = result["arms"][arm]
        lines.append(
            f"| {arm} | {item['termination_reason']} | {item['finite_trace']} | "
            f"{item['qualification_count']} | {item['promotion_count']} | "
            f"{item['rejection_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_selected_crossed_case(
    *,
    matrix_config: Path,
    case_id: str,
    patient_config: Path,
    trajectory_config: Path,
    output_root: Path,
    smoke_duration_s: float | None = None,
) -> dict[str, Any]:
    """Run one new cell or verify one reused cell without executing it."""

    case, matrix = select_crossed_case(matrix_config, case_id)
    if case["execution_source"] == "read_only_existing_formal_bridge":
        return verify_reused_evidence(matrix_config, case_id)

    structural_smoke = smoke_duration_s is not None
    if structural_smoke and not 0.0 < float(smoke_duration_s) <= 0.5:
        raise ValueError("structural smoke duration must lie in (0, 0.5] seconds")
    case_output_dir = output_path_for_case(output_root, case)
    if case_output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {case_output_dir}")

    patient_spec, _ = select_patient_case(patient_config, case["patient_id"])
    patient_record = patient_case_record(patient_spec)
    trajectory, _ = select_trajectory(trajectory_config, case["trajectory_id"])
    if float(trajectory["duration_s"]) != float(case["duration_s"]):
        raise RuntimeError("matrix and frozen trajectory duration differ")
    if float(case["wall_time_limit_s"]) != float(case["duration_s"]) + 9.0:
        raise RuntimeError("matrix runtime no longer follows duration plus 9 seconds")
    if _sha256(patient_config) != matrix["source_contracts"]["patient_config"][
        "sha256"
    ]:
        raise RuntimeError("patient config hash differs from frozen matrix")
    if _sha256(trajectory_config) != matrix["source_contracts"][
        "trajectory_config"
    ]["sha256"]:
        raise RuntimeError("trajectory config hash differs from frozen matrix")

    true_human = patient_spec.build_human()
    patient_metadata = {
        "case": case["patient_id"],
        "patient_case_id": case["patient_id"],
        "variation_spec": patient_record["variation_spec"],
        "raw_human_parameters": patient_record["raw_human_parameters"],
        "crossed_replication_case_id": case_id,
    }

    def selected_reference(time_s: float) -> Any:
        return trajectory_reference(trajectory, time_s)

    executed_wall_time_limit_s = (
        float(smoke_duration_s)
        if structural_smoke
        else float(case["wall_time_limit_s"])
    )
    evidence_category = (
        SMOKE_EVIDENCE_CATEGORY if structural_smoke else FORMAL_EVIDENCE_CATEGORY
    )
    execution_source = (
        "structural_smoke_fresh_run" if structural_smoke else "new_formal_run"
    )
    comparison, summaries, traces = run_paired_ab(
        case_output_dir,
        sensor_case_name=matrix["fixed_contract"]["sensor_regime"],
        measurement_seed=int(case["measurement_seed"]),
        true_human=true_human,
        true_metadata=patient_metadata,
        human_label=case["patient_id"],
        wall_time_limit_s=executed_wall_time_limit_s,
        evidence_category=evidence_category,
        write_comparison_outputs=False,
        reference_fn=selected_reference,
        reference_phase_duration_s=float(case["duration_s"]),
        trajectory_label=case["trajectory_id"],
        trajectory_waypoints=trajectory_waypoints(trajectory),
    )

    registered = comparison["registered_configuration"]
    expected_registered = {
        "sensor_case": REGISTERED_SENSOR_CASE,
        "measurement_seed": case["measurement_seed"],
        "mpc_seed": REGISTERED_MPC_SEED,
        "wall_time_limit_s": executed_wall_time_limit_s,
        "reference_phase_duration_s": case["duration_s"],
        "human": case["patient_id"],
        "trajectory": case["trajectory_id"],
    }
    for field, expected in expected_registered.items():
        if registered.get(field) != expected:
            raise RuntimeError(
                f"paired runner crossed-factor mismatch at {field}: "
                f"{registered.get(field)!r} != {expected!r}"
            )

    isolation = verify_case_pair_isolation(
        comparison, summaries, traces, patient_record
    )
    if not all(_trace_is_finite(trace) for trace in traces.values()):
        raise RuntimeError("nonfinite value in crossed-replication trace")
    for arm in ("prior_only", "trusted_adaptive"):
        if not _promotions_follow_qualification(summaries[arm]):
            raise RuntimeError(f"{arm} promotion preceded qualification")
    population_prior = nominal_base_parameters()
    for arm in ("prior_only", "trusted_adaptive"):
        np.testing.assert_allclose(
            traces[arm]["dynamic_base_estimate"][0],
            population_prior,
            rtol=0.0,
            atol=1e-12,
        )

    controller_fingerprint, controller_payload = _frozen_controller_fingerprint(
        comparison, int(case["measurement_seed"])
    )
    matrix_hash = _sha256(matrix_config)
    patient_hash = _sha256(patient_config)
    trajectory_hash = _sha256(trajectory_config)
    reference_validation = _reference_validation(trajectory)
    repo_root = Path(__file__).resolve().parents[3]
    provenance = {
        "patient_id": case["patient_id"],
        "trajectory_id": case["trajectory_id"],
        "measurement_seed": case["measurement_seed"],
        "mpc_seed": REGISTERED_MPC_SEED,
        "sensor_regime": REGISTERED_SENSOR_CASE,
        "matrix_config_path": str(matrix_config.resolve()),
        "matrix_config_sha256": matrix_hash,
        "patient_config_path": str(patient_config.resolve()),
        "patient_config_sha256": patient_hash,
        "trajectory_config_path": str(trajectory_config.resolve()),
        "trajectory_config_sha256": trajectory_hash,
        "controller_fingerprint_sha256": controller_fingerprint,
        "controller_fingerprint_payload": controller_payload,
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": BASELINE_COMMIT,
        "evidence_category": evidence_category,
        "matrix_execution_class": case["execution_source"],
        "execution_source": execution_source,
        "reused_vs_newly_executed": "newly_executed",
        "preregistered_runtime_limit_s": case["wall_time_limit_s"],
        "executed_wall_time_limit_s": executed_wall_time_limit_s,
        "runtime_rule": "trajectory_duration_s_plus_9.0_s",
        "structural_smoke": structural_smoke,
        "fresh_state_semantics": "fresh_per_arm_per_crossed_case",
        **_git_provenance(repo_root),
    }
    arms: dict[str, Any] = {}
    for arm in ("prior_only", "trusted_adaptive"):
        trust = summaries[arm]["hierarchical_trust"]
        arm_provenance = {
            "patient_id": case["patient_id"],
            "trajectory_id": case["trajectory_id"],
            "measurement_seed": case["measurement_seed"],
            "matrix_config_sha256": matrix_hash,
            "patient_config_sha256": patient_hash,
            "trajectory_config_sha256": trajectory_hash,
            "controller_fingerprint_sha256": controller_fingerprint,
            "baseline_tag": BASELINE_TAG,
            "baseline_commit": BASELINE_COMMIT,
            "arm": arm,
            "evidence_category": evidence_category,
            "matrix_execution_class": case["execution_source"],
            "execution_source": execution_source,
            "reused_vs_newly_executed": "newly_executed",
        }
        summaries[arm]["evidence_category"] = evidence_category
        summaries[arm]["crossed_replication_provenance"] = arm_provenance
        counts = trust["counts"]
        arms[arm] = {
            "provenance": arm_provenance,
            "termination_reason": summaries[arm]["termination_reason"],
            "finite_trace": True,
            "initial_control_beta": traces[arm]["dynamic_base_estimate"][0].tolist(),
            "final_control_beta": traces[arm]["dynamic_base_estimate"][-1].tolist(),
            "qualification_count": int(counts["qualified"]),
            "promotion_count": int(counts["control_promotions"]),
            "rejection_count": int(counts["rejected"]),
            "pending_count": int(counts["pending"]),
            "promotion_only_after_valid_qualification": True,
        }
    result = _strict_json(
        {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "evidence_category": evidence_category,
            "scientific_interpretation_permitted": not structural_smoke,
            "matrix_case": case,
            "patient": patient_record,
            "trajectory": trajectory,
            "provenance": provenance,
            "reference_validation": reference_validation,
            "registered_configuration": registered,
            "ab_isolation": isolation,
            "fresh_state_validation": {
                "initial_control_beta_population_prior": True,
                "new_reference_execution_layer_per_arm": True,
                "new_estimator_factory_per_arm": True,
                "no_estimator_trust_or_pacing_object_accepted_from_another_case": True,
            },
            "arms": arms,
            "comparison": comparison["trusted_adaptive_minus_prior_only"],
        }
    )
    case_output_dir.mkdir(parents=True, exist_ok=True)
    for arm in ("prior_only", "trusted_adaptive"):
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
    (case_output_dir / "comparison_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(case_output_dir / "comparison_summary.md", result)
    if structural_smoke:
        (case_output_dir / SMOKE_MARKER).write_text(
            "structural smoke only; scientific interpretation prohibited\n",
            encoding="utf-8",
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-config", type=Path, default=DEFAULT_MATRIX_CONFIG)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--patient-config", type=Path, default=DEFAULT_PATIENT_CONFIG)
    parser.add_argument(
        "--trajectory-config", type=Path, default=DEFAULT_TRAJECTORY_CONFIG
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--smoke-duration-s", type=float)
    args = parser.parse_args()
    result = run_selected_crossed_case(
        matrix_config=args.matrix_config,
        case_id=args.case_id,
        patient_config=args.patient_config,
        trajectory_config=args.trajectory_config,
        output_root=args.output_dir,
        smoke_duration_s=args.smoke_duration_s,
    )
    if result["schema_version"] == REUSED_SCHEMA_VERSION:
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
