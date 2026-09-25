"""Reproduce frozen pre-step startup exceptions without changing the controller.

The original loaded-runtime initializer is called. Temporary wrappers only
record its IK return and initial-support candidate before delegating to the
original validation; no MuJoCo integration or production source is changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1


def _one(case_path: Path) -> dict:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    human, geometry, spec, _ = hidden_plant(case)
    record = {"case_key": case["case_key"], "case_path": str(case_path),
              "evidence": "isolated_development_replay_of_previously_failed_formal_case",
              "physical_mujoco_steps_executed": 0}
    original_prepare = HumanWaypointMPCShadowContractV1.prepare
    original_ik = runtime.solve_cr12_stage5_ik

    def record_ik(*args, **kwargs):
        result = original_ik(*args, **kwargs)
        record["loaded_preload_ik_success"] = True
        record["loaded_preload_robot_q_rad"] = np.asarray(result).tolist()
        return result

    def record_prepare(self, candidate):
        if candidate.label == "initial_support":
            start = np.asarray(self.spec.start_return_target_rad)
            goal = np.asarray(self.spec.outbound_goal_target_rad)
            measured = np.asarray(candidate.q_waypoint_rad)
            candidate_axis = measured - start
            phase_axis = goal - start
            tolerance = np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            record["initial_support"] = {
                "registered_physical_start_deg": np.rad2deg(start).tolist(),
                "registered_goal_deg": np.rad2deg(goal).tolist(),
                "causal_nominal_prior_estimate_deg": np.rad2deg(measured).tolist(),
                "estimate_minus_physical_initial_deg": np.rad2deg(candidate_axis).tolist(),
                "phase_axis_deg": np.rad2deg(phase_axis).tolist(),
                "phase_dot_candidate_rad2": float(phase_axis @ candidate_axis),
                "inside_origin_tolerance": bool(np.all(np.abs(candidate_axis) <= tolerance+1e-12)),
                "source_predicate_rejects": bool(
                    float(phase_axis @ candidate_axis) < -1e-12
                    and not np.all(np.abs(candidate_axis) <= tolerance+1e-12)),
            }
        return original_prepare(self, candidate)

    runtime.solve_cr12_stage5_ik = record_ik
    HumanWaypointMPCShadowContractV1.prepare = record_prepare
    try:
        try:
            runtime._initialize_loaded_runtime("startup_dgn_pre_step", np.asarray(
                spec.start_return_target_rad), spec=spec,
                physical_human=human, physical_geometry=geometry)
        except Exception as error:
            record["observed_result"] = f"{type(error).__name__}: {error}"
        else:
            record["observed_result"] = "INITIALIZATION_SUCCEEDED"
    finally:
        runtime.solve_cr12_stage5_ik = original_ik
        HumanWaypointMPCShadowContractV1.prepare = original_prepare
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = [_one(path) for path in args.case]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps([{"case_key": row["case_key"],
                       "result": row["observed_result"],
                       "ik_success": row.get("loaded_preload_ik_success"),
                       "predicate_rejects": row.get("initial_support", {}).get(
                           "source_predicate_rejects")} for row in rows], sort_keys=True))


if __name__ == "__main__":
    main()
