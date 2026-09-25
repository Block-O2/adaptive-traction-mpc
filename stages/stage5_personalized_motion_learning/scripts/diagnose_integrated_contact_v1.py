"""Evaluation-only contact/assembly diagnosis; never exports controller inputs.

All modifications of q below are explicitly static diagnostic probes in cloned
MjData; they are not task rollouts or a state-reset control mechanism.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import mujoco
import numpy as np

from dev_b_matched_diagnostics_v1 import load_checkpoint, save_json, integration_state
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant

STAGE = Path(__file__).resolve().parents[1]
RESULTS = STAGE / "results/full3d_adaptive_integration_v1"


def contacts(plant):
    m, d = plant.model, plant.data
    out = []
    for index in range(d.ncon):
        c = d.contact[index]
        if plant.bed_geom_id not in (c.geom1, c.geom2):
            continue
        force = np.zeros(6)
        mujoco.mj_contactForce(m, d, index, force)
        frame = np.asarray(c.frame).reshape(3, 3)
        fw, mw = frame.T @ force[:3], frame.T @ force[3:]
        bodies = (int(m.geom_bodyid[c.geom1]), int(m.geom_bodyid[c.geom2]))
        generalized = np.zeros(m.nv)
        for body, sign in zip(bodies, (-1, 1)):
            mujoco.mj_applyFT(m, d, sign*fw, sign*mw, c.pos, body, generalized)
        jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
        human_body = bodies[1] if c.geom1 == plant.bed_geom_id else bodies[0]
        mujoco.mj_jac(m, d, jp, jr, c.pos, human_body)
        n_jac = frame[0] @ jp
        out.append({
            "index": index, "geom1": m.geom(c.geom1).name, "geom2": m.geom(c.geom2).name,
            "geom_body_ids": bodies, "distance_m": float(c.dist), "position_world_m": c.pos.copy(),
            "frame_rows_world": frame.copy(), "contact_wrench_local_n_nm": force,
            "force_on_geom2_world_n": fw, "moment_on_geom2_world_nm": mw,
            "generalized_contact_nm": generalized, "human_generalized_contact_nm": generalized[plant.human_dof_indices],
            "normal_point_jacobian": n_jac,
            "normal_effective_inverse_mass": float(n_jac @ np.linalg.solve(full_mass(m,d), n_jac)),
            "efc_address": int(c.efc_address), "dim": int(c.dim),
            "friction": c.friction.copy(), "solref": c.solref.copy(), "solimp": c.solimp.copy(),
        })
    return out


def full_mass(m, d):
    mass = np.zeros((m.nv,m.nv))
    mujoco.mj_fullM(m, d, mass)
    return mass


def inspect_checkpoint(key):
    cpdir = RESULTS / "dev_b_first_divergence_v1/capture_v3" / key
    cp = load_checkpoint(cpdir / "checkpoint.pkl.gz")
    p = cp["runtime"]["plant"]
    state = integration_state(p)
    baseline_contacts = contacts(p)
    hip = p.model.body("hip").id
    thigh = p.model.geom("thigh_geom").id
    world_hip = p.data.xpos[hip].copy()
    lower_proximal = world_hip[2] - p.model.geom_size[thigh,0]
    result = {
        "case_key": key, "checkpoint_time_s": float(p.data.time),
        "integration_sha256": hashlib.sha256(state.tobytes()).hexdigest(),
        "hip_world_m": world_hip, "bed_z_m": float(p.data.geom_xpos[p.bed_geom_id,2]),
        "thigh_radius_m": float(p.model.geom_size[thigh,0]),
        "proximal_sphere_clearance_m": float(lower_proximal - p.data.geom_xpos[p.bed_geom_id,2]),
        "eq_active": p.data.eq_active.copy(), "contacts": baseline_contacts,
        "q_true_evaluation_only": p.data.qpos[p.human_qpos_indices].copy(),
        "dq_true_evaluation_only": p.data.qvel[p.human_dof_indices].copy(),
        "qacc_true_evaluation_only": p.data.qacc[p.human_dof_indices].copy(),
        "qfrc_constraint": p.data.qfrc_constraint.copy(),
        "sum_bed_contact_generalized_nm": sum((r["generalized_contact_nm"] for r in baseline_contacts), np.zeros(p.model.nv)),
        "mass_matrix": full_mass(p.model,p.data),
        "human_body_masses_kg": [float(p.model.body_mass[p.model.body(n).id]) for n in ("hip","shank")],
        "interface_parameters": vars(p.interface_parameters),
        "static_q_sweep": [],
    }
    for q1 in (0,5,15,40,80):
        q = copy.deepcopy(p)
        q.data.qpos[q.human_qpos_indices[0]] = np.radians(q1)
        q.data.qvel[:] = 0
        mujoco.mj_forward(q.model, q.data)
        result["static_q_sweep"].append({"q1_deg":q1,"contacts":contacts(q)})
    assert np.array_equal(state, integration_state(p)), "read-only diagnosis mutated checkpoint"
    return result


def initial_census():
    rows = []
    for path in sorted((RESULTS / "fresh_qualification_v1/formal_case_bundle_v1/cases").glob("*.json")):
        case = json.loads(path.read_text())
        human, geometry, spec, _ = hidden_plant(case)
        p = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
        # Static mechanics only: robot remains unactuated, no interface force is
        # used. Human-bed collision geometry is independent of robot q here.
        p.data.qpos[p.human_qpos_indices] = spec.start_return_target_rad
        p.data.eq_active[:] = 0
        mujoco.mj_forward(p.model,p.data)
        bed = float(p.data.geom_xpos[p.bed_geom_id,2])
        thigh = p.model.geom("thigh_geom").id
        gap = float(p.data.xpos[p.model.body("hip").id,2] - p.model.geom_size[thigh,0] - bed)
        rows.append({"case_key":case["case_key"], "hidden_hip_shift_xz_m":case["physical"]["hip_translation_xz_m"],
                     "immutable_proximal_thigh_gap_m":gap, "initial_bed_contacts":contacts(p),
                     "classification":"STATIC_EVALUATION_ONLY_NOT_A_ROLLOUT"})
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    keys=("balanced_near_upper_current_rom_r01","balanced_ordinary_r01","balanced_middle_r01","development_nominal")
    record={"schema":"integrated_recovery_contact_diagnostic_v1", "category":"NONDEPLOYABLE_EVALUATION_ONLY",
            "command":sys.argv, "mujoco_version":mujoco.__version__,
            "checkpoints":[inspect_checkpoint(k) for k in keys], "old24_initial_geometry":initial_census()}
    save_json(args.output,record)
    print(json.dumps({"output":str(args.output),"negative_fixed_hip_gap_cases":sum(r["immutable_proximal_thigh_gap_m"] < -1e-9 for r in record["old24_initial_geometry"]),
                      "matched_contacts":[{"case":r["case_key"],"gap_m":r["proximal_sphere_clearance_m"],"normal_n":sum(c["contact_wrench_local_n_nm"][0] for c in r["contacts"])} for r in record["checkpoints"]]}))


if __name__=="__main__":main()
