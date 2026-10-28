"""Recompute raw evidence independently of env reward and runtime summaries."""
from pathlib import Path
import argparse,json,math,bisect,hashlib
from stream_json import array_items,object_value

def norm(v):return math.sqrt(sum(x*x for x in v))
def audit(path,qindices=None,vindices=None):
    keep=('time_s','task_phase','cuff_force_world_n','cuff_moment_world_nm','interval_force_cost_n_s')
    trace=[{k:x[k] for k in keep} for x in array_items(path,'trace') if x['stage']=='TASK']
    if len(trace)<2:raise ValueError('NO_COMPLETE_TASK_BOUNDARY_TRACE')
    # Trace rows are sampled at interval START. A partial rollout may end at
    # the next callback before its boundary is appended to trace. Close that
    # final interval only from the separately captured physical boundary.
    boundary=object_value(path,'last_boundary');original_terminal_phase=trace[-1]['task_phase']
    recorded_jf=sum(x.get('interval_force_cost_n_s',0.) for x in trace)
    closure_added=False
    if boundary and boundary['time_s']>trace[-1]['time_s']+1e-10:
        if boundary['time_s']-trace[-1]['time_s']>.005+1e-8:raise ValueError('UNOBSERVED_BOUNDARY_GAP')
        trace.append({**trace[-1],'time_s':boundary['time_s'],'interval_force_cost_n_s':0.});closure_added=True
    totals={};jf=jm=0.;errors=[];intervals=0
    for left,right in zip(trace[:-1],trace[1:]):
        dt=right['time_s']-left['time_s']
        if dt<=0:errors.append('NONINCREASING_TASK_TIME');continue
        f=norm(left['cuff_force_world_n'])*dt;m=norm(left['cuff_moment_world_nm'])*dt
        phase=left['task_phase'];p=totals.setdefault(phase,{'duration_s':0.,'J_F':0.,'J_M':0.})
        p['duration_s']+=dt;p['J_F']+=f;p['J_M']+=m;jf+=f;jm+=m;intervals+=1
    keep_receipt=('applied','native_steps','start_physics_s','end_physics_s','source_sample_time_s','command_torque_nm')
    receipts=[{k:x.get(k) for k in keep_receipt} for x in array_items(path,'command_receipts')]
    applied=[(i,r) for i,r in enumerate(receipts) if r.get('applied') and r.get('native_steps',0)>0]
    starts=[r['start_physics_s'] for _,r in applied]
    assert starts==sorted(starts),'NONMONOTONIC_RECEIPTS'
    ownership_counts={i:0 for i,_ in applied};count=task_count=0;last_time=None;native_dt=.00025
    task_start=trace[0]['time_s'];task_end=trace[-1]['time_s']
    qmin=[math.inf]*2;qmax=[-math.inf]*2;vmax=[0.]*2;final_q=final_v=None;contacts=0;torque_mismatch=0;unowned=0;grid_errors=0
    for row in array_items(path,'native_states_evaluation_only'):
        t=row['time_s'];count+=1
        if last_time is not None and abs(t-last_time-native_dt)>1e-9:grid_errors+=1
        last_time=t
        idx=bisect.bisect_right(starts,t-native_dt+1e-10)-1
        if idx<0 or t>applied[idx][1]['end_physics_s']+1e-9:unowned+=1
        else:
            ri,r=applied[idx];ownership_counts[ri]+=1
            if max(abs(a-b) for a,b in zip(row['command_torque_nm'],r['command_torque_nm']))>1e-10:torque_mismatch+=1
        if task_start+1e-10<t<=task_end+1e-9:
            task_count+=1;contacts+=bool(row['contact_pairs_evaluation_only'])
            if qindices is not None and vindices is not None:
                q=[row['qpos_evaluation_only'][i] for i in qindices];v=[row['qvel_evaluation_only'][i] for i in vindices]
                if not all(math.isfinite(x) for x in q+v):errors.append('NONFINITE_NATIVE_HUMAN')
                qmin=[min(a,b) for a,b in zip(qmin,q)];qmax=[max(a,b) for a,b in zip(qmax,q)]
                vmax=[max(a,abs(b)) for a,b in zip(vmax,v)];final_q=q;final_v=v
    count_mismatches=[i for i,r in applied if ownership_counts[i]!=r['native_steps']]
    source_age_errors=[i for i,r in applied if r['start_physics_s']-r['source_sample_time_s']< -1e-10 or r['start_physics_s']-r['source_sample_time_s']>=.1-1e-12]
    out={'category':'INDEPENDENT_RECOMPUTATION_FROM_SAVED_RAW','path':str(path),
        'task_duration_s':task_end-task_start,'terminal_phase':original_terminal_phase,'boundary_closure_added':closure_added,
        'J_F_N_s':jf,'J_M_Nm_s':jm,'phase_integrals':totals,'force_peak_N':max(norm(x['cuff_force_world_n']) for x in trace),
        'moment_peak_Nm':max(norm(x['cuff_moment_world_nm']) for x in trace),
        'recorded_interval_J_F':recorded_jf,'J_F_abs_difference':abs(jf-recorded_jf),
        'boundary_intervals':intervals,'native_steps_all':count,'native_task_steps':task_count,'native_grid_errors':grid_errors,
        'unowned_native_steps':unowned,'torque_receipt_mismatches':torque_mismatch,'receipt_count_mismatches':count_mismatches,
        'source_age_errors':source_age_errors,'task_native_contact_steps':contacts,'errors':errors,
        'human_index_source':'caller must supply indices from actual model audit','human_motion':None,
        'full_qualification':'NOT_GRANTED_BY_THIS_AUDIT_ALONE'}
    if final_q is not None:out['human_motion']={'q_min_deg':[math.degrees(x) for x in qmin],'q_max_deg':[math.degrees(x) for x in qmax],
        'abs_dq_max_deg_s':[math.degrees(x) for x in vmax],'final_q_deg':[math.degrees(x) for x in final_q],'final_dq_deg_s':[math.degrees(x) for x in final_v]}
    out['accounting_pass']=not(errors or count_mismatches or source_age_errors or grid_errors or unowned or torque_mismatch) and abs(jf-recorded_jf)<1e-6
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('raw');p.add_argument('--out',required=True);p.add_argument('--qindices');p.add_argument('--vindices');a=p.parse_args()
    indices=lambda x:None if x is None else [int(v) for v in x.split(',')]
    result=audit(Path(a.raw),indices(a.qindices),indices(a.vindices))
    Path(a.out).write_text(json.dumps(result,indent=2));print(json.dumps(result))
