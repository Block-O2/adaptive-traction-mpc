#!/usr/bin/env python3
"""Fixed-snapshot audit for the Stage-5 Goal-MPC runtime regression.

This is an engineering timing diagnostic only.  It restores the exact MPC
object/RNG state before every solve and never advances the rehabilitation
plant.  ``legacy_full20`` is a counterfactual code-path isolation: it omits the
Acceleration-Semantics V2 prefix predicate while leaving the current solver,
horizon, population, iterations, costs, and all other prediction code intact.
It is not an online controller option.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import gc
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import time
from typing import Any

import numpy as np
import scipy

from traction_mpc_stage5.controller_interface import (
    make_interface_aware_first_action_batch_preview,
)


try:
    from audit_stage5_runtime_telemetry_v2 import _build_fixed_snapshot
except ModuleNotFoundError:  # imported by a test through a file spec
    telemetry_path = Path(__file__).with_name("audit_stage5_runtime_telemetry_v2.py")
    telemetry_spec = importlib.util.spec_from_file_location(
        "stage5_runtime_telemetry_v2_for_v3", telemetry_path
    )
    assert telemetry_spec is not None and telemetry_spec.loader is not None
    telemetry_module = importlib.util.module_from_spec(telemetry_spec)
    telemetry_spec.loader.exec_module(telemetry_module)
    _build_fixed_snapshot = telemetry_module._build_fixed_snapshot


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not len(array) or not np.all(np.isfinite(array)):
        raise ValueError("timing values must be one non-empty finite vector")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(np.max(array)),
    }


def environment_record() -> dict[str, Any]:
    thread_names = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
    try:
        numpy_configuration: Any = np.show_config(mode="dicts")
    except TypeError:  # pragma: no cover - compatibility with older NumPy
        numpy_configuration = "text_only_on_this_numpy_version"
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "logical_cpu_count": os.cpu_count(),
        "load_average_1_5_15": list(os.getloadavg()),
        "thread_environment": {name: os.environ.get(name) for name in thread_names},
        "numpy_configuration": numpy_configuration,
    }


def build_preview(
    snapshot: dict[str, Any], mode: str, *, capture_prefix_diagnostics: bool = False
) -> Any:
    common = {
        "q_rad": snapshot["observation"].as_array()[:2],
        "human_model": snapshot["human_model"],
        "cuff_allocator": snapshot["mpc"].cuff_allocator,
    }
    if mode in ("v2_prefix", "v2_prefix_uncached", "v2_prefix_reference"):
        common.update(
            {
                "state_rad_rad_s": snapshot["observation"].as_array(),
                "acceleration_limits_rad_s2": np.asarray(
                    snapshot["spec"].task_joint_acceleration_limit_rad_s2,
                    dtype=float,
                ),
            }
        )
    elif mode != "legacy_full20":
        raise ValueError(f"unknown benchmark mode: {mode}")
    preview = make_interface_aware_first_action_batch_preview(
        snapshot["execution_context"].preview_command_batch,
        snapshot["predictor"],
        snapshot["interface_state"],
        **common,
        capture_prefix_diagnostics=capture_prefix_diagnostics,
    )
    if mode == "v2_prefix_uncached":
        preview._reuse_cached_subsets = False
    if mode == "v2_prefix_reference":
        preview._use_optimized_prefix_numpy = False
    return preview


def one_solve(
    snapshot: dict[str, Any],
    mpc_snapshot: dict[str, Any],
    mode: str,
    *,
    capture_prefix_diagnostics: bool = False,
):
    mpc = snapshot["mpc"]
    mpc.__dict__.clear()
    mpc.__dict__.update(deepcopy(mpc_snapshot))
    preview = build_preview(
        snapshot, mode, capture_prefix_diagnostics=capture_prefix_diagnostics
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
        raise RuntimeError("fixed runtime snapshot produced NO_SAFE_ACTION")
    return np.asarray(action, dtype=float), diagnostics, wall_ms, process_ms, preview


def equivalence_gate() -> dict[str, Any]:
    """Compare former duplicate-subset execution with cached exact reuse."""

    tolerance = 1.0e-11

    def near_equal(left: Any, right: Any) -> bool:
        if isinstance(left, dict) and isinstance(right, dict):
            return left.keys() == right.keys() and all(
                near_equal(left[key], right[key]) for key in left
            )
        if isinstance(left, list) and isinstance(right, list):
            return len(left) == len(right) and all(
                near_equal(a, b) for a, b in zip(left, right, strict=True)
            )
        if isinstance(left, (float, np.floating)) and isinstance(
            right, (float, np.floating)
        ):
            return bool(np.isclose(left, right, atol=tolerance, rtol=0.0))
        return left == right

    snapshot = _build_fixed_snapshot()
    mpc_snapshot = deepcopy(snapshot["mpc_snapshot"])
    old_action, old_diag, _, _, old_preview = one_solve(
        snapshot, mpc_snapshot, "v2_prefix_uncached"
    )
    old_sequence = snapshot["mpc"].last_sequence.copy()
    new_action, new_diag, _, _, new_preview = one_solve(
        snapshot, mpc_snapshot, "v2_prefix"
    )
    new_sequence = snapshot["mpc"].last_sequence.copy()
    candidate_count = snapshot["mpc"].config.candidate_count
    old_populations = [
        item for item in old_preview._screen_cache if len(item[0]) == candidate_count
    ]
    new_populations = [
        item for item in new_preview._screen_cache if len(item[0]) == candidate_count
    ]
    population_rows: list[dict[str, Any]] = []
    for new in new_populations:
        new_actions, new_prediction = new
        matches = [
            old
            for old in old_populations
            if np.array_equal(old[0], new_actions)
        ]
        if not matches:
            raise RuntimeError("optimized CEM population has no former-path match")
        old_actions, old_prediction = matches[0]
        population_rows.append(
            {
                "candidate_actions_exact": bool(np.array_equal(old_actions, new_actions)),
                "candidate_feasibility_mask_exact": bool(
                    np.array_equal(old_prediction.feasible, new_prediction.feasible)
                ),
                "maximum_prefix_state_abs_difference": float(
                    np.max(
                        np.abs(
                            old_prediction.predicted_prefix_states_rad_rad_s
                            - new_prediction.predicted_prefix_states_rad_rad_s
                        )
                    )
                ),
                "maximum_prefix_margin_abs_difference": float(
                    np.max(
                        np.abs(
                            old_prediction.prefix_acceleration_margin_rad_s2
                            - new_prediction.prefix_acceleration_margin_rad_s2
                        )
                    )
                ),
                "maximum_executable_force_abs_difference": float(
                    np.max(
                        np.abs(
                            old_prediction.executable_batch.force_total_n
                            - new_prediction.executable_batch.force_total_n
                        )
                    )
                ),
            }
        )
    scalar_fields = (
        "status",
        "objective",
        "minimum_constraint_margin",
        "feasible_candidate_evaluations",
        "first_action_feasible_candidate_evaluations",
        "first_action_feasible_candidates_per_iteration",
        "first_action_filter_statuses_per_iteration",
        "selected_executable_force_norm_n",
        "selected_executable_force_margin_n",
        "selected_executable_command",
        "selected_safety_filter",
        "hold_population_constraint_audit",
    )
    matching_fields = {}
    for name in scalar_fields:
        if name in ("objective", "minimum_constraint_margin"):
            matching_fields[name] = bool(
                np.isclose(old_diag[name], new_diag[name], atol=tolerance, rtol=0.0)
            )
        else:
            matching_fields[name] = near_equal(old_diag[name], new_diag[name])
    passed = bool(
        np.allclose(old_action, new_action, atol=tolerance, rtol=0.0)
        and np.allclose(old_sequence, new_sequence, atol=tolerance, rtol=0.0)
        and all(matching_fields.values())
        and all(
            row["candidate_actions_exact"]
            and row["candidate_feasibility_mask_exact"]
            and row["maximum_prefix_state_abs_difference"] <= tolerance
            and row["maximum_prefix_margin_abs_difference"] <= tolerance
            and row["maximum_executable_force_abs_difference"] <= tolerance
            for row in population_rows
        )
    )
    return {
        "passed": passed,
        "absolute_tolerance": tolerance,
        "selected_first_action_max_abs_difference": float(
            np.max(np.abs(old_action - new_action))
        ),
        "selected_sequence_max_abs_difference": float(
            np.max(np.abs(old_sequence - new_sequence))
        ),
        "diagnostic_fields_exact": matching_fields,
        "cem_populations": population_rows,
    }


def build_benchmark_snapshot(label: str = "nominal") -> dict[str, Any]:
    snapshot = _build_fixed_snapshot()
    if label == "nominal":
        return snapshot
    if label == "progressive_theta5":
        from traction_mpc_stage5.human_model_replication import _model

        snapshot["human_model"] = _model(
            snapshot["human_model"].geometry,
            (0.999984460611625, 1.000264489157326, 1.087992468652811),
        )
        return snapshot
    raise ValueError(f"unknown fixed snapshot label: {label}")


def run_benchmark(
    *, mode: str, warmup: int, solves: int, snapshot_label: str = "nominal"
) -> dict[str, Any]:
    if warmup < 1 or solves < 20:
        raise ValueError("benchmark requires at least one warmup and 20 solves")
    snapshot = build_benchmark_snapshot(snapshot_label)
    mpc_snapshot = deepcopy(snapshot["mpc_snapshot"])
    for _ in range(warmup):
        one_solve(snapshot, mpc_snapshot, mode)

    wall: list[float] = []
    process: list[float] = []
    sections: dict[str, list[float]] = defaultdict(list)
    selected: np.ndarray | None = None
    gc_before = [dict(item) for item in gc.get_stats()]
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for _ in range(solves):
        action, diagnostics, wall_ms, process_ms, _ = one_solve(
            snapshot, mpc_snapshot, mode
        )
        if selected is None:
            selected = action.copy()
        elif not np.array_equal(action, selected):
            raise RuntimeError("restored fixed snapshot did not reproduce its action")
        wall.append(wall_ms)
        process.append(process_ms)
        for name, value in diagnostics["implementation_timing_ms"].items():
            sections[str(name)].append(float(value))
    gc_after = [dict(item) for item in gc.get_stats()]
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    assert selected is not None
    return {
        "schema": "stage5_fixed_snapshot_runtime_regression_v3",
        "mode": mode,
        "measurement_boundary": "wall/process immediately around GoalDirectedHumanSpaceMPC.solve_goal only",
        "excluded_from_timing": [
            "Human-ID and future validation",
            "progressive authority logic",
            "plant stepping and task-state update",
            "trace/JSON logging",
            "plotting/reporting",
        ],
        "fixed_snapshot": {
            "label": snapshot_label,
            "phase": "OUTBOUND",
            "horizon_candidates_iterations": [
                snapshot["mpc"].config.horizon_steps,
                snapshot["mpc"].config.candidate_count,
                snapshot["mpc"].config.cem_iterations,
            ],
            "warmup_solves": warmup,
            "measured_solves": solves,
            "mpc_and_rng_state_restored_each_solve": True,
            "selected_action_nm": selected.tolist(),
        },
        "wall_ms": summarize(wall),
        "process_cpu_ms": summarize(process),
        "wall_minus_process_ms": summarize(
            (np.asarray(wall) - np.asarray(process)).tolist()
        ),
        "mean_process_cpu_to_wall_percent": float(
            100.0 * np.sum(process) / np.sum(wall)
        ),
        "section_ms": {name: summarize(values) for name, values in sections.items()},
        "system": {
            "environment": environment_record(),
            "gc_before": gc_before,
            "gc_after": gc_after,
            "max_rss_platform_units_before": rss_before,
            "max_rss_platform_units_after": rss_after,
        },
        "controller_or_scientific_change": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=(
            "v2_prefix",
            "v2_prefix_reference",
            "v2_prefix_uncached",
            "legacy_full20",
        ),
        required=True,
    )
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--solves", type=int, default=300)
    parser.add_argument(
        "--snapshot", choices=("nominal", "progressive_theta5"), default="nominal"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--equivalence-only", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    result = (
        {
            "schema": "stage5_runtime_subset_cache_equivalence_v1",
            "equivalence": equivalence_gate(),
        }
        if args.equivalence_only
        else run_benchmark(
            mode=args.mode,
            warmup=args.warmup,
            solves=args.solves,
            snapshot_label=args.snapshot,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            (
                result
                if args.equivalence_only
                else {"mode": args.mode, "wall_ms": result["wall_ms"]}
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
