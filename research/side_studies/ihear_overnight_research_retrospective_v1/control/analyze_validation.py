"""Fixed-denominator held-out analysis; no simulation."""
from pathlib import Path
import os,json,time,itertools,hashlib
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def science(c):return {k:v for k,v in c.items() if k not in ['id','stage']}
def boundary_state(ident,phase,index):
    p=S/'output'/(ident+'_DECISIONS.json')
    if not p.exists():return None
    row=next((r for r in load(p)['rows'] if r.get('phase')==phase and r.get('native_index')==index),None)
    if row is None:return None
    with np.load(S/'source/results'/ident/'trace.npz') as z:origin=float(z['time_s'][z['stage']=='TASK'][0])
    target=origin+float(row['task_s'])
    with np.load(S/'motion_series'/(ident+'.npz')) as z:
        i=int(np.argmin(abs(z['time_s']-target)));error=float(abs(z['time_s'][i]-target));assert error<1e-8,'BOUNDARY_NATIVE_ALIGNMENT'
        return dict(phase=phase,native_index=index,physical_time_s=target,true_q_rad=z['true_q_rad'][i].tolist(),true_dq_rad_s=z['true_dq_rad_s'][i].tolist(),time_error_s=error,source='real forward native state; no qpos/qvel assignment')
def negative_control(ident,base):
    record=next(r for r in load(S/'EXPLORATION_RESULTS.json')['complete_evaluations'] if r['id']==ident)
    by={r['decision_index']:r for r in load(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'))['rows']}
    enabled={r['decision_index'] for r in record['free_execution'] if r['richer_intent_owned_actual_steps']}
    decisions=load(S/'output'/(ident+'_DECISIONS.json'))['rows']
    with np.load(S/'source/results'/ident/'trace.npz') as z:origin=float(z['time_s'][z['stage']=='TASK'][0])
    prefix_rows=[d for d in decisions if d.get('legal_shared_prefix')]
    condition=next(c for c in load(S/'RUN_PLAN.json')['validation_conditions'] if c['name']==ident.split('_')[0])
    assert all(sum(d['phase']==phase for d in prefix_rows)==len(actions) for phase,actions in condition['prefix'].items()),'SHARED_PREFIX_ROW_COUNT'
    shared=set()
    for d in prefix_rows:
        matches=[index for index,r in by.items() if d['phase']==r['phase'] and abs(origin+d['task_s']-r['proposal_physics_s'])<1e-8]
        assert len(matches)==1,'SHARED_PREFIX_RECEIPT_UNIQUE_MATCH'
        shared.add(matches[0])
    times=[r['first_execution_physics_s'] for index,r in by.items() if index not in shared and (index in enabled or r.get('physically_executed_nonzero')) and r.get('first_execution_physics_s') is not None]
    first=min(times) if times else None
    excluded={'selected_schedule_label'};mismatches=[];compared={}
    with np.load(S/'source/results'/ident/'trace.npz') as a,np.load(S/'source/results'/base/'trace.npz') as b:
        ma=a['time_s']<first-1e-9 if first is not None else np.ones(len(a['time_s']),bool)
        mb=b['time_s']<first-1e-9 if first is not None else np.ones(len(b['time_s']),bool)
        for key in a.files:
            if key in excluded or a[key].shape[0]!=len(ma):continue
            x=a[key][ma];y=b[key][mb]
            same=x.shape==y.shape and (np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y))
            compared[key]=same
            if not same:mismatches.append(key)
    return dict(candidate=ident,B=base,first_phase_enabled_or_native_nonzero_owned_plan_execution_physics_s=first,shared_prefix_decision_indices=sorted(shared),shared_prefix_native_steps=sum(by[i]['actual_native_steps'] for i in shared),status='PASS' if not mismatches else 'FAIL',mismatches=mismatches,pre_intervention_fields=compared,excluded_proposal_identity_fields=sorted(excluded),scope='strict physical/control trace before first non-shared potential intervention; shared legal prefix is included in equality check; native nonzero plus phase-enabled free plans; no same RETURN-state claim after different OUTBOUND')
def main():
    selection=load(S/'FROZEN_SELECTION.json');pin=load(S/'preservation/FREEZE_PIN.json');plan=load(S/'RUN_PLAN.json')
    events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];evaluations=[json.loads(x) for x in (S/'EVALUATIONS.jsonl').read_text().splitlines()]
    starts={r['id']:r for r in events if r['event']=='START'};ends={r['id']:r for r in events if r['event']=='END'};tests=[r for r in starts.values() if r.get('mode') in ['repeat','V1','V2','V3','V4']]
    first=min((r['unix'] for r in tests),default=None)
    freeze_checks=dict(selection_bytes_unchanged=sha(S/'FROZEN_SELECTION.json')==pin['selection_sha256'],pinned_copy_equal=sha(S/'preservation/FROZEN_SELECTION_PINNED.json')==pin['selection_sha256'],manifest_unchanged=sha(S/'CODE_MANIFEST.json')==pin['code_manifest_sha256'],run_plan_unchanged=sha(S/'RUN_PLAN.json')==pin['run_plan_sha256'],freeze_and_pin_before_first_test=first is not None and selection['unix']<=pin['pin_unix']<first,full_scientific_selection_equal=all(science(selection[arm]['candidate'])==pin['candidate_scientific_fields'][arm] for arm in ['best','secondary','diagnostic']))
    assert all(freeze_checks.values()),('FREEZE_CONTRACT',freeze_checks)
    rows=[];states=[];checks=[];conditions=plan['validation_conditions'];assert len(conditions)==4
    secondary_alias=science(selection['secondary']['candidate'])==science(selection['best']['candidate'])
    for condition in conditions:
        name=condition['name'];base=name+'_B0_match';bp=S/'reports'/(base+'_MEASURED.json');b=load(bp) if bp.exists() else None
        if b:
            state=dict(condition=name,B_OUT_after_shared_prefix=boundary_state(base,'OUTBOUND',len(condition['prefix'].get('OUTBOUND',[]))))
            if condition['prefix'].get('RETURN'):state['B_RETURN_after_shared_prefix']=boundary_state(base,'RETURN',len(condition['prefix']['RETURN']))
            states.append(state)
        for arm in ['frozen_best','frozen_secondary']:
            ident=name+'_'+arm;alias=arm=='frozen_secondary' and secondary_alias;actual_id=name+'_frozen_best' if alias else ident
            r=next((r for r in evaluations if r['id']==actual_id),None);attempted=actual_id in starts;terminal=actual_id in ends
            row=dict(condition=name,arm=arm,candidate=ident,actual_evaluation_id=actual_id,B=base,prefix=condition['prefix'],attempted=attempted,terminal=terminal,secondary_alias_of_primary=alias,complete_task=False,J_F_N_s=None,B_J_F_N_s=b['J_F_N_s'] if b else None,gain_percent=None,motion_pass=False,failed_requirements=['NOT_RUN' if not attempted else 'INCOMPLETE_OR_UNRESOLVED_TASK'],full_JF_status='NOT_EVALUABLE',qualification='NOT_RUN' if not attempted else 'UNRESOLVED',no_parameter_update=False)
            if r is not None and b:
                frozen=selection['best' if arm=='frozen_best' else 'secondary']['candidate'];same=science(r['candidate'])==science(frozen);assert same,'FULL_VALIDATION_CANDIDATE_CHANGED'
                exact=load(S/'reports'/(actual_id+'_SNAPSHOT.json'))['hash']==load(S/'reports'/(base+'_SNAPSHOT.json'))['hash'];assert exact,'VALIDATION_INITIAL_STATE_MISMATCH'
                m=load(S/'reports'/(actual_id+'_MEASURED.json'));c=r['comparison'];gain=(b['J_F_N_s']-m['J_F_N_s'])/b['J_F_N_s']*100;assert abs(gain-c['gain_percent'])<1e-10
                control=negative_control(actual_id,base);checks.append(control)
                absolute_ok=m['axes']['PHYSICAL_TASK_VALID']=='PASS' and m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS'
                passed=bool(c['acceptance_pass'] and absolute_ok and control['status']=='PASS' and terminal)
                fail=list(c['failed_requirements'])+([] if absolute_ok else ['ABSOLUTE_PHYSICS_OR_TASK'])+([] if control['status']=='PASS' else ['PRE_INTERVENTION_CAUSAL_CONTROL'])+([] if terminal else ['ATTEMPT_NOT_TERMINAL'])
                row.update(complete_task=True,J_F_N_s=m['J_F_N_s'],gain_percent=gain,motion_pass=passed,failed_requirements=fail,full_JF_status='COMPLETE_TASK',qualification='PASS' if passed else 'FAIL',full_initial_snapshot_equal=exact,comparison=c,no_parameter_update=same,physically_generated_state=True,negative_control_status=control['status'])
            elif terminal:row.update(qualification='FAIL',failed_requirements=['TERMINAL_INCOMPLETE_TASK'],task_failure_report=str(S/'reports'/(actual_id+'_TASK_FAILURE.json')))
            rows.append(row)
    differences=[]
    for a,b in itertools.combinations(states,2):
        x=a['B_OUT_after_shared_prefix'];y=b['B_OUT_after_shared_prefix']
        if x and y:differences.append(dict(conditions=[a['condition'],b['condition']],q_max_abs_difference_rad=float(np.max(abs(np.asarray(x['true_q_rad'])-y['true_q_rad']))),dq_max_abs_difference_rad_s=float(np.max(abs(np.asarray(x['true_dq_rad_s'])-y['true_dq_rad_s'])))))
    primary=[r for r in rows if r['arm']=='frozen_best'];secondary=[r for r in rows if r['arm']=='frozen_secondary'];classified=all(r['attempted'] and r['terminal'] and r['qualification'] in ['PASS','FAIL'] for r in rows)
    force_counts=dict(primary_force_reduction_count=sum(r['gain_percent'] is not None and r['gain_percent']>0 for r in primary),primary_force_reduction_and_motion_pass_count=sum(r['motion_pass'] and r['gain_percent'] is not None and r['gain_percent']>0 for r in primary))
    output=dict(generated_unix=time.time(),frozen_before_any_validation=all(freeze_checks.values()),freeze_checks=freeze_checks,freeze_unix=selection['unix'],pin_unix=pin['pin_unix'],first_test_START_unix=first,no_validation_reselection=all(freeze_checks.values()),same_Human=True,new_Human=False,clock='SCIENTIFIC_SIMULATION',rows=rows,real_boundary_states=states,pairwise_OUT_state_differences=differences,pre_intervention_negative_controls=checks,primary_pass=sum(r['motion_pass'] for r in primary),primary_condition_count=4,primary_attempted_count=sum(r['attempted'] for r in primary),primary_complete_task_count=sum(r['complete_task'] for r in primary),secondary_pass=sum(r['motion_pass'] for r in secondary),secondary_condition_count=4,secondary_attempted_count=sum(r['attempted'] for r in secondary),secondary_complete_task_count=sum(r['complete_task'] for r in secondary),secondary_independent_arm=not secondary_alias,scope='four preregistered same-Human legal shared prefixes; frozen unconsumed suffix; incomplete attempted conditions remain in denominator with full JF NOT_EVALUABLE; no cross-Human/full original-slot generalization',status='COMPLETE' if classified else 'PARTIAL_OR_PENDING',physics_attempts_added_by_this_analysis=0)
    output.update(force_counts)
    (S/'VALIDATION_RESULTS.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:output[k] for k in ['status','primary_pass','primary_condition_count','primary_attempted_count','primary_complete_task_count','secondary_pass','secondary_condition_count']}))
if __name__=='__main__':main()
