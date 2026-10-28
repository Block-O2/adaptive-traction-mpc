"""Independent CLOSED continuous ILC raw audit; no model fit or physics.

Original scorer is invoked read-only only after mandatory whole-tree closure.
Original B audit functions are SHA-pinned; missing parent history is reported,
never imputed. Raw archive native count and newly paid fork delta are separate.
"""
import argparse
import ast
import collections
import gc
import hashlib
import importlib.util
import inspect
import itertools
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY_SHA = '37d788f33448a21a18efae38cae665aa34bfe7c74cbe4295451471f273df4833'
HARD = ['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'tolist'):return clean(value.tolist())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def save(path,value):
    path=Path(path).resolve()
    if not path.is_relative_to(HERE/'audit'):raise ValueError('FAMILY_AUDIT_ONLY')
    with path.open('x') as stream:json.dump(clean(value),stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def closure(root,group):
    paths={k:root/r for k,r in dict(done=f'jobs/{group}/WORKER_DONE.json',exit=f'owned/{group}_EXIT.json',supervisor=f'owned/{group}_SUPERVISOR.json',supervisor_end=f'owned/{group}_SUPERVISOR_END.json').items()}
    errors=['MISSING:'+k for k,p in paths.items() if not p.is_file()]
    docs={k:read(p) for k,p in paths.items() if p.is_file()};end=docs.get('supervisor_end',{})
    if end.get('state')!='STOP' or end.get('survivors'):errors.append('SUPERVISOR_ACTIVE_OR_SURVIVORS')
    owners=list(end.get('known_owned',{}).values())
    owners += [v for k,v in docs.get('supervisor',{}).items() if k in ('identity','worker') and isinstance(v,dict)]
    owners += [read(p) for p in (root/'owned').glob(group+'*_PROCESS.json')]
    for old in owners:
        if 'pid' not in old or 'start_ticks' not in old:continue
        path=Path('/proc')/str(old['pid'])/'stat'
        try:fields=path.read_text().rsplit(')',1)[1].split()
        except (FileNotFoundError,ProcessLookupError):continue
        if int(fields[19])==int(old['start_ticks']) and fields[0]!='Z':errors.append('LIVE_OWNED_PID:'+str(old['pid']))
    if docs.get('exit',{}).get('active_child') is not None:errors.append('EXIT_ACTIVE_CHILD')
    rows=[json.loads(line) for line in (root/'runtime/ATTEMPTS.jsonl').read_text().splitlines() if line.strip()]
    rows=[r for r in rows if r.get('id','').startswith(group+'_') and r.get('event') in ('START','END')]
    starts=collections.Counter(r['id'] for r in rows if r['event']=='START');ends=collections.Counter(r['id'] for r in rows if r['event']=='END')
    if starts!=ends or not starts or any(v!=1 for v in starts.values()):errors.append('ALL_START_END_EXACT_ONCE')
    for row in rows:
        if row['event']=='END' and row.get('joined') is not True:errors.append('NOT_JOINED:'+row['id'])
    return dict(status='CLOSED' if not errors else 'DO_NOT_READ_RAW',errors=errors,metadata=docs,events=rows,ids=list(starts),metadata_files_sha256={str(p.relative_to(root)):sha(p) for p in paths.values() if p.is_file()},owned_identities_checked=len(owners))


def original_helpers():
    path=HERE/'audit_persistent_b_closed_v1.py'
    if sha(path)!=LEGACY_SHA:raise ValueError('FROZEN_B_AUDIT_CHANGED')
    spec=importlib.util.spec_from_file_location('_independent_frozen_B_audit',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=inspect.getsource(module.rebuild)
    old="""    history=read(root/'history'/(ident+'_COMPLETE_HISTORY.json'))
    if abs(jf-history['JF_N_s'])>1e-6 or abs(jm-history['JM_Nm_s'])>1e-6: errors.append('COMPLETE_HISTORY_JF_JM_MISMATCH')
"""
    new="""    history_path=root/'history'/(ident+'_COMPLETE_HISTORY.json')
    if history_path.is_file():
        history=read(history_path)
        if abs(jf-history['JF_N_s'])>1e-6 or abs(jm-history['JM_Nm_s'])>1e-6: errors.append('COMPLETE_HISTORY_JF_JM_MISMATCH')
    elif not ident.endswith('_parent'): errors.append('MISSING_COMPLETE_CAUSAL_HISTORY')
"""
    if source.count(old)!=1:raise ValueError('EXACT_INDEPENDENT_HISTORY_BLOCK_NOT_FOUND')
    namespace=dict(module.__dict__);exec(compile(source.replace(old,new),'<independent C audit: parent history optional, never imputed>','exec'),namespace)
    return module,namespace['rebuild']


def raw_equal(root,left,right,helper,np):
    errors=[];counts={}
    with np.load(root/'runtime/source/results'/left/'trace.npz',allow_pickle=False) as a,np.load(root/'runtime/source/results'/right/'trace.npz',allow_pickle=False) as b:
        if set(a.files)!=set(b.files):errors.append('TRACE_SCHEMA')
        for key in set(a.files)&set(b.files):
            x,y=a[key],b[key]
            equal=x.shape==y.shape and (np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y))
            if not equal:errors.append('TRACE:'+key)
    fields={'native_states_evaluation_only':['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index'],
            'command_receipts':['receipt_index','applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind']}
    for kind,keys in fields.items():
        counts[kind]=0
        streams=[helper.array_items(root/'runtime/source/results'/ident/'runtime_artifacts.json.gz',kind) for ident in (left,right)]
        for a,b in itertools.zip_longest(*streams):
            counts[kind]+=1
            if a is None or b is None:errors.append(kind+':LENGTH');break
            bad=[k for k in keys if a.get(k)!=b.get(k)]
            if bad:errors.append(kind+':'+','.join(bad));break
    return dict(left=left,right=right,status='PASS' if not errors else 'FAIL',errors=errors,counts=counts)


def recipe_check(root,ident,row,config,np):
    summary=read(root/'runtime/source/results'/ident/'summary.json')
    path=root/'runtime/reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
    if not path.is_file():return dict(errors=[] if ident.endswith('_parent') else ['NO_RECEIPT_LINEAGE'],parent_only=ident.endswith('_parent'))
    lineage=read(path);owners={r['decision_index']:r for r in lineage['rows']};errors=[];modal=[]
    if lineage['status']!='PASS':errors.append('ORIGINAL_LINEAGE_NOT_PASS')
    action=row.get('action',{});changed=False
    for record in summary['learning_records']:
        meta=record.get('selected_plan',{}).get('execution_screen',{}).get('coordination_modal_v2')
        if meta is None:continue
        own=owners.get(record['decision_index'],{});native=own.get('actual_native_steps',0)
        if not np.array_equal(np.asarray(meta['parameters']),np.asarray(action.get('x',[]))):errors.append('MODAL_FROZEN_ACTION_IDENTITY')
        delta=float(np.max(abs(np.asarray(meta['proposed_target_rad'])-np.asarray(meta['original_target_rad']))))
        applied=meta['status']=='ACCEPTED' and record.get('selected_plan_activated') is True and native>0 and delta>1e-12
        changed=changed or applied;modal.append(dict(decision_index=record['decision_index'],status=meta['status'],activated=record.get('selected_plan_activated'),owned_native_steps=native,nominal_target_change_rad=delta,actual_reference_changed=applied))
    components=[];full=True
    applicable=action.get('family')=='H150' or (action.get('family')=='modal8_retimed' and not any(action.get('x',[])))
    if applicable:
        for component,field in [('second_round_posture','posture'),('early_return_duration','early'),('terminal_hip_timing','timing')]:
            found=[]
            for record in summary['learning_records']:
                meta=record.get('selected_plan',{}).get('execution_screen',{}).get(component)
                if meta is not None:found.append(dict(status=meta['status'],activated=record.get('selected_plan_activated'),native=owners.get(record['decision_index'],{}).get('actual_native_steps',0)))
            okay=len(found)==len(config['H150'].get(field,[])) and all(r['status']=='ACCEPTED' and r['activated'] is True and r['native']>0 for r in found)
            components.append(dict(component=component,pass_=okay,rows=found));full=full and okay
    if 'actual_modal_action_changed' in row and row['actual_modal_action_changed']!=changed:errors.append('ACTUAL_ACTION_CHANGED_FLAG_MISMATCH')
    return dict(errors=errors,actual_modal_action_changed=changed,modal=modal,full_H150_components_applicable=applicable,full_H150_components_pass=full,components=components)


def check_boundary(root,ident,events):
    path=root/'audit/persistent'/(ident+'_PERSISTENT_BOUNDARY.json');row=read(path);errors=[];previous=row['before']['physical_time_s']
    for step in row['steps']:
        if abs(step['start_s']-previous)>1e-8 or abs(step['end_s']-step['start_s']-.00025)>1e-8:errors.append('NATIVE_GRID')
        if step['command']!=row['held_command'] or step['inherited_receipt_index']!=row['prior_positive_receipt']:errors.append('HELD_COMMAND_RECEIPT')
        previous=step['end_s']
    if row['actual_new_native_steps']!=len(row['steps']) or row['observed_native_steps']!=len(row['steps']):errors.append('BOUNDARY_COUNT')
    if abs(previous-row['after']['physical_time_s'])>1e-8:errors.append('BOUNDARY_END_CLOCK')
    for key in ('plant_identity','observer_identity','measurement_layer_identity','updater_identity','repetition_index'):
        if row['before'][key]!=row['after'][key]:errors.append('BOUNDARY_REPLACED:'+key)
    if any(s['wall_active'] or s['planner_request_outstanding'] for s in (row['before'],row['after'])):errors.append('BOUNDARY_NOT_QUIESCENT')
    end=next(r for r in events if r['id']==ident and r['event']=='END')
    if end.get('actual_new_native_steps')!=row['actual_new_native_steps']:errors.append('BOUNDARY_END_DELTA')
    return dict(id=ident,errors=errors,source_sha256=sha(path),record=row)


def audit(root,group,closed,log):
    import numpy as np
    helper,rebuild=original_helpers();mode,compare,matched=helper.original_functions(root)
    config_path=root/'experiments'/(group+'.json');config=read(config_path);manifest_path=root/'jobs'/group/'SOURCE_MANIFEST.json';manifest=read(manifest_path)
    errors=[]
    if sha(config_path)!=manifest['config_sha256']:errors.append('CONFIG_SHA_CHANGED')
    for rel,expected in manifest['files'].items():
        if sha(root/rel)!=expected:errors.append('SOURCE_CHANGED:'+rel)
    for event in closed['events']:
        if event['event']=='START' and (event.get('config_sha256')!=sha(config_path) or event.get('job_source_sha256')!=sha(manifest_path)):errors.append('START_SOURCE_CONFIG:'+event['id'])
    case_path=root/config['case_path'];case=read(case_path)
    if sha(case_path)!=config['case_sha256']:errors.append('CASE_SHA_CHANGED')
    descriptor=dict(case_key=case['case_key'],physical_variant=case['cell']['family'],candidate=case['coordination_candidate'],path=str(case_path.relative_to(root/'runtime/source')),sha256=sha(case_path))
    scoring=read(root/'runtime/source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring']
    measured={};trials=[];boundaries=[];total=0
    for ident in closed['ids']:
        before=time.monotonic();cpu=time.process_time()
        if '_BOUNDARY_' in ident:
            result=check_boundary(root,ident,closed['events']);boundaries.append(result);total+=result['record']['actual_new_native_steps'];errors += [ident+':'+e for e in result['errors']];continue
        row_path=root/'attempts'/(ident+'_RESULT.json');row=read(row_path) if row_path.is_file() else {}
        delta_path=root/'audit/persistent'/(ident+'_PERSISTENT_DELTA_ACCOUNTING.json');delta=read(delta_path) if delta_path.is_file() else {}
        result=dict(id=ident,worker_result=row,delta=delta,errors=[],complete_original=row.get('complete') is True)
        if row.get('complete') is not True:
            result['status']='INCOMPLETE_NOT_RANKED';result['original_failure_documents']={}
            for suffix in ('_DATA.json','_PARTIAL_COMPUTE.json'):
                path=root/'runtime/output'/(ident+suffix)
                if path.is_file():result['original_failure_documents'][str(path.relative_to(root))]=dict(sha256=sha(path),document=read(path))
            result['new_native_count']=delta.get('actual_new_native_steps')
        else:
            fresh=clean(mode.evaluate(helper.ArchivePath(root/'runtime/source/results'/ident),descriptor,scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg']))
            old=read(root/'runtime/output'/(ident+'_DATA.json'))['metric']['physical_audit']['unchanged_evaluator']
            m,rebuilt=rebuild(root,ident,np);measured[ident]=m;result.update(rebuilt);result['fresh_original_evaluator']=fresh
            for key in ('physical_task_result','scientific_validity','overall_result_for_mode','raw_scorer_v2'):
                if fresh[key]!=old[key]:result['errors'].append('ORIGINAL_CACHE_BYPASS_MISMATCH:'+key)
            origin=delta.get('counter_origin_s',0. if delta.get('before') is None else delta['before']['physical_time_s'])
            n=0;first=None;last=None
            for native in helper.array_items(root/'runtime/source/results'/ident/'runtime_artifacts.json.gz','native_states_evaluation_only'):
                begin=native.get('physical_interval_start_s',native['time_s']-.00025)
                if begin>=origin-1e-8:
                    n+=1
                    if first is None:first=begin
                    last=native['time_s']
            result.update(raw_archive_native_count=result.pop('native_count'),new_native_count=n,counter_origin_s=origin,new_native_start_s=first,new_native_end_s=last)
            if n!=delta.get('actual_new_native_steps') or n!=result['incremental_metric'] or n!=row.get('actual_new_native_steps'):result['errors'].append('NEW_NATIVE_DELTA_RECOUNT_MISMATCH')
            if last is None or abs(last-delta['after']['physical_time_s'])>1e-8 or first is None or abs(first-origin)>1e-8:result['errors'].append('NEW_NATIVE_TIME_ORIGIN_END')
            cached=read(root/'runtime/reports'/(ident+'_MEASURED.json'))
            for signal_name,statistics in m['motion']['raw']['full'].items():
                for name,value in statistics.items():
                    if not np.allclose(value,cached['motion']['raw']['full'][signal_name][name],rtol=1e-12,atol=1e-9):result['errors'].append('RAW_MOTION_MISMATCH:'+signal_name+'/'+name)
            result['recipe']=recipe_check(root,ident,row,config,np);result['errors']+=result['recipe']['errors']
            binding_path=root/'audit/persistent'/(ident+'_ACTUAL_PLANT_BINDING_EVALUATION_ONLY.json')
            if not binding_path.is_file():result['errors'].append('MISSING_ACTUAL_PLANT_BINDING')
            else:
                binding=read(binding_path);result['actual_plant_binding']=binding
                if binding['case_sha256']!=sha(case_path):result['errors'].append('ACTUAL_PLANT_CASE_SHA')
            summary=read(root/'runtime/source/results'/ident/'summary.json')
            if summary.get('qualification',{}).get('hidden_case_evaluation_only')!=case:result['errors'].append('SUMMARY_ACTUAL_CASE_MISMATCH')
        if isinstance(result.get('new_native_count'),int):total+=result['new_native_count']
        else:result['errors'].append('UNKNOWN_NATIVE_COST_NOT_ZERO')
        result.update(audit_wall_s=time.monotonic()-before,audit_cpu_s=time.process_time()-cpu)
        trials.append(result);log(dict(event='TRIAL_AUDIT_COMPLETE',id=ident,wall_s=result['audit_wall_s'],CPU_s=result['audit_cpu_s'],errors=result['errors']))
        gc.collect()
    by_id={t['id']:t for t in trials}
    for trial in trials:
        ident=trial['id']
        if ident not in measured:continue
        reference=ident if ident==group+'_T1_B' else (group+'_T2_H150_T3_B' if '_T3_' in ident else group+'_T2_B')
        if reference not in measured:trial['errors'].append('MISSING_COMPLETE_SAME_STAGE_B');continue
        motion=compare(measured[ident],measured[reference]);full_recipe=trial['recipe']['full_H150_components_pass']
        qualified=bool(motion['acceptance_pass'] and matched(measured[ident]['phase_durations']) and trial['fresh_original_evaluator']['overall_result_for_mode']=='PASS' and full_recipe)
        trial.update(independent_motion_vs_same_stage_B=clean(motion),independent_qualified=qualified,actual_hard_conditions=trial['fresh_original_evaluator']['physical_task_result']['scorer_v2_common_conditions'])
        if qualified!=trial['worker_result'].get('qualified'):trial['errors'].append('FINAL_QUALIFICATION_MISMATCH')
        errors += [ident+':'+e for e in trial['errors']]
    pairs=[(group+'_T2_ZERO_MODAL',group+'_T2_H150'),(group+'_T2_H150_T3_ZERO_MODAL',group+'_T2_H150_T3_H150'),(group+'_T2_parent',group+'_T2_B'),(group+'_T2_H150_T3_parent',group+'_T2_H150_T3_B')]
    raw_pairs=[]
    for a,b in pairs:
        if a in measured and b in measured:
            pair=raw_equal(root,a,b,helper,np);raw_pairs.append(pair)
            if pair['status']!='PASS':errors.append('EXACT_RAW_FAILED:'+a+'|'+b)
    sessions=[]
    for previous,boundary_id,next_id in [(group+'_T1_B',group+'_BOUNDARY_1_2',group+'_T2_parent'),(group+'_T2_H150',group+'_T2_H150_BOUNDARY_2_3',group+'_T2_H150_T3_parent')]:
        if previous not in by_id or next_id not in by_id:continue
        bound=next(b for b in boundaries if b['id']==boundary_id)['record'];left=by_id[previous]['delta']['after'];right=by_id[next_id]['delta']['before'];stamps=[left,bound['before'],bound['after'],right];bad=[]
        for key in ('plant_identity','observer_identity','measurement_layer_identity','updater_identity'):
            if len({s[key] for s in stamps})!=1:bad.append('SESSION_OBJECT:'+key)
        if abs(left['physical_time_s']-bound['before']['physical_time_s'])>1e-8 or abs(right['physical_time_s']-bound['after']['physical_time_s'])>1e-8:bad.append('CLOCK_DISCONTINUITY')
        if len({s['repetition_index'] for s in stamps})!=1:bad.append('BOUNDARY_REPETITION_CHANGED')
        first_event=next(e for e in closed['events'] if e['id']==boundary_id and e['event']=='START');next_event=next(e for e in closed['events'] if e['id']==next_id and e['event']=='START')
        if (first_event['pid'],first_event['start_ticks'])!=(next_event['pid'],next_event['start_ticks']):bad.append('CONTINUATION_OWNER_CHANGED')
        if previous.endswith('_H150'):
            process=read(root/'owned'/(previous+'_PROCESS.json'))
            if (process['pid'],process['start_ticks'])!=(next_event['pid'],next_event['start_ticks']):bad.append('T3_NOT_IN_OWN_REAL_T2_H150_CHILD')
        sessions.append(dict(previous_trial=previous,boundary=boundary_id,next_stage=next_id,stamps=stamps,errors=bad));errors+=bad
    aliases=[]
    for path in (root/'audit/persistent').glob(group+'*_ALIAS.json'):
        value=read(path);aliases.append(dict(path=str(path.relative_to(root)),sha256=sha(path),record=value))
        if value['new_native_steps']!=0 or value['alias_of'] not in by_id:errors.append('ALIAS_INVALID:'+path.name)
    causal={};frozen_path=root/'freeze'/(group+'_T2_H150_T3_DECISIONS.json')
    if frozen_path.is_file():
        frozen=read(frozen_path);causal['T3_frozen_decisions']=frozen;causal['source_sha256']=sha(frozen_path)
        boundary_start=next(e for e in closed['events'] if e['id']==group+'_T2_H150_BOUNDARY_2_3' and e['event']=='START')
        if frozen['frozen_unix']>=boundary_start['unix'] or frozen['actual_source_trial']!=group+'_T2_H150' or frozen.get('future_T3_results_consumed') is not False:errors.append('T3_HISTORY_FREEZE_CAUSAL_ORDER')
        if frozen['source_native_session']!=by_id[group+'_T2_H150']['delta']['after']:errors.append('T3_HISTORY_NOT_OWN_H150_SESSION')
        spec=importlib.util.spec_from_file_location('_pure_closed_history_projection',HERE/'modal_ilc_projection_v1.py');projection=importlib.util.module_from_spec(spec);spec.loader.exec_module(projection)
        source_id=frozen['actual_source_trial'];rows=read(root/'history'/(source_id+'_CAUSAL_HISTORY.json'))
        with np.load(root/'runtime/source/results'/source_id/'trace.npz',allow_pickle=False) as trace:
            ix=np.flatnonzero(trace['stage']=='TASK');lookup={round(float(trace['time_s'][i]),8):int(i) for i in ix};bad=[]
            for item in rows:
                i=lookup.get(round(float(item['time_s']),8))
                if i is None or item.get('truth_used') is not False:bad.append('CAUSAL_ROW_CLOCK_OR_TRUTH');continue
                expected=[trace['estimated_human_state_rad_rad_s'][i],np.r_[trace['reference_q_rad'][i],trace['reference_dq_rad_s'][i]],trace['physical_cuff_force_world_n'][i],trace['physical_cuff_moment_world_nm'][i]]
                for key,value in zip(('estimated_q_dq','reference_q_dq','measured_force','measured_moment'),expected):
                    if not np.array_equal(np.asarray(item[key]),value):bad.append('CAUSAL_ROW_SOURCE:'+key)
            i=int(ix[-1]);rows.append(dict(time_s=float(trace['time_s'][i]),phase=str(trace['task_phase'][i]),estimated_q_dq=trace['estimated_human_state_rad_rad_s'][i].tolist(),reference_q_dq=np.r_[trace['reference_q_rad'][i],trace['reference_dq_rad_s'][i]].tolist(),truth_used=False))
        stats=projection.extract_executed_slot_statistics(rows,read(root/'history'/(source_id+'_SLOT_REQUESTS.json')),read(root/'runtime/source/results'/source_id/'summary.json'),read(root/'runtime/reports'/(source_id+'_EXECUTED_RESIDUAL_RECEIPTS.json')))
        recalculated={name:projection.project_slot_history(stats,gain=gain) for name,gain in [('enabled',.25),('smaller_gain',.10)]}
        for name,value in recalculated.items():
            if not math.isclose(value['x3'],frozen[name]['x3'],abs_tol=1e-12,rel_tol=0.):bad.append('ILC_PROJECTION_MISMATCH:'+name)
        causal.update(causal_trace_alignment_errors=sorted(set(bad)),reconstructed_slot_statistics=stats,recomputed_updates=recalculated);errors+=bad
    bo=[]
    for path in (root/'freeze').glob(group+'_T2_H150_T3_C2B_V2_*.json'):bo.append(dict(path=str(path.relative_to(root)),sha256=sha(path),record=read(path)))
    parent_checks=[]
    for prefix in (group+'_T2',group+'_T2_H150_T3'):
        path=root/'runtime/reports'/(prefix+'_PARENT_CHECKS.json')
        if path.is_file():
            checks=read(path);parent_checks.extend(checks)
            if any(r.get('unchanged') is not True or r.get('before')!=r.get('after') for r in checks):errors.append('PARENT_MUTATED:'+prefix)
    return dict(status='INDEPENDENT_CONTINUOUS_RAW_AUDIT_PASS' if not errors else 'INDEPENDENT_AUDIT_REVIEW_REQUIRED',errors=errors,trials=trials,boundaries=boundaries,sessions=sessions,raw_equivalence=raw_pairs,aliases=aliases,T3_causal_history=causal,BO_original_artifacts_only=bo,parent_checks=parent_checks,observed_total_new_native_steps=total,physical_steps_from_audit=0,model_fit_forward_from_audit=0,original_job_native_observation_not_second_execution=True,limitations=['Known-heavy exposed continuous engineering only; no independent patient generalization','Boundary native times and controls recorded, no every-step boundary qpos/qvel archive; hidden-state bitwise identity through unlogged boundary not measured','Parent B tasks are paid actual computation, not extra independent samples','BO source results read only; audit never refits or calls predictor','Original qualification retained even when cost or projected history improves'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(ROOT));parser.add_argument('--group',required=True);parser.add_argument('--closed-job-approved',action='store_true');args=parser.parse_args()
    if not args.closed_job_approved:raise ValueError('EXPLICIT_PARENT_CLOSED_APPROVAL_REQUIRED')
    root=Path(args.root).resolve();group=args.group
    if root!=ROOT or not group.replace('_','').isalnum():raise ValueError('ROOT_GROUP_SCOPE')
    closed=closure(root,group)
    if closed['status']!='CLOSED':raise ValueError('NOT_CLOSED_NO_RAW:'+str(closed['errors']))
    out=HERE/'audit'/(group+'_INDEPENDENT_CONTINUOUS_V1');out.mkdir(exist_ok=False)
    started=time.monotonic();cpu=time.process_time()
    save(out/'START.json',dict(parent_authorization='Root explicitly authorized closed V8CONTILC01 raw/scorer/continuity/ILC/BO/resource audit',closure=closed,source_sha256=sha(__file__),wall_cap_s=240,threads=1,fit_physics=0))
    def log(record):
        with (out/'PROGRESS.jsonl').open('a') as stream:stream.write(json.dumps(clean(record),sort_keys=True,allow_nan=False)+'\n')
        print(json.dumps(clean(record),sort_keys=True),flush=True)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('READONLY_AUDIT_240S_CAP')));signal.alarm(240)
    try:
        result=audit(root,group,closed,log);result.update(audit_wall_s=time.monotonic()-started,audit_CPU_s=time.process_time()-cpu,audit_source_sha256=sha(__file__))
        save(out/'RESULT.json',result);save(out/'END.json',dict(status=result['status'],result_sha256=sha(out/'RESULT.json'),wall_s=result['audit_wall_s'],CPU_s=result['audit_CPU_s'],physics_fit=0));print(json.dumps(dict(status=result['status'],result_sha256=sha(out/'RESULT.json'),wall_s=result['audit_wall_s'],CPU_s=result['audit_CPU_s'])),flush=True)
    except BaseException as error:
        save(out/'FAILED.json',dict(error_type=type(error).__name__,error=str(error),wall_s=time.monotonic()-started,CPU_s=time.process_time()-cpu,paid_partial_progress_preserved=True,automatic_retry=False,physics_fit=0));raise
    finally:signal.alarm(0)


if __name__=='__main__':main()
