"""Evaluation-only generalized contact-load decomposition of saved checkpoints."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import mujoco
from dev_b_matched_diagnostics_v1 import load_checkpoint, save_json, physics_record


def probe(path):
    cp=load_checkpoint(path/"checkpoint.pkl.gz")
    p=cp["runtime"]["plant"]; d=p.data; m=p.model; idx=p.human_dof_indices
    contact_types={int(mujoco.mjtConstraint.mjCNSTR_CONTACT_FRICTIONLESS),
        int(mujoco.mjtConstraint.mjCNSTR_CONTACT_PYRAMIDAL),int(mujoco.mjtConstraint.mjCNSTR_CONTACT_ELLIPTIC)}
    contributions=[]
    for i in range(d.ncon):
        mask=np.isin(d.efc_type[:d.nefc],list(contact_types))&(d.efc_id[:d.nefc]==i)
        multipliers=np.zeros(d.nefc)
        multipliers[mask]=d.efc_force[:d.nefc][mask]
        force=np.zeros(m.nv)
        mujoco.mj_mulJacTVec(m,d,force,multipliers)
        load=np.zeros(6)
        mujoco.mj_contactForce(m,d,i,load)
        contributions.append({"pair":[m.geom(int(d.contact[i].geom1)).name,m.geom(int(d.contact[i].geom2)).name],
            "generalized_human_nm":force[idx],"generalized_all_nm":force,
            "local_contact_wrench":load,"constraint_rows":int(mask.sum()),"distance_m":d.contact[i].dist})
    mass=np.zeros((m.nv,m.nv))
    mujoco.mj_fullM(m,d,mass)
    interface=p._evaluate_current_interface()
    cuff=(p._site_pose_jacobian(p.sleeve_site_id)[:,idx].T@interface.human_wrench_world)
    contact=sum((x["generalized_human_nm"] for x in contributions),np.zeros(2))
    q=d.qpos[p.human_qpos_indices].copy(); dq=d.qvel[idx].copy(); ddq=d.qacc[idx].copy()
    # Required cuff-only input versus total cuff+constraint input at this
    # same physical state, without removing any physical contact or stepping.
    models={}
    for name,model in [("old",cp["recovery"]["old_model"]),("new",cp["recovery"]["target_model"])]:
        inverse=model.inverse_dynamics(q,dq,ddq)
        models[name]={"inverse_at_true_state_acceleration_nm":inverse,
            "minus_cuff_nm":inverse-cuff,"minus_cuff_and_contact_nm":inverse-cuff-contact,
            "ddq_with_cuff_rad_s2":model.continuous_dynamics(np.r_[q,dq],cuff)[2:],
            "ddq_with_cuff_and_contact_rad_s2":model.continuous_dynamics(np.r_[q,dq],cuff+contact)[2:]}
    full_balance=(mass@d.qacc+d.qfrc_bias-d.qfrc_passive-d.qfrc_applied-d.qfrc_actuator-d.qfrc_constraint)
    return {"schema":"NONDEPLOYABLE_DEV_B_EVALUATION_ONLY_CONTACT_PROBE",
        "timestamp_s":d.time,"physics":physics_record(p),"contacts":contributions,
        "human_cuff_generalized_input_nm":cuff,"human_contact_generalized_input_nm":contact,
        "human_total_constraint_nm":d.qfrc_constraint[idx].copy(),
        "noncontact_constraint_nm":d.qfrc_constraint[idx]-contact,
        "human_mass_matrix":mass[np.ix_(idx,idx)],"human_bias_nm":d.qfrc_bias[idx].copy(),
        "human_passive_nm":d.qfrc_passive[idx].copy(),"human_applied_nm":d.qfrc_applied[idx].copy(),
        "human_actuator_nm":d.qfrc_actuator[idx].copy(),"equation_balance_nm":full_balance[idx],
        "models":models,"interpretation":"oracle local consistency; contact-inclusive acceleration must not establish intrinsic dynamics identification"}


def main():
    a=argparse.ArgumentParser();a.add_argument("--root",type=Path,required=True);a.add_argument("--output",type=Path,required=True)
    args=a.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    result={p.name:probe(p) for p in sorted(args.root.iterdir()) if (p/"capture_manifest.json").exists()}
    save_json(args.output,result)
    for key,r in result.items():
        print(key,"contact_tau",r["human_contact_generalized_input_nm"],"new_minus_cuff",r["models"]["new"]["minus_cuff_nm"],"new_minus_total",r["models"]["new"]["minus_cuff_and_contact_nm"])


if __name__=="__main__":main()
