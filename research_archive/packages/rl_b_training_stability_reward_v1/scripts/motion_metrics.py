"""Evaluation-only Human motion from lossless saved native evidence. No simulator."""
from pathlib import Path
import json,sys
from research_common import ROOT,RUNTIME,atomic,sha,now
sys.path.insert(0,str(RUNTIME))
from stream_json import array_items,read_evidence
import numpy as np

def read(p):
    with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def metrics(run,destination=None):
    run=Path(run);ep=run/'env/episode_0001'
    destination=Path(destination) if destination else run
    assert destination.resolve().is_relative_to(ROOT),'HISTORICAL_OUTPUT_WRITE_FORBIDDEN'
    destination.mkdir(parents=True,exist_ok=True);out=destination/'COMMON_MOTION_METRICS.json'
    if out.exists():return read(out)
    m=read(ep/'episode_summary.json');raw=ep/'runtime_artifacts.json'
    start=m['native_steps_total']*.00025-m['task_s'];end=m['native_steps_total']*.00025
    qi=m['physical_evaluation_only']['human_qpos_indices'];vi=m['physical_evaluation_only']['human_dof_indices']
    data=[]
    for x in array_items(raw,'native_states_evaluation_only'):
        if start-.020000001<=x['time_s']<=end+1e-9:
            data.append([x['time_s'],*[x['qpos_evaluation_only'][i] for i in qi],*[x['qvel_evaluation_only'][i] for i in vi]])
    z=np.asarray(data);t=z[:,0];q=z[:,1:3];v=z[:,3:5];task=t>start+1e-9
    a=(v[1:]-v[:-1])/(t[1:]-t[:-1])[:,None];at=t[1:]
    j=(a[1:]-a[:-1])/(at[1:]-at[:-1])[:,None];jt=at[1:]
    vv=v[task];aa=a[at>start+1e-9];jj=j[jt>start+1e-9]
    assert len(vv)==len(aa)==len(jj)==m['task_native_steps']
    trace=[x for x in array_items(raw,'trace') if x['stage']=='TASK']
    unique={float(x['time_s']):x for x in trace};trace=[unique[k] for k in sorted(unique)]
    actual=np.asarray([x['truth_state'][:2] for x in trace]);ref=np.asarray([x['q_ref_rad'] for x in trace])
    tracking=np.degrees(np.sqrt(np.mean((actual-ref)**2,axis=0)))
    contract=read(ep/'public_reward_contract.json');target=np.asarray(contract['start_return_target_rad']);goal=np.asarray(contract['outbound_goal_target_rad'])
    returned=np.asarray([x['truth_state'][:2] for x in trace if x['task_phase']=='RETURN'])
    outbound=np.asarray([x['truth_state'][:2] for x in trace if x['task_phase']=='OUTBOUND'])
    rms=lambda x:np.degrees(np.sqrt(np.mean(x*x,axis=0))).tolist()
    peak=lambda x:np.degrees(np.max(np.abs(x),axis=0)).tolist()
    result=dict(time_utc=now(),category='SAVED_ACTUAL_NATIVE_HUMAN_EVALUATION_ONLY',
       run=str(run),source_sha256=sha(Path(__file__)),status=m['status'],success=m['success'],
       integral_scope='COMPLETE_TASK' if m['success'] else 'FAILED_PARTIAL_TASK',task_s=m['task_s'],
       JF=m['force_integral_N_s'],JM=m['moment_integral_Nm_s'],task_native_steps=len(vv),
       tracking_RMS_deg=tracking.tolist(),velocity_RMS_deg_s=rms(vv),velocity_peak_deg_s=peak(vv),
       acceleration_RMS_deg_s2=rms(aa),acceleration_peak_deg_s2=peak(aa),
       jerk_RMS_deg_s3=rms(jj),jerk_peak_deg_s3=peak(jj),
       terminal_q_deg=np.degrees(q[-1]).tolist(),terminal_dq_deg_s=np.degrees(v[-1]).tolist(),
       terminal_return_signed_error_deg=np.degrees(q[-1]-target).tolist(),
       terminal_return_absolute_error_deg=np.degrees(np.abs(q[-1]-target)).tolist(),
       RETURN_overshoot_below_goal_deg=np.degrees(np.maximum(0.,target-returned).max(0)).tolist() if len(returned) else None,
       OUTBOUND_overshoot_above_goal_deg=np.degrees(np.maximum(0.,outbound-goal).max(0)).tolist() if len(outbound) else None,
       definitions='Tracking: unique last 5ms TASK trace physical truth minus applied q_ref (original scorer convention). Derivatives: backward native velocity differences including pre-TASK anchors. No invented jerk threshold.',
       generalization='KNOWN_NOMINAL_ONLY',formal_matched_qualification='NOT_GRANTED')
    np.savez_compressed(destination/'ACTUAL_HUMAN_TASK_SERIES.npz',time_s=t[task]-start,q_rad=q[task],
                        dq_rad_s=vv,ddq_rad_s2=aa,jerk_rad_s3=jj)
    atomic(out,result);return result
if __name__=='__main__':
    x=metrics(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None);print(json.dumps({k:x[k] for k in ['success','JF','JM','tracking_RMS_deg','jerk_RMS_deg_s3']}))
