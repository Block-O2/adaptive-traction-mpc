"""Short unactuated CR12-cuff-Human physical prefix for assembly validation.

This is a MECHANICAL DEVELOPMENT diagnostic, not a controller performance run.
Robot ctrl is zero; the same compliant interface, bed and Human plant step.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.rigid_table_assembly_v1 import assess_assembly


STAGE = Path(__file__).resolve().parents[1]
OLD = STAGE / "results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases"
NEW = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v1/cases"
NOMINAL = STAGE / "configs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/nominal_reference_rigid_table_v1.json"
DEFAULT_OUT = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/prefix_v1"


def contact_forces(plant: Stage5CR12SensorBoundaryPlant) -> dict[str, dict]:
    model, data = plant.model, plant.data
    bed = plant.bed_geom_id
    relevant = {model.geom("thigh_geom").id: "thigh",
                model.geom("shank_geom").id: "shank"}
    row = {name: {"normal_n": 0.0, "tangent_n": 0.0,
                  "contact": False, "distance_m": None}
           for name in relevant.values()}
    for i in range(data.ncon):
        contact = data.contact[i]
        pair = {int(contact.geom1), int(contact.geom2)}
        if bed not in pair:
            continue
        for geom_id, name in relevant.items():
            if geom_id not in pair:
                continue
            force = np.zeros(6)
            mujoco.mj_contactForce(model, data, i, force)
            row[name]["normal_n"] += float(force[0])
            row[name]["tangent_n"] += float(np.linalg.norm(force[1:3]))
            row[name]["contact"] = True
            row[name]["distance_m"] = (float(contact.dist) if row[name]["distance_m"] is None
                                        else min(float(contact.dist), row[name]["distance_m"]))
    return row


def run_one(case: dict, *, label: str) -> dict:
    human, geometry, spec, _ = hidden_plant(case)
    plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
    plant.reset(np.asarray(spec.start_return_target_rad))
    initial = contact_forces(plant)
    steps = round(0.1 / plant.model.opt.timestep)
    intervals = []
    native = mujoco.mj_step2

    def observed(model: mujoco.MjModel, data: mujoco.MjData) -> None:
        start = float(data.time)
        native(model, data)
        measured = contact_forces(plant)
        intervals.append({"t0_s": start, "t1_s": float(data.time), **measured})

    mujoco.mj_step2 = observed
    try:
        for _ in range(steps):
            plant.step()
    finally:
        mujoco.mj_step2 = native
    result = {"case_key": case["case_key"], "label": label,
              "evidence_category": "unactuated_short_physical_mechanics_prefix_not_controller_outcome",
              "assembly": assess_assembly(case, verify_robot=False),
              "initial_contact": initial,
              "interval_count": len(intervals),
              "duration_s": sum(row["t1_s"] - row["t0_s"] for row in intervals),
              "contacts": {},
              "actual_CR12_cuff_Human_MuJoCo_stepping": True}
    for name in ("thigh", "shank"):
        dt = np.asarray([row["t1_s"] - row["t0_s"] for row in intervals])
        force = np.asarray([row[name]["normal_n"] for row in intervals])
        contact = np.asarray([row[name]["contact"] for row in intervals], dtype=bool)
        distance = [row[name]["distance_m"] for row in intervals
                    if row[name]["distance_m"] is not None]
        result["contacts"][name] = {
            "normal_peak_n": float(np.max(force)),
            "normal_impulse_n_s": float(np.dot(dt, force)),
            "contact_duration_s": float(np.sum(dt[contact])),
            "first_contact_s": next((row["t0_s"] for row in intervals
                                     if row[name]["contact"]), None),
            "minimum_contact_distance_m": min(distance) if distance else None,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.mkdir(parents=True)
    cases = [
        (OLD / "balanced_near_upper_current_rom_r01.json", "historical_fixed_overlap"),
        (NEW / "balanced_near_upper_current_rom_r01.json", "repaired_strongest_overlap"),
        (NEW / "balanced_ordinary_r01.json", "unchanged_legal_comparison"),
        (NOMINAL, "positive_gap_nominal_reference"),
    ]
    rows = []
    for path, label in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        row = run_one(case, label=label)
        rows.append(row)
        print(json.dumps({"label": label, "thigh": row["contacts"]["thigh"]}), flush=True)
    (args.output / "PREFIX_CONTACT_RESULTS.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
