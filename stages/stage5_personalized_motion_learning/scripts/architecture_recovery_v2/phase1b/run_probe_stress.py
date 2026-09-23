#!/usr/bin/env python3
"""Run commissioning only on ordinary and clearance-boundary development cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    make_benchmark_case,
    run_closed_loop_case,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    config = json.loads(args.config.read_text())
    source_path = Path(__file__).resolve()
    source_hash = _sha256(source_path)
    config_hash = _sha256(args.config)
    status_before = _git("status", "--short")
    rows: list[dict[str, Any]] = []
    for case in config["cases"]:
        setup, task = make_benchmark_case(
            int(case["setup_seed"]),
            task_seed=int(case["task_seed"]),
            high_rom=bool(case["high_rom"]),
            task_profile=str(case["task_profile"]),
            domain=config["mechanics_domain"],
        )
        row = run_closed_loop_case(
            setup,
            task,
            str(config["arm"]),
            probe_duration_s=float(config["probe_duration_s"]),
            probe_control_dt_s=float(config["probe_control_dt_s"]),
            commissioning_only=True,
        )
        row["clearance_class"] = case["clearance_class"]
        rows.append(row)
        print(
            f"[{case['setup_seed']}:{case['task_seed']}] "
            f"profile={case['task_profile']} class={case['clearance_class']} "
            f"completed={row['completed']} reason={row['termination_reason']}",
            flush=True,
        )
    successful = [row for row in rows if row["completed"]]
    payload = {
        "schema": config["schema"],
        "study_id": config["study_id"],
        "evidence_category": config["evidence_category"],
        "git_branch": _git("branch", "--show-current"),
        "git_head": _git("rev-parse", "HEAD"),
        "config_path": str(args.config),
        "config_sha256": config_hash,
        "source_path": str(source_path),
        "source_sha256": source_hash,
        "source_or_config_changed_during_run": (
            source_hash != _sha256(source_path) or config_hash != _sha256(args.config)
        ),
        "git_status_changed_during_run": status_before != _git("status", "--short"),
        "summary": {
            "case_count": len(rows),
            "completed_count": len(successful),
            "probe_rom_violation_count": sum(
                bool(row.get("probe_rom_violation")) for row in rows
            ),
            "probe_clearance_violation_count": sum(
                bool(row.get("probe_clearance_violation")) for row in rows
            ),
            "probe_consistency_abort_count": sum(
                int(row.get("probe_consistency_abort_count", 0)) for row in rows
            ),
            "probe_min_clearance_m_min": min(
                float(row["probe_min_clearance_m_evaluation_only"])
                for row in rows
                if row.get("probe_min_clearance_m_evaluation_only") is not None
            ),
            "probe_force_peak_n_max": max(
                float(row.get("probe_force_peak_n", 0.0)) for row in rows
            ),
            "probe_moment_peak_nm_max": max(
                float(row.get("probe_moment_peak_nm", 0.0)) for row in rows
            ),
            "handoff_speed_deg_s_max": max(
                float(
                    np.max(
                        np.abs(row["handoff_true_dq_deg_s_evaluation_only"])
                    )
                )
                for row in successful
            ),
            "geometry_hip_error_m_max": max(
                float(row["geometry_error_evaluation_only"]["hip_position_m"])
                for row in successful
            ),
            "geometry_thigh_error_m_max": max(
                float(row["geometry_error_evaluation_only"]["thigh_length_m"])
                for row in successful
            ),
            "geometry_cuff_distance_error_m_max": max(
                float(row["geometry_error_evaluation_only"]["knee_to_cuff_m"])
                for row in successful
            ),
            "commissioning_accepted_dynamic_updates_min": min(
                int(row["commissioning_accepted_dynamic_updates"])
                for row in successful
            ),
            "clearance_evaluation_step_s_maximum": max(
                float(row["clearance_evaluation_step_s_maximum"])
                for row in successful
            ),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

