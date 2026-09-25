"""Read-only instrumentation of actual physics solves up to DEV-B checkpoint.

Replays recorded planning delay; no host-latency result is inferred. The force
sample is read after mj_step2 and before the plant refreshes next-boundary
forward dynamics, so impulses use the force for the executed interval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import mujoco
import numpy as np

from dev_b_matched_diagnostics_v1 import capture, load_checkpoint, save_json, integration_state

STAGE=Path(__file__).resolve().parents[1]
RESULTS=STAGE/"results/full3d_adaptive_integration_v1"


def run(key, output):
    if output.exists():raise FileExistsError(output)
    source=RESULTS/"dev_b_first_divergence_v1/capture_v3"/key
    manifest=json.loads((source/"capture_manifest.json").read_text())
    rows=[]
    details={}
    native=mujoco.mj_step2

    def observed(model,data):
        start=float(data.time)
        q0=data.qpos.copy(); v0=data.qvel.copy()
        native(model,data)
        bed=model.geom("bed").id
        thigh=model.geom("thigh_geom").id
        shank=model.geom("shank_geom").id
        sums=np.zeros(4)
        penetration=np.zeros(2)
        active=np.zeros(2)
        for i in range(data.ncon):
            c=data.contact[i]
            pair={int(c.geom1),int(c.geom2)}
            if bed not in pair:continue
            j=0 if thigh in pair else 1 if shank in pair else None
            if j is None:continue
            f=np.zeros(6);mujoco.mj_contactForce(model,data,i,f)
            sums[2*j]+=f[0];sums[2*j+1]+=np.linalg.norm(f[1:3])
            penetration[j]=min(penetration[j],float(c.dist));active[j]=1
            if j not in details or f[0]>details[j]["normal_n"]:
                details[j]={"interval_start_s":start,"interval_end_s":float(data.time),
                    "normal_n":float(f[0]),"distance_m":float(c.dist),"position_world_m":c.pos.copy(),
                    "frame_rows_world":c.frame.reshape(3,3).copy(),"wrench_local_n_nm":f.copy(),
                    "geom1":model.geom(c.geom1).name,"geom2":model.geom(c.geom2).name}
        rows.append((start,float(data.time),*sums,*penetration,*active,*q0,*v0,*data.ctrl.copy()))

    mujoco.mj_step2=observed
    started=time.perf_counter()
    try:capture(Path(manifest["case_path"]),Path(manifest["historical_path"]),output)
    finally:mujoco.mj_step2=native
    elapsed=time.perf_counter()-started
    arr=np.asarray(rows)
    np.savez_compressed(output/"executed_contact_intervals.npz",rows=arr,
        columns=np.asarray(["interval_start_s","interval_end_s","thigh_normal_n","thigh_tangent_n",
                            "shank_normal_n","shank_tangent_n","thigh_min_contact_dist_m","shank_min_contact_dist_m",
                            "thigh_contact","shank_contact"]+[f"qpos_{i}" for i in range(8)]+
                           [f"qvel_{i}" for i in range(8)]+[f"ctrl_{i}" for i in range(6)]))
    baseline=load_checkpoint(source/"checkpoint.pkl.gz")["runtime"]["plant"]
    replay=load_checkpoint(output/"checkpoint.pkl.gz")["runtime"]["plant"]
    original_state=integration_state(baseline);replay_state=integration_state(replay)
    dt=arr[:,1]-arr[:,0]
    contacts={}
    for j,name in enumerate(("thigh","shank")):
        mask=arr[:,8+j]>0
        contacts[name]={"interval_count":int(np.sum(mask)),"duration_s":float(np.sum(dt[mask])),
            "onset_s":float(arr[np.flatnonzero(mask)[0],0]) if np.any(mask) else None,
            "normal_peak_n":float(np.max(arr[:,2+2*j])),
            "normal_impulse_n_s":float(np.dot(dt,arr[:,2+2*j])),
            "tangent_peak_n":float(np.max(arr[:,3+2*j])),
            "tangent_norm_integral_n_s":float(np.dot(dt,arr[:,3+2*j])),
            "minimum_distance_m":float(np.min(arr[:,6+j])),"peak_contact_detail":details.get(j)}
    result={"schema":"integrated_recovery_contact_replay_v1","case_key":key,
        "category":"DEVELOPMENT_REPLAY_WITH_RECORDED_PLANNING_DELAY","command":sys.argv,
        "force_timestamp":"mj_step2 constraint solve at interval_start; read before boundary refresh",
        "physical_interval_count":len(rows),"total_duration_s":float(np.sum(dt)),
        "checkpoint_max_integration_state_difference":float(np.max(np.abs(original_state-replay_state))),
        "exact_checkpoint_match":bool(np.array_equal(original_state,replay_state)),
        "checkpoint_integration_sha256":hashlib.sha256(replay_state.tobytes()).hexdigest(),
        "wall_s_not_latency_qualification":elapsed,"contacts":contacts,
        "historical_planner_ms_replayed":manifest["historical_planner_ms_replayed"]}
    save_json(output/"contact_summary.json",result)
    print(json.dumps({"case":key,"exact_match":result["exact_checkpoint_match"],"contacts":contacts},default=lambda x:x.tolist() if hasattr(x,"tolist") else str(x)),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--case-key",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();run(args.case_key,args.output)
