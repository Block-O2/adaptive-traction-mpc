"""Read-only physical-data analysis; no imported runner, plant or optimizer."""
from pathlib import Path
import os,json,time,hashlib,collections,math,sys
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
def load(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()] if Path(p).exists() else []
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda:f.read(2**20),b''):h.update(part)
    return h.hexdigest()
def put(name,data):
    p=S/name;temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n');temp.replace(p)
def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    return value
HARD=['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation','case_hash']

def layers(row,metric):
    evaluator=metric['native_physical_audit']['unchanged_evaluator'];physical=evaluator['physical_task_result']
    conditions=physical['scorer_v2_common_conditions'];hard={k:conditions.get(k) for k in HARD}
    safety=all(v is True for v in hard.values()) and bool(physical.get('finite_trace')) and bool(physical.get('finite_native')) and bool(physical.get('activation_certificates_valid')) and bool(physical.get('reference_boundary_C2'))
    a=bool(safety and metric['axes']['PHYSICAL_TASK_VALID']=='PASS' and metric['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS')
    b=bool(row['comparison']['acceptance_pass'])
    return dict(A_original_physics_and_task='PASS' if a else 'FAIL_OR_UNRESOLVED',A_hard_conditions=hard,
                B_frozen_motion_comparison='PASS' if b else 'FAIL',B_failed_requirements=row['comparison']['failed_requirements'],
                level='LEVEL1' if a and b else 'PHYSICAL_RESEARCH_MOTION_FAIL' if a else 'UNQUALIFIED',
                native_B_new_level2_claim=False,host_level3='NOT_RUN',clinical='NOT_ESTABLISHED')

def dense_recheck(ident,base_ident=None):
    metric=load(S/'reports'/(ident+'_MEASURED.json'));p=S/'motion_series'/(ident+'.npz')
    with np.load(p) as z:
        t=z['time_s'].copy();q=z['true_q_rad'].copy();v=z['true_dq_rad_s'].copy();a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2);phase=z['phase'].copy()
        assert np.array_equal(a,z['acceleration_rad_s2']) and np.array_equal(j,z['jerk_rad_s3']),'DENSE_DERIVATIVE_MISMATCH'
    assert np.all(np.isfinite(q)) and np.all(np.isfinite(v)) and np.max(abs(np.diff(t)-.00025))<1e-10
    stats={}
    for name,x in [('velocity_deg_s',np.rad2deg(v)),('acceleration_deg_s2',np.rad2deg(a)),('jerk_deg_s3',np.rad2deg(j))]:
        r=dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
        for key,value in r.items():assert np.max(abs(value-np.asarray(metric['motion']['raw']['full'][name][key])))<1e-8,'MOTION_METRIC_RECHECK'
        stats[name]=r
    exposure={}
    if base_ident:
        b=load(S/'reports'/(base_ident+'_MEASURED.json'))
        for name,x in [('velocity_deg_s',np.rad2deg(v)),('acceleration_deg_s2',np.rad2deg(a)),('jerk_deg_s3',np.rad2deg(j))]:
            threshold=1.1*np.asarray(b['motion']['raw']['full'][name]['max_abs'])
            exceed=abs(x)>threshold
            exposure[name]=dict(threshold_basis='110% of matched B raw max, diagnostic exposure; jerk max not a frozen pass gate',threshold=threshold,
                                full_duration_s=np.sum(exceed[:-1]*np.diff(t)[:,None],axis=0),
                                phase_duration_s={ph:np.sum(exceed[:-1]*(phase[:-1]==ph)[:,None]*np.diff(t)[:,None],axis=0) for ph in ['OUTBOUND','HOLD','RETURN']})
    trace=S/'source/results'/ident/'trace.npz';summary=load(S/'source/results'/ident/'summary.json')
    with np.load(trace) as z:
        use=z['stage']=='TASK';tt=z['time_s'][use];force=np.linalg.norm(z['physical_cuff_force_world_n'][use],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][use],axis=1)
        references=z['reference_q_rad'][use];truth=z['evaluation_only_human_state_rad_rad_s'][use]
        _,reverse=np.unique(tt[::-1],return_index=True)
        unique_indices=np.sort(len(tt)-1-reverse)
        tracking=np.rad2deg(np.sqrt(np.mean((truth[unique_indices,:2]-references[unique_indices])**2,axis=0)))
    dt=np.diff(tt);jf=float(force[:-1]@dt);mi=float(moment[:-1]@dt)
    assert abs(jf-metric['J_F_N_s'])<1e-8 and abs(mi-metric['moment_integral_Nm_s'])<1e-8,'INDEPENDENT_FORCE_INTEGRAL'
    assert np.max(abs(tracking-np.asarray(metric['tracking_RMS_deg'])))<1e-8,'TRACKING_RECHECK'
    transitions={r['to']:r['time_s'] for r in summary['task']['phase_transitions']}
    bounds=[tt[0],transitions['HOLD'],transitions['RETURN'],transitions['COMPLETE']];costs={}
    for ph,start,end in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
        interval=np.maximum(0,np.minimum(tt[1:],end)-np.maximum(tt[:-1],start))
        costs[ph]=dict(J_F_N_s=float(force[:-1]@interval),moment_integral_Nm_s=float(moment[:-1]@interval),duration_s=float(interval.sum()))
    assert abs(sum(x['J_F_N_s'] for x in costs.values())-jf)<1e-8
    assert abs(sum(x['moment_integral_Nm_s'] for x in costs.values())-mi)<1e-8
    for ph,cost in costs.items():
        for key in ['J_F_N_s','moment_integral_Nm_s']:
            assert abs(cost[key]-metric['phase_cost']['phases'][ph][key])<1e-8,'PHASE_METRIC_RECHECK'
    return clean(dict(id=ident,status='PASS',native_motion_samples=len(t),raw_motion_stats=stats,exceedance_exposure=exposure,J_F_N_s=jf,moment_integral_Nm_s=mi,phase_costs=costs,tracking_RMS_deg=tracking,
                      dense_hash=sha(p),trace_hash=sha(trace),source='independent npz/summary recheck, no physics; raw derivatives, original left TASK integral'))

def main():
    events=lines(S/'ATTEMPTS.jsonl');evaluations=lines(S/'EVALUATIONS.jsonl');failures=lines(S/'FAILED_CANDIDATES.jsonl')
    starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END']
    assert len({r['id'] for r in starts})==len(starts),'DUPLICATE_START'
    counts=collections.Counter(r['id'] for r in ends);assert all(n==1 for n in counts.values()),'DUPLICATE_END'
    records=[]
    for row in evaluations:
        p=S/'reports'/(row['id']+'_MEASURED.json');m=load(p)
        summary=load(S/'source/results'/row['id']/'summary.json')
        lineage=load(S/'reports'/(row['id']+'_EXECUTED_RESIDUAL_RECEIPTS.json'))
        owner={x['decision_index']:x for x in lineage['rows']};free_execution=[]
        for rec in summary['learning_records']:
            meta=rec.get('selected_plan',{}).get('execution_screen',{}).get('free_trajectory')
            if not meta:continue
            actual=owner.get(rec.get('decision_index'),{})
            parameters=meta['parameters'];phase=actual.get('phase')
            indices=([0,1,2,3,4,10,11,12,13] if phase=='OUTBOUND' else [5,6,7,8,9,14,15,16,17] if phase=='RETURN' else [])
            phase_enabled=any(abs(parameters[i])>1e-12 for i in indices)
            target_change=float(np.max(abs(np.asarray(meta.get('proposed_target',[0,0]))-np.asarray(meta.get('original_target',[0,0]))))) if 'proposed_target' in meta else None
            owned=bool(rec.get('selected_plan_activated') and actual.get('actual_native_steps',0)>0)
            free_execution.append(dict(decision_index=rec.get('decision_index'),position_proposal_status=meta['status'],parameters=meta['parameters'],
                                       activated=bool(rec.get('selected_plan_activated')),actual_native_steps=actual.get('actual_native_steps',0),phase=actual.get('phase'),
                                       registered_free_metadata_owned_plan=owned,phase_parameters_enabled=phase_enabled,
                                       accepted_position_target_change_rad=target_change if meta['status']=='ACCEPTED' else None,
                                       richer_intent_owned_actual_steps=owned and phase_enabled,
                                       interpretation='phase-enabled receipt-owned plan; parameter presence alone does not prove a changed physical trajectory or realized velocity'))
        dense=S/'motion_series'/(row['id']+'.npz')
        with np.load(dense) as z:
            motion_hash=hashlib.sha256(z['time_s'].tobytes()+z['true_q_rad'].tobytes()+z['true_dq_rad_s'].tobytes()).hexdigest()
        records.append(dict(**row,layers=layers(row,m),complete_evaluation_relative_path=str(p.relative_to(S)),complete_evaluation_sha256=sha(p),
                            actual_motion_hash=motion_hash,free_execution=free_execution,
                            motion=m['motion'],dose=m['dose'],tracking_RMS_deg=m['tracking_RMS_deg'],force_peak_N=m['force_peak_N'],moment_peak_Nm=m['moment_peak_Nm'],moment_integral_Nm_s=m['moment_integral_Nm_s'],clearance=m['clearance'],phase_durations=m['phase_durations']))
    physics=[]
    for start in starts:
        ident=start['id'];data=S/'output'/(ident+'_DATA.json');partial=S/'output'/(ident+'_PARTIAL_COMPUTE.json')
        if data.exists():
            x=load(data)['metric'];physics.append(dict(id=ident,complete_task=bool(x['task_valid']),actual_new_native_steps=x['actual_new_native_physics_steps'],actual_new_simulation_s=x['actual_new_simulation_seconds'],main_model_calls=x.get('actual_new_main_model_inverse_dynamics_api_calls'),native_model_calls=x.get('actual_new_native_worker_model_inverse_dynamics_api_calls')))
        elif partial.exists():
            x=load(partial);physics.append(dict(id=ident,complete_task=False,partial=True,actual_new_native_steps=x.get('actual_new_native_physics_steps'),actual_new_simulation_s=x.get('actual_new_simulation_seconds'),error_status=x['status']))
        else:physics.append(dict(id=ident,status='ACTIVE_OR_UNRESOLVED',actual_new_native_steps=None))
    selection=load(S/'FROZEN_SELECTION.json') if (S/'FROZEN_SELECTION.json').exists() else None
    output=dict(version='IHEAR_OVERNIGHT_EXPLORATION_RESULTS_v1',generated_unix=time.time(),status='FROZEN_PENDING_FINAL_VERIFICATION' if selection else 'IN_PROGRESS',
                budget=load(S/'RUN_PLAN.json'),physical_attempt_start_count=len(starts),physical_attempt_end_count=len(ends),open_attempt_ids=[r['id'] for r in starts if counts[r['id']]==0],
                all_attempts_including_failures_and_parents=events,actual_physical_work=physics,known_actual_new_native_steps=sum(x['actual_new_native_steps'] or 0 for x in physics),
                actual_step_total_exact=all(x['actual_new_native_steps'] is not None for x in physics),complete_evaluations=records,failed_candidates=failures,
                physical_candidate_rollout_count=sum(r.get('kind')=='FULL_TASK_FORK' for r in starts),unique_complete_candidate_parameter_keys=len({json.dumps(dict(phases=r['candidate'].get('phases'),table=r['candidate'].get('table'),free=r['candidate'].get('free_parameters')),sort_keys=True) for r in evaluations}),
                unique_actual_complete_motion_sequences=len({r['actual_motion_hash'] for r in records}),richer_intent_owned_rollout_count=sum(any(x['richer_intent_owned_actual_steps'] for x in r['free_execution']) for r in records),
                frozen_selection=selection,no_training=True,no_online_adaptation=True,no_formal_B_change=True,clock='SCIENTIFIC_SIMULATION',
                clinical_qualification=False,levels_note='All richer nonzero references are LEVEL1 at most. Motion-fail candidates remain physical research, not high-quality validated motions. Host/deployment not tested.',
                mathematical_rejections=lines(S/'MATHEMATICAL_REJECTIONS.jsonl'),optimizer_status=lines(S/'OPTIMIZER_STATUS.jsonl'),
                wrapper_repair_cycles=2,wrapper_repair_denominator_not_reset=True)
    put('EXPLORATION_RESULTS.json',output)
    if selection:
        reps=[selection['best']['base_id'],selection['best']['id'],selection['diagnostic']['id']]
        checks=[dense_recheck(ident,selection['best']['base_id']) for ident in dict.fromkeys(reps)]
        put('INDEPENDENT_SELECTED_METRIC_CHECKS.json',dict(status='PASS',checks=checks,claimed_scope='selected B/best/strong representative only, other complete rows retain original full audits'))
    print(json.dumps(dict(attempts=len(starts),complete_evaluations=len(records),motion_pass=sum(r['layers']['B_frozen_motion_comparison']=='PASS' for r in records),frozen=bool(selection),known_actual_new_native_steps=output['known_actual_new_native_steps'])),flush=True)

if __name__=='__main__':main()
