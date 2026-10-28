"""Read only original saved events/lineage/receipts; never invent an action receipt."""
from pathlib import Path
import json,hashlib,sys
ADAPTER_SCHEMA='v8.reviewed_onpolicy_receipt_adapter.v1'
HARD=['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(path):return json.loads(Path(path).read_text())

def _binding(package,config,context25,logical_context_id,row):
    package=Path(package);ident=row['id']
    assert ident.startswith(config['group']+'_')
    assert load(package/'experiments'/(config['group']+'.json'))==config,'CONFIG_NOT_EXACT_SAVED_FROZEN_DOCUMENT'
    assert config['onpolicy_sampling']['development_context_id']==logical_context_id
    assert sha(package/config['case_path'])==config['case_sha256']
    route=load(package/config['onpolicy_sampling']['case_route_manifest'])
    assert route['development_routes'][logical_context_id]['case_sha256']==config['case_sha256']
    result_path=package/'attempts'/(ident+'_RESULT.json')
    saved=load(result_path);assert saved==row,'PASSED_ROW_NOT_ORIGINAL_SAVED_RESULT'
    found={}
    for raw in (package/'runtime/ATTEMPTS.jsonl').read_bytes().splitlines():
        ev=json.loads(raw)
        if ev.get('id')!=ident or ev['event'] not in ['START','END']:continue
        assert ev['event'] not in found,'DUPLICATE_ORIGINAL_EVENT'
        found[ev['event']]={'record':ev,'raw_line_without_newline_sha256':hashlib.sha256(raw).hexdigest(),'canonical_record_sha256':digest(ev)}
    assert set(found)=={'START','END'},'ACTUAL_START_END_REQUIRED'
    assert found['START']['record']['config_sha256']==sha(package/'experiments'/(config['group']+'.json'))
    assert found['START']['record']['group']==config['group']
    context_sha=digest({'names':context25['feature_names'],'values':context25['features']})
    return {'package':package,'id':ident,'result_path':result_path,'row':saved,'events':found,'context_sha':context_sha}

def build_baseline_receipt(*,package,config,context25,logical_context_id,row):
    b=_binding(package,config,context25,logical_context_id,row)
    assert row['id']==config['group']+'_B' and row['action']=={'family':'B'}
    assert row['complete'] is True and row['qualified'] is True
    assert b['events']['END']['record']['returncode']==0 and b['events']['END']['record']['joined'] is True
    return {'complete':True,'original_qualified':True,'JF_N_s':row['JF'],'JM_Nm_s':row['JM'],'result_source_sha256':sha(b['result_path']),'result_path':str(b['result_path'].relative_to(b['package'])),'context_group_evaluation_only':logical_context_id,'causal_features_sha256':b['context_sha'],'case_sha256_evaluation_only':config['case_sha256'],'completed_original_B_not_a_training_sample':True}

def build_onpolicy_receipt(*,package,config,context25,logical_context_id,proposal,row):
    b=_binding(package,config,context25,logical_context_id,row);P=b['package'];ident=b['id']
    assert proposal['attempt_id']==ident and proposal['context_group_evaluation_only']==logical_context_id
    assert proposal['causal_features_sha256']==b['context_sha']
    assert row['action']==proposal['proposal_recipe']['action'],'ACTUAL_TOP_LEVEL_POLICY_PROPOSAL_MISMATCH'
    assert digest(proposal['proposal_recipe'])==proposal['proposal_recipe_sha256'],'ACTUAL_RECIPE_BODY_HASH'
    prediction=load(P/'predictions'/(ident+'.json'))
    assert prediction['proposal_identity_sha256']==proposal['proposal_identity_sha256']
    assert prediction['collection_policy_sha256']==proposal['collection_policy_sha256']
    assert prediction['created_unix']<=b['events']['START']['record']['unix'],'PROPOSAL_NOT_BEFORE_PHYSICS'
    proposal_path=P/prediction['proposal_path']
    assert sha(proposal_path)==prediction['proposal_file_sha256']
    assert load(proposal_path)==proposal,'PRESAMPLED_FILE_NOT_EXACT'
    measured_path=P/row['metrics_path'] if row.get('metrics_path') else None
    m=load(measured_path) if measured_path and measured_path.is_file() else None
    data_path=P/'runtime/output'/(ident+'_DATA.json')
    data=load(data_path) if data_path.is_file() else None
    audit=(m or {}).get('native_physical_audit') or (data or {}).get('metric',{}).get('physical_audit',{})
    common=audit.get('unchanged_evaluator',{}).get('physical_task_result',{}).get('scorer_v2_common_conditions',{})
    # Three-valued evidence: missing is UNKNOWN, never a fabricated safe value.
    hard=True if any(common.get(k) is False for k in HARD) else False if all(common.get(k) is True for k in HARD) else None
    lineage_path=Path(m['execution_lineage_path']) if m and m.get('execution_lineage_path') else None
    if lineage_path is not None:assert lineage_path.resolve().is_relative_to(P.resolve())
    lineage=load(lineage_path) if lineage_path and lineage_path.is_file() else None
    owns=bool(lineage and lineage.get('status')=='PASS' and lineage.get('ownership_error_count')==0 and m['axes'].get('SCIENTIFIC_EXECUTION_CAUSAL_VALID')=='PASS')
    raw=P/'runtime/source/results'/ident/'runtime_artifacts.json.gz'
    stream_sha=None;receipts=positive=positive_steps=0
    if raw.exists():
        sys.path.insert(0,str(P/'runtime/code'))
        from stream_runtime_evidence import array_items
        h=hashlib.sha256()
        for r in array_items(raw,'command_receipts'):
            h.update(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()+b'\n');receipts+=1
            if r.get('applied') is True and isinstance(r.get('native_steps'),int) and r['native_steps']>0:
                positive+=1;positive_steps+=r['native_steps']
        stream_sha=h.hexdigest() if receipts else None
    end=b['events']['END']['record'];engineering=bool(row.get('complete') is True and row.get('error') is None and end.get('returncode')==0 and end.get('joined') is True and end.get('parent_hash_equal') is True and owns and hard is not None)
    protected=bool(isinstance(row.get('protected_task_failure'),dict) and hard is False)
    receipt={'attempt_id':ident,'arm_id':proposal['arm_id'],'proposal_identity_sha256':proposal['proposal_identity_sha256'],'selected_full_recipe_sha256':proposal['proposal_recipe_sha256'],'context_group_evaluation_only':logical_context_id,'causal_features_sha256':b['context_sha'],'genuine_new_physical_attempt':True,'historical_or_cached_outcome':False,'attempt_start_sha256':b['events']['START']['canonical_record_sha256'],'attempt_end_sha256':b['events']['END']['canonical_record_sha256'],'result_source_sha256':sha(b['result_path']),'native_ownership_sha256':sha(lineage_path) if lineage_path and lineage_path.is_file() else None,'applied_reference_receipt_stream_sha256':stream_sha,'actual_new_native_steps':row.get('actual_new_native_steps'),'engineering_complete':engineering,'ownership_and_causality_audit_pass':owns,'complete':row.get('complete'),'original_qualified':row.get('qualified'),'protected_task_failure':protected,'true_hard_safety_violation':hard,'JF_N_s':row.get('JF'),'JM_Nm_s':row.get('JM'),'case_sha256_evaluation_only':config['case_sha256'],'events_original_records_and_hash_scopes':b['events'],'safety_source':{'path':str(measured_path.relative_to(P)) if measured_path else str(data_path.relative_to(P)),'required_common_conditions':{k:common.get(k) for k in HARD},'unknown_is_not_false':True},'ownership_source':{'path':str(lineage_path.relative_to(P)) if lineage_path else None,'original_lineage_join_kind':lineage.get('join_kind') if lineage else None,'original_lineage_status':lineage.get('status') if lineage else None,'null_request_ids_not_fabricated':True},'applied_stream_scope':{'path':str(raw.relative_to(P)),'container_sha256':sha(raw) if raw.exists() else None,'hash_definition':'sha256 of every original command_receipts object as sorted compact UTF-8 JSON plus newline, in original order; includes inherited prefix; no proposal-only substitution','receipt_count':receipts,'positive_step_receipts':positive,'archived_positive_native_steps_including_inherited_prefix':positive_steps,'selected_recipe_not_claimed_to_own_every_archived_step':True},'event_pid_semantics':'Original START/END writer is fork parent; this adapter does not relabel it as child physical owner','original_complete_failures_and_partial_preserved':True,'original_motion_failure_requirements':row.get('motion_vs_B',{}).get('failed_requirements')}
    return receipt
