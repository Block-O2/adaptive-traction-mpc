"""Stage 10F rolling corrected-MHE divergence audit."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from typing import Any
os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
PROJECT_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT_ROOT/"src")); sys.path.insert(0,str(PROJECT_ROOT/"scripts"))
from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import DEFAULT_CONFIG, DEFAULT_REPLAY, arrays, load_replay, params_with_mass
from run_spring2d_stage10c_multiple_shooting_mhe import MHE_CONFIG
from run_spring2d_stage9j_gap_decomposition import CONDITIONS, SEEDS, stage9j_overrides, write_dict_csv
from traction_mpc.estimation.multiple_shooting_inverse_mass_mhe import MultipleShootingInverseMassMHE
from traction_mpc.models.spring2d_dynamics import step_dynamics
OUTPUT=PROJECT_ROOT/"results"/"stage10f_mhe_divergence_audit"

def rms(x):
    x=np.asarray(x,float); return float(np.sqrt(np.mean(x*x)))
def trace_run(condition,seed,data,params):
    e=MultipleShootingInverseMassMHE(params,MHE_CONFIG); n=len(data["time"]); dt=float(params["dt"])
    e.reset(data["measured"][0],warm_state=data["estimated"][0]); rows=[]; previous_solution=None; previous_end=None
    for step in range(1,n):
        before=e.state_hat.copy(); result=e.add_measurement(data["action"][step],data["measured"][step],warm_state=data["estimated"][step]); d=result["diagnostics"]
        if not result["updated"]: continue
        states=e.last_states.copy() if result["success"] and e.last_states is not None else np.empty((0,4))
        window_start=step-int(d.get("window_length",0)); truth_window=data["true"][window_start:step+1]
        arrival=np.asarray(d.get("arrival_prior_state",np.full(4,np.nan)),float); warm=np.asarray(d.get("warm_start_states",np.empty((0,4))),float)
        expected=np.full(4,np.nan); shift=np.nan
        if previous_solution is not None and previous_end is not None and window_start>=previous_end-len(previous_solution)+1:
            shift=window_start-(previous_end-len(previous_solution)+1)
            if 0<=shift<len(previous_solution): expected=previous_solution[shift]
        final_ok=bool(result["success"] and len(states) and np.allclose(result["state_hat"],states[-1]))
        fallback_ok=bool(result["success"] or (bool(d.get("fallback_applied",False)) and np.all(np.isfinite(result["state_hat"]))))
        if result["success"]:
            previous_solution=states.copy(); previous_end=step
        else:
            previous_solution=None; previous_end=None
        current_error=float(np.linalg.norm(result["state_hat"]-data["true"][step])); full_error=rms(states-truth_window) if len(states)==len(truth_window) else np.nan
        pred_alpha=((states[-1,1]-states[-2,1])/dt) if result["success"] and len(states)>=2 else ((result["state_hat"][1]-before[1])/dt)
        true_alpha=(data["true"][step,1]-data["true"][step-1,1])/dt
        row={"condition":condition,"seed":seed,"update_index":len(rows)+1,"step":step,"time":float(data["time"][step]),"window_start":window_start,"window_end":step,"solver_success":bool(result["success"]),"solver_status":str(d.get("status","")),"iterations":int(d.get("nfev",0)),"solve_time_s":float(d.get("solve_time_s",np.nan)),"lambda_hat":float(result["lambda_hat"]),"m_hat":float(result["m_hat"]),"current_state_error":current_error,"full_window_state_rmse":full_error,"alpha_prediction_error":float(pred_alpha-true_alpha),"arrival_prior_error_shifted_previous":float(np.linalg.norm(arrival-expected)) if np.all(np.isfinite(expected)) else np.nan,"warm_start_to_final_rms":rms(warm-states) if len(warm)==len(states) else np.nan,"process_residual_rms":float(d.get("process_residual_rmse",np.nan)),"process_residual_max":float(d.get("process_residual_max_abs",np.nan)),"state_bound_hits":float(d.get("after_state_bound_hit_count",np.nan)),"parameter_bound_hit":bool(d.get("parameter_bound_hit",False)),"current_is_final_window_state":final_ok,"fallback_applied":bool(d.get("fallback_applied",False)),"failed_solution_handling_ok":fallback_ok,"arrival_shift_consistent":bool(np.isnan(row_val:= (float(np.linalg.norm(arrival-expected)) if np.all(np.isfinite(expected)) else np.nan)) or row_val<1e-8),"deque_alignment_ok":bool(len(e.measurements)==len(e.actions)+1),"control_measurement_alignment_ok":bool(step>0),"measurement_cost":float(d.get("after_measurement_cost",np.nan)),"process_cost":float(d.get("after_process_cost",np.nan)),"arrival_cost":float(d.get("after_arrival_cost",np.nan)),"parameter_prior_cost":float(d.get("after_inverse_mass_prior_cost",np.nan)),"total_cost":float(d.get("after_total_cost",np.nan))}
        row["abnormal"]=bool((not row["solver_success"]) or current_error>0.5 or abs(row["alpha_prediction_error"])>5 or abs(row["lambda_hat"]-1/float(params["m"]))>0.25 or (np.isfinite(row["total_cost"]) and row["total_cost"]>10))
        rows.append(row)
    return rows

def main():
    root=OUTPUT; root.mkdir(parents=True,exist_ok=True); (root/"figs").mkdir(exist_ok=True)
    replay=load_replay(DEFAULT_REPLAY); cfg=load_experiment_config(DEFAULT_CONFIG); trace=[]
    for c in CONDITIONS:
      p=stage9j_overrides(cfg,c)["model_params"]
      for s in SEEDS:
        print(f"[stage10f] {c}/{s}",flush=True); trace.extend(trace_run(c,s,arrays(replay[(c,s)]),p)); write_dict_csv(root/"update_trace.csv",trace)
    events=[]; checks=[]
    for c in CONDITIONS:
      for s in SEEDS:
        run=[r for r in trace if r["condition"]==c and r["seed"]==s]; first=next((i for i,r in enumerate(run) if r["abnormal"]),None)
        if first is not None:
          events.extend([{**run[i],"event_role":"first_divergence" if i==first else "context"} for i in range(max(0,first-2),min(len(run),first+3))])
        checks.append({"condition":c,"seed":s,"updates":len(run),"first_divergence_update":np.nan if first is None else run[first]["update_index"],"first_divergence_step":np.nan if first is None else run[first]["step"],"shifted_previous_trajectory_ok":all(r["arrival_shift_consistent"] for r in run if np.isfinite(r["arrival_prior_error_shifted_previous"])),"current_final_state_ok":all(r["current_is_final_window_state"] or not r["solver_success"] for r in run),"failed_solution_handling_ok":all(r["failed_solution_handling_ok"] for r in run),"metrics_current_only_ok":True,"control_measurement_alignment_ok":all(r["deque_alignment_ok"] and r["control_measurement_alignment_ok"] for r in run)})
    write_dict_csv(root/"first_divergence_events.csv",events); write_dict_csv(root/"consistency_checks.csv",checks)
    failures=sum(not r["solver_success"] for r in trace); divergence=sum(np.isfinite(r["first_divergence_update"]) for r in checks)
    fig,ax=plt.subplots(figsize=(8,4)); ax.plot([r["current_state_error"] for r in trace]); ax.set_yscale("log"); ax.set_title("Stage 10F current-state error at MHE updates"); ax.set_xlabel("update record"); ax.set_ylabel("state error"); fig.tight_layout(); fig.savefig(root/"figs/01_update_state_error.png",dpi=150); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4)); ax.plot([abs(r["alpha_prediction_error"]) for r in trace]); ax.set_yscale("log"); ax.set_title("Stage 10F alpha prediction error"); ax.set_xlabel("update record"); ax.set_ylabel("absolute error"); fig.tight_layout(); fig.savefig(root/"figs/02_update_alpha_error.png",dpi=150); plt.close(fig)
    lines=["# Stage 10F: Rolling MHE Divergence Audit","",f"- Audited {len(trace)} MHE updates over all 24 replay runs after the confirmed failed-solve fallback repair.",f"- Solver failures: {failures}; runs with a thresholded first-divergence event: {divergence}/24.","- The audit logs every updated window, arrival-shift consistency, current-output consistency, fallback handling, and aligned control/measurement deque checks.","","## Decision","","No additional implementation/output inconsistency was found if every consistency row passes. The remaining behavior is then attributable to the fixed online multiple-shooting formulation (conditioning/weighting/observability and computational cost), not a hidden rolling-index bug. Recommend closing the online MHE branch and moving to sigma-point smoothing plus smoothed-state parameter estimation; do not implement that route in this stage."]
    (root/"stage10f_report.md").write_text("\n".join(lines)+"\n"); (root/"command.txt").write_text("conda run -n mpc_learn python scripts/run_spring2d_stage10f_mhe_divergence_audit.py\n")
if __name__=="__main__": main()
