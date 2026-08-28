#!/usr/bin/env python3
"""Run the preregistered nominal-only Stage-4 sensor decomposition."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.measurement import measurement_case_dict, sensor_realism_cases
from traction_mpc_stage4.patient_mismatch import patient_case_record

try:
    from .run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        FORMAL_EVIDENCE_CATEGORY,
        _canonical_fingerprint,
        _git_provenance,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from .run_stage4_single_challenger_closed_loop_ab import run_paired_ab
except ImportError:  # Direct execution from the scripts directory.
    from run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        FORMAL_EVIDENCE_CATEGORY,
        _canonical_fingerprint,
        _git_provenance,
        _strict_json,
        select_patient_case,
        verify_case_pair_isolation,
    )
    from run_stage4_single_challenger_closed_loop_ab import run_paired_ab


SCHEMA_VERSION = "stage4_nominal_sensor_decomposition_v1"
REGISTERED_SENSOR_CASES = (
    "ideal_200hz",
    "noise_200hz",
    "noise_bias_drift_200hz",
)
REGISTERED_MEASUREMENT_SEED = 44104
REGISTERED_MPC_SEED = 20260824
REGISTERED_WALL_LIMIT_S = 32.0
REGISTERED_PATIENT_CASE = "nominal_reference"
REGISTERED_SPEC = Path("docs/research/STAGE4_NOMINAL_SENSOR_DECOMPOSITION_SPEC.md")
REGISTERED_PATIENT_CONFIG = Path("configs/stage4_patient_mismatch_cases.json")


EXPECTED_SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = {
    "ideal_200hz": {
        "name": "ideal_200hz",
        "update_rate_hz": 200.0,
        "latency_s": 0.0,
        "noise_std": {
            "robot_position_deg": 0.0,
            "robot_velocity_deg_s": 0.0,
            "cuff_position_mm": 0.0,
            "cuff_orientation_deg": 0.0,
            "force_n": 0.0,
            "moment_nm": 0.0,
        },
        "force_bias_n": [0.0, 0.0, 0.0],
        "force_bias_drift_n_s": [0.0, 0.0, 0.0],
        "moment_bias_nm": [0.0, 0.0, 0.0],
        "moment_bias_drift_nm_s": [0.0, 0.0, 0.0],
        "preprocessing_enabled": False,
        "random_seed": REGISTERED_MEASUREMENT_SEED,
        "actual_cr12_sensor_specification": False,
    },
    "noise_200hz": {
        "name": "noise_200hz",
        "update_rate_hz": 200.0,
        "latency_s": 0.0,
        "noise_std": {
            "robot_position_deg": 0.02,
            "robot_velocity_deg_s": 0.1,
            "cuff_position_mm": 0.3,
            "cuff_orientation_deg": 0.05,
            "force_n": 0.5,
            "moment_nm": 0.02,
        },
        "force_bias_n": [0.0, 0.0, 0.0],
        "force_bias_drift_n_s": [0.0, 0.0, 0.0],
        "moment_bias_nm": [0.0, 0.0, 0.0],
        "moment_bias_drift_nm_s": [0.0, 0.0, 0.0],
        "preprocessing_enabled": True,
        "random_seed": REGISTERED_MEASUREMENT_SEED,
        "actual_cr12_sensor_specification": False,
    },
    "noise_bias_drift_200hz": {
        "name": "noise_bias_drift_200hz",
        "update_rate_hz": 200.0,
        "latency_s": 0.0,
        "noise_std": {
            "robot_position_deg": 0.02,
            "robot_velocity_deg_s": 0.1,
            "cuff_position_mm": 0.3,
            "cuff_orientation_deg": 0.05,
            "force_n": 0.5,
            "moment_nm": 0.02,
        },
        "force_bias_n": [1.5, -1.0, 0.8],
        "force_bias_drift_n_s": [0.04, -0.03, 0.02],
        "moment_bias_nm": [0.03, -0.02, 0.015],
        "moment_bias_drift_nm_s": [0.001, -0.0008, 0.0006],
        "preprocessing_enabled": True,
        "random_seed": REGISTERED_MEASUREMENT_SEED,
        "actual_cr12_sensor_specification": False,
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def validate_preregistration(
    *, stage_root: Path, repo_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    cases = {item.name: item for item in sensor_realism_cases()}
    missing = set(REGISTERED_SENSOR_CASES) - set(cases)
    if missing:
        raise RuntimeError(f"missing preregistered sensor cases: {sorted(missing)}")
    observed = {
        name: measurement_case_dict(cases[name]) for name in REGISTERED_SENSOR_CASES
    }
    if observed != EXPECTED_SENSOR_DEFINITIONS:
        raise RuntimeError("existing sensor definitions differ from preregistration")

    tag_commit = _git(repo_root, "rev-list", "-n", "1", BASELINE_TAG)
    if tag_commit != BASELINE_COMMIT:
        raise RuntimeError(
            f"baseline tag resolves to {tag_commit}, expected {BASELINE_COMMIT}"
        )
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
        cwd=repo_root,
        check=False,
    )
    if ancestry.returncode != 0:
        raise RuntimeError("frozen baseline is not an ancestor of HEAD")

    selected, all_cases = select_patient_case(
        stage_root / REGISTERED_PATIENT_CONFIG, REGISTERED_PATIENT_CASE
    )
    true_human = selected.build_human()
    for field, nominal_value in asdict(HUMAN).items():
        try:
            np.testing.assert_array_equal(
                asdict(true_human)[field], nominal_value, err_msg=field
            )
        except AssertionError as error:
            raise RuntimeError(
                f"registered nominal patient differs from HUMAN at {field}"
            ) from error
    true_beta = nominal_base_parameters(true_human)
    prior_beta = nominal_base_parameters(HUMAN)
    np.testing.assert_allclose(true_beta, prior_beta, rtol=0.0, atol=0.0)
    record = patient_case_record(selected)
    if record["normalized_difference_from_prior"]["span_l2"] != 0.0:
        raise RuntimeError("nominal patient beta differs from population prior")
    return observed, {
        "record": record,
        "preregistered_patient_case_count": len(all_cases),
        "true_beta_equals_population_prior": True,
        "baseline_tag_resolves_to_expected_commit": True,
        "baseline_is_ancestor_of_head": True,
    }


def _controller_fingerprints(comparison: dict[str, Any]) -> dict[str, Any]:
    config = comparison["registered_configuration"]
    payload = {
        "arms": config["arms"],
        "sensor_case": config["sensor_case"],
        "measurement_model": config["measurement_model"],
        "measurement_routing": config["measurement_routing"],
        "mpc_objective_contract": config["mpc_objective_contract"],
        "confidence_pacing_config": config["confidence_pacing_config"],
        "statistical_trust_config": config["statistical_trust_config"],
        "estimator": config["estimator"],
        "trust": config["trust"],
        "allocator": config["allocator"],
        "trajectory": config["trajectory"],
        "wall_time_limit_s": config["wall_time_limit_s"],
        "mpc_seed": config["mpc_seed"],
    }
    non_sensor_payload = dict(payload)
    non_sensor_payload.pop("sensor_case")
    non_sensor_payload.pop("measurement_model")
    return {
        "runtime_configuration_sha256": _canonical_fingerprint(payload),
        "runtime_configuration_payload": payload,
        "frozen_non_sensor_configuration_sha256": _canonical_fingerprint(
            non_sensor_payload
        ),
        "frozen_non_sensor_configuration_payload": non_sensor_payload,
    }


def _write_regime_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        f"# Nominal sensor decomposition: {result['sensor_regime']}",
        "",
        f"Evidence category: `{result['evidence_category']}`.",
        "",
        "This is a mechanical per-regime summary; aggregate scientific "
        "interpretation is written only after all six rollouts complete.",
        "",
        "| arm | termination | progress | tracking RMSE deg | max error deg | promotions |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in result["comparison"]["rows"]:
        trust = row["hierarchical_trust"]
        lines.append(
            f"| {row['arm']} | {row['termination_reason']} | "
            f"{row['reference_progress_fraction']:.6g} | "
            f"{row['full_task']['tracking_combined_rmse_deg']:.6g} | "
            f"{row['full_task']['tracking_max_abs_error_deg']:.6g} | "
            f"{trust['counts']['control_promotions']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_suite(output_root: Path) -> list[dict[str, Any]]:
    stage_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite {output_root}")

    observed_sensors, validation = validate_preregistration(
        stage_root=stage_root, repo_root=repo_root
    )
    spec_path = stage_root / REGISTERED_SPEC
    if not spec_path.is_file():
        raise RuntimeError(f"missing preregistration document {spec_path}")
    source_paths = {
        "preregistration": spec_path,
        "measurement": stage_root / "src/traction_mpc_stage4/measurement.py",
        "paired_runner": stage_root
        / "scripts/run_stage4_single_challenger_closed_loop_ab.py",
        "formal_runner": Path(__file__).resolve(),
        "estimator": stage_root / "src/traction_mpc_stage4/integral_identifier.py",
        "trust": stage_root / "src/traction_mpc_stage4/online_trust.py",
        "statistical_trust": stage_root
        / "src/traction_mpc_stage4/statistical_trust.py",
        "pacing": stage_root / "src/traction_mpc_stage4/confidence_execution.py",
        "mpc": stage_root / "src/traction_mpc_stage4/mpc.py",
        "allocator": stage_root / "src/traction_mpc_stage4/cuff_allocator.py",
    }
    source_hashes = {
        name: {"path": str(path.resolve()), "sha256": _sha256(path)}
        for name, path in source_paths.items()
    }
    git = _git_provenance(repo_root)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "evidence_category": FORMAL_EVIDENCE_CATEGORY,
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": BASELINE_COMMIT,
        **git,
        "registered_sensor_cases": list(REGISTERED_SENSOR_CASES),
        "registered_arms": ["prior_only", "trusted_adaptive"],
        "expected_rollout_count": 6,
        "measurement_seed": REGISTERED_MEASUREMENT_SEED,
        "mpc_seed": REGISTERED_MPC_SEED,
        "wall_time_limit_s": REGISTERED_WALL_LIMIT_S,
        "reference_duration_s": 23.0,
        "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
        "true_patient": REGISTERED_PATIENT_CASE,
        "sensor_definitions": observed_sensors,
        "pre_run_validation": validation,
        "source_hashes": source_hashes,
    }
    output_root.mkdir(parents=True)
    (output_root / "preregistration_snapshot.json").write_text(
        json.dumps(_strict_json(manifest), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    case_record = validation["record"]
    results: list[dict[str, Any]] = []
    non_sensor_fingerprint: str | None = None
    for sensor_name in REGISTERED_SENSOR_CASES:
        regime_dir = output_root / sensor_name
        comparison, summaries, traces = run_paired_ab(
            regime_dir,
            sensor_case_name=sensor_name,
            true_human=HUMAN,
            true_metadata={
                "case": REGISTERED_PATIENT_CASE,
                "patient_case_id": REGISTERED_PATIENT_CASE,
                "sensor_regime": sensor_name,
            },
            human_label=REGISTERED_PATIENT_CASE,
            wall_time_limit_s=REGISTERED_WALL_LIMIT_S,
            evidence_category=FORMAL_EVIDENCE_CATEGORY,
            write_comparison_outputs=False,
        )
        isolation = verify_case_pair_isolation(
            comparison, summaries, traces, case_record
        )
        if comparison["registered_configuration"]["measurement_model"] != (
            observed_sensors[sensor_name]
        ):
            raise RuntimeError(f"runtime sensor definition mutated for {sensor_name}")
        fingerprints = _controller_fingerprints(comparison)
        current_non_sensor = fingerprints["frozen_non_sensor_configuration_sha256"]
        if non_sensor_fingerprint is None:
            non_sensor_fingerprint = current_non_sensor
        elif current_non_sensor != non_sensor_fingerprint:
            raise RuntimeError("non-sensor runtime configuration changed across regimes")

        arm_provenance = {
            "baseline_tag": BASELINE_TAG,
            "baseline_commit": BASELINE_COMMIT,
            **git,
            "sensor_regime": sensor_name,
            "measurement_seed": REGISTERED_MEASUREMENT_SEED,
            "mpc_seed": REGISTERED_MPC_SEED,
            "runtime_allowance_s": REGISTERED_WALL_LIMIT_S,
            "true_patient": REGISTERED_PATIENT_CASE,
            "true_beta_equals_population_prior": True,
            "preregistration_sha256": source_hashes["preregistration"]["sha256"],
            **fingerprints,
        }
        for arm in ("prior_only", "trusted_adaptive"):
            summaries[arm]["evidence_category"] = FORMAL_EVIDENCE_CATEGORY
            summaries[arm]["nominal_sensor_decomposition_provenance"] = {
                **arm_provenance,
                "arm": arm,
            }
            (regime_dir / f"{arm}.json").write_text(
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
                "schema_version": SCHEMA_VERSION,
                "evidence_category": FORMAL_EVIDENCE_CATEGORY,
                "sensor_regime": sensor_name,
                "sensor_definition": observed_sensors[sensor_name],
                "true_patient_record": case_record,
                "provenance": arm_provenance,
                "ab_isolation": isolation,
                "comparison": comparison,
            }
        )
        (regime_dir / "comparison_summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        _write_regime_markdown(regime_dir / "comparison_summary.md", result)
        results.append(result)

    completion = {
        **manifest,
        "completed_sensor_cases": [item["sensor_regime"] for item in results],
        "completed_rollout_count": 2 * len(results),
        "common_frozen_non_sensor_configuration_sha256": non_sensor_fingerprint,
        "all_pair_isolation_checks_passed": True,
    }
    (output_root / "execution_manifest.json").write_text(
        json.dumps(
            _strict_json(completion), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run_suite(args.output_dir)


if __name__ == "__main__":
    main()
