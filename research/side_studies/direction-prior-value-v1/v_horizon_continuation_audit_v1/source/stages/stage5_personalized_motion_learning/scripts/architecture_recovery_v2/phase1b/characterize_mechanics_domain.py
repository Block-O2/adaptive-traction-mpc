#!/usr/bin/env python3
"""Characterize the Phase-1B conditional mechanics domain before control runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    _maximum_hidden_dynamic_wrench_over_reference,
    _maximum_hidden_static_wrench_over_reference,
    _minimum_hidden_clearance_over_reference,
    make_benchmark_case,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _features(setup: Any, task: Any) -> dict[str, float]:
    return {
        "height_m": float(setup.human.height_m),
        "body_mass_kg": float(setup.human.body_mass_kg),
        "hip_x_m": float(setup.geometry.hip_plane_m[0]),
        "hip_z_m": float(setup.geometry.hip_plane_m[1]),
        "full_shank_length_m": float(setup.full_shank_length_m),
        "cuff_fraction": float(setup.cuff_fraction),
        "initial_q1_deg": float(np.degrees(setup.initial_q_rad[0])),
        "initial_q2_deg": float(np.degrees(setup.initial_q_rad[1])),
        "goal_q1_deg": float(np.degrees(task.goal_q_rad[0])),
        "goal_q2_deg": float(np.degrees(task.goal_q_rad[1])),
        "duration_s": float(task.duration_s),
    }


def _distribution(records: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    if not records:
        return {}
    return {
        key: {
            "mean": float(np.mean([record[key] for record in records])),
            "p05": float(
                np.percentile([record[key] for record in records], 5, method="linear")
            ),
            "p95": float(
                np.percentile([record[key] for record in records], 95, method="linear")
            ),
        }
        for key in records[0]
    }


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
    count = int(config["case_count_per_profile_rom_cell"])
    mechanics = dict(config["mechanics_domain"])
    unconditioned = dict(mechanics)
    unconditioned.update(
        {
            "minimum_reference_clearance_m": None,
            "generation_static_force_peak_n_maximum": None,
            "generation_static_moment_peak_nm_maximum": None,
        }
    )
    proposal_rows: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    cell_index = 0
    for profile in config["task_profiles"]:
        for high_rom in (False, True):
            for offset in range(count):
                setup_seed = int(config["setup_seed_start"]) + cell_index * 1000 + offset
                task_seed = int(config["task_seed_start"]) + cell_index * 1000 + offset
                setup, task = make_benchmark_case(
                    setup_seed,
                    task_seed=task_seed,
                    high_rom=high_rom,
                    task_profile=profile,
                    domain=unconditioned,
                )
                clearance = _minimum_hidden_clearance_over_reference(setup, task)
                static_force, static_moment = (
                    _maximum_hidden_static_wrench_over_reference(setup, task)
                )
                dynamic_force, dynamic_moment = (
                    _maximum_hidden_dynamic_wrench_over_reference(setup, task)
                )
                clearance_ok = clearance >= float(
                    mechanics["minimum_reference_clearance_m"]
                )
                static_force_ok = static_force <= float(
                    mechanics["generation_static_force_peak_n_maximum"]
                )
                static_moment_ok = static_moment <= float(
                    mechanics["generation_static_moment_peak_nm_maximum"]
                )
                proposal_rows.append(
                    {
                        "profile": profile,
                        "high_rom": high_rom,
                        "setup_seed": setup_seed,
                        "task_seed": task_seed,
                        "minimum_reference_clearance_m": clearance,
                        "static_force_peak_n": static_force,
                        "static_moment_peak_nm": static_moment,
                        "dynamic_force_peak_n": dynamic_force,
                        "dynamic_moment_peak_nm": dynamic_moment,
                        "clearance_ok": clearance_ok,
                        "static_force_ok": static_force_ok,
                        "static_moment_ok": static_moment_ok,
                        "mechanics_feasible": (
                            clearance_ok and static_force_ok and static_moment_ok
                        ),
                        "features": _features(setup, task),
                    }
                )
                accepted_setup, accepted_task = make_benchmark_case(
                    setup_seed,
                    task_seed=task_seed,
                    high_rom=high_rom,
                    task_profile=profile,
                    domain=mechanics,
                )
                accepted_rows.append(
                    {
                        "profile": profile,
                        "high_rom": high_rom,
                        "setup_seed": setup_seed,
                        "task_seed": task_seed,
                        "generation_attempt": accepted_setup.generation_attempt,
                        "generation_rejection_counts": (
                            accepted_setup.generation_rejection_counts
                        ),
                        "minimum_reference_clearance_m": (
                            accepted_setup.generation_min_reference_clearance_m
                        ),
                        "static_force_peak_n": (
                            accepted_setup.generation_static_force_peak_n
                        ),
                        "static_moment_peak_nm": (
                            accepted_setup.generation_static_moment_peak_nm
                        ),
                        "dynamic_force_peak_n": (
                            accepted_setup.generation_dynamic_force_peak_n
                        ),
                        "dynamic_moment_peak_nm": (
                            accepted_setup.generation_dynamic_moment_peak_nm
                        ),
                        "features": _features(accepted_setup, accepted_task),
                    }
                )
            print(
                f"completed profile={profile} high_rom={high_rom} cases={count}",
                flush=True,
            )
            cell_index += 1

    summary: dict[str, Any] = {}
    dynamic_gate = config["dynamic_diagnostic_gates"]
    for profile in config["task_profiles"]:
        summary[profile] = {}
        for high_rom, label in ((False, "standard"), (True, "high_rom")):
            proposed = [
                row
                for row in proposal_rows
                if row["profile"] == profile and row["high_rom"] == high_rom
            ]
            accepted = [
                row
                for row in accepted_rows
                if row["profile"] == profile and row["high_rom"] == high_rom
            ]
            draws = sum(int(row["generation_attempt"]) + 1 for row in accepted)
            rejection_counts: dict[str, int] = {}
            for row in accepted:
                for reason, value in row["generation_rejection_counts"].items():
                    rejection_counts[reason] = rejection_counts.get(reason, 0) + int(value)
            summary[profile][label] = {
                "proposal_count": len(proposed),
                "unconditioned_mechanics_feasible_count": sum(
                    bool(row["mechanics_feasible"]) for row in proposed
                ),
                "unconditioned_mechanics_feasible_fraction": float(
                    np.mean([bool(row["mechanics_feasible"]) for row in proposed])
                ),
                "unconditioned_clearance_pass_fraction": float(
                    np.mean([bool(row["clearance_ok"]) for row in proposed])
                ),
                "unconditioned_static_force_pass_fraction": float(
                    np.mean([bool(row["static_force_ok"]) for row in proposed])
                ),
                "unconditioned_static_moment_pass_fraction": float(
                    np.mean([bool(row["static_moment_ok"]) for row in proposed])
                ),
                "conditional_case_count": len(accepted),
                "conditional_proposal_draw_count": draws,
                "conditional_realized_acceptance_fraction": len(accepted) / draws,
                "conditional_generation_attempt_max": max(
                    int(row["generation_attempt"]) for row in accepted
                ),
                "conditional_rejection_counts": rejection_counts,
                "dynamic_force_pass_fraction": float(
                    np.mean(
                        [
                            float(row["dynamic_force_peak_n"])
                            <= float(dynamic_gate["force_peak_n_maximum"])
                            for row in accepted
                        ]
                    )
                ),
                "dynamic_moment_pass_fraction": float(
                    np.mean(
                        [
                            float(row["dynamic_moment_peak_nm"])
                            <= float(dynamic_gate["moment_peak_nm_maximum"])
                            for row in accepted
                        ]
                    )
                ),
                "dynamic_force_peak_n_max": max(
                    float(row["dynamic_force_peak_n"]) for row in accepted
                ),
                "dynamic_moment_peak_nm_max": max(
                    float(row["dynamic_moment_peak_nm"]) for row in accepted
                ),
                "proposal_feature_distribution": _distribution(
                    [row["features"] for row in proposed]
                ),
                "accepted_feature_distribution": _distribution(
                    [row["features"] for row in accepted]
                ),
            }
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
        "truth_usage": (
            "hidden truth is used only for setup proposal, mechanics filtering, "
            "and evaluation; no deployable controller is executed"
        ),
        "config": config,
        "summary": summary,
        "proposal_rows": proposal_rows,
        "accepted_rows": accepted_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

