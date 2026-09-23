#!/usr/bin/env python3
"""Test deployable nominal support during mechanics-aware commissioning."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel, nominal_base_parameters
from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as bench
from study_probe_candidates import _candidate_probe


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def _supported_probe(
    *probe_args: Any,
    interior_delta_deg: np.ndarray,
    harmonic_amplitude_deg: np.ndarray,
    nominal_hold_scale: float,
    **probe_kwargs: Any,
) -> tuple[np.ndarray, float]:
    force, moment = _candidate_probe(
        *probe_args,
        **probe_kwargs,
        interior_delta_deg=interior_delta_deg,
        harmonic_amplitude_deg=harmonic_amplitude_deg,
    )
    _, position_xz, phi, velocity_xz, phi_dot, geometry, _, _ = probe_args
    state = geometry.estimate_state(
        np.array([position_xz[0], 0.0, position_xz[1]]),
        bench._rotation_from_phi(float(phi)),
        np.array([velocity_xz[0], 0.0, velocity_xz[1]]),
        np.array([0.0, -float(phi_dot), 0.0]),
    )
    model = BaseParameterHumanModel(geometry, nominal_base_parameters(), bench.HUMAN)
    hold_tau = model.inverse_dynamics(state[:2], np.zeros(2), np.zeros(2))
    allocation = model.allocate_generalized_action(hold_tau, state[:2])
    hold_force = np.asarray(allocation["force_world_n"], dtype=float)[[0, 2]]
    hold_moment = float(np.asarray(allocation["wrench_world"], dtype=float)[4])
    force = force + nominal_hold_scale * hold_force
    force_norm = float(np.linalg.norm(force))
    if force_norm > bench.PROBE_FORCE_LIMIT_N:
        force *= bench.PROBE_FORCE_LIMIT_N / force_norm
    moment = float(
        np.clip(
            moment + nominal_hold_scale * hold_moment,
            -bench.PROBE_MOMENT_LIMIT_NM,
            bench.PROBE_MOMENT_LIMIT_NM,
        )
    )
    return force, moment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    config = json.loads(args.config.read_text())
    base_path = Path(config["base_case_config"])
    base = json.loads(base_path.read_text())
    source_path = Path(__file__).resolve()
    dependency_path = Path(__file__).with_name("study_probe_candidates.py")
    hashes = {
        "study_config": _sha256(args.config),
        "base_case_config": _sha256(base_path),
        "source": _sha256(source_path),
        "candidate_dependency": _sha256(dependency_path),
    }
    status_before = _git("status", "--short")
    original_probe = bench._probe_wrench
    rows: list[dict[str, Any]] = []
    try:
        for candidate in config["candidates"]:
            delta = np.asarray(candidate["interior_delta_deg"], dtype=float)
            amplitude = np.asarray(candidate["harmonic_amplitude_deg"], dtype=float)
            scale = float(candidate["nominal_hold_scale"])

            def active_probe(*probe_args: Any, **probe_kwargs: Any) -> tuple[np.ndarray, float]:
                return _supported_probe(
                    *probe_args,
                    **probe_kwargs,
                    interior_delta_deg=delta,
                    harmonic_amplitude_deg=amplitude,
                    nominal_hold_scale=scale,
                )

            bench._probe_wrench = active_probe
            for case in base["cases"]:
                setup, task = bench.make_benchmark_case(
                    int(case["setup_seed"]),
                    task_seed=int(case["task_seed"]),
                    high_rom=bool(case["high_rom"]),
                    task_profile=str(case["task_profile"]),
                    domain=base["mechanics_domain"],
                )
                row = bench.run_closed_loop_case(
                    setup,
                    task,
                    str(base["arm"]),
                    probe_duration_s=float(base["probe_duration_s"]),
                    probe_control_dt_s=float(base["probe_control_dt_s"]),
                    commissioning_only=True,
                )
                row["candidate_id"] = candidate["id"]
                row["clearance_class"] = case["clearance_class"]
                rows.append(row)
            print(f"completed candidate={candidate['id']}", flush=True)
    finally:
        bench._probe_wrench = original_probe
    summary: dict[str, Any] = {}
    for candidate in config["candidates"]:
        selected = [row for row in rows if row["candidate_id"] == candidate["id"]]
        completed = [row for row in selected if row["completed"]]
        summary[candidate["id"]] = {
            "case_count": len(selected),
            "completed_count": len(completed),
            "clearance_violation_count": sum(bool(row.get("probe_clearance_violation")) for row in selected),
            "rom_violation_count": sum(bool(row.get("probe_rom_violation")) for row in selected),
            "consistency_abort_count": sum(int(row.get("probe_consistency_abort_count", 0)) for row in selected),
            "minimum_clearance_m": min(float(row["probe_min_clearance_m_evaluation_only"]) for row in selected if row.get("probe_min_clearance_m_evaluation_only") is not None),
            "force_peak_n_max": max(float(row.get("probe_force_peak_n", 0.0)) for row in selected),
            "moment_peak_nm_max": max(float(row.get("probe_moment_peak_nm", 0.0)) for row in selected),
            "geometry_error_m_max": {
                key: max((float(row["geometry_error_evaluation_only"][key]) for row in completed), default=None)
                for key in ("hip_position_m", "thigh_length_m", "knee_to_cuff_m")
            },
            "accepted_dynamic_updates_min": min((int(row["commissioning_accepted_dynamic_updates"]) for row in completed), default=None),
            "handoff_speed_deg_s_max": max((float(np.max(np.abs(row["handoff_true_dq_deg_s_evaluation_only"]))) for row in completed), default=None),
        }
    payload = {
        "schema": config["schema"],
        "study_id": config["study_id"],
        "evidence_category": config["evidence_category"],
        "git_branch": _git("branch", "--show-current"),
        "git_head": _git("rev-parse", "HEAD"),
        "hashes_before": hashes,
        "source_or_config_changed_during_run": hashes != {
            "study_config": _sha256(args.config),
            "base_case_config": _sha256(base_path),
            "source": _sha256(source_path),
            "candidate_dependency": _sha256(dependency_path),
        },
        "git_status_changed_during_run": status_before != _git("status", "--short"),
        "truth_usage": "candidate nominal support uses estimated cuff state, registered Human prior, and estimated geometry; hidden truth remains plant/evaluation only",
        "config": config,
        "summary": summary,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

