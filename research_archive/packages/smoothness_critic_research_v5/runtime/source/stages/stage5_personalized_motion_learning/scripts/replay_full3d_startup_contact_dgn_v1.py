"""Matched physical replay with evaluation-only 0.25 ms bed-contact telemetry.

Only the diagnostic process monkeypatches the existing truth monitor. It does
not change plant dynamics, measurements, action selection or source files.
Wall-clock planner timing can be perturbed by this instrumentation and must
not be used as a production runtime comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from traction_mpc_stage5.fresh_qualification_v1.physics_monitor import TruePhysicsMonitor
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    records: list[tuple[float, float, float, int]] = []
    original = TruePhysicsMonitor.observe

    def instrument(self: TruePhysicsMonitor, plant: object, *, integrated_step: bool = True) -> None:
        original(self, plant, integrated_step=integrated_step)
        if not integrated_step or self.stage != "COMMISSIONING":
            return
        model, data = plant.model, plant.data
        bed = int(plant.bed_geom_id)
        shank = int(model.geom("shank_geom").id)
        force = np.zeros(6, dtype=float)
        normal_force_n = 0.0
        smallest_distance_m = float("inf")
        count = 0
        for index in range(data.ncon):
            contact = data.contact[index]
            if {int(contact.geom1), int(contact.geom2)} != {bed, shank}:
                continue
            mujoco.mj_contactForce(model, data, index, force)
            normal_force_n += max(0.0, float(force[0]))
            smallest_distance_m = min(smallest_distance_m, float(contact.dist))
            count += 1
        records.append((float(data.time), normal_force_n,
                        smallest_distance_m if count else float("nan"), count))

    TruePhysicsMonitor.observe = instrument
    try:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        summary = run_executed_case(args.output / "episode", qualification_case=case,
                                    qualification_arm="continual_adaptive",
                                    simulate_planning_latency=True,
                                    formal_qualification=False)
    finally:
        TruePhysicsMonitor.observe = original

    array = np.asarray(records, dtype=float)
    if len(array) == 0:
        raise RuntimeError("instrumented physical commissioning produced no steps")
    np.savez_compressed(args.output / "bed_contact_025ms.npz",
                        time_s=array[:, 0], normal_force_n=array[:, 1],
                        contact_distance_m=array[:, 2], contact_count=array[:, 3])
    contact = array[:, 3] > 0
    dt = np.diff(np.concatenate(([array[0, 0] - 0.00025], array[:, 0])))
    with np.load(args.output / "episode" / "trace.npz", allow_pickle=False) as fresh, \
            np.load(args.baseline / "trace.npz", allow_pickle=False) as old:
        current_comm = fresh["stage"] == "COMMISSIONING"
        baseline_comm = old["stage"] == "COMMISSIONING"
        max_differences = {}
        for name in ("time_s", "reference_q_rad", "estimated_human_state_rad_rad_s",
                     "evaluation_only_human_state_rad_rad_s", "cr12_q_rad",
                     "cr12_actuator_command_nm", "physical_cuff_force_world_n",
                     "shank_bed_contact_evaluation_only"):
            a = fresh[name][current_comm]
            b = old[name][baseline_comm]
            max_differences[name] = (None if a.shape != b.shape else
                                     float(np.max(np.abs(a.astype(float) - b.astype(float)))))
    diagnostic = {
        "schema": "full3d_startup_dgn_v1_matched_contact_replay",
        "case_key": case["case_key"],
        "baseline": str(args.baseline),
        "replay": str(args.output / "episode"),
        "evidence_category": "development_diagnostic_replay_of_existing_case",
        "source_or_scientific_parameters_changed": False,
        "instrumentation_changes_planner_wall_clock_comparability": True,
        "replay_status": summary["status"],
        "replay_abort_reason": summary["abort_reason"],
        "matched_commissioning_max_abs_differences": max_differences,
        "physical_step_count": len(array),
        "contact_step_count": int(np.count_nonzero(contact)),
        "contact_first_time_s": None if not np.any(contact) else float(array[np.flatnonzero(contact)[0], 0]),
        "contact_last_time_s": None if not np.any(contact) else float(array[np.flatnonzero(contact)[-1], 0]),
        "contact_duration_integral_s": float(np.sum(dt[contact])),
        "normal_force_peak_n": float(np.max(array[:, 1])),
        "normal_force_integral_n_s": float(np.sum(array[:, 1] * dt)),
        "minimum_contact_distance_m": None if not np.any(contact) else float(
            np.nanmin(array[:, 2])),
    }
    (args.output / "diagnostic_summary.json").write_text(
        json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(diagnostic, sort_keys=True))


if __name__ == "__main__":
    main()
