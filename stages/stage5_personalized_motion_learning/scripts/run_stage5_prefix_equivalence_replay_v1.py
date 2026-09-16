#!/usr/bin/env python3
"""Paired implementation-only replay for the Stage-5 prefix refactor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


TOLERANCE = 1.0e-10


def _maximum_difference(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(left) - np.asarray(right))))


def run_replay(output_dir: Path) -> dict[str, Any]:
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    common = {
        "spec": PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        "maximum_duration_s": 30.5,
        "record_selected_horizon_diagnostics": True,
        "use_loaded_local_hold": True,
        "use_bumpless_return_handoff": True,
        "initialize_loaded_equilibrium_with_plant_truth": True,
        "planning_physical_force_ceiling_n": 180.0,
        "planning_joint_velocity_ceiling_rad_s": tuple(np.radians((15.0, 25.0))),
        "mpc_config": HumanMPCConfig(random_seed=20260824),
    }
    reference = run_goal_mpc_smoke(
        output / "reference",
        plant_case_name="prefix_equivalence_reference",
        use_optimized_prefix_numpy=False,
        **common,
    )
    optimized = run_goal_mpc_smoke(
        output / "optimized",
        plant_case_name="prefix_equivalence_optimized",
        use_optimized_prefix_numpy=True,
        **common,
    )
    with np.load(output / "reference" / "trace.npz") as loaded:
        reference_trace = {name: loaded[name] for name in loaded.files}
    with np.load(output / "optimized" / "trace.npz") as loaded:
        optimized_trace = {name: loaded[name] for name in loaded.files}

    exact_fields = (
        "task_phase",
        "selected_v2_prefix_acceleration_feasible",
        "control_human_model_version",
    )
    numerical_fields = (
        "estimated_state_rad_rad_s",
        "evaluation_human_q_rad",
        "evaluation_human_dq_rad_s",
        "executed_generalized_action_nm",
        "executed_command_wrench_world",
        "physical_cuff_force_world_n",
        "physical_cuff_moment_world_nm",
        "deployable_realized_acceleration_rad_s2",
        "selected_v2_prefix_acceleration_rad_s2",
        "selected_v2_prefix_state_rad_rad_s",
        "selected_v2_prefix_acceleration_margin_rad_s2",
    )
    exact = {
        name: bool(np.array_equal(reference_trace[name], optimized_trace[name]))
        for name in exact_fields
        if name in reference_trace and name in optimized_trace
    }
    numerical = {
        name: _maximum_difference(reference_trace[name], optimized_trace[name])
        for name in numerical_fields
    }
    summary_fields = (
        "task_status",
        "true_episode_complete",
        "abort_reason",
        "phase_transitions",
        "force_gate_event_count",
        "brake_event_count",
        "safety_filter_status_counts",
        "mpc_status_counts",
        "mujoco_warning_counts",
    )
    summary_equal = {
        name: reference.get(name) == optimized.get(name) for name in summary_fields
    }
    passed = bool(
        all(exact.values())
        and max(numerical.values()) <= TOLERANCE
        and all(summary_equal.values())
    )
    result = {
        "schema": "stage5_prefix_equivalence_replay_v1",
        "passed": passed,
        "absolute_tolerance": TOLERANCE,
        "reference_result": reference.get("task_status"),
        "optimized_result": optimized.get("task_status"),
        "reference_runtime_ms": reference.get("mpc_runtime_ms"),
        "optimized_runtime_ms": optimized.get("mpc_runtime_ms"),
        "summary_fields_equal": summary_equal,
        "exact_trace_fields": exact,
        "numerical_trace_max_abs_difference": numerical,
        "control_or_scientific_parameter_change": False,
    }
    (output / "comparison.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_replay(args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
