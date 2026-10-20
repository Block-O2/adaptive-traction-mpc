#!/usr/bin/env python3
"""Profile complete CEM solves with exact first-action command screening.

This is a fixed-state engineering micro-profile.  It does not advance the
plant, run a trajectory, or write into a scientific result directory.
"""

from __future__ import annotations

import argparse
import json
from time import perf_counter_ns

import numpy as np

from traction_mpc_stage3.frames import (
    ATTACHMENT_FROM_CUFF,
    ENGINEERING_ATTACHMENT_FROM_CUFF,
)
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import OneShotHumanEstimatorV2
from traction_mpc_stage4.executable_command import (
    make_stage4_first_action_batch_preview,
)
from traction_mpc_stage4.measurement import CausalMeasurementLayer, sensor_realism_cases
from traction_mpc_stage4.mpc import SAFE_ACTION, HumanSpaceMPC
from traction_mpc_stage4.reference import teaching_reference
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument(
        "--geometry", choices=("legacy", "engineering-140mm"), default="legacy"
    )
    args = parser.parse_args()
    if args.warmup < 0 or args.iterations <= 0:
        raise ValueError("warmup must be nonnegative and iterations positive")

    attachment_from_cuff = (
        ATTACHMENT_FROM_CUFF
        if args.geometry == "legacy"
        else ENGINEERING_ATTACHMENT_FROM_CUFF
    )
    reference = teaching_reference(0.0)
    plant = SensorBoundaryStage4Plant(
        HUMAN,
        attachment_from_cuff=attachment_from_cuff,
    )
    truth = plant.reset(reference.q_rad)
    measurement = CausalMeasurementLayer(sensor_realism_cases()[0], truth).current
    estimator = OneShotHumanEstimatorV2(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        reference.q_rad,
    )
    state = estimator.geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    allocator = default_engineering_cuff_allocator()
    controller = HumanSpaceMPC(cuff_allocator=allocator)
    config = controller.config
    dimensions = (
        config.horizon_steps,
        config.candidate_count,
        config.elite_count,
        config.cem_iterations,
    )
    if dimensions != (15, 32, 6, 2):
        raise RuntimeError(f"unexpected scientific dimensions: {dimensions}")
    latency_ns = np.empty(args.iterations)
    status_counts: dict[str, int] = {}
    for index in range(args.warmup + args.iterations):
        start = perf_counter_ns()
        preview = make_stage4_first_action_batch_preview(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=estimator.model,
            cuff_allocator=allocator,
            reference=reference,
        )
        action, diagnostics = controller.solve(
            state,
            0.0,
            teaching_reference,
            estimator.model,
            first_action_batch_preview=preview,
        )
        elapsed = perf_counter_ns() - start
        status = str(diagnostics["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        if action is None or status != SAFE_ACTION:
            raise RuntimeError("nominal timing fixture produced NO_SAFE_ACTION")
        if index >= args.warmup:
            latency_ns[index - args.warmup] = elapsed

    latency_ms = latency_ns / 1.0e6
    mean_ms = float(np.mean(latency_ms))
    print(
        json.dumps(
            {
                "evidence_category": "engineering_microprofile_not_scientific",
                "geometry": args.geometry,
                "warmup": args.warmup,
                "iterations": args.iterations,
                "horizon_steps": config.horizon_steps,
                "candidate_count": config.candidate_count,
                "elite_count": config.elite_count,
                "cem_iterations": config.cem_iterations,
                "latency_ms": {
                    "mean": mean_ms,
                    "median": float(np.median(latency_ms)),
                    "p95": float(np.percentile(latency_ms, 95.0)),
                    "max": float(np.max(latency_ms)),
                    "over_20_ms_count": int(
                        np.count_nonzero(latency_ms > 20.0)
                    ),
                },
                "effective_hz_from_mean": 1000.0 / mean_ms,
                "status_counts_including_warmup": status_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
