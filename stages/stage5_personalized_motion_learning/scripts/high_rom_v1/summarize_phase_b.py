"""Aggregate retained Stage-B development traces against preregistered rules."""
from __future__ import annotations
import json, hashlib, math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/'stages/stage5_personalized_motion_learning'
DOC=STAGE/'docs/high_rom_v1'
OUT=STAGE/'results/high_rom_v1/development'

def dwell(time,mask):
    ix=np.where(mask)[0]
    if not len(ix):return 0.
    first=last=int(ix[0]);longest=0.
    for index in ix[1:]:
        index=int(index)
        if index!=last+1:
            longest=max(longest,float(time[last]-time[first]));first=index
        last=index
    return max(longest,float(time[last]-time[first]))

def score(path,case,contract,goal_deg=(120.,120.),start_deg=(5.,10.)):
    result={'case_key':case['case_key'],'physical_variant':case['physical_variant'],
            'candidate':case['candidate'],'output':str(path),'registered_case_sha256':case['sha256']}
    casefile=ROOT/case['path']
    result['case_hash_valid']=casefile.is_file() and hashlib.sha256(casefile.read_bytes()).hexdigest()==case['sha256']
    final=path/'HIGH_ROM_CASE_RESULT.json'
    if not final.exists():return {**result,'status':'NOT_RUN','pass':False}
    launch=json.loads(final.read_text());result['status']=launch['status'];result['abort_reason']=launch.get('abort_reason');result['host_elapsed_s']=launch.get('elapsed_host_s')
    if not (path/'summary.json').exists() or not (path/'trace.npz').exists():return {**result,'pass':False,'classification':'INCOMPLETE_OR_RUNTIME_EXCEPTION'}
    summary=json.loads((path/'summary.json').read_text());z=np.load(path/'trace.npz');t=z['time_s'];true=z['evaluation_only_human_state_rad_rad_s'];hat=z['estimated_human_state_rad_rad_s'];task=z['stage']=='TASK';goal=np.radians(goal_deg);start=np.radians(start_deg)
    angle=np.radians(contract['angle_completion_tolerance_deg']);speed=np.radians(contract['velocity_completion_tolerance_deg_s'])
    return_start=next((r['time_s'] for r in summary['task']['phase_transitions'] if r['to']=='RETURN'),None)
    goal_valid=task & (t <= return_start+1e-9 if return_start is not None else True) & np.all(np.abs(true[:,:2]-goal)<=angle,axis=1) & np.all(np.abs(true[:,2:])<=speed,axis=1)
    true_dwell=dwell(t,goal_valid)
    returned=bool(np.all(np.abs(true[-1,:2]-start)<=angle) and np.all(np.abs(true[-1,2:])<=speed))
    transitions=summary['task']['phase_transitions'];phase=[(r['from'],r['to']) for r in transitions];expected=[('OUTBOUND','HOLD'),('HOLD','RETURN'),('RETURN','COMPLETE')]
    phase_times=[float(transitions[0]['time_s']-t[np.where(task)[0][0]])]+[float(transitions[i]['time_s']-transitions[i-1]['time_s']) for i in range(1,len(transitions))] if np.any(task) and transitions else []
    requests=[r for r in summary['timing']['requests'] if r.get('stage')=='TASK'];activation=[r['activation_age_ms'] for r in requests if r.get('activation_age_ms') is not None];max_age=max(activation,default=None)
    torque=float(summary['task']['peak_robot_torque_fraction'] or 0.);force=float(summary['task']['peak_force_n'] or 0.);moment=float(summary['task']['peak_moment_nm'] or 0.)
    v=np.max(np.abs(np.degrees(true[task,2:])),axis=0) if np.any(task) else np.full(2,np.nan)
    rv=np.max(np.abs(np.degrees(z['cr12_dq_rad_s'][task])),axis=0) if np.any(task) else np.full(6,np.nan)
    av=task & z['actual_human_acceleration_valid'];a=np.max(np.abs(np.degrees(z['actual_human_acceleration_rad_s2'][av])),axis=0) if np.any(av) else np.full(2,np.nan)
    session=float(summary['task'].get('minimum_session_clearance_m_deployable') or -math.inf);truth=float(summary['task'].get('minimum_true_physical_clearance_m_evaluation_only') or -math.inf)
    sleeve=z['dev_d_measured_sleeve_gap_m'][task];sleeve_min=float(np.min(sleeve[np.isfinite(sleeve)])) if np.any(np.isfinite(sleeve)) else None
    monitor=summary['qualification']['true_physics'];contacts=int(monitor['shank_bed_contact_steps']['TASK']);romviol=int(monitor['rom_violation_steps']['TASK'])
    conditions={'summary_complete':summary['status']=='COMPLETE','transition_order':phase==expected,'true_goal_dwell':true_dwell>=contract['true_goal_dwell_min_s'],'true_return':returned,'phase_timeouts':len(phase_times)==3 and all(x<=contract['phase_timeout_s']+1e-9 for x in phase_times) and summary['task']['physics_duration_s']<=contract['global_task_timeout_s']+1e-9,'force':force<=contract['force_limit_n'],'moment':moment<=contract['moment_limit_nm'],'torque':torque<=contract['robot_torque_fraction_max'],'human_speed':bool(np.all(v<=contract['human_velocity_limit_deg_s'])),'human_acceleration':bool(np.all(a<=contract['human_acceleration_limit_deg_s2'])),'robot_speed':bool(np.all(rv<=contract['robot_velocity_limit_deg_s'])),'session_clearance':session>=contract['clearance_m_min'],'true_clearance':truth>=contract['clearance_m_min'],'measured_sleeve_clearance':sleeve_min is not None and sleeve_min>=contract['clearance_m_min'],'no_shank_table_contact':contacts<=contract['physical_shank_table_contact_count_max'],'no_human_rom_violation':romviol==0,'plan_age':max_age is not None and max_age<contract['plan_max_activation_age_ms'],'case_hash':result['case_hash_valid']}
    result.update(pass_=all(conditions.values()),conditions=conditions,true_goal_continuous_dwell_s=true_dwell,true_return=returned,final_true_q_deg=np.degrees(true[-1,:2]).tolist(),final_true_dq_deg_s=np.degrees(true[-1,2:]).tolist(),maximum_estimation_error_deg=np.max(np.abs(np.degrees(hat[task,:2]-true[task,:2])),axis=0).tolist(),peak_force_n=force,peak_moment_nm=moment,peak_robot_torque_fraction=torque,peak_human_speed_deg_s=v.tolist(),peak_human_acceleration_deg_s2=a.tolist(),peak_robot_speed_deg_s=rv.tolist(),minimum_session_shank_clearance_m=session,minimum_true_shank_clearance_m=truth,minimum_measured_sleeve_gap_m=sleeve_min,maximum_plan_activation_age_ms=max_age,task_physics_duration_s=summary['task']['physics_duration_s'],phase_durations_s=phase_times)
    result['pass']=result.pop('pass_');return result

def main():
    matrix_path=DOC/'PHASE_B_MATRIX.json';matrix=json.loads(matrix_path.read_text());out={'schema':'high_rom_v1_phase_b_development_results','matrix_sha256':hashlib.sha256(matrix_path.read_bytes()).hexdigest(),'matrix_cases':len(matrix['rows']),'planned_runs':len(matrix['cases']),'rows':[]}
    out['attempt_history']=[]
    for case in matrix['cases']:
        short=case['case_key'].removeprefix('high_rom_').removesuffix('_v1')
        paths=sorted(OUT.glob(short+'_attempt_*'))
        attempts=[score(path,case,matrix['scoring']) for path in paths]
        out['attempt_history'].extend(attempts)
        out['rows'].append(attempts[-1] if attempts else score(OUT/(short+'_attempt_01'),case,matrix['scoring']))
    out['completed_count']=sum(r['status']=='COMPLETE' for r in out['rows']);out['passed_count']=sum(r['pass'] for r in out['rows']);out['failed_count']=sum(r['status'] not in ('COMPLETE','NOT_RUN') for r in out['rows']);out['not_run_count']=sum(r['status']=='NOT_RUN' for r in out['rows']);out['single_candidate_all_eight_pass']=all(r['pass'] for r in out['rows'] if r['candidate']=='high_rom_sync_feedback_v1') and sum(r['candidate']=='high_rom_sync_feedback_v1' for r in out['rows'])==8
    (DOC/'PHASE_B_RESULTS.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps({k:out[k] for k in ('completed_count','passed_count','failed_count','not_run_count','single_candidate_all_eight_pass')}))
if __name__=='__main__':main()
