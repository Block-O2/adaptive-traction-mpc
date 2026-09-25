"""Evaluation-only aligned reference/physical table-gap diagnosis.

Hidden geometry is used exclusively after a completed run, not by production
reference generation or control. Capsule/cylinder support functions are
analytic; the report distinguishes these from native MuJoCo contact force.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage3.coupled import (
    BED_HEIGHT_M, SHANK_RADIUS_M, THIGH_RADIUS_M,
    SLEEVE_HALF_LENGTH_M, SLEEVE_OUTER_RADIUS_M,
)
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant


STAGE = Path(__file__).resolve().parents[1]
BASE = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"


def gaps(q: np.ndarray, human: object, geometry: object) -> dict[str, np.ndarray]:
    """Signed distances for the physical hidden limb; evaluation only."""
    q = np.atleast_2d(np.asarray(q, dtype=float))
    origin = geometry.world_from_human.translation
    x_axis = geometry.world_from_human.rotation[:, 0]
    z_axis = geometry.world_from_human.rotation[:, 2]
    thigh_direction = np.cos(q[:, 0, None]) * x_axis + np.sin(q[:, 0, None]) * z_axis
    shank_angle = q[:, 0] - q[:, 1]
    shank_direction = np.cos(shank_angle[:, None]) * x_axis + np.sin(shank_angle[:, None]) * z_axis
    hip = np.broadcast_to(origin, thigh_direction.shape)
    knee = hip + human.thigh_length_m * thigh_direction
    ankle = knee + human.shank_length_m * shank_direction
    sleeve_a = knee + (human.sleeve_center_m - SLEEVE_HALF_LENGTH_M) * shank_direction
    sleeve_b = knee + (human.sleeve_center_m + SLEEVE_HALF_LENGTH_M) * shank_direction
    # A cylinder's vertical support radius is R times the vertical projection
    # of the plane perpendicular to its unit axis. This is not a contact force.
    sleeve_radial_z = SLEEVE_OUTER_RADIUS_M * np.sqrt(
        np.maximum(0.0, 1.0 - shank_direction[:, 2] ** 2))
    return {
        "thigh": np.minimum(hip[:, 2], knee[:, 2]) - THIGH_RADIUS_M - BED_HEIGHT_M,
        "shank": np.minimum(knee[:, 2], ankle[:, 2]) - SHANK_RADIUS_M - BED_HEIGHT_M,
        "sleeve": np.minimum(sleeve_a[:, 2], sleeve_b[:, 2]) - sleeve_radial_z - BED_HEIGHT_M,
    }


def first_event(time: np.ndarray, stage: np.ndarray, distance: np.ndarray) -> dict[str, object]:
    first = np.flatnonzero(distance < -1e-9)
    minimum = int(np.argmin(distance))
    return {
        "first_negative_time_s": None if not len(first) else float(time[first[0]]),
        "first_negative_stage": None if not len(first) else str(stage[first[0]]),
        "first_negative_distance_m": None if not len(first) else float(distance[first[0]]),
        "minimum_signed_distance_m": float(distance[minimum]),
        "minimum_time_s": float(time[minimum]),
        "minimum_stage": str(stage[minimum]),
        "negative_boundary_count": int(len(first)),
    }


def analyze(case_path: Path, run: Path) -> dict[str, object]:
    case = json.loads(case_path.read_text())
    human, geometry, _, _ = hidden_plant(case)
    with np.load(run / "trace.npz", allow_pickle=True) as trace:
        time = np.asarray(trace["time_s"], dtype=float)
        stage = np.asarray(trace["stage"])
        q_ref = np.asarray(trace["reference_q_rad"], dtype=float)
        q_hat = np.asarray(trace["estimated_human_state_rad_rad_s"], dtype=float)[:, :2]
        q_true = np.asarray(trace["evaluation_only_human_state_rad_rad_s"], dtype=float)[:, :2]
        cuff_desired = np.asarray(trace["desired_cuff_position_world_m"], dtype=float)
        cuff_actual = np.asarray(trace["physical_cuff_position_world_m"], dtype=float)
        cuff_error = np.linalg.norm(cuff_desired - cuff_actual, axis=1)
        finite_cuff_error = cuff_error[np.isfinite(cuff_error)]
        requested = gaps(q_ref, human, geometry)
        estimated = gaps(q_hat, human, geometry)
        actual = gaps(q_true, human, geometry)
        report = {
            "schema": "dev_d_reference_truth_evaluation_only_v1",
            "case_key": case["case_key"],
            "case_path": str(case_path),
            "run_path": str(run),
            "geometry_source": "HIDDEN_PHYSICAL_CASE_EVALUATION_ONLY",
            "boundary_count": len(time),
            "sample_interval_s": 0.005,
            "requested": {name: first_event(time, stage, d) for name, d in requested.items()},
            "estimated_evaluated_with_truth_geometry": {
                name: first_event(time, stage, d) for name, d in estimated.items()},
            "actual_evaluation_only": {
                name: first_event(time, stage, d) for name, d in actual.items()},
            "cuff_position_error_m": {
                "maximum": (None if not len(finite_cuff_error)
                            else float(np.max(finite_cuff_error))),
                "at_first_actual_sleeve_negative": None,
            },
        }
        first = np.flatnonzero(actual["sleeve"] < -1e-9)
        if len(first):
            i = int(first[0])
            report["cuff_position_error_m"]["at_first_actual_sleeve_negative"] = (
                None if not np.isfinite(cuff_error[i]) else float(cuff_error[i]))
            report["first_actual_sleeve_negative_snapshot"] = {
                "time_s": float(time[i]), "stage": str(stage[i]),
                "q_ref_rad": q_ref[i].tolist(), "q_hat_rad": q_hat[i].tolist(),
                "q_true_rad_evaluation_only": q_true[i].tolist(),
                "requested_sleeve_gap_m": float(requested["sleeve"][i]),
                "actual_sleeve_gap_m": float(actual["sleeve"][i]),
                "desired_cuff_position_world_m": (None if not np.all(np.isfinite(cuff_desired[i]))
                                                  else cuff_desired[i].tolist()),
                "actual_cuff_position_world_m": cuff_actual[i].tolist(),
                "cuff_position_error_m": (None if not np.isfinite(cuff_error[i])
                                          else float(cuff_error[i])),
            }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = analyze(args.case, args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"case": report["case_key"], "requested": report["requested"],
                      "actual": report["actual_evaluation_only"]}, sort_keys=True))


if __name__ == "__main__":
    main()
