#!/usr/bin/env python3
"""Controlled fixed-snapshot telemetry for the frozen V1 runtime question."""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from dataclasses import replace
import gc
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import tempfile
import time
from typing import Any

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import (
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.goal_mpc_smoke import (
    FIXED_HUMAN_MODEL_VERSION,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.hold_stabilizer import solve_loaded_hold_equilibrium
from traction_mpc_stage5.interface_robustness_campaign import scaled_interface
from traction_mpc_stage5.loaded_execution import (
    build_stage5_loaded_execution_context,
    loaded_execution_target_from_equilibrium,
)
from traction_mpc_stage5.task import (
    GoalTaskState,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
)


DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "runtime_telemetry_v2"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _command_probe(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return {"available": False, "error": type(error).__name__}
    output_reports_error = "error" in completed.stdout.lower()
    return {
        "available": completed.returncode == 0 and not output_reports_error,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def summarize_window(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("runtime window cannot be empty")
    wall = np.asarray([row["wall_ms"] for row in rows], dtype=float)
    process = np.asarray([row["process_ms"] for row in rows], dtype=float)
    section_names = sorted(
        {
            key.removeprefix("section__")
            for row in rows
            for key in row
            if key.startswith("section__")
        }
    )
    return {
        "count": len(rows),
        "wall_mean_ms": float(np.mean(wall)),
        "wall_p95_ms": float(np.percentile(wall, 95)),
        "wall_max_ms": float(np.max(wall)),
        "process_mean_ms": float(np.mean(process)),
        "process_p95_ms": float(np.percentile(process, 95)),
        "process_max_ms": float(np.max(process)),
        "wall_minus_process_mean_ms": float(np.mean(wall - process)),
        "section_mean_ms": {
            name: float(
                np.mean([row.get(f"section__{name}", 0.0) for row in rows])
            )
            for name in section_names
        },
    }


def classify_runtime_growth(
    first: dict[str, Any], last: dict[str, Any], *, material_ratio: float = 1.10
) -> dict[str, Any]:
    wall_ratio = last["wall_mean_ms"] / first["wall_mean_ms"]
    process_ratio = last["process_mean_ms"] / first["process_mean_ms"]
    if wall_ratio >= material_ratio and process_ratio < 1.05:
        comparison_case = "A"
        interpretation = "wall_only_growth_supports_scheduling_or_contention"
    elif wall_ratio >= material_ratio and process_ratio >= material_ratio:
        comparison_case = "B"
        interpretation = "wall_and_process_growth_supports_compute_throughput_effect"
    elif wall_ratio < material_ratio and process_ratio < material_ratio:
        comparison_case = "C"
        interpretation = "fixed_snapshot_did_not_reproduce_campaign_slowdown"
    else:
        comparison_case = "mixed"
        interpretation = "wall_and_process_evidence_is_mixed"
    return {
        "comparison_case": comparison_case,
        "interpretation": interpretation,
        "wall_ratio": float(wall_ratio),
        "wall_change_percent": float(100.0 * (wall_ratio - 1.0)),
        "process_ratio": float(process_ratio),
        "process_change_percent": float(100.0 * (process_ratio - 1.0)),
        # Frequency/thermal/scheduler telemetry is frequently unavailable on
        # macOS without privileged tools.  This diagnostic never promotes B4
        # solely from timing ratios.
        "b1_to_b6_classification": "B6",
    }


def _build_fixed_snapshot() -> dict[str, Any]:
    session: dict[str, Any] = {}
    spec = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5)
    with tempfile.TemporaryDirectory(prefix="stage5_runtime_telemetry_setup_") as temp:
        run_goal_mpc_smoke(
            Path(temp) / "setup_5ms",
            spec=spec,
            maximum_duration_s=0.005,
            plant_interface_parameters=scaled_interface(0.9, 0.9, 0.8),
            plant_case_name="runtime_telemetry_fixed_snapshot_setup",
            record_selected_horizon_diagnostics=True,
            use_loaded_local_hold=True,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
            planning_physical_force_ceiling_n=180.0,
            planning_joint_velocity_ceiling_rad_s=tuple(np.radians((15.0, 25.0))),
            mpc_config=HumanMPCConfig(random_seed=20260824),
            session_context=session,
        )
    plant = session["plant"]
    human_model = session["estimator"].model
    measurement = session["mpc_layer"].current
    low_level_measurement = session["low_level_layer"].current
    observation, interface_state = session["interface_observer"].update(
        measurement,
        human_model,
        human_model_version=FIXED_HUMAN_MODEL_VERSION,
    )
    predictor = session["screening_interface_predictor"]
    predictor.update_from_measurement(interface_state)
    state = observation.as_array()
    operating_point = solve_loaded_hold_equilibrium(
        spec,
        human_model,
        session["cuff_allocator"],
        target_q_rad=state[:2],
        target_dq_rad_s=state[2:],
    )
    execution_context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=low_level_measurement,
        observation=observation,
        interface_state=interface_state,
        human_model=human_model,
        cuff_allocator=session["cuff_allocator"],
        target=loaded_execution_target_from_equilibrium(operating_point, human_model),
    )
    return {
        "mpc": session["mpc"],
        "mpc_snapshot": deepcopy(session["mpc"].__dict__),
        "observation": observation,
        "interface_state": interface_state,
        "predictor": predictor,
        "human_model": human_model,
        "execution_context": execution_context,
        "spec": spec,
        "task_state": GoalTaskState(
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=0.005,
            hold_elapsed_s=0.0,
            start_validated=True,
            outbound_hold_completed=False,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--solves", type=int, default=7000)
    parser.add_argument("--sample-every", type=int, default=100)
    parser.add_argument("--window", type=int, default=200)
    args = parser.parse_args()
    if args.solves < 400 or args.window < 20 or 2 * args.window > args.solves:
        raise ValueError("benchmark needs >=400 solves and disjoint >=20-solve windows")
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    try:
        import psutil  # type: ignore
    except ImportError:
        psutil = None
    process = None if psutil is None else psutil.Process(os.getpid())
    if process is not None:
        process.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)
    host = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "psutil_available": psutil is not None,
        "cpu_frequency_available": bool(
            psutil is not None and psutil.cpu_freq() is not None
        ),
        "thermal_pmset": _command_probe(["pmset", "-g", "therm"]),
        "thermal_sysctl": _command_probe(
            ["sysctl", "machdep.xcpm.cpu_thermal_level"]
        ),
        "power_metrics": {
            "available": False,
            "reason": "powermetrics requires privileged sampling and was not invoked",
        },
    }
    snapshot = _build_fixed_snapshot()
    mpc = snapshot["mpc"]
    mpc_snapshot = snapshot["mpc_snapshot"]
    gc_events = 0

    def gc_callback(phase: str, info: dict[str, Any]) -> None:
        nonlocal gc_events
        del info
        if phase == "stop":
            gc_events += 1

    rows: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    selected_action: np.ndarray | None = None
    start_elapsed = time.perf_counter()
    gc.callbacks.append(gc_callback)
    try:
        for index in range(args.solves):
            mpc.__dict__.clear()
            mpc.__dict__.update(deepcopy(mpc_snapshot))
            # Part B resolves the frozen V1 runtime observation independently
            # of Part A. Omitting full state/limits intentionally reproduces
            # the V1 full-20-ms-only first-action screen on an exact snapshot.
            preview = make_interface_aware_first_action_batch_preview(
                snapshot["execution_context"].preview_command_batch,
                snapshot["predictor"],
                snapshot["interface_state"],
                q_rad=snapshot["observation"].as_array()[:2],
                human_model=snapshot["human_model"],
                cuff_allocator=mpc.cuff_allocator,
            )
            process_start = time.process_time_ns()
            wall_start = time.perf_counter_ns()
            action, diagnostics = mpc.solve_goal(
                snapshot["observation"],
                snapshot["task_state"],
                snapshot["spec"],
                snapshot["human_model"],
                first_action_batch_preview=preview,
            )
            wall_ms = (time.perf_counter_ns() - wall_start) / 1.0e6
            process_ms = (time.process_time_ns() - process_start) / 1.0e6
            if action is None:
                raise RuntimeError("fixed representative snapshot became infeasible")
            action = np.asarray(action, dtype=float)
            if selected_action is None:
                selected_action = action.copy()
            elif not np.array_equal(action, selected_action):
                raise RuntimeError("restored fixed snapshot selected a different action")
            row: dict[str, Any] = {
                "solve_index": index,
                "elapsed_wall_s": time.perf_counter() - start_elapsed,
                "wall_ms": wall_ms,
                "process_ms": process_ms,
            }
            for name, value in diagnostics["implementation_timing_ms"].items():
                row[f"section__{name}"] = float(value)
            rows.append(row)
            if index % args.sample_every == 0 or index + 1 == args.solves:
                sample: dict[str, Any] = {
                    "solve_index": index,
                    "elapsed_wall_s": row["elapsed_wall_s"],
                    "gc_count": list(gc.get_count()),
                    "gc_collections": [item["collections"] for item in gc.get_stats()],
                    "gc_events_since_start": gc_events,
                    "system_load_1_5_15": list(os.getloadavg()),
                    "max_rss_platform_units": resource.getrusage(
                        resource.RUSAGE_SELF
                    ).ru_maxrss,
                }
                if process is None:
                    sample.update(
                        {
                            "rss_bytes": None,
                            "process_cpu_percent": None,
                            "system_cpu_percent": None,
                            "cpu_frequency_mhz": None,
                            "thread_count": None,
                            "voluntary_context_switches": None,
                            "involuntary_context_switches": None,
                        }
                    )
                else:
                    switches = process.num_ctx_switches()
                    frequency = psutil.cpu_freq()
                    sample.update(
                        {
                            "rss_bytes": process.memory_info().rss,
                            "process_cpu_percent": process.cpu_percent(interval=None),
                            "system_cpu_percent": psutil.cpu_percent(interval=None),
                            "cpu_frequency_mhz": (
                                None if frequency is None else frequency.current
                            ),
                            "thread_count": process.num_threads(),
                            "voluntary_context_switches": switches.voluntary,
                            "involuntary_context_switches": switches.involuntary,
                        }
                    )
                telemetry.append(sample)
            if (index + 1) % 500 == 0:
                print(
                    f"fixed snapshot {index + 1}/{args.solves} "
                    f"elapsed={row['elapsed_wall_s']:.1f}s",
                    flush=True,
                )
    finally:
        gc.callbacks.remove(gc_callback)

    fieldnames = sorted({key for row in rows for key in row})
    with (output / "per_solve.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _write_json(output / "system_telemetry.json", telemetry)
    first = summarize_window(rows[: args.window])
    middle_start = len(rows) // 2 - args.window // 2
    middle = summarize_window(rows[middle_start : middle_start + args.window])
    last = summarize_window(rows[-args.window :])
    classification = classify_runtime_growth(first, last)
    first_sections = first["section_mean_ms"]
    last_sections = last["section_mean_ms"]
    common = sorted(set(first_sections) & set(last_sections))
    section_ratios = {
        name: (
            None
            if first_sections[name] == 0.0
            else float(last_sections[name] / first_sections[name])
        )
        for name in common
    }
    result = {
        "schema": "stage5_controlled_runtime_telemetry_audit_v2",
        "historical_question": {
            "first_five_episode_mean_ms": 18.10,
            "last_five_episode_mean_ms": 21.01,
            "relative_growth_percent": 16.08,
        },
        "fixed_snapshot": {
            "condition": "low_low_low=(0.9,0.9,0.8)",
            "phase": "OUTBOUND",
            "production_horizon_candidates_iterations": [15, 32, 2],
            "identical_mpc_rng_state_restored_each_solve": True,
            "selected_action_nm": selected_action.tolist(),
            "acceleration_screening_version": "frozen_v1_full_20ms_only",
            "solve_count": len(rows),
            "elapsed_wall_s": rows[-1]["elapsed_wall_s"],
        },
        "host_telemetry_availability": host,
        "windows": {"fresh": first, "middle": middle, "post_long": last},
        "first_to_last": classification,
        "section_first_to_last_ratios": section_ratios,
        "section_ratio_mean": float(
            np.mean([value for value in section_ratios.values() if value is not None])
        ),
        "section_ratio_std": float(
            np.std([value for value in section_ratios.values() if value is not None])
        ),
        "gc_events": gc_events,
        "raw_files": ["per_solve.csv", "system_telemetry.json"],
        "classification": {
            "b1_to_b6": classification["b1_to_b6_classification"],
            "reason": (
                "Fixed-snapshot timing can separate wall-only from process-time "
                "growth, but unavailable privileged thermal/frequency telemetry "
                "prevents attributing throughput changes specifically to B4."
            ),
        },
        "controller_or_scientific_change": False,
        "controller_optimization_performed": False,
    }
    _write_json(output / "runtime_audit.json", result)
    print(json.dumps(result["first_to_last"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
