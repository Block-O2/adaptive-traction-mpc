"""Micro-profile the side-effect-free executable-command preview."""

from __future__ import annotations

import argparse
import json
from time import perf_counter_ns

import numpy as np

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2
from traction_mpc_stage3.frames import (
    ATTACHMENT_FROM_CUFF,
    ENGINEERING_ATTACHMENT_FROM_CUFF,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument(
        "--geometry", choices=("legacy", "engineering-140mm"), default="legacy"
    )
    args = parser.parse_args()
    if args.iterations <= 0 or args.warmup < 0:
        raise ValueError("iterations must be positive and warmup nonnegative")

    geometry = (
        ATTACHMENT_FROM_CUFF
        if args.geometry == "legacy"
        else ENGINEERING_ATTACHMENT_FROM_CUFF
    )
    plant = CoupledUR10eHumanV2(attachment_from_cuff=geometry)
    observation = plant.reset(np.radians([5.0, 10.0]))
    inputs = (
        observation.attachment_position_m + np.array([2.0e-4, -1.0e-4, 3.0e-4]),
        np.array([0.002, -0.003, 0.001]),
        observation.attachment_rotation_matrix,
        np.array([0.01, 0.0, -0.02]),
        np.array([4.0, -3.0, 2.0, 0.2, -0.1, 0.3]),
    )
    for _ in range(args.warmup):
        plant.preview_executable_command(*inputs)
    latency_ns = np.empty(args.iterations)
    for index in range(args.iterations):
        start = perf_counter_ns()
        plant.preview_executable_command(*inputs)
        latency_ns[index] = perf_counter_ns() - start
    latency_us = latency_ns / 1000.0
    print(
        json.dumps(
            {
                "geometry": args.geometry,
                "iterations": args.iterations,
                "warmup": args.warmup,
                "control_period_us": 5000.0,
                "latency_us": {
                    "mean": float(np.mean(latency_us)),
                    "p95": float(np.percentile(latency_us, 95.0)),
                    "max": float(np.max(latency_us)),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
