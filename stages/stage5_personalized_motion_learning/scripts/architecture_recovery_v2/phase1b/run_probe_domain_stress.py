#!/usr/bin/env python3
"""Stress the retained probe over the versioned Phase-1B mechanics domain."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import make_benchmark_case, run_closed_loop_case


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    config = json.loads(args.config.read_text())
    source_path = Path(__file__).resolve()
    source_hash, config_hash = _sha256(source_path), _sha256(args.config)
    status_before = _git("status", "--short")
    rows: list[dict[str, Any]] = []
    count = int(config["case_count_per_profile_rom_cell"])
    cell = 0
    for profile in config["task_profiles"]:
        for high_rom in (False, True):
            for offset in range(count):
                setup_seed = int(config["setup_seed_start"]) + cell * 1000 + offset
                task_seed = int(config["task_seed_start"]) + cell * 1000 + offset
                setup, task = make_benchmark_case(
                    setup_seed, task_seed=task_seed, high_rom=high_rom,
                    task_profile=profile, domain=config["mechanics_domain"],
                )
                row = run_closed_loop_case(
                    setup, task, str(config["arm"]),
                    probe_duration_s=float(config["probe_duration_s"]),
                    probe_control_dt_s=float(config["probe_control_dt_s"]),
                    commissioning_only=True,
                )
                rows.append(row)
            print(f"completed profile={profile} high_rom={high_rom} cases={count}", flush=True)
            cell += 1
    completed = [row for row in rows if row["completed"]]
    attempts = sum(int(row["setup_evaluation_only"]["generation_attempt"]) + 1 for row in rows)
    payload = {
        "schema": config["schema"], "study_id": config["study_id"],
        "evidence_category": config["evidence_category"],
        "git_branch": _git("branch", "--show-current"), "git_head": _git("rev-parse", "HEAD"),
        "config_path": str(args.config), "config_sha256": config_hash,
        "source_path": str(source_path), "source_sha256": source_hash,
        "source_or_config_changed_during_run": source_hash != _sha256(source_path) or config_hash != _sha256(args.config),
        "git_status_changed_during_run": status_before != _git("status", "--short"),
        "summary": {
            "case_count": len(rows), "completed_count": len(completed),
            "realized_generation_acceptance_fraction": len(rows) / attempts,
            "generation_attempt_max": max(int(row["setup_evaluation_only"]["generation_attempt"]) for row in rows),
            "probe_clearance_violation_count": sum(bool(row.get("probe_clearance_violation")) for row in rows),
            "probe_rom_violation_count": sum(bool(row.get("probe_rom_violation")) for row in rows),
            "probe_consistency_abort_count": sum(int(row.get("probe_consistency_abort_count", 0)) for row in rows),
            "probe_min_clearance_m_min": min(float(row["probe_min_clearance_m_evaluation_only"]) for row in rows if row.get("probe_min_clearance_m_evaluation_only") is not None),
            "probe_force_peak_n_max": max(float(row.get("probe_force_peak_n", 0.0)) for row in rows),
            "probe_moment_peak_nm_max": max(float(row.get("probe_moment_peak_nm", 0.0)) for row in rows),
            "handoff_speed_deg_s_max": max((float(np.max(np.abs(row["handoff_true_dq_deg_s_evaluation_only"]))) for row in completed), default=None),
            "geometry_error_m_max": {
                key: max((float(row["geometry_error_evaluation_only"][key]) for row in completed), default=None)
                for key in ("hip_position_m", "thigh_length_m", "knee_to_cuff_m")
            },
            "accepted_dynamic_updates_min": min((int(row["commissioning_accepted_dynamic_updates"]) for row in completed), default=None),
            "clearance_evaluation_step_s_maximum": 0.005,
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

