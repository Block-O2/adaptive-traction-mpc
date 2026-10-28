#!/usr/bin/env python3
"""Paired fixed-snapshot benchmark for NumPy and native prefix backends."""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import time
from typing import Any

import numpy as np


RUNTIME_PATH = Path(__file__).with_name("audit_stage5_runtime_regression_v3.py")
SPEC = importlib.util.spec_from_file_location("stage5_runtime_for_native_bench", RUNTIME_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


def _summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(np.max(array)),
    }


def _run_one(
    snapshot: dict[str, Any], mpc_snapshot: dict[str, Any], mode: str
) -> tuple[np.ndarray, np.ndarray, float, float, dict[str, float]]:
    process_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    action, diagnostics, _, _, _ = RUNTIME.one_solve(snapshot, mpc_snapshot, mode)
    wall_ms = (time.perf_counter_ns() - wall_start) / 1.0e6
    process_ms = (time.process_time_ns() - process_start) / 1.0e6
    return (
        action,
        snapshot["mpc"].last_sequence.copy(),
        wall_ms,
        process_ms,
        diagnostics["implementation_timing_ms"],
    )


def benchmark_snapshot(label: str, warmup: int, solves: int) -> dict[str, Any]:
    snapshot = RUNTIME.build_benchmark_snapshot(label)
    mpc_snapshot = deepcopy(snapshot["mpc_snapshot"])
    modes = ("v2_prefix", "v2_prefix_native")
    for _ in range(warmup):
        for mode in modes:
            _run_one(snapshot, mpc_snapshot, mode)

    records = {
        mode: {
            "wall_ms": [],
            "process_ms": [],
            "prefix_ms": [],
            "non_prefix_ms": [],
            "sections": defaultdict(list),
            "action": None,
            "sequence": None,
        }
        for mode in modes
    }
    for index in range(solves):
        order = modes if index % 2 == 0 else tuple(reversed(modes))
        for mode in order:
            action, sequence, wall_ms, process_ms, sections = _run_one(
                snapshot, mpc_snapshot, mode
            )
            record = records[mode]
            if record["action"] is None:
                record["action"] = action.copy()
                record["sequence"] = sequence.copy()
            elif not np.array_equal(action, record["action"]) or not np.array_equal(
                sequence, record["sequence"]
            ):
                raise RuntimeError("fixed snapshot was not deterministic")
            record["wall_ms"].append(wall_ms)
            record["process_ms"].append(process_ms)
            record["prefix_ms"].append(
                float(sections["first_action_executable_screening"])
            )
            record["non_prefix_ms"].append(
                wall_ms - float(sections["first_action_executable_screening"])
            )
            for name, value in sections.items():
                record["sections"][name].append(float(value))

    output: dict[str, Any] = {
        "label": label,
        "warmup_solves_per_backend": warmup,
        "measured_solves_per_backend": solves,
        "paired_alternating_order": True,
        "backends": {},
    }
    for mode, record in records.items():
        output["backends"][mode] = {
            "total_wall_ms": _summary(record["wall_ms"]),
            "process_cpu_ms": _summary(record["process_ms"]),
            "prefix_screen_ms": _summary(record["prefix_ms"]),
            "non_prefix_wall_ms": _summary(record["non_prefix_ms"]),
            "sections_ms": {
                name: _summary(values)
                for name, values in record["sections"].items()
            },
            "selected_action_nm": record["action"].tolist(),
        }
    reference = output["backends"]["v2_prefix"]
    native = output["backends"]["v2_prefix_native"]
    output["speedup"] = {
        "prefix_mean": (
            reference["prefix_screen_ms"]["mean"]
            / native["prefix_screen_ms"]["mean"]
        ),
        "total_mean": (
            reference["total_wall_ms"]["mean"]
            / native["total_wall_ms"]["mean"]
        ),
        "total_p95": (
            reference["total_wall_ms"]["p95"]
            / native["total_wall_ms"]["p95"]
        ),
    }
    output["selected_action_exact"] = bool(
        np.array_equal(records[modes[0]]["action"], records[modes[1]]["action"])
    )
    output["selected_sequence_exact"] = bool(
        np.array_equal(
            records[modes[0]]["sequence"], records[modes[1]]["sequence"]
        )
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--solves", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmup < 1 or args.solves < 20:
        raise ValueError("benchmark requires warmup >= 1 and solves >= 20")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    result = {
        "schema": "stage5_native_prefix_paired_benchmark_v1",
        "snapshots": [
            benchmark_snapshot(label, args.warmup, args.solves)
            for label in ("nominal", "progressive_theta5")
        ],
        "controller_or_scientific_change": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                row["label"]: {
                    mode: {
                        "prefix": values["prefix_screen_ms"],
                        "total": values["total_wall_ms"],
                    }
                    for mode, values in row["backends"].items()
                }
                for row in result["snapshots"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
