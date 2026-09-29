"""Read-only quantitative audit of the V3 waypoint lattice and its decisions."""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import numpy as np

STAGE = Path(__file__).resolve().parents[2]
RAW = STAGE / "results/zero_value_30rep_baseline_v3/formal_session_01"
OUT = STAGE / "docs/safe_action_horizon_exploration_v1"


def summarize(values):
    return {"count":len(values),"min":float(min(values)),"median":float(statistics.median(values)),"max":float(max(values)),"mean":float(statistics.mean(values))} if values else {"count":0}


def audit():
    rows=[]
    selected={}
    for rep in range(1,31):
        decisions=json.loads((RAW/f"rep_{rep:02d}"/"runtime_artifacts.json").read_text())["task_decisions"]
        for index,dec in enumerate(decisions):
            ev=dec["evaluations"]
            feasible=[x for x in ev if x["feasible"]]
            vec=np.asarray([x["proposed_delta_q_rad"] for x in feasible])
            targets=np.asarray([x["target_q_rad"] for x in feasible])
            pair=np.linalg.norm(targets[:,None,:]-targets[None,:,:],axis=2)
            norms=np.linalg.norm(vec,axis=1)
            angular=0.0
            if len(vec)>1:
                cos=np.clip((vec@vec.T)/(norms[:,None]*norms[None,:]),-1,1)
                angular=float(np.degrees(np.arccos(cos)).max())
            ratio=np.abs(vec[:,0])/(np.abs(vec[:,1])+1e-12)
            midpoint=[]
            for x in feasible:
                sch=x["schedule"]
                t=min(0.25,float(sch["duration_s"]))
                u=t/float(sch["duration_s"])
                s=10*u**3-15*u**4+6*u**5
                midpoint.append(np.asarray(sch["start_q_rad"])+s*(np.asarray(sch["target_q_rad"])-np.asarray(sch["start_q_rad"])))
            midpoint=np.asarray(midpoint)
            midpoint_dist=float(np.linalg.norm(midpoint[:,None,:]-midpoint[None,:,:],axis=2).max())
            margins=[]
            for x in feasible:
                scr=x["execution_screen"]
                margins.append({"force_n":scr["force_limit_n"]-scr["peak_force_n"],"moment_nm":scr["moment_limit_nm"]-scr["peak_moment_nm"],"clearance_m":x["schedule"]["minimum_reference_shank_clearance_m"]})
            score=[float(x["total_cost"]) for x in feasible]
            best=min(score)
            second=sorted(score)[1] if len(score)>1 else best
            row={"repetition":rep,"decision_index":index,"phase":dec["phase"],"candidate_count":len(ev),"feasible_count":len(feasible),"selected_label":dec["executed_label"],"max_pairwise_target_distance_deg":float(np.degrees(pair.max())),"angular_spread_deg":angular,"hip_knee_absolute_increment_ratio_range":[float(ratio.min()),float(ratio.max())],"predicted_quintic_position_spread_at_0p25s_deg":float(np.degrees(midpoint_dist)),"cost_gap_second_best":second-best,"minimum_candidate_force_margin_n":min(x["force_n"] for x in margins),"minimum_candidate_moment_margin_nm":min(x["moment_nm"] for x in margins),"minimum_candidate_schedule_clearance_m":min(x["clearance_m"] for x in margins),"selected_delta_q_deg":next(x["proposed_delta_q_deg"] for x in feasible if x["label"]==dec["executed_label"])}
            rows.append(row)
            if rep in (2,6,16,26): selected[f"rep_{rep:02d}_decision_{index:02d}"]=row
    phase={}
    for name in ("OUTBOUND","HOLD","RETURN"):
        rs=[r for r in rows if r["phase"]==name]
        phase[name]={"count":len(rs),"max_pairwise_target_distance_deg":summarize([r["max_pairwise_target_distance_deg"] for r in rs]),"angular_spread_deg":summarize([r["angular_spread_deg"] for r in rs]),"predicted_quintic_position_spread_at_0p25s_deg":summarize([r["predicted_quintic_position_spread_at_0p25s_deg"] for r in rs]),"cost_gap_second_best":summarize([r["cost_gap_second_best"] for r in rs]),"feasible_count":summarize([r["feasible_count"] for r in rs])}
    result={"schema":"current_action_space_audit_v1","source":"30 V3 raw task-decision records; no exploration rollouts","total_decisions":len(rows),"joint_dimensions":2,"action":"direct next Human hip/knee joint increment; scheduler certifies constrained quintic and execution mechanics screen","generator":{"maximum_waypoint_step_fraction_of_task_span":0.2,"action_scales":[0.5,1.0],"directions":[[1,.5],[1,.75],[1,1],[.75,1],[.5,1]],"nonnegative_phase_progress_only":True},"per_phase":phase,"selected_labels":{label:sum(r["selected_label"]==label for r in rows) for label in sorted(set(r["selected_label"] for r in rows))},"representative_decisions":selected,"all_decisions":rows,"trajectory_spread_note":"0.25 s common-time quintic position estimate from recorded starts/endpoints/durations; low-ROM waypoint terminal velocities are zero"}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"CURRENT_ACTION_SPACE_AUDIT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    lines=["# Current action-space audit", "", "Read-only audit of all 390 V3 decisions. Action is the next 2D Human hip/knee waypoint increment from the fresh deployable state. Existing candidates are positive phase-progress pairs at 0.5 or 1.0 scale of 20% task span, with five hip/knee ratios. Scheduling, continuous clearance, and predicted mechanics screens are already applied.", "", "| Phase | Decisions | Feasible candidate count, median | Max pairwise target distance, median (deg) | Angular spread, median (deg) | 0.25 s predicted path spread, median (deg) |", "|---|---:|---:|---:|---:|---:|"]
    for name,p in phase.items():
        lines.append(f"| {name} | {p['count']} | {p['feasible_count']['median']:.1f} | {p['max_pairwise_target_distance_deg']['median']:.3f} | {p['angular_spread_deg']['median']:.3f} | {p['predicted_quintic_position_spread_at_0p25s_deg']['median']:.3f} |")
    lines += ["", "The complete per-decision pairwise, direction, hip/knee-ratio, cost-gap and feasibility-margin values are in JSON. Identical chosen labels alone cannot prove that ranking is robust or that this small positive-progress lattice covers the legal action landscape. Counterfactual rollouts are needed before judging headroom.", ""]
    (OUT/"CURRENT_ACTION_SPACE_AUDIT.md").write_text("\n".join(lines))
    print(json.dumps({"total_decisions":len(rows),"selected_labels":result["selected_labels"],"phase":phase},indent=2))

if __name__=="__main__": audit()
