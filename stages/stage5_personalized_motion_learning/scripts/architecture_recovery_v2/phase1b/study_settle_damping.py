#!/usr/bin/env python3
"""Discriminate settle damping on the preserved oscillatory development case."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

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
    case = config["case"]
    rows = []
    for candidate in config["candidates"]:
        setup, task = make_benchmark_case(
            int(case["setup_seed"]), task_seed=int(case["task_seed"]),
            high_rom=bool(case["high_rom"]), task_profile=str(case["task_profile"]),
            domain=config["mechanics_domain"],
        )
        row = run_closed_loop_case(
            setup, task, "adaptive", commissioning_only=True,
            probe_settle_translation_kd_n_s_per_m=float(candidate["translation_kd_n_s_per_m"]),
            probe_settle_orientation_kd_nm_s_per_rad=float(candidate["orientation_kd_nm_s_per_rad"]),
        )
        row["candidate_id"] = candidate["id"]
        rows.append(row)
        print(f"candidate={candidate['id']} completed={row['completed']} reason={row['termination_reason']}", flush=True)
    payload = {
        "schema": config["schema"], "study_id": config["study_id"],
        "evidence_category": config["evidence_category"],
        "git_branch": _git("branch", "--show-current"), "git_head": _git("rev-parse", "HEAD"),
        "config_path": str(args.config), "config_sha256": config_hash,
        "source_path": str(source_path), "source_sha256": source_hash,
        "source_or_config_changed_during_run": source_hash != _sha256(source_path) or config_hash != _sha256(args.config),
        "git_status_changed_during_run": status_before != _git("status", "--short"),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

