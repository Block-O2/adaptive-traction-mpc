"""Offline aggregation, raw recomputation and explicit split/causal-benefit accounting."""
from pathlib import Path
import json,sys,time,hashlib,collections,importlib.util
import numpy as np
P=Path(__file__).resolve().parent
def read(n,default=None):
    f=P/n;return json.loads(f.read_text()) if f.exists() else default
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
    h=hashlib.sha256()
    with Path(f).open('rb') as s:
        for b in iter(lambda:s.read(2**20),b''):h.update(b)
    return h.hexdigest()
def raw_difference(a,b):
    fields=['estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n']
    result={}
    with np.load(P/'source/results'/a/'trace.npz') as x,np.load(P/'source/results'/b/'trace.npz') as y:
        tx=x['time_s'];ty=y['time_s'];sameclock=tx.shape==ty.shape and np.allclose(tx,ty,atol=1e-8,rtol=0)
        for k in fields:
            if sameclock and x[k].shape==y[k].shape:result[k]=dict(exact_equal=bool(np.array_equal(x[k],y[k],equal_nan=True)),max_abs_difference=float(np.nanmax(abs(x[k]-y[k]))))
            else:result[k]=dict(exact_equal=False,reason='different_time_grid_or_length')
    return dict(a=a,b=b,same_clock_grid=bool(sameclock),fields=result,any_applied_command_difference=not result['cr12_actuator_command_nm']['exact_equal'])
def main():
    independent='--independent' in sys.argv
    cohort=read('COHORT.json');starts={};ends={};events=[json.loads(s) for s in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
    for e in events:
        target=starts if e['event']=='START' else ends if e['event']=='END' else None
        if target is not None:
            assert e['id'] not in target,'DUPLICATE_EVENT';target[e['id']]=e
    assert len(starts)<=80
    if independent:
        spec=importlib.util.spec_from_file_location('raw_independent',P/'control/independent_recompute.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker);checker.P=P
    checks=[];attempts=[]
    for ident,start in starts.items():
        end=ends.get(ident);summary=read('source/results/'+ident+'/summary.json',{});metric=read('output/'+ident+'.json',{})
        completed=summary.get('status')=='COMPLETE'
        audit=read('derived/'+ident+'_INDEPENDENT.json')
        if independent and completed and (P/'reports'/f'{ident}_MEASURED.json').exists() and audit is None:
            try:audit=checker.measure(ident)
            except Exception as e:audit=dict(id=ident,status='FAIL',error=str(e));put('derived/'+ident+'_INDEPENDENT_FAILURE.json',audit)
        if audit:checks.append(audit)
        applied=read('reports/'+ident+'_EVALUATION.json',{}).get('interventions')
        attempts.append(dict(id=ident,patient_id=start.get('patient_id'),run_group=start.get('run_group'),kind=start.get('kind'),trial_number=start.get('trial_number'),
            learning_method=start.get('learning_method'),controller_version=start.get('controller_version'),parent_state=start.get('parent_state'),
            proposed_action=start.get('proposed_action'),accepted_applied_action=applied,start_unix=start['unix'],end_unix=None if end is None else end['unix'],
            returncode=None if end is None else end.get('returncode'),joined=False if end is None else end.get('joined',False),
            actual_new_native_steps=None if end is None else end.get('actual_new_native_steps'),complete_task=completed,
            partial_reason=summary.get('abort_reason') or (read('reports/'+ident+'_ERROR.json',{}) or {}).get('error'),
            JF_complete_N_s=metric.get('J_F') if completed else None,independent_recompute=None if audit is None else audit['status']))
    rows=[];groups=[];continuity=[];third=[];predictions=[]
    mapping={'P00':'P00R','P05':'P05','P08':'P08','V12':'V12','V13':'V13','U14':'U14','U15':'U15','U16':'U16'}
    for patient in cohort['patients']:
        pid=patient['patient_id'];group=mapping[pid];result=read(group+'_RESULTS.json')
        if result is None:
            attempted=any(e.get('patient_id')==pid for e in starts.values())
            groups.append(dict(patient_id=pid,split=patient['split'],status='ATTEMPTED_NO_COMPLETED_COMPARISON' if attempted else 'NOT_RUN',
                reason='V13 reserved by the pre-validation budget amendment; no physics executed' if pid=='V13' else 'see retained attempts and failure records' if attempted else 'no physics executed'))
            continue
        arms={r['method']:r for r in result['rows']};base=arms.get('B');fixed=arms.get('H150');h=read('learning/'+group+'_T1_HISTORY.json')
        groups.append(dict(patient_id=pid,split=patient['split'],status='EXECUTED',rows=len(arms),history_ready=h is not None,
            history_sample_count=None if h is None else h['sample_count'],first_JF_N_s=None if h is None else h['JF_N_s'],
            first_raw_history_sha256=None if h is None else h['raw_history_sha256']))
        for r in result['rows']:
            method=r['method'];qualified=r.get('complete_qualified',False);decision=r['decision'];action=decision['action']
            disabled=arms.get(method+'_DISABLED') if method in ['ILC','BO','VALUE'] else None
            # In development the only no-history ILC rule is the preregistered A0 baseline.
            disabled_scope='population-history imputation; current history withheld'
            if method=='ILC' and disabled is None:disabled=base;disabled_scope='zero-update B; weaker development ablation'
            def gain(other):
                return None if other is None or r['J_F_N_s'] is None or other['J_F_N_s'] is None else other['J_F_N_s']-r['J_F_N_s']
            gb=0. if r is base else gain(base);gd=gain(disabled);gh=gain(fixed)
            adapted=bool(r['interventions'].get('actual_action_adapted',False))
            diff=None
            if r['complete_task'] and base and base['complete_task']:
                diff=raw_difference(r['id'],base['id']);put('derived/'+r['id']+'_APPLIED_DIFFERENCE.json',diff)
                if adapted:assert diff['any_applied_command_difference'],'ACCEPTED_WITHOUT_APPLIED_DIFFERENCE'
            disabled_diff=None
            if disabled and r['complete_task'] and disabled['complete_task']:
                disabled_diff=raw_difference(r['id'],disabled['id']);put('derived/'+r['id']+'_HISTORY_ABLATION_DIFFERENCE.json',disabled_diff)
            causal=bool(method in ['ILC','BO','VALUE'] and qualified and disabled and disabled.get('complete_qualified',False)
                and gd is not None and gd>.01 and gb is not None and gb>.01 and disabled_diff and disabled_diff['any_applied_command_difference'])
            if not adapted and method in ['ILC','BO','VALUE']:outcome='NO_ACTION_CHANGE'
            elif qualified and gb is not None and gb>.01:outcome='QUALIFIED_FORCE_IMPROVEMENT_VS_B'
            elif qualified and gb is not None and gb>1e-8:outcome='QUALIFIED_SMALL_FORCE_SIGNAL_BELOW_0_01_N_s'
            elif r['complete_task'] and gb is not None and gb>.01 and not qualified:outcome='FORCE_SIGNAL_WITH_QUALIFICATION_FAILURE'
            elif adapted:outcome='ACTION_CHANGED_NO_BENEFIT'
            else:outcome='FIXED_CONTROL'
            measured=read(r.get('measured_path') or 'not_present',{})
            row=dict(id=r['id'],patient_id=pid,split=patient['split'],trial_number=2,method=method,action=action,
                history_enabled=decision.get('history_enabled'),history_source=decision.get('history_sha256'),complete_task=r['complete_task'],
                absolute_safety=r['axes']['absolute_safety'],task=r['axes']['task'],execution=r['axes']['causal_execution'],
                motion_relative=r.get('motion_relative','PENDING'),complete_qualified=qualified,action_adapted=adapted,outcome=outcome,
                JF_N_s=r['J_F_N_s'],moment_Nm_s=r['moment_integral_Nm_s'],tracking_RMS_deg=measured.get('tracking_RMS_deg'),
                motion_extra=r.get('motion_extra'),failed_motion=[] if not r.get('motion_comparison') else r['motion_comparison']['failed_requirements'],
                gain_vs_B_N_s=gb,gain_vs_disabled_N_s=gd,gain_vs_H150_N_s=gh,
                disabled_scope=disabled_scope if disabled else None,history_causal_benefit=causal,
                H150_complete_qualified=None if fixed is None else fixed.get('complete_qualified',False),
                above_both_frozen_B_and_H150=bool(qualified and fixed and fixed.get('complete_qualified',False) and gb is not None and gb>.01 and gh is not None and gh>.01),
                strict_history_ablation_pass=causal and patient['split']!='development',raw_difference=diff,
                independent_recompute=read('derived/'+r['id']+'_INDEPENDENT.json',{}).get('status'))
            rows.append(row)
            if decision.get('predictions'):
                selected=decision['predictions'][decision['selected_index']]
                predictions.append(dict(id=r['id'],method=method,patient_id=pid,split=patient['split'],predicted_JF_N_s=selected['predicted_full_JF_N_s'],
                    actual_JF_N_s=r['J_F_N_s'],uncertainty_N_s=selected['uncertainty_N_s'],complete_qualified=qualified,
                    predicted_gain_vs_B_N_s=decision['predictions'][0]['predicted_full_JF_N_s']-selected['predicted_full_JF_N_s'],actual_gain_vs_B_N_s=gb))
        for r in result['rows']:
            c=read('audit/'+r['id']+'_CONTINUITY.json');f=read('audit/'+r['id']+'_FORK.json')
            if c:continuity.append(dict(id=r['id'],patient_id=pid,**c,fork=f,preparation=read('output/'+r['id']+'_PREPARATION.json')))
        tr=read(group+'_T3_RESULTS.json')
        if tr:
            for r in tr['rows']:
                r['independent_recompute']=read('derived/'+r['id']+'_INDEPENDENT.json',{}).get('status')
                c=read('audit/'+r['id']+'_CONTINUITY.json');f=read('audit/'+r['id']+'_FORK.json')
                if c:continuity.append(dict(id=r['id'],patient_id=pid,**c,fork=f,preparation=read('output/'+r['id']+'_PREPARATION.json')))
            by={r['method']:r for r in tr['rows']};gain=tr['improvement_vs_KEEP_N_s']
            t2=next((r for r in rows if r['patient_id']==pid and r['method']=='ILC'),None)
            tr.update(patient_id=pid,split=patient['split'],few_repetition_benefit=bool(t2 and t2['complete_qualified'] and (t2['gain_vs_B_N_s'] or 0)>.01 and gain is not None and gain>.01 and all(by[m].get('complete_qualified') for m in ['B','KEEP','ILC'])))
            third.append(tr)
    learning=[r for r in rows if r['method'] in ['ILC','BO','VALUE']]
    tests=[r for r in learning if r['split']=='heldout']
    bymethod={m:sorted({r['patient_id'] for r in tests if r['method']==m and r['history_causal_benefit']}) for m in ['ILC','BO','VALUE']}
    flags=dict(HISTORY_DATA_READY=any(g.get('history_ready') for g in groups),LEARNING_MODEL_TRAINED=(P/'models/METHOD_FREEZE.json').exists(),
        ACTION_ADAPTED=any(r['action_adapted'] for r in learning),TRIAL_2_QUALIFIED=any(r['complete_qualified'] for r in learning),
        HISTORY_CAUSAL_BENEFIT=any(r['strict_history_ablation_pass'] for r in learning),
        FEW_REPETITION_BENEFIT=any(r['few_repetition_benefit'] for r in third),
        CROSS_PATIENT_GENERALIZATION='LIMITED_ENGINEERED_HELDOUT_EVIDENCE' if any(len(v)>=2 for v in bymethod.values()) else 'NOT_DEMONSTRATED')
    put('LEARNING_RESULTS.json',dict(flags=flags,rows=rows,groups=groups,training=read('models/TRAINING_RESULTS.json'),
        heldout_history_benefit_patients_by_method=bymethod,
        predictions=predictions,history_enabled_vs_disabled_threshold_N_s=.01,
        conclusion='YES_WITHIN_REPORTED_SCOPE' if flags['HISTORY_CAUSAL_BENEFIT'] else 'NOT_DEMONSTRATED_FOR_PATIENT_SPECIFIC_HISTORY',
        independent_patients_executed=len({g['patient_id'] for g in groups if g['status']=='EXECUTED'}),
        broad_clinical_or_population_generalization=False))
    put('CONTINUOUS_REPETITION_RESULTS.json',dict(first_second_groups=groups,continuity=continuity,third_repetition=third,
        no_direct_human_state_assignment=True,state_continuity_assertion='actual live os.fork, persistent identity, native clock and original boundary; hashes corroborate but do not reconstruct state'))
    put('VALIDATION_RESULTS.json',dict(validation=[r for r in rows if r['split']=='validation'],heldout=[r for r in rows if r['split']=='heldout'],
        not_run=[g for g in groups if g['status']=='NOT_RUN'],method_freeze=read('models/METHOD_FREEZE.json'),no_test_retraining=True,
        outcome_exposure_after_this_study=sorted({r['patient_id'] for r in rows}),
        future_reuse_note='If future algorithms are designed using these revealed results, these patients cannot remain strict unseen tests for that future study. V13 has no physical outcomes in this package.'))
    native=sum(r['actual_new_native_steps'] or 0 for r in attempts)
    # Add final qualification to every attempt without rewriting immutable START/END events.
    # Relative motion qualification is available only after the matched arms have closed.
    paired_qualification={r['id']:dict(absolute_safety=r['absolute_safety'],task=r['task'],execution=r['execution'],
        motion_relative=r['motion_relative'],complete_qualified=r['complete_qualified'],failed_motion=r['failed_motion'],
        scope='same-live-parent Trial2 comparison') for r in rows}
    for tr in third:
        for r in tr['rows']:
            paired_qualification[r['id']]=dict(absolute_safety=r['axes']['absolute_safety'],task=r['axes']['task'],execution=r['axes']['causal_execution'],
                motion_relative=r['motion_relative'],complete_qualified=r['complete_qualified'],
                failed_motion=[] if not r.get('motion_comparison') else r['motion_comparison']['failed_requirements'],scope='same-live-parent Trial3 comparison')
    for attempt in attempts:
        ident=attempt['id'];evaluation=read('reports/'+ident+'_EVALUATION.json',{});axes=evaluation.get('axes',{})
        if ident in paired_qualification:qualification=paired_qualification[ident]
        elif 'BOUNDARY' in (attempt['kind'] or ''):
            qualification=dict(absolute_safety='NOT_A_FULL_TASK_EVALUATION',task='NOT_APPLICABLE',execution='ORIGINAL_BOUNDARY_COMPLETED' if attempt['returncode']==0 else 'FAIL',
                motion_relative='NOT_APPLICABLE',complete_qualified=None,failed_motion=[],scope='preparation only; counted in physics budget')
        else:
            reference=attempt['complete_task'] and attempt['trial_number']==1
            qualification=dict(absolute_safety=axes.get('absolute_safety','NOT_EVALUABLE'),task=axes.get('task','NOT_COMPLETED'),execution=axes.get('causal_execution','NOT_EVALUABLE'),
                motion_relative=evaluation.get('motion_relative','NOT_EVALUABLE'),complete_qualified=bool(reference and evaluation.get('absolute_task_execution_qualified')),
                failed_motion=[],scope='first B task is its own reference; no relative candidate comparison' if reference else 'failed or partial attempt; no complete-task qualification')
        attempt['final_qualification']=qualification
        attempt['qualification_source']='paired result and reports/'+ident+'_EVALUATION.json' if ident in paired_qualification else 'reports/'+ident+'_EVALUATION.json' if evaluation else 'immutable START/END and retained error record'
        if attempt['complete_task']:assert qualification['task']=='PASS' and qualification['complete_qualified'] is not None
    matched_parents={(e.get('patient_id'),e.get('trial_number'),e['parent_snapshot_hash']) for e in starts.values() if e.get('parent_snapshot_hash') and e['id'] in ends and (ends[e['id']].get('actual_new_native_steps') or 0)>0}
    put('ATTEMPT_ACCOUNTING.json',dict(starts=len(starts),ends=len(ends),open_starts=sorted(set(starts)-set(ends)),unmatched_ends=sorted(set(ends)-set(starts)),
        budget=80,total_new_native_steps=native,failed_returncodes=[r['id'] for r in attempts if r['returncode'] not in [0,None]],
        complete_task_results=sum(r['complete_task'] for r in attempts),boundary_starts=sum('BOUNDARY' in (r['kind'] or '') for r in attempts),
        independent_patient_identities=sorted({r['patient_id'] for r in attempts}),attempts=attempts,
        final_qualification_note='Post-execution join; immutable START/END events are preserved. Relative motion is assessed after matched controls complete.',
        full_task_qualification_failures=[r['id'] for r in attempts if r['complete_task'] and not r['final_qualification']['complete_qualified']],
        executed_matched_live_parent_count=len(matched_parents),matched_parents=[dict(patient=p,trial_number=t,hash=h) for p,t,h in sorted(matched_parents)],
        complete_first_trials=sum(r['complete_task'] and r['trial_number']==1 and 'BOUNDARY' not in (r['kind'] or '') for r in attempts),
        complete_second_trials=sum(r['complete_task'] and r['trial_number']==2 for r in attempts),
        complete_third_trials=sum(r['complete_task'] and r['trial_number']==3 for r in attempts),
        statistical_independence_note='Trial2 and Trial3 live parents within the same patient are not independent patient samples; P00R is the P00 retry',
        serial_semantics='Parents wait while child runs; nested T3 forks extend the owner lifetime but own native steps are counted separately',
        total_recomputed_complete_tasks=len(checks),independent_recompute_failures=[r['id'] for r in checks if r['status']!='PASS']))
    print('AGGREGATED',len(starts),'STARTS',len(rows),'T2 rows',len(third),'T3 groups',json.dumps(flags),flush=True)
if __name__=='__main__':main()
