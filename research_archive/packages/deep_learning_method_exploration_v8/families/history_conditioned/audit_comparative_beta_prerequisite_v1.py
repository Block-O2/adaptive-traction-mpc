"""Closed V8COMPENG03 prerequisite DATA, not all-five-complete approval.

Seven original scorer replays; full motion only for genuinely complete tasks.
No selector/model imports, forward, fit or physics. Original partial failures
and costs are preserved and never used as full-task rewards or motion arrays.
"""
import ast
import gc
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import signal
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];GROUP='V8COMPENG03'
HARD=['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def clean(o):
    if isinstance(o,dict):return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)):return [clean(v) for v in o]
    if hasattr(o,'tolist'):return clean(o.tolist())
    if isinstance(o,float) and not math.isfinite(o):return None
    return o
def save(path,value):
    with Path(path).open('x') as stream:json.dump(clean(value),stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    start=time.monotonic();cpu=time.process_time()
    common=module(HERE/'audit_continuous_closed_v1.py','_closed_continuous_audit_helpers');closed=common.closure(ROOT,GROUP)
    assert closed['status']=='CLOSED' and len(closed['ids'])==7
    out=HERE/'audit'/f'{GROUP}_BETA_PREREQUISITE_V1';out.mkdir(exist_ok=False)
    save(out/'START.json',dict(closure=closed,parent_authorized_closed_audit=True,wall_cap_s=120,source_sha256=sha(__file__),model_fit_physics=0))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('CLOSED_PREREQUISITE_120S')));signal.alarm(120)
    try:
        import numpy as np
        helper=module(HERE/'audit_persistent_b_closed_v1.py','_frozen_original_raw_audit')
        assert sha(HERE/'audit_persistent_b_closed_v1.py')=='37d788f33448a21a18efae38cae665aa34bfe7c74cbe4295451471f273df4833'
        source=inspect.getsource(helper.rebuild)
        old="""    history=read(root/'history'/(ident+'_COMPLETE_HISTORY.json'))
    if abs(jf-history['JF_N_s'])>1e-6 or abs(jm-history['JM_Nm_s'])>1e-6: errors.append('COMPLETE_HISTORY_JF_JM_MISMATCH')
"""
        assert source.count(old)==1
        namespace=dict(helper.__dict__);exec(compile(source.replace(old,"    # Comparative tasks have no persistent COMPLETE_HISTORY contract. No history imputed.\n"),'<comparative independent rebuild; no persistent history requirement>','exec'),namespace)
        rebuild=namespace['rebuild'];mode,compare,matched=helper.original_functions(ROOT)
        cfg_path=ROOT/'experiments'/f'{GROUP}.json';cfg=read(cfg_path);manifest_path=ROOT/'jobs'/GROUP/'SOURCE_MANIFEST.json';manifest=read(manifest_path);errors=[]
        assert manifest['config_sha256']==sha(cfg_path)
        for rel,expected in manifest['files'].items():assert sha(ROOT/rel)==expected,rel
        for event in closed['events']:
            if event['event']=='START':assert event['config_sha256']==sha(cfg_path) and event['job_source_sha256']==sha(manifest_path)
        case_path=ROOT/cfg['case_path'];case=read(case_path);assert sha(case_path)==cfg['case_sha256']
        descriptor=dict(case_key=case['case_key'],physical_variant=case['cell']['family'],candidate=case['coordination_candidate'],path=str(case_path.relative_to(ROOT/'runtime/source')),sha256=sha(case_path))
        scoring=read(ROOT/'runtime/source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring'];trials=[];measures={}
        for ident in closed['ids']:
            began=time.monotonic();tick=time.process_time();row_path=ROOT/'attempts'/f'{ident}_RESULT.json';row=read(row_path) if row_path.is_file() else None
            data_path=ROOT/'runtime/output'/f'{ident}_DATA.json';data=read(data_path);metric=data['metric'];path=ROOT/'runtime/source/results'/ident
            fresh=clean(mode.evaluate(helper.ArchivePath(path),descriptor,scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg']))
            cached=metric['physical_audit']['unchanged_evaluator'];bad=[]
            for key in ('physical_task_result','scientific_validity','overall_result_for_mode','raw_scorer_v2'):
                if fresh[key]!=cached[key]:bad.append('ORIGINAL_SCORER_CACHE_BYPASS_MISMATCH:'+key)
            hard={k:fresh['physical_task_result']['scorer_v2_common_conditions'].get(k) for k in HARD}
            if not all(v is True for v in hard.values()):bad.append('HARD_FALSE_OR_UNKNOWN')
            origin=0. if data.get('child') is None else float(data['child']['physical_time_at_fork']);native=0
            for item in helper.array_items(path/'runtime_artifacts.json.gz','native_states_evaluation_only'):
                if item.get('physical_interval_start_s',item['time_s']-.00025)>=origin-1e-8:native+=1
            if native!=metric['actual_new_native_physics_steps'] or (row and native!=row['actual_new_native_steps']):bad.append('NATIVE_DELTA_RECOUNT')
            complete=metric['task_valid'] is True and (row is None or row['complete'] is True)
            item=dict(id=ident,complete=complete,worker_result=row,independent_fresh_original_evaluator=fresh,hard11=hard,new_native_steps=native,counter_origin_s=origin,errors=bad,source_files_sha256={str(p.relative_to(ROOT)):sha(p) for p in [path/'trace.npz',path/'summary.json',path/'runtime_artifacts.json.gz',data_path]})
            if complete:
                measured,recount=rebuild(ROOT,ident,np);measures[ident]=measured;item['independent_full_raw_motion_integral']=recount;bad+=recount['errors']
                item['JF_N_s']=measured['J_F_N_s'];item['JM_Nm_s']=measured['moment_integral_Nm_s']
            else:
                item.update(full_motion_arrays=None,full_qualified=False,partial_JF_unranked=metric.get('J_F'),partial_JM_unranked=metric.get('moment_integral'),original_abort=fresh['raw_scorer_v2'].get('abort_reason'),full_cost_or_reward_not_imputed=True)
                if row is None or row['complete'] is not False or row['qualified'] is not False:bad.append('PARTIAL_STATUS_CHANGED')
            summary=read(path/'summary.json')
            if summary.get('qualification',{}).get('hidden_case_evaluation_only')!=case:bad.append('ACTUAL_CASE_SUMMARY')
            launch=read(path/'HIGH_ROM_CASE_RESULT.json')
            if launch.get('case_sha256')!=cfg['case_sha256']:bad.append('LAUNCH_CASE_SHA')
            item.update(audit_wall_s=time.monotonic()-began,audit_CPU_s=time.process_time()-tick);trials.append(item)
            print(json.dumps(dict(id=ident,complete=complete,hard11_all_true=all(v is True for v in hard.values()),native=native,errors=bad,CPU_s=item['audit_CPU_s'])),flush=True);gc.collect()
        for item in trials:
            ident=item['id']
            if ident in measures:
                comparison=compare(measures[ident],measures[GROUP+'_B']);qualified=bool(comparison['acceptance_pass'] and matched(measures[ident]['phase_durations']) and item['independent_fresh_original_evaluator']['overall_result_for_mode']=='PASS')
                item.update(independent_motion_vs_B=clean(comparison),full_qualified=qualified)
                if item['worker_result'] is not None and qualified!=item['worker_result']['qualified']:item['errors'].append('QUALIFICATION_MISMATCH')
            errors += [ident+':'+e for e in item['errors']]
        equivalence=[common.raw_equal(ROOT,GROUP+'_HISTORY_B',GROUP+'_B',helper,np),common.raw_equal(ROOT,GROUP+'_parent',GROUP+'_B',helper,np)]
        if any(p['status']!='PASS' for p in equivalence):errors.append('B_HISTORY_PARENT_RAW_EQUIVALENCE')
        context_path=ROOT/'predictions'/f'{GROUP}_FROZEN_CONTEXT_DECISIONS.json';context=read(context_path);b_start=next(e for e in closed['events'] if e['id']==GROUP+'_B' and e['event']=='START')
        if len(context['decisions'])!=55 or context['created_unix']>=b_start['unix'] or context.get('before_any_candidate_outcome') is not True or context['counts']!={'API_started':28,'API_returned':28,'new_fit':0}:errors.append('PRE_B_55_DECISIONS_CAUSALITY_OR_COUNTS')
        raw_path=ROOT/'history'/f'{GROUP}_PREFORK_CAUSAL_CONTEXT.json';raw=read(raw_path);body={k:v for k,v in raw.items() if k!='causal_payload_sha256'}
        if digest(body)!=raw['causal_payload_sha256']:errors.append('RAW_CONTEXT_CHECKSUM')
        proof_reports=[]
        for label,record in [('A3',context['A_source_proof_audit'])]+list(context['extension_records'].items()):
            proof=record['proof_audit'];proof_bad=[]
            if proof['job_source_manifest_sha256']!=sha(manifest_path) or proof['config_sha256']!=sha(cfg_path) or proof['prefork_payload_file_sha256']!=sha(raw_path) or proof['prefork_payload_checksum']!=raw['causal_payload_sha256']:proof_bad.append('ACTUAL_PROOF_SOURCE_DATA_BINDING')
            if proof.get('current_task_B_or_candidate_result_used') is not False or proof.get('actual_in_memory_callback_code_checked') is not True:proof_bad.append('ACTUAL_CALLBACK_CAUSAL_PROOF')
            for role,item in proof['roles'].items():
                actual=sha(ROOT/item['path'])
                if actual!=item['actual_file_sha256'] or actual!=item['job_manifest_file_sha256'] or actual!=item['expected_profile_sha256'] or manifest['files'][item['path']]!=actual or Path(item['actual_loaded_module_file']).resolve()!=(ROOT/item['path']).resolve():proof_bad.append('LOADED_SOURCE_ROLE:'+role)
            proof_reports.append(dict(label=label,roles=len(proof['roles']),errors=proof_bad));errors+=proof_bad
        binding_path=ROOT/'predictions'/f'{GROUP}_HISTORY_MODULE_SOURCE_BINDING.json';binding=read(binding_path);module_proofs=[]
        for rel,item in binding['actual_modules'].items():
            actual=sha(ROOT/rel);okay=Path(item['actual_loaded_path']).resolve()==(ROOT/rel).resolve() and item['sha256']==actual and cfg['frozen_artifacts'].get(rel)==actual and manifest['files'].get(rel)==actual
            module_proofs.append(dict(path=rel,sha256=actual,actual_loaded_and_both_freezes_match=okay))
            if not okay:errors.append('C_ACTUAL_MODULE_PROOF:'+rel)
        if len(module_proofs)!=3:errors.append('C_EXACT_THREE_MODULES_REQUIRED')
        history_path=ROOT/'predictions'/f'{GROUP}_FROZEN_HISTORY_DECISIONS.json';history=read(history_path)
        if history.get('B_complete_before_selection') is not True or history.get('scope')!='COLD_REPLAY_NOT_CONTINUOUS_TRIAL' or len(history['decisions'])!=5:errors.append('C_HISTORY_COLD_REPLAY_SCHEMA')
        core=[GROUP+'_'+tag for tag in ('B','LATE_H150','EARLY_H150','LATE_PHASE','EARLY_PHASE')];by_id={t['id']:t for t in trials};all_complete=all(by_id[i]['complete'] for i in core)
        report=dict(schema='v8.independent_beta_prerequisite_review_data.v1',status='PASS_CLOSED_SOURCE_CAUSAL_HARD_DATA_WITH_TWO_PHASE_PARTIAL' if not errors else 'REVIEW_REQUIRED',errors=errors,group=GROUP,closure=closed,trials=trials,all_five_core_complete=all_complete,all_five_core_qualified=all(by_id[i]['full_qualified'] for i in core),core_complete_tags=[i.removeprefix(GROUP+'_') for i in core if by_id[i]['complete']],core_partial_tags=[i.removeprefix(GROUP+'_') for i in core if not by_id[i]['complete']],all_seven_original_hard11_true=all(all(v is True for v in t['hard11'].values()) for t in trials),true_hard_safety_violation=False if all(all(v is True for v in t['hard11'].values()) for t in trials) else 'UNKNOWN_OR_TRUE_SEE_ORIGINAL',all_expected_pre_B_selectors_bound_before_B=not any('PRE_B_' in e for e in errors),pre_B_decision_count=55,outer_API_counts=context['counts'],nested_A_API_calls=context['nested_A_inference_API_calls'],API_count_not_equal_to_55_decisions=True,source_proof_audits=proof_reports,C_actual_loaded_module_proofs=module_proofs,C_scope='B completed then COLD_REPLAY history-conditioned choices; no persistent trial claim',raw_equivalence=equivalence,source_files_sha256={str(p.relative_to(ROOT)):sha(p) for p in [context_path,raw_path,binding_path,history_path,cfg_path,manifest_path]},actual_new_native_steps_observed=sum(t['new_native_steps'] for t in trials),all_five_complete_PASS_claim=False,Beta_initialization_sampling_update_permission_granted=False,physics_model_import_fit_forward=0,original_scorer_replays=7,audit_source_sha256=sha(__file__),wall_s=time.monotonic()-start,CPU_s=time.process_time()-cpu)
        save(out/'RESULT.json',report);save(out/'END.json',dict(status=report['status'],result_sha256=sha(out/'RESULT.json'),wall_s=report['wall_s'],CPU_s=report['CPU_s'],physics_fit=0));print(json.dumps(dict(status=report['status'],result_sha256=sha(out/'RESULT.json'),wall_s=report['wall_s'],CPU_s=report['CPU_s'],all_five_core_complete=all_complete)),flush=True)
    except BaseException as error:
        save(out/'FAILED.json',dict(error_type=type(error).__name__,error=str(error),CPU_s=time.process_time()-cpu,wall_s=time.monotonic()-start,no_auto_retry=True,model_fit_physics=0));raise
    finally:signal.alarm(0)


if __name__=='__main__':main()
