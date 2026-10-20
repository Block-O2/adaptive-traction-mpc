#!/usr/bin/env python3
"""Discriminate mechanics-aware commissioning candidates without production edits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage3.reference import quintic_progress
from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as bench


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _candidate_probe(
    time_s: float,
    position_xz_m: np.ndarray,
    phi_rad: float,
    velocity_xz_m_s: np.ndarray,
    phi_dot_rad_s: float,
    commissioning_geometry: Any,
    commissioning_start_q_rad: np.ndarray,
    duration_s: float,
    *,
    interior_delta_deg: np.ndarray,
    harmonic_amplitude_deg: np.ndarray,
) -> tuple[np.ndarray, float]:
    start_q = np.asarray(commissioning_start_q_rad, dtype=float)
    interior_q = start_q + np.radians(interior_delta_deg)
    entry_duration = 0.35 * duration_s
    excitation_duration = 0.45 * duration_s
    excitation_end = entry_duration + excitation_duration
    if time_s < entry_duration:
        progress, progress_velocity, _ = quintic_progress(time_s / entry_duration)
        target_q = start_q + (interior_q - start_q) * progress
        target_dq = (interior_q - start_q) * progress_velocity / entry_duration
    elif time_s < excitation_end:
        normalized = (time_s - entry_duration) / excitation_duration
        phase = 2.0 * math.pi * normalized
        phase_rate = 2.0 * math.pi / excitation_duration
        window = math.sin(math.pi * normalized) ** 2
        window_rate = math.pi * math.sin(2.0 * math.pi * normalized) / excitation_duration
        shapes = np.array([math.sin(phase), math.sin(2.0 * phase)]) * window
        shape_rates = np.array(
            [
                math.cos(phase) * phase_rate * window + math.sin(phase) * window_rate,
                math.cos(2.0 * phase) * 2.0 * phase_rate * window
                + math.sin(2.0 * phase) * window_rate,
            ]
        )
        target_q = interior_q + np.radians(harmonic_amplitude_deg * shapes)
        target_dq = np.radians(harmonic_amplitude_deg * shape_rates)
    else:
        target_q = interior_q
        target_dq = np.zeros(2)
    target_pose = commissioning_geometry.cuff_pose(target_q)
    target_linear, _ = commissioning_geometry.cuff_velocity(target_q, target_dq)
    target = target_pose.translation[[0, 2]]
    target_velocity = target_linear[[0, 2]]
    target_phi = float(target_q[0] - target_q[1])
    target_phi_dot = float(target_dq[0] - target_dq[1])
    force = bench.PROBE_TRANSLATION_KP_N_PER_M * (
        target - position_xz_m
    ) + bench.PROBE_TRANSLATION_KD_N_S_PER_M * (
        target_velocity - velocity_xz_m_s
    )
    norm = float(np.linalg.norm(force))
    if norm > bench.PROBE_FORCE_LIMIT_N:
        force *= bench.PROBE_FORCE_LIMIT_N / norm
    moment = float(
        -np.clip(
            bench.PROBE_ORIENTATION_KP_NM_PER_RAD * (target_phi - phi_rad)
            + bench.PROBE_ORIENTATION_KD_NM_S_PER_RAD
            * (target_phi_dot - phi_dot_rad_s),
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
    hashes = {
        "study_config": _sha256(args.config),
        "base_case_config": _sha256(base_path),
        "source": _sha256(source_path),
    }
    status_before = _git("status", "--short")
    original_probe = bench._probe_wrench
    rows: list[dict[str, Any]] = []
    try:
        for candidate in config["candidates"]:
            delta = np.asarray(candidate["interior_delta_deg"], dtype=float)
            amplitude = np.asarray(candidate["harmonic_amplitude_deg"], dtype=float)

            def active_probe(*probe_args: Any, **probe_kwargs: Any) -> tuple[np.ndarray, float]:
                return _candidate_probe(
                    *probe_args,
                    **probe_kwargs,
                    interior_delta_deg=delta,
                    harmonic_amplitude_deg=amplitude,
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
            "clearance_violation_count": sum(
                bool(row.get("probe_clearance_violation")) for row in selected
            ),
            "rom_violation_count": sum(
                bool(row.get("probe_rom_violation")) for row in selected
            ),
            "consistency_abort_count": sum(
                int(row.get("probe_consistency_abort_count", 0)) for row in selected
            ),
            "minimum_clearance_m": min(
                float(row["probe_min_clearance_m_evaluation_only"])
                for row in selected
                if row.get("probe_min_clearance_m_evaluation_only") is not None
            ),
            "force_peak_n_max": max(float(row.get("probe_force_peak_n", 0.0)) for row in selected),
            "moment_peak_nm_max": max(float(row.get("probe_moment_peak_nm", 0.0)) for row in selected),
            "geometry_error_m_max": {
                key: max(
                    float(row["geometry_error_evaluation_only"][key]) for row in completed
                ) if completed else None
                for key in ("hip_position_m", "thigh_length_m", "knee_to_cuff_m")
            },
            "accepted_dynamic_updates_min": min(
                (int(row["commissioning_accepted_dynamic_updates"]) for row in completed),
                default=None,
            ),
            "handoff_speed_deg_s_max": max(
                (
                    float(np.max(np.abs(row["handoff_true_dq_deg_s_evaluation_only"])))
                    for row in completed
                ),
                default=None,
            ),
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
        },
        "git_status_changed_during_run": status_before != _git("status", "--short"),
        "truth_usage": "hidden truth is used only by plant generation and evaluation; candidate probe receives deployable cuff observations and estimated geometry",
        "config": config,
        "summary": summary,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

