#!/usr/bin/env python3
"""Bound a control-effective mass-matrix margin over development proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import make_benchmark_case


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def _minimum_eigenvalue(beta: np.ndarray, q2_grid: np.ndarray) -> float:
    return float(
        min(
            np.linalg.eigvalsh(
                np.array(
                    [
                        [beta[0] + 2.0 * beta[2] * math.cos(q2), -(beta[1] + beta[2] * math.cos(q2))],
                        [-(beta[1] + beta[2] * math.cos(q2)), beta[1]],
                    ]
                )
            ).min()
            for q2 in q2_grid
        )
    )


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
    start, stop, count = config["q2_grid_deg"]
    q2_grid = np.radians(np.linspace(float(start), float(stop), int(count)))
    rows = []
    for offset in range(int(config["sample_count"])):
        seed = int(config["setup_seed_start"]) + offset
        setup, _ = make_benchmark_case(seed, task_seed=seed + 1_000_000, domain=config["hidden_generation"])
        rows.append({"setup_seed": seed, "minimum_mass_matrix_eigenvalue": _minimum_eigenvalue(setup.beta, q2_grid)})
    values = np.asarray([row["minimum_mass_matrix_eigenvalue"] for row in rows])
    payload = {
        "schema": config["schema"], "study_id": config["study_id"],
        "evidence_category": config["evidence_category"],
        "git_branch": _git("branch", "--show-current"), "git_head": _git("rev-parse", "HEAD"),
        "config_path": str(args.config), "config_sha256": config_hash,
        "source_path": str(source_path), "source_sha256": source_hash,
        "source_or_config_changed_during_run": source_hash != _sha256(source_path) or config_hash != _sha256(args.config),
        "git_status_changed_during_run": status_before != _git("status", "--short"),
        "summary": {
            "sample_count": len(rows), "minimum": float(values.min()),
            "p01": float(np.percentile(values, 1, method="linear")),
            "p05": float(np.percentile(values, 5, method="linear")),
            "median": float(np.median(values)), "maximum": float(values.max()),
            "true_proposal_below_candidate_count": {
                str(value): int(np.sum(values < float(value)))
                for value in config["candidate_minimum_eigenvalues"]
            }
        },
        "truth_usage": "hidden true dynamics are used only to characterize the proposal family and select a conservative estimator validity guard",
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

