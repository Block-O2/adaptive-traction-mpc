#!/usr/bin/env python3
"""Run preregistered report-validation phases.

Formal gain selection, benchmark, and demo execution remain user-only.  The
``smoke`` phase is capped at 0.5 s and is explicitly non-scientific.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from traction_mpc_stage4.report_validation import (
    canonical_json_sha256,
    gain_candidates,
    gain_lock_payload,
    load_gain_lock,
    load_report_validation_matrix,
    prepare_fresh_output_directory,
    run_coupled_pd_gain_smoke,
    run_report_arm,
    run_structural_smoke,
    select_gain_candidate,
    sha256_file,
    write_gain_lock,
    write_strict_json,
)
from traction_mpc_stage4.report_generalization import (
    run_generalization_phase,
    run_generalization_structural_smoke,
)


def run_gain_tuning(*, matrix_path: Path, output_dir: Path) -> dict[str, Any]:
    """Execute all nine full-length nominal tuning runs and lock one gain pair."""

    matrix_path = Path(matrix_path).resolve()
    matrix = load_report_validation_matrix(matrix_path)
    matrix_hash = sha256_file(matrix_path)
    prepare_fresh_output_directory(output_dir)
    tuning = matrix["gain_tuning"]
    records: list[dict[str, Any]] = []
    for candidate in gain_candidates(matrix):
        candidate_hash = canonical_json_sha256(candidate)
        result = run_report_arm(
            matrix=matrix,
            matrix_path=matrix_path,
            gain_lock=candidate,
            gain_lock_sha256=candidate_hash,
            controller_id="pd_feedback",
            patient_id=tuning["patient_id"],
            trajectory_id=tuning["trajectory_id"],
            evidence_category="nominal_gain_selection",
            formal_execution=True,
            duration_s=float(matrix["shared_contract"]["wall_time_limit_s"]),
            output_dir=Path(output_dir) / "candidates" / candidate["candidate_id"],
        )
        records.append(
            {
                **candidate,
                **result["metrics"],
                "candidate_definition_sha256": candidate_hash,
            }
        )
    try:
        selected = select_gain_candidate(
            records, tie_tolerance=float(tuning["tie_tolerance"])
        )
    except RuntimeError:
        status = {
            "status": "no_mechanically_eligible_candidate",
            "formal_gain_lock_created": False,
            "candidate_records": records,
            "required_next_action": "stop_and_request_user_direction",
        }
        write_strict_json(Path(output_dir) / "gain_selection_status.json", status)
        raise
    lock = gain_lock_payload(
        matrix_sha256=matrix_hash,
        candidate_records=records,
        selected=selected,
        lock_kind="formal",
    )
    lock_path = Path(output_dir) / "frozen_pd_gains.json"
    lock_hash = write_gain_lock(lock_path, lock)
    status = {
        "status": "gain_lock_created",
        "formal_gain_lock_created": True,
        "gain_lock_path": str(lock_path),
        "gain_lock_sha256": lock_hash,
        "selected_candidate_id": selected["candidate_id"],
        "candidate_count": len(records),
    }
    write_strict_json(Path(output_dir) / "gain_selection_status.json", status)
    return status


def _phase_cases(matrix: dict[str, Any], phase: str) -> tuple[dict[str, str], ...]:
    if phase == "benchmark":
        block = matrix["benchmark_matrix"]
        return tuple(
            {
                "case_id": f"{patient_id}__{trajectory_id}",
                "patient_id": patient_id,
                "trajectory_id": trajectory_id,
                "evidence_category": block["evidence_category"],
            }
            for patient_id in block["patients"]
            for trajectory_id in block["trajectories"]
        )
    if phase == "demo":
        return tuple(
            {
                "case_id": scene["scene_id"],
                "patient_id": scene["patient_id"],
                "trajectory_id": scene["trajectory_id"],
                "evidence_category": matrix["visualization_matrix"][
                    "evidence_category"
                ],
            }
            for scene in matrix["visualization_matrix"]["scenes"]
            if scene["source"] == "new_demo_only_rollouts"
        )
    raise ValueError("phase must be benchmark or demo")


def run_matrix_phase(
    *,
    matrix_path: Path,
    phase: str,
    gain_lock_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    matrix_path = Path(matrix_path).resolve()
    matrix = load_report_validation_matrix(matrix_path)
    matrix_hash = sha256_file(matrix_path)
    lock, lock_hash = load_gain_lock(gain_lock_path, required_kind="formal")
    if lock["report_validation_config_sha256"] != matrix_hash:
        raise ValueError("gain lock belongs to a different report-validation matrix")
    prepare_fresh_output_directory(output_dir)
    controllers = [item["controller_id"] for item in matrix["controllers"]]
    cases = _phase_cases(matrix, phase)
    arms: list[dict[str, Any]] = []
    for case in cases:
        for controller_id in controllers:
            arm_dir = Path(output_dir) / case["case_id"] / controller_id
            result = run_report_arm(
                matrix=matrix,
                matrix_path=matrix_path,
                gain_lock=lock,
                gain_lock_sha256=lock_hash,
                controller_id=controller_id,
                patient_id=case["patient_id"],
                trajectory_id=case["trajectory_id"],
                evidence_category=case["evidence_category"],
                formal_execution=True,
                duration_s=float(matrix["shared_contract"]["wall_time_limit_s"]),
                output_dir=arm_dir,
            )
            arms.append(
                {
                    **case,
                    "controller_id": controller_id,
                    "output_dir": str(arm_dir),
                    "termination_reason": result["summary"]["termination_reason"],
                    "controller_fingerprint_sha256": result["provenance"][
                        "controller_fingerprint_sha256"
                    ],
                }
            )
    expected = (
        int(matrix["benchmark_matrix"]["new_rollout_count"])
        if phase == "benchmark"
        else int(matrix["visualization_matrix"]["new_rollout_count"])
    )
    if len(arms) != expected:
        raise RuntimeError(f"{phase} arm count {len(arms)} differs from {expected}")
    manifest = {
        "schema_version": "stage4_report_validation_phase_manifest_v1",
        "phase": phase,
        "formal_execution": True,
        "evidence_category": cases[0]["evidence_category"],
        "report_validation_config_sha256": matrix_hash,
        "gain_lock_sha256": lock_hash,
        "arm_count": len(arms),
        "arms": arms,
    }
    write_strict_json(Path(output_dir) / "phase_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix-config",
        type=Path,
        default=Path("configs/stage4_report_validation_matrix.json"),
    )
    parser.add_argument(
        "--phase",
        choices=(
            "gain-tuning",
            "benchmark",
            "demo",
            "smoke",
            "gain-smoke",
            "generalization-statistical",
            "generalization-trajectory-demo",
            "generalization-smoke",
        ),
        required=True,
    )
    parser.add_argument("--gain-lock", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--smoke-duration-s", type=float)
    args = parser.parse_args()

    if args.phase == "generalization-smoke":
        if args.gain_lock is None:
            parser.error("generalization-smoke requires the frozen formal gain lock")
        duration = 0.25 if args.smoke_duration_s is None else args.smoke_duration_s
        result = run_generalization_structural_smoke(
            matrix_path=args.matrix_config,
            gain_lock_path=args.gain_lock,
            output_dir=args.output_dir,
            duration_s=duration,
        )
    elif args.phase in {
        "generalization-statistical",
        "generalization-trajectory-demo",
    }:
        if args.gain_lock is None:
            parser.error(f"{args.phase} requires the frozen formal gain lock")
        if args.smoke_duration_s is not None:
            parser.error("formal generalization phases do not accept smoke duration")
        result = run_generalization_phase(
            matrix_path=args.matrix_config,
            gain_lock_path=args.gain_lock,
            phase=(
                "statistical"
                if args.phase == "generalization-statistical"
                else "trajectory-demo"
            ),
            output_dir=args.output_dir,
        )
    elif args.phase == "smoke":
        if args.gain_lock is not None:
            parser.error("smoke creates its own non-formal gain lock")
        duration = 0.1 if args.smoke_duration_s is None else args.smoke_duration_s
        result = run_structural_smoke(
            matrix_path=args.matrix_config,
            output_dir=args.output_dir,
            duration_s=duration,
        )
    elif args.phase == "gain-smoke":
        if args.gain_lock is not None:
            parser.error("gain-smoke uses preregistered v2 candidate definitions")
        duration = 1.5 if args.smoke_duration_s is None else args.smoke_duration_s
        result = run_coupled_pd_gain_smoke(
            matrix_path=args.matrix_config,
            output_dir=args.output_dir,
            duration_s=duration,
        )
    elif args.phase == "gain-tuning":
        if args.gain_lock is not None or args.smoke_duration_s is not None:
            parser.error("formal gain tuning does not accept a gain lock or smoke duration")
        result = run_gain_tuning(
            matrix_path=args.matrix_config,
            output_dir=args.output_dir,
        )
    else:
        if args.gain_lock is None:
            parser.error(f"{args.phase} requires --gain-lock")
        if args.smoke_duration_s is not None:
            parser.error("formal matrix phases do not accept a smoke duration")
        result = run_matrix_phase(
            matrix_path=args.matrix_config,
            phase=args.phase,
            gain_lock_path=args.gain_lock,
            output_dir=args.output_dir,
        )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
