#!/usr/bin/env python3
"""Run the preregistered multi-seed nominal sensor decomposition."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from traction_mpc_stage3.human import HUMAN

try:
    from .run_stage4_nominal_sensor_decomposition import (
        REGISTERED_MPC_SEED,
        REGISTERED_PATIENT_CASE,
        REGISTERED_SENSOR_CASES,
        REGISTERED_WALL_LIMIT_S,
        _controller_fingerprints,
        validate_preregistration,
    )
    from .run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        FORMAL_EVIDENCE_CATEGORY,
        _canonical_fingerprint,
        _git_provenance,
        _strict_json,
        verify_case_pair_isolation,
    )
    from .run_stage4_single_challenger_closed_loop_ab import run_paired_ab
except ImportError:  # Direct execution from scripts/.
    from run_stage4_nominal_sensor_decomposition import (
        REGISTERED_MPC_SEED,
        REGISTERED_PATIENT_CASE,
        REGISTERED_SENSOR_CASES,
        REGISTERED_WALL_LIMIT_S,
        _controller_fingerprints,
        validate_preregistration,
    )
    from run_stage4_patient_mismatch_robustness import (
        BASELINE_COMMIT,
        BASELINE_TAG,
        FORMAL_EVIDENCE_CATEGORY,
        _canonical_fingerprint,
        _git_provenance,
        _strict_json,
        verify_case_pair_isolation,
    )
    from run_stage4_single_challenger_closed_loop_ab import run_paired_ab


SCHEMA_VERSION = "stage4_nominal_sensor_multiseed_pair_v1"
MANIFEST_SCHEMA_VERSION = "stage4_nominal_sensor_multiseed_manifest_v1"
REGISTERED_MEASUREMENT_SEEDS = (44104, 54113, 64122, 74131, 84140)
REGISTERED_SPEC = Path(
    "docs/research/STAGE4_NOMINAL_SENSOR_MULTISEED_SPEC.md"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_sensor_definition(
    base_definition: dict[str, Any], measurement_seed: int
) -> dict[str, Any]:
    result = deepcopy(base_definition)
    result["random_seed"] = int(measurement_seed)
    return result


def validate_seed_set() -> None:
    expected = tuple(44104 + 10009 * index for index in range(5))
    if REGISTERED_MEASUREMENT_SEEDS != expected:
        raise RuntimeError("measurement seed set differs from preregistration")
    if len(set(REGISTERED_MEASUREMENT_SEEDS)) != 5:
        raise RuntimeError("measurement seeds must be unique")


def _seed_invariant_fingerprint(comparison: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(comparison["registered_configuration"])
    recorded_seed = config.pop("measurement_seed")
    model_seed = config["measurement_model"].pop("random_seed")
    if recorded_seed != model_seed:
        raise RuntimeError("registered and runtime measurement seeds differ")
    payload = {
        "registered_configuration_without_measurement_seed": config,
        "measurement_seed_is_only_removed_field": True,
    }
    return {
        "seed_invariant_runtime_configuration_sha256": _canonical_fingerprint(
            payload
        ),
        "seed_invariant_runtime_configuration_payload": payload,
    }


def _write_pair_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Stage-4 nominal sensor multi-seed pair",
        "",
        f"Measurement seed: `{result['measurement_seed']}`; sensor regime: "
        f"`{result['sensor_regime']}`.",
        "",
        "This is a preregistered per-pair mechanical summary. Scientific "
        "interpretation is generated only after the full matrix completes.",
        "",
        "| arm | termination | progress | tracking RMSE deg | oracle RMSE Nm | qualifications | promotions |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in result["comparison"]["rows"]:
        trust = row["hierarchical_trust"]
        lines.append(
            f"| {row['arm']} | {row['termination_reason']} | "
            f"{row['reference_progress_fraction']:.6g} | "
            f"{row['full_task']['tracking_combined_rmse_deg']:.6g} | "
            f"{row['estimator_control_model_prediction_error_god_view']['combined_rmse_nm']:.6g} | "
            f"{len(trust['qualifications'])} | "
            f"{len(trust['control_promotions'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_suite(output_root: Path) -> list[dict[str, Any]]:
    validate_seed_set()
    stage_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite {output_root}")

    base_sensors, validation = validate_preregistration(
        stage_root=stage_root, repo_root=repo_root
    )
    spec_path = stage_root / REGISTERED_SPEC
    if not spec_path.is_file():
        raise RuntimeError(f"missing preregistration document {spec_path}")
    source_paths = {
        "preregistration": spec_path,
        "measurement": stage_root / "src/traction_mpc_stage4/measurement.py",
        "sensor_realism": stage_root / "src/traction_mpc_stage4/sensor_realism.py",
        "human": stage_root / "src/traction_mpc_stage3/human.py",
        "paired_runner": stage_root
        / "scripts/run_stage4_single_challenger_closed_loop_ab.py",
        "formal_runner": Path(__file__).resolve(),
        "estimator": stage_root / "src/traction_mpc_stage4/integral_identifier.py",
        "online_trust": stage_root / "src/traction_mpc_stage4/online_trust.py",
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
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "evidence_category": FORMAL_EVIDENCE_CATEGORY,
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": BASELINE_COMMIT,
        **git,
        "measurement_seeds": list(REGISTERED_MEASUREMENT_SEEDS),
        "seed_generation_rule": "44104 + 10009*k for k=0..4",
        "sensor_regimes": list(REGISTERED_SENSOR_CASES),
        "arms": ["prior_only", "trusted_adaptive"],
        "expected_pair_count": 15,
        "expected_rollout_count": 30,
        "mpc_seed": REGISTERED_MPC_SEED,
        "wall_time_limit_s": REGISTERED_WALL_LIMIT_S,
        "reference_duration_s": 23.0,
        "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
        "true_patient": REGISTERED_PATIENT_CASE,
        "base_sensor_definitions": base_sensors,
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
    regime_seed_invariant_fingerprints: dict[str, str] = {}
    common_non_sensor_fingerprint: str | None = None
    for measurement_seed in REGISTERED_MEASUREMENT_SEEDS:
        for sensor_name in REGISTERED_SENSOR_CASES:
            pair_dir = output_root / f"seed_{measurement_seed}" / sensor_name
            expected_sensor = expected_sensor_definition(
                base_sensors[sensor_name], measurement_seed
            )
            comparison, summaries, traces = run_paired_ab(
                pair_dir,
                sensor_case_name=sensor_name,
                measurement_seed=measurement_seed,
                true_human=HUMAN,
                true_metadata={
                    "case": REGISTERED_PATIENT_CASE,
                    "patient_case_id": REGISTERED_PATIENT_CASE,
                    "sensor_regime": sensor_name,
                    "measurement_seed": measurement_seed,
                },
                human_label=REGISTERED_PATIENT_CASE,
                wall_time_limit_s=REGISTERED_WALL_LIMIT_S,
                evidence_category=FORMAL_EVIDENCE_CATEGORY,
                write_comparison_outputs=False,
            )
            isolation = verify_case_pair_isolation(
                comparison, summaries, traces, case_record
            )
            runtime_sensor = comparison["registered_configuration"][
                "measurement_model"
            ]
            if runtime_sensor != expected_sensor:
                raise RuntimeError(
                    f"runtime sensor definition mutated for {measurement_seed}/{sensor_name}"
                )
            if comparison["registered_configuration"]["mpc_seed"] != (
                REGISTERED_MPC_SEED
            ):
                raise RuntimeError("MPC seed changed during multi-seed suite")

            fingerprints = _controller_fingerprints(comparison)
            seed_invariant = _seed_invariant_fingerprint(comparison)
            current_seed_invariant = seed_invariant[
                "seed_invariant_runtime_configuration_sha256"
            ]
            previous = regime_seed_invariant_fingerprints.get(sensor_name)
            if previous is None:
                regime_seed_invariant_fingerprints[sensor_name] = (
                    current_seed_invariant
                )
            elif previous != current_seed_invariant:
                raise RuntimeError(
                    f"non-seed configuration changed across seeds for {sensor_name}"
                )
            current_non_sensor = fingerprints[
                "frozen_non_sensor_configuration_sha256"
            ]
            if common_non_sensor_fingerprint is None:
                common_non_sensor_fingerprint = current_non_sensor
            elif current_non_sensor != common_non_sensor_fingerprint:
                raise RuntimeError("non-sensor configuration changed across matrix")

            provenance = {
                "baseline_tag": BASELINE_TAG,
                "baseline_commit": BASELINE_COMMIT,
                **git,
                "measurement_seed": measurement_seed,
                "sensor_regime": sensor_name,
                "mpc_seed": REGISTERED_MPC_SEED,
                "runtime_allowance_s": REGISTERED_WALL_LIMIT_S,
                "true_patient": REGISTERED_PATIENT_CASE,
                "true_beta_equals_population_prior": True,
                "preregistration_sha256": source_hashes["preregistration"][
                    "sha256"
                ],
                **fingerprints,
                **seed_invariant,
            }
            for arm in ("prior_only", "trusted_adaptive"):
                summaries[arm]["evidence_category"] = FORMAL_EVIDENCE_CATEGORY
                summaries[arm]["nominal_sensor_multiseed_provenance"] = {
                    **provenance,
                    "arm": arm,
                }
                (pair_dir / f"{arm}.json").write_text(
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
                    "measurement_seed": measurement_seed,
                    "sensor_regime": sensor_name,
                    "sensor_definition": expected_sensor,
                    "true_patient_record": case_record,
                    "provenance": provenance,
                    "ab_isolation": isolation,
                    "comparison": comparison,
                }
            )
            (pair_dir / "comparison_summary.json").write_text(
                json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
            _write_pair_markdown(pair_dir / "comparison_summary.md", result)
            results.append(result)

    completion = {
        **manifest,
        "completed_pair_count": len(results),
        "completed_rollout_count": 2 * len(results),
        "completed_pairs": [
            {
                "measurement_seed": item["measurement_seed"],
                "sensor_regime": item["sensor_regime"],
            }
            for item in results
        ],
        "regime_seed_invariant_configuration_sha256": (
            regime_seed_invariant_fingerprints
        ),
        "common_frozen_non_sensor_configuration_sha256": (
            common_non_sensor_fingerprint
        ),
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
