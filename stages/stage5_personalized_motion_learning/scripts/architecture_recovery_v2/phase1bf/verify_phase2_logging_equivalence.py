#!/usr/bin/env python3
"""Verify Phase-2-only logging leaves a frozen adaptive rollout unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    make_benchmark_case,
    run_closed_loop_case,
)


BEHAVIOR_KEYS = (
    "completed",
    "termination_reason",
    "sample_count",
    "q_tracking_rmse_deg",
    "q_tracking_max_abs_deg",
    "dq_tracking_rmse_deg_s",
    "final_q_error_deg",
    "final_dq_deg_s",
    "force_peak_n",
    "moment_peak_nm",
    "solver_failure_count",
    "safety_abort_count",
    "estimated_rom_supervisor_abort_count",
    "dynamics_adaptation",
    "dynamics_update_trace",
    "accepted_dynamic_update_times_s",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-result", type=Path, required=True)
    parser.add_argument("--setup-seed", type=int, default=111002)
    parser.add_argument("--task-seed", type=int, default=121002)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    reference_result = json.loads(args.reference_result.read_text())
    reference = next(
        row
        for row in reference_result["rows"]
        if row["arm"] == "adaptive"
        and row["seed"] == args.setup_seed
        and row["task_seed"] == args.task_seed
    )
    setup, task = make_benchmark_case(
        args.setup_seed,
        task_seed=args.task_seed,
        task_profile=reference["task_id"],
        high_rom=reference["high_rom_case"],
        domain=reference_result["hidden_generation"],
    )
    replay = run_closed_loop_case(setup, task, "adaptive")
    comparisons = {
        key: replay[key] == reference[key] for key in BEHAVIOR_KEYS
    }
    payload = {
        "schema": "architecture_recovery_v2.phase1bf.logging_equivalence.v1",
        "evidence_category": "smoke_behavioral_equivalence",
        "reference_result": str(args.reference_result),
        "reference_result_sha256": hashlib.sha256(
            args.reference_result.read_bytes()
        ).hexdigest(),
        "case": {
            "setup_seed": args.setup_seed,
            "task_seed": args.task_seed,
            "task_profile": reference["task_id"],
            "high_rom": reference["high_rom_case"],
        },
        "behavior_comparisons": comparisons,
        "all_behavior_fields_equal": all(comparisons.values()),
        "new_logging_fields_present": all(
            key in replay
            for key in (
                "probe_force_exposure_n_s",
                "probe_moment_exposure_nm_s",
                "task_force_exposure_n_s",
                "task_moment_exposure_nm_s",
                "full_episode_force_exposure_n_s",
                "full_episode_moment_exposure_nm_s",
            )
        ),
        "new_logging": {
            key: replay[key]
            for key in (
                "probe_force_exposure_n_s",
                "probe_moment_exposure_nm_s",
                "task_force_exposure_n_s",
                "task_moment_exposure_nm_s",
                "full_episode_force_exposure_n_s",
                "full_episode_moment_exposure_nm_s",
            )
        },
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
