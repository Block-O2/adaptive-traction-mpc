#!/usr/bin/env python3
"""Frozen-snapshot region profile for the unchanged Stage-5 V2 prefix screen."""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import time
import tracemalloc
from typing import Any

import numpy as np


AUDIT_PATH = Path(__file__).with_name("audit_stage5_runtime_regression_v3.py")
SPEC = importlib.util.spec_from_file_location("stage5_runtime_v3_for_prefix", AUDIT_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _sum_screen_records(records: list[dict[str, float]]) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    for record in records:
        for name, seconds in record.items():
            result[name] += 1000.0 * float(seconds)
    return dict(result)


def profile_prefix_regions(*, warmup: int, solves: int) -> dict[str, Any]:
    """Profile both CEM prefix screens in each deterministic solve."""

    if warmup < 1 or solves < 20:
        raise ValueError("profile requires warmup >= 1 and solves >= 20")
    snapshot = AUDIT._build_fixed_snapshot()
    mpc_snapshot = deepcopy(snapshot["mpc_snapshot"])
    for _ in range(warmup):
        AUDIT.one_solve(snapshot, mpc_snapshot, "v2_prefix")

    wall_ms: list[float] = []
    process_ms: list[float] = []
    regions: dict[str, list[float]] = defaultdict(list)
    screen_count: list[int] = []
    for _ in range(solves):
        mpc = snapshot["mpc"]
        mpc.__dict__.clear()
        mpc.__dict__.update(deepcopy(mpc_snapshot))
        preview = AUDIT.build_preview(snapshot, "v2_prefix")
        preview._profile_prefix_regions = True
        process_start = time.process_time_ns()
        wall_start = time.perf_counter_ns()
        action, _ = mpc.solve_goal(
            snapshot["observation"],
            snapshot["task_state"],
            snapshot["spec"],
            snapshot["human_model"],
            first_action_batch_preview=preview,
        )
        wall_ms.append((time.perf_counter_ns() - wall_start) / 1.0e6)
        process_ms.append((time.process_time_ns() - process_start) / 1.0e6)
        if action is None:
            raise RuntimeError("profile snapshot produced NO_SAFE_ACTION")
        screen_count.append(len(preview.prefix_region_profiles_s))
        for name, value in _sum_screen_records(
            preview.prefix_region_profiles_s
        ).items():
            regions[name].append(value)

    # A separate solve records Python-visible peak allocation.  Tracemalloc is
    # intentionally outside the representative runtime sample because its
    # tracing overhead is substantial.
    mpc = snapshot["mpc"]
    mpc.__dict__.clear()
    mpc.__dict__.update(deepcopy(mpc_snapshot))
    preview = AUDIT.build_preview(snapshot, "v2_prefix")
    tracemalloc.start()
    before_current, _ = tracemalloc.get_traced_memory()
    action, _ = mpc.solve_goal(
        snapshot["observation"],
        snapshot["task_state"],
        snapshot["spec"],
        snapshot["human_model"],
        first_action_batch_preview=preview,
    )
    after_current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if action is None:
        raise RuntimeError("allocation snapshot produced NO_SAFE_ACTION")

    return {
        "schema": "stage5_prefix_screen_region_profile_v1",
        "snapshot": "runtime_v3_fixed_outbound",
        "candidate_batch": snapshot["mpc"].config.candidate_count,
        "cem_iterations": snapshot["mpc"].config.cem_iterations,
        "prefix_times_ms": [5, 10, 15, 20],
        "physical_substep_ms": 0.25,
        "substeps_per_screen": 80,
        "screen_calls_per_solve": sorted(set(screen_count)),
        "warmup": warmup,
        "solves": solves,
        "instrumented_wall_ms": AUDIT.summarize(wall_ms),
        "instrumented_process_cpu_ms": AUDIT.summarize(process_ms),
        "instrumented_region_ms_per_solve": {
            name: AUDIT.summarize(values) for name, values in regions.items()
        },
        "instrumented_region_mean_sum_ms": float(
            sum(np.mean(values) for values in regions.values())
        ),
        "python_visible_allocation_bytes_one_solve": {
            "net_current_delta": int(after_current - before_current),
            "peak_above_start": int(peak - before_current),
        },
        "note": (
            "Region timers are diagnostic and add overhead; production timing "
            "must use the uninstrumented benchmark."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--solves", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    result = profile_prefix_regions(warmup=args.warmup, solves=args.solves)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
