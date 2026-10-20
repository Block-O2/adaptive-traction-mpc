#!/usr/bin/env python3
"""Run the versioned physical CR12 adaptive-integration development case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--disable-robot-actuation", action="store_true")
    parser.add_argument("--simulate-planning-latency", action="store_true")
    parser.add_argument("--task-timeout-s", type=float, default=30.0)
    args = parser.parse_args()
    result = run_executed_case(
        args.output_dir,
        actuation_enabled=not args.disable_robot_actuation,
        task_timeout_s=args.task_timeout_s,
        simulate_planning_latency=args.simulate_planning_latency,
    )
    print(
        json.dumps(
            _jsonable({
                "status": result["status"],
                "abort_reason": result["abort_reason"],
                "actuation_enabled": result["actuation_enabled"],
                "commissioning": result["commissioning"],
                "task": result["task"],
                "output_dir": str(args.output_dir),
            }),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
