"""Offline diagnostic extraction; immutable saved traces and frozen reward."""
from inventory_v1 import *
import csv, collections, shutil
GAMMA=float(np.exp(-.02/150.));START=np.radians([5.,10.]);GOAL=np.radians([120.,120.])
def stats(a):
    a=np.asarray(a,float)
    return dict(n=len(a),min=np.min(a,axis=0).tolist(),p05=np.quantile(a,.05,axis=0).tolist(),median=np.median(a,axis=0).tolist(),mean=np.mean(a,axis=0).tolist(),std=np.std(a,axis=0).tolist(),p95=np.quantile(a,.95,axis=0).tolist(),max=np.max(a,axis=0).tolist()) if len(a) else None
def extract(row):
    trace=R/row['trace'];assert sha(trace)==row['trace_sha256']
    ep=trace.parent;summary=json.loads((ep/'summary.json').read_text())
    with np.load(trace) as z:
        mask=z['stage']=='TASK';t=z['time_s'][mask];t=t-t[0]
        q=z['estimated_human_state_rad_rad_s'][mask,:2];truth=z['evaluation_only_human_state_rad_rad_s'][mask,:2];ref=z['reference_q_rad'][mask]
        phase=z['task_phase'][mask];dq=z['estimated_human_state_rad_rad_s'][mask,2:]
        rdq=z['reference_dq_rad_s'][mask];rddq=z['reference_ddq_rad_s2'][mask]
    with np.load(ep/'SAC_ACTOR_ACTIONS.npz') as a:
        raw=a['raw_action'].copy();exe=a['executed_action'].copy();at=a['task_s'].astype(float);status=a['status'].copy();reasons=a['rejection_reason'].copy();fallback=a['fallback'].copy()
    accepted=np.isin(status,['ACCEPTED','IDENTICAL_CONTINUATION']);delta=np.abs(exe-raw)
    progress=np.clip((q-START)/(GOAL-START),0,1);trprogress=np.clip((truth-START)/(GOAL-START),0,1)
    out=phase=='OUTBOUND';outp=progress[out]
    transitions=summary['task']['phase_transitions'];phases=list(dict.fromkeys(phase.tolist()));reached=[p for p in phases if p in ('OUTBOUND','HOLD','RETURN','COMPLETE')]
    # Reconstruct potential at next policy decisions from saved 5ms causal trace.
    # All original formal failures stay OUTBOUND. Successful diagnostic rollouts
    # retain exact per-step reward separately; no inferred decomposition replaces it.
    idx=np.abs(t[:,None]-at[None,:]).argmin(axis=0)
    phi=progress[idx].mean(axis=1)
    shaping=-5*phi[0]-5*(1-GAMMA)*phi[1:].sum() if len(phi) else 0.
    parts=dict(force=-row['J_F']/100,shaping=float(shaping),completion=500. if summary['status']=='COMPLETE' else 0.,failure=0. if summary['status']=='COMPLETE' else -1000.,rejection=-.2*int(np.sum(~accepted)))
    goalerr=np.abs(q-GOAL);syncerr=np.max(np.degrees(goalerr),axis=1)
    first_last=stats(raw);windows=[]
    for lo,hi in ((0,.5),(.5,1.5),(1.5,3),(3,10)):
        keep=(at>=lo)&(at<hi)
        if np.any(keep):windows.append(dict(time_range_s=[lo,hi],raw=stats(raw[keep]),executed=stats(exe[keep])))
    result=dict(step=row['training_step'],scope=row['scope'],tag=row['tag'],valid=row['valid'],status=summary['status'],termination_time_s=float(t[-1]),termination_reason=summary.get('abort_reason'),reached_phase=reached[-1] if reached else None,phases=reached,entered_hold='HOLD' in reached,started_return='RETURN' in reached,max_outbound_mean_progress=float(outp.mean(axis=1).max()),max_outbound_synchronized_min_progress=float(outp.min(axis=1).max()),max_outbound_per_joint_progress=outp.max(axis=0).tolist(),max_true_outbound_synchronized_min_progress=float(trprogress[out].min(axis=1).max()),goal_box_closest_max_joint_error_deg=float(syncerr.min()),goal_box_any_within_2deg=bool(np.any(syncerr<=2)),q_est_min_deg=np.degrees(q.min(axis=0)).tolist(),q_est_max_deg=np.degrees(q.max(axis=0)).tolist(),q_est_final_deg=np.degrees(q[-1]).tolist(),q_true_final_deg=np.degrees(truth[-1]).tolist(),reference_final_deg=np.degrees(ref[-1]).tolist(),tracking_rmse_deg=np.sqrt(np.mean(np.degrees(q-ref)**2,axis=0)).tolist(),tracking_peak_abs_deg=np.max(np.abs(np.degrees(q-ref)),axis=0).tolist(),raw_action=first_last,executed_action=stats(exe),raw_target_deg=stats((raw+1)*62.5),executed_target_deg=stats((exe+1)*62.5),raw_saturation_joint_rate=np.mean(np.abs(raw)>=.95,axis=0).tolist(),raw_saturation_any_rate=float(np.mean(np.any(np.abs(raw)>=.95,axis=1))),executed_saturation_any_rate=float(np.mean(np.any(np.abs(exe)>=.95,axis=1))),raw_executed_difference_mean_abs=delta.mean(axis=0).tolist(),raw_executed_difference_max_abs=delta.max(axis=0).tolist(),target_difference_mean_abs_deg=(delta*62.5).mean(axis=0).tolist(),actual_target_modification_rate=float(np.mean(np.any(delta>1e-5,axis=1))),rejection_rate=float(np.mean(~accepted)),fallback_rate=float(np.mean(fallback)),status_counts=dict(collections.Counter(status.tolist())),rejection_reasons=dict(collections.Counter(reasons[~accepted].tolist())),decision_count=len(raw),force_peak_n=row['force_peak'],moment_peak_nm=row['moment_peak'],clearance_m=row['clearance'],true_clearance_m=row['physical_clearance'],J_F_unranked_if_invalid=row['J_F'],reward_parts_offline_estimate=parts,deterministic_return_offline_estimate=sum(parts.values()),reward_reconstruction='force/rejection/terminal exact from archived metrics; OUTBOUND shaping sampled nearest5ms causal trace, verified against exact same-wrapper300k diagnostic',success_proxy=dict(complete=summary['status']=='COMPLETE',hold='HOLD' in reached,returned='RETURN' in reached,simultaneous_goal_box_2deg=bool(np.any(syncerr<=2))),action_time_windows=windows,summary_task=summary['task'],trace=str(trace),trace_sha256=sha(trace),action_sha256=sha(ep/'SAC_ACTOR_ACTIONS.npz'))
    actual_goal=np.all(np.degrees(goalerr)<=1.,axis=1)&np.all(np.abs(np.degrees(dq))<=2.,axis=1)
    reference_proxy=np.all(np.abs(np.degrees(ref-GOAL))<=1.,axis=1)&np.all(np.abs(rdq)<=1e-10,axis=1)&np.all(np.abs(rddq)<=1e-10,axis=1)
    nearest=int(np.argmin(syncerr));longest=duration=0.
    for i,good in enumerate(actual_goal):
        duration=duration+(t[i]-t[i-1] if i else 0.) if good else 0.;longest=max(longest,duration)
    result.update(actual_goal_position_1deg_samples=int(np.sum(np.all(np.degrees(goalerr)<=1.,axis=1))),actual_goal_position_and_speed_samples=int(np.sum(actual_goal)),longest_goal_position_speed_dwell_s=longest,goal_reference_settled_proxy_samples=int(np.sum(reference_proxy)),joint_goal_and_reference_proxy_samples=int(np.sum(actual_goal&reference_proxy)),closest_goal_task_s=float(t[nearest]),closest_goal_q_deg=np.degrees(q[nearest]).tolist(),closest_goal_dq_deg_s=np.degrees(dq[nearest]).tolist(),closest_goal_reference_deg=np.degrees(ref[nearest]).tolist(),closest_goal_reference_dq_deg_s=np.degrees(rdq[nearest]).tolist(),actual_goal_proxy_definition='1deg position and2deg/s velocity; controller reference must also settle, terminal ownership/certification not proven by this proxy',task_physical_ROM_violation_steps=summary.get('qualification',{}).get('true_physics',{}).get('rom_violation_steps'))
    np.savez_compressed(O/f'paths_{row["training_step"]:07d}_{row["scope"]}_{row["tag"]}.npz',task_s=t,q_est_deg=np.degrees(q),q_true_evaluation_only_deg=np.degrees(truth),reference_deg=np.degrees(ref),dq_est_deg_s=np.degrees(dq),phase=phase,action_s=at,raw_action=raw,executed_action=exe)
    return result
def run():
    inv=json.loads((D/'INVENTORY.json').read_text());rows=[]
    for item in sorted(inv['evaluations'],key=lambda r:(r['step'],r['scope'])):
        rows.append(extract(json.loads(Path(item['path']).read_text())))
    primary=[r for r in rows if r['step']>=50000 and r['tag']=='periodic'];assert len(primary)==22
    save('ALL_22_EVALUATION_AUDIT.json',primary);save('EARLY_AND_MEMORY_EVALUATION_AUDIT.json',[r for r in rows if r not in primary])
    fields=['step','scope','valid','termination_time_s','termination_reason','reached_phase','max_outbound_mean_progress','max_outbound_synchronized_min_progress','goal_box_closest_max_joint_error_deg','entered_hold','started_return','rejection_rate','actual_target_modification_rate','raw_saturation_any_rate','force_peak_n','moment_peak_nm','clearance_m','true_clearance_m','deterministic_return_offline_estimate','J_F_unranked_if_invalid']
    for folder in (D,L):
        with (folder/'ALL_22_EVALUATION_AUDIT.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(primary)
    # Existing frozen-contract adversarial reward evidence is reused, never rerun
    # or rescored as formal SAC results.
    old=S/'docs/single_human_sac_expert_v1/r2';root=old.parent;historical=[]
    for name in ('reference','final_reference','early_failure','no_motion','minimal_motion','stalling','timeout','repeated_rejection_after_prefix','skip_hold','incomplete_return'):
        p=old/f'RUN_{name}_20ms_NATIVE.json'
        if not p.exists():p=root/p.name
        if not p.exists():continue
        r=json.loads(p.read_text());historical.append(dict(name=name,path=str(p),sha256=sha(p),status=r.get('status'),reward_totals=r.get('reward_totals'),result=r.get('result'),physical_success=r.get('physical_success'),trace_J_F=r.get('trace_J_F')))
    save('HISTORICAL_REWARD_AUDIT.json',historical)
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    for r in rows:
        if r['scope']=='NATIVE':print(json.dumps({k:r[k] for k in ('step','termination_time_s','termination_reason','max_outbound_mean_progress','max_outbound_synchronized_min_progress','q_est_max_deg','q_est_final_deg','raw_saturation_any_rate','actual_target_modification_rate','rejection_rate','deterministic_return_offline_estimate')}),flush=True)
if __name__=='__main__':run()
