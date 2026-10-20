"""Evaluation-only signed geometry sweep of executed 5 ms trace boundaries.

This repositions an isolated diagnostic MjData from *recorded* physical q and
CR12 q; it never advances or influences the controller/plant execution.
It is a discrete geometric audit, not continuous-time collision proof.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant


STAGE = Path(__file__).resolve().parents[1]
ASSEMBLY = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v1/cases"
NOMINAL = STAGE / "configs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/nominal_reference_rigid_table_v1.json"


def _distance(model, data, left: list[int], right: list[int]) -> tuple[float, list[str] | None]:
    nearest = None
    minimum = math.inf
    segment = np.zeros(6)
    for a in left:
        for b in right:
            if a == b:
                continue
            value = float(mujoco.mj_geomDistance(model, data, a, b, 10.0, segment))
            if value < minimum:
                minimum = value
                nearest = [model.geom(a).name, model.geom(b).name]
    return minimum, nearest


def audit_one(case_path: Path, run_dir: Path) -> dict:
    case = json.loads(case_path.read_text())
    human, geometry, _, _ = hidden_plant(case)
    plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
    model, data = plant.model, plant.data
    trace = np.load(run_dir / "trace.npz", allow_pickle=True)
    times = np.asarray(trace["time_s"], dtype=float)
    phases = [str(x) for x in trace["stage"]]
    qh = np.asarray(trace["evaluation_only_human_state_rad_rad_s"], dtype=float)[:, :2]
    qr = np.asarray(trace["cr12_q_rad"], dtype=float)
    if not (len(times) == len(qh) == len(qr) == len(phases)):
        raise ValueError("unaligned boundary trace")
    bed = [plant.bed_geom_id]
    human_geoms = [model.geom("thigh_geom").id, model.geom("shank_geom").id]
    modeled = {
        "thigh_bed": ([human_geoms[0]], bed),
        "shank_bed": ([human_geoms[1]], bed),
        "sleeve_bed": ([model.geom("sleeve_geom").id], bed),
        "cuff_bar_bed": ([model.geom("stage5_cuff_bar_geom").id], bed),
        "adapter_bed": ([model.geom("cuff_adapter_geom").id], bed),
    }
    arm = [i for i in sorted(plant.robot_collision_geom_ids)
           if model.geom(i).name != "cuff_adapter_geom"
           and model.body(int(model.geom_bodyid[i])).name
           not in {"xMateCR12_base", "xMateCR12_link1"}]
    modeled["articulated_robot_bed"] = (arm, bed)
    modeled["articulated_robot_human"] = (arm, human_geoms)
    modeled["adapter_human"] = ([model.geom("cuff_adapter_geom").id], human_geoms)
    minima = {name: {"distance_m": math.inf, "time_s": None,
                     "stage": None, "nearest_pair": None}
              for name in modeled}
    stage_minima: dict[str, dict[str, float]] = {}
    for k, (t, stage) in enumerate(zip(times, phases, strict=True)):
        data.qpos[plant.human_qpos_indices] = qh[k]
        data.qpos[plant.robot_qpos_indices] = qr[k]
        mujoco.mj_forward(model, data)
        stage_minima.setdefault(stage, {name: math.inf for name in modeled})
        for name, (left, right) in modeled.items():
            value, pair = _distance(model, data, left, right)
            stage_minima[stage][name] = min(stage_minima[stage][name], value)
            if value < minima[name]["distance_m"]:
                minima[name] = {"distance_m": value, "time_s": float(t),
                                "stage": stage, "nearest_pair": pair}
    return {"schema": "rigid_table_v1_executed_boundary_geometry_audit",
            "case_key": case["case_key"],
            "evidence_category": "evaluation_only_reconstruction_from_executed_trace",
            "trace_boundary_count": len(times),
            "time_start_s": float(times[0]), "time_end_s": float(times[-1]),
            "sampling_limit": "recorded 5 ms boundaries; not continuous-time or all 0.25 ms physics states",
            "hidden_truth_used_as_controller_input": False,
            "minimum_signed_distances": minima,
            "minimum_by_stage_m": stage_minima}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.mkdir(parents=True)
    rows = []
    for run in sorted(args.runs.iterdir()):
        if not (run / "trace.npz").exists():
            continue
        case_path = NOMINAL if run.name == "nominal_reference_rigid_table_v1" else ASSEMBLY / f"{run.name}.json"
        result = audit_one(case_path, run)
        (args.output / f"{run.name}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        rows.append({"case_key": run.name,
                     "minimum_signed_distances_m": {
                         name: item["distance_m"] for name, item
                         in result["minimum_signed_distances"].items()},
                     "worst_stage": min(result["minimum_signed_distances"].values(),
                                        key=lambda item: item["distance_m"])["stage"]})
        print(json.dumps(rows[-1], sort_keys=True), flush=True)
    (args.output / "SUMMARY.json").write_text(
        json.dumps({"schema": "rigid_table_v1_executed_boundary_geometry_batch",
                    "count": len(rows), "rows": rows},
                   indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
