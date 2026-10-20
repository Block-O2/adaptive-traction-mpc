#!/usr/bin/env python3
"""Compare knee-led reference geometries before a Phase-1B material revision.

This is a proposal-level mechanics diagnostic. Hidden truth is used only for
case generation and evaluation; no deployable estimator/controller is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import (
    HiddenSetup,
    TaskSpec,
    _hidden_shank_clearance_m,
    _quintic_segment,
    make_benchmark_case,
    make_task_reference,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _bounded_reference(
    setup: HiddenSetup,
    task: TaskSpec,
    hip_fraction: float,
    knee_fraction: float,
) -> Callable[[float], CuffPoseReference]:
    start = setup.initial_q_rad
    goal = task.goal_q_rad
    midpoint = start + np.array([hip_fraction, knee_fraction]) * (goal - start)
    outbound = 0.40 * task.duration_s
    hold = 0.12 * task.duration_s
    returning = 0.40 * task.duration_s
    first = 0.52 * outbound

    def reference(time_s: float) -> CuffPoseReference:
        time = float(np.clip(time_s, 0.0, task.duration_s))
        if time <= first:
            q, dq, ddq = _quintic_segment(time, 0.0, first, start, midpoint)
        elif time <= outbound:
            q, dq, ddq = _quintic_segment(
                time, first, outbound - first, midpoint, goal
            )
        elif time <= outbound + hold:
            q, dq, ddq = goal.copy(), np.zeros(2), np.zeros(2)
        elif time <= outbound + hold + returning * 0.48:
            q, dq, ddq = _quintic_segment(
                time,
                outbound + hold,
                returning * 0.48,
                goal,
                midpoint,
            )
        else:
            q, dq, ddq = _quintic_segment(
                time,
                outbound + hold + returning * 0.48,
                returning * 0.52,
                midpoint,
                start,
            )
        return CuffPoseReference(q, dq, ddq, setup.geometry.cuff_pose(q))

    return reference


def _reference(
    setup: HiddenSetup, task: TaskSpec, profile: dict[str, Any]
) -> Callable[[float], CuffPoseReference]:
    if profile["kind"] == "bounded":
        return _bounded_reference(
            setup,
            task,
            float(profile["hip_midpoint_fraction"]),
            float(profile["knee_midpoint_fraction"]),
        )
    production_id = str(profile.get("production_id", profile["id"]))
    return make_task_reference(
        setup.initial_q_rad,
        task.goal_q_rad,
        production_id,
        task.duration_s,
        setup.geometry,
    )


def _evaluate(
    setup: HiddenSetup,
    task: TaskSpec,
    profile: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    reference = _reference(setup, task, profile)
    clearance = min(
        _hidden_shank_clearance_m(setup, reference(time_s).q_rad)
        for time_s in np.linspace(
            0.0, task.duration_s, int(gate["clearance_sample_count"])
        )
    )
    model = BaseParameterHumanModel(setup.geometry, setup.beta, setup.human)
    force_peak = 0.0
    moment_peak = 0.0
    for time_s in np.linspace(
        0.0, task.duration_s, int(gate["static_wrench_sample_count"])
    ):
        q = reference(time_s).q_rad
        tau = model.inverse_dynamics(q, np.zeros(2), np.zeros(2))
        allocation = model.allocate_generalized_action(tau, q)
        force_peak = max(
            force_peak,
            float(np.linalg.norm(np.asarray(allocation["force_world_n"]))),
        )
        moment_peak = max(
            moment_peak,
            float(
                np.linalg.norm(
                    np.asarray(allocation["wrench_world"], dtype=float)[3:]
                )
            ),
        )
    clearance_ok = clearance >= float(gate["minimum_reference_clearance_m"])
    force_ok = force_peak <= float(gate["static_force_peak_n_maximum"])
    moment_ok = moment_peak <= float(gate["static_moment_peak_nm_maximum"])
    return {
        "profile": profile["id"],
        "minimum_reference_clearance_m": float(clearance),
        "static_force_peak_n": force_peak,
        "static_moment_peak_nm": moment_peak,
        "clearance_ok": clearance_ok,
        "force_ok": force_ok,
        "moment_ok": moment_ok,
        "mechanics_feasible": clearance_ok and force_ok and moment_ok,
    }


def _summary(rows: list[dict[str, Any]], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for profile in profiles:
        name = profile["id"]
        selected = [row for row in rows if row["profile"] == name]
        strata: dict[str, Any] = {}
        for label, subset in (
            ("all", selected),
            ("standard", [row for row in selected if not row["high_rom"]]),
            ("high_rom", [row for row in selected if row["high_rom"]]),
        ):
            feasible = sum(bool(row["mechanics_feasible"]) for row in subset)
            strata[label] = {
                "case_count": len(subset),
                "mechanics_feasible_count": feasible,
                "mechanics_feasible_fraction": feasible / len(subset),
                "clearance_pass_fraction": float(
                    np.mean([bool(row["clearance_ok"]) for row in subset])
                ),
                "force_pass_fraction": float(
                    np.mean([bool(row["force_ok"]) for row in subset])
                ),
                "moment_pass_fraction": float(
                    np.mean([bool(row["moment_ok"]) for row in subset])
                ),
                "minimum_clearance_m_p05": float(
                    np.percentile(
                        [row["minimum_reference_clearance_m"] for row in subset],
                        5,
                        method="linear",
                    )
                ),
                "static_force_peak_n_p95": float(
                    np.percentile(
                        [row["static_force_peak_n"] for row in subset],
                        95,
                        method="linear",
                    )
                ),
                "static_moment_peak_nm_p95": float(
                    np.percentile(
                        [row["static_moment_peak_nm"] for row in subset],
                        95,
                        method="linear",
                    )
                ),
            }
        result[name] = strata
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    config = json.loads(args.config.read_text())
    count = int(config["case_count_per_rom_stratum"])
    source_path = Path(__file__).resolve()
    source_hash_before = _sha256(source_path)
    config_hash_before = _sha256(args.config)
    git_status_before = _git("status", "--short")
    rows: list[dict[str, Any]] = []
    for high_rom, setup_start, task_start in (
        (
            False,
            int(config["standard_setup_seed_start"]),
            int(config["standard_task_seed_start"]),
        ),
        (
            True,
            int(config["high_rom_setup_seed_start"]),
            int(config["high_rom_task_seed_start"]),
        ),
    ):
        for offset in range(count):
            setup_seed = setup_start + offset
            task_seed = task_start + offset
            setup, task = make_benchmark_case(
                setup_seed,
                task_seed=task_seed,
                high_rom=high_rom,
                task_profile="coordinated",
                domain=config["hidden_generation"],
            )
            for profile in config["profiles"]:
                row = _evaluate(setup, task, profile, config["mechanics_gate"])
                row.update(
                    {
                        "setup_seed": setup_seed,
                        "task_seed": task_seed,
                        "high_rom": high_rom,
                        "initial_q_deg": np.degrees(setup.initial_q_rad).tolist(),
                        "goal_q_deg": np.degrees(task.goal_q_rad).tolist(),
                        "duration_s": task.duration_s,
                        "hidden_hip_xz_m": setup.geometry.hip_plane_m.tolist(),
                        "hidden_full_shank_length_m": setup.full_shank_length_m,
                    }
                )
                rows.append(row)
        print(f"completed stratum high_rom={high_rom} cases={count}", flush=True)
    payload = {
        "schema": config["schema"],
        "study_id": config["study_id"],
        "evidence_category": config["evidence_category"],
        "git_branch": _git("branch", "--show-current"),
        "git_head": _git("rev-parse", "HEAD"),
        "config_path": str(args.config),
        "config_sha256": config_hash_before,
        "source_path": str(source_path),
        "source_sha256": source_hash_before,
        "source_or_config_changed_during_run": (
            source_hash_before != _sha256(source_path)
            or config_hash_before != _sha256(args.config)
        ),
        "git_status_changed_during_run": git_status_before != _git("status", "--short"),
        "truth_usage": "hidden setup truth is used only for proposal generation and mechanics evaluation; no controller is executed",
        "config": config,
        "summary": _summary(rows, config["profiles"]),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

