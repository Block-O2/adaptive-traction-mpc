"""Read-only numerical aggregation/plots of retained DEV-B diagnostic output."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dev_b_matched_diagnostics_v1 import save_json


def difference(a,b):
    v=np.asarray(a,dtype=float)-np.asarray(b,dtype=float)
    return {"vector":v,"l2":float(np.linalg.norm(v))}


def summarize_case(path):
    a=json.loads((path/"algebra.json").read_text())
    r=a["records"]
    names=["old_model_old_estimate","new_model_old_estimate_old_allocation",
           "old_model_new_estimate_old_allocation","new_model_new_estimate_old_allocation",
           "new_model_new_estimate"]
    result={"state_jump_rad_rad_s":difference(a["state_new"],a["state_old"]),
        "state_error_old_rad_rad_s":difference(a["state_old"],a["state_true_evaluation_only"]),
        "state_error_new_rad_rad_s":difference(a["state_new"],a["state_true_evaluation_only"]),
        "effects":{},"physical_branches":{},"prediction":a["prediction_evaluation_only"],
        "context_delta_nm":a["commissioning_vs_active_recovery_context_torque_delta_nm"],
        "production_chain_closure_nm":a["production_command_max_abs_difference_nm"]}
    getters={"human_action_nm":lambda x:x["generalized_action_nm"],
        "robot_torque_nm":lambda x:x["command"]["joint_torque_command_nm"],
        "allocator_force_n":lambda x:x["command"]["force_allocator_n"],
        "allocator_moment_nm":lambda x:x["command"]["moment_allocator_nm"]}
    for field,get in getters.items():
        v00,v10,v01,v11,v11g=[np.asarray(get(r[n])) for n in names]
        model=v10-v00
        state=v01-v00
        interaction=v11-v10-v01+v00
        geometry=v11g-v11
        total=v11g-v00
        parts={"model_at_old_state":model,"state_at_old_model":state,
            "interaction":interaction,"allocation_geometry_at_new_state":geometry}
        result["effects"][field]={"total":total,"total_l2":np.linalg.norm(total),
            "parts":{k:{"vector":v,"l2":np.linalg.norm(v),
                "projection_on_total_fraction":float(v@total/(total@total)) if total@total>1e-24 else 0}
                for k,v in parts.items()},"sum_error":sum(parts.values())-total}
    new=r["new_model_new_estimate"]
    old=r["old_model_old_estimate"]
    zero=r["new_beta_zero_residual"]
    old_same=r["old_model_new_estimate"]
    result["beta_residual_separation"]={field:{"beta":difference(get(zero),get(old_same)),
        "residual":difference(get(new),get(zero))} for field,get in getters.items()}
    prior=a["previous_command_record"]
    result["adjacent_historical_jump_nm"]=difference(new["command"]["joint_torque_command_nm"],prior["command"]["joint_torque_command_nm"])
    result["common_state_component_delta_nm"]={k:difference(new["robot_torque_components"][k],old["robot_torque_components"][k])
        for k in new["robot_torque_components"]}
    result["adjacent_component_delta_nm"]={k:difference(new["robot_torque_components"][k],prior["components"][k])
        for k in new["robot_torque_components"]}
    result["allocation_geometry_force_delta_n"]=difference(a["allocations"]["new"]["result"]["wrench_world"][:3],a["allocations"]["old"]["result"]["wrench_world"][:3])
    result["allocation_geometry_moment_delta_nm"]=difference(a["allocations"]["new"]["result"]["wrench_world"][3:],a["allocations"]["old"]["result"]["wrench_world"][3:])
    result["allocation_dual_condition"]={k:a["allocations"][k]["dual_condition"] for k in ("old","new")}
    result["initial_new_generalized_action_nm"]=new["generalized_action_nm"]
    result["initial_old_generalized_action_nm"]=old["generalized_action_nm"]
    result["new_beta"]=new["beta"]
    result["old_beta"]=old["beta"]
    result["new_residual_nm"]=new["residual_nm"]
    for f in path.glob("*.json"):
        if f.stem not in ("retained_model","activated_model","activated_duplicate","new_model_old_estimate","old_model_new_estimate","diagnostic_action_transfer_100ms"):
            continue
        b=json.loads(f.read_text())
        phy=b["physics"]
        t=np.array([x["time_s"] for x in phy])
        force=np.array([np.linalg.norm(x["human_cuff_wrench_world"][:3]) for x in phy])
        moment=np.array([np.linalg.norm(x["human_cuff_wrench_world"][3:]) for x in phy])
        acc=np.array([x["ddq_true_rad_s2"] for x in phy])
        dq=np.array([x["dq_true_rad_s"] for x in phy])
        q=np.array([x["q_true_rad"] for x in phy])
        start=np.array(new["reference"]["q_rad"])
        tau=np.array([x["command"]["joint_torque_command_nm"] for x in b["records"]])
        deltas=np.diff(np.vstack([prior["command"]["joint_torque_command_nm"],tau]),axis=0)
        result["physical_branches"][f.stem]={"duration_s":b["duration_s"],"abort":b["abort_reason"],
            "intervals":len(b["records"]),"physics_boundaries":len(phy),
            "first_robot_command_jump_l2_nm":np.linalg.norm(deltas[0]) if len(deltas) else None,
            "max_robot_command_step_l2_nm":np.max(np.linalg.norm(deltas,axis=1)) if len(deltas) else None,
            "peak_cuff_force_n":np.max(force),"peak_cuff_moment_nm":np.max(moment),
            "force_integral_n_s_left_interval":np.sum(force[:-1]*np.diff(t)),
            "moment_integral_nm_s_left_interval":np.sum(moment[:-1]*np.diff(t)),
            "physical_ddq_peak_abs_rad_s2":np.max(np.abs(acc),axis=0),
            "first5ms_mean_ddq_rad_s2":(dq[min(20,len(dq)-1)]-dq[0])/(t[min(20,len(t)-1)]-t[0]) if len(t)>1 else None,
            "final_q_true_deg":np.degrees(q[-1]),
            "final_q_start_error_deg":np.degrees(q[-1]-start),
            "final_dq_true_deg_s":np.degrees(dq[-1]),
            "minimum_true_clearance_m":min(x["true_shank_clearance_m"] for x in phy),
            "bed_contact_boundaries":sum(x["bed_normal_load_n"]>0 for x in phy),
            "peak_bed_normal_load_n":max(x["bed_normal_load_n"] for x in phy),
            "initial_spring_energy_j":phy[0]["spring_energy_j"],
            "maximum_spring_energy_j":max(x["spring_energy_j"] for x in phy),
            "final_spring_energy_j":phy[-1]["spring_energy_j"],
            "min_session_clearance_m":min(x["session_clearance_m"] for x in b["records"]) if b["records"] else None,
            "truth_consumed_by_branch_control":b["truth_consumed_by_branch_control"]}
    return result


def plot_case(path,output):
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout="constrained")
    for name,label in [("retained_model","Retained prior"),("activated_model","Production activation"),
                       ("diagnostic_action_transfer_100ms","Diagnostic 100 ms action transfer")]:
        f=path/(name+".json")
        if not f.exists(): continue
        b=json.loads(f.read_text())
        phy=b["physics"]; rows=b["records"]
        t=np.array([x["time_s"] for x in phy]); t-=t[0]
        tc=np.array([x["timestamp_s"] for x in rows]); tc-=phy[0]["time_s"]
        axes[0,0].plot(tc,[x["command"]["joint_torque_command_nm"][1] for x in rows],label=label)
        axes[0,1].plot(t,[np.linalg.norm(x["human_cuff_wrench_world"][:3]) for x in phy],label=label)
        axes[1,0].plot(t,[x["ddq_true_rad_s2"][1] for x in phy],label=label)
        target=np.array(rows[0]["reference"]["q_rad"])
        axes[1,1].plot(t,[np.max(np.abs(np.degrees(np.array(x["q_true_rad"])-target))) for x in phy],label=label)
    for ax,title,ylabel in zip(axes.flat,["CR12 joint 2 command","Physical Human-site cuff force","Human joint 2 instantaneous acceleration","True Human error to registered start"],["Torque (Nm)","Force norm (N)","Acceleration (rad/s²)","Max joint error (deg)"]):
        ax.set(title=title,xlabel="Time since matched activation (s)",ylabel=ylabel)
        ax.grid(alpha=.25)
    axes[0,0].legend(fontsize=8)
    fig.suptitle("DEV-B diagnostic only — identical checkpoint and scheduled reference")
    fig.savefig(output,dpi=170)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    results={}
    for c in sorted(args.root.iterdir()):
        if not c.is_dir():continue
        result={}
        for a in sorted(c.glob("analysis_*ms")):
            if (a/"historical_replay_validation.json").exists():
                result[a.name]=summarize_case(a)
        if result: results[c.name]=result
    save_json(args.output/"summary.json",results)
    target=args.root/"balanced_near_upper_current_rom_r01"
    for a in target.glob("analysis_*ms"):
        if (a/"historical_replay_validation.json").exists():
            plot_case(a,args.output/("largest_jump_"+a.name+".png"))
    print(json.dumps({"cases":len(results),"output":str(args.output)}))


if __name__=="__main__":main()
