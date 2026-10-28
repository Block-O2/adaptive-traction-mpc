"""One closed implementation failure reconciliation; no resimulation/update."""
from pathlib import Path
import copy,hashlib,importlib.util,json,sys,time
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'families/ppo_reward'))
from onpolicy_update_driver_v2 import OnPolicyArm
from categorical_policy import digest
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:json.dump(obj,stream,indent=2,allow_nan=False);stream.write('\n')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def tuples(x):return tuple(tuples(v) for v in x) if isinstance(x,list) else x
def main():
    group='V8OP01H';run=P/'families/ppo_reward/onpolicy_runs/GENUINE_V1';config=load(P/'experiments'/(group+'.json'))
    done=load(P/'jobs'/group/'WORKER_DONE.json');end=load(P/'owned'/(group+'_SUPERVISOR_END.json'))
    assert done['status']=='FAILED_PRESERVED' and done['error']=='PRESAMPLED_FILE_NOT_EXACT'
    assert end['state']=='STOP' and end['worker_exit_code']==1 and not end['survivors']
    assert (P/'owned'/(group+'_EXIT.json')).exists()
    original_path=P/config['onpolicy_sampling']['output_directory']/'PENDING_CHECKPOINTS.json';pending=load(original_path)
    assert pending['stage']=='STOPPED_WITH_PRESERVED_PENDING'
    assert [len(pending['snapshots'][a]['pending']) for a in ['RF_RAW','PPO_RAW','RF_SCALED','PPO_SCALED']]==[1,0,0,0]
    ident=group+'_OP_RF_RAW_01';source=P/config['onpolicy_sampling']['output_directory']/'OP_RF_RAW_01_PROPOSAL.json';proposal=load(source)
    row=load(P/'attempts'/(ident+'_RESULT.json'));assert row['complete'] is True and row['qualified'] is True
    assert proposal['attempt_id']==ident and proposal['physical_result'] is None
    # Reproduce only the serialization defect, using the actual saved proposal.
    memory=copy.deepcopy(proposal)
    for field in ['rng_before','rng_after']:memory[field]=tuples(memory[field])
    assert memory!=proposal and digest(memory)==digest(proposal)
    kwargs=dict(package=P,config=config,context25=pending['context25'],logical_context_id=config['onpolicy_sampling']['development_context_id'],row=row)
    old=module('_v8_closed_old_adapter',P/'source/v8_onpolicy_receipt_adapter_v1.py');new=module('_v8_closed_corrected_adapter',P/'source/v8_onpolicy_receipt_adapter_v2.py')
    try:old.build_onpolicy_receipt(proposal=memory,**kwargs)
    except AssertionError as error:assert str(error)=='PRESAMPLED_FILE_NOT_EXACT'
    else:raise AssertionError('ORIGINAL_DEFECT_NOT_REPRODUCED')
    receipt=old.build_onpolicy_receipt(proposal=proposal,**kwargs)
    corrected=new.build_onpolicy_receipt(proposal=memory,**kwargs)
    assert receipt==corrected,'CORRECTION_CHANGED_ACTUAL_PHYSICAL_RECEIPT'
    assert receipt['engineering_complete'] and receipt['ownership_and_causality_audit_pass'] and receipt['true_hard_safety_violation'] is False
    receipt_path=P/config['onpolicy_sampling']['output_directory']/'OP_RF_RAW_01_PHYSICAL_RECEIPT.json';write_new(receipt_path,receipt)
    identity=load(run/'RUN_IDENTITY.json');menu=load(P/'freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json')
    arm=OnPolicyArm.restore(pending['snapshots']['RF_RAW'],approved_contract_sha256=identity['approved_contract_sha256'],frozen_menu_sha256=menu['full_recipe_sha256'],categorical_dependency_sha256=sha(P/'families/ppo_reward/categorical_policy.py'))
    before=copy.deepcopy(arm.policy);rng_before=arm.rng.getstate();arm.accept_physical_receipt(receipt)
    assert arm.policy==before and arm.rng.getstate()==rng_before
    pending['snapshots']['RF_RAW']=arm.snapshot();pending['stage']='MAIN_RECONCILED_CLOSED_SERIALIZATION_FAILURE_CANCEL_ONLY_NO_UPDATE'
    output=P/config['onpolicy_sampling']['output_directory']/'main_reconciliation_v1';write_new(output/'PENDING_CHECKPOINTS.json',pending)
    events=[json.loads(line) for line in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines() if json.loads(line)['id'].startswith(group+'_')]
    starts=[e for e in events if e['event']=='START'];ends=[e for e in events if e['event']=='END'];assert len(starts)==len(ends)==3
    assert all(any(e['id']==s['id'] and e.get('joined') is True for e in ends) for s in starts)
    review={'status':'CLOSED_IMPLEMENTATION_FAILURE_RECONCILED_CANCEL_ALL_ARMS_ONLY','source_pending_sha256':sha(original_path),'proposal_file_sha256':sha(source),'original_result_sha256':sha(P/'attempts'/(ident+'_RESULT.json')),'materialized_receipt_path':str(receipt_path.relative_to(P)),'materialized_receipt_sha256':sha(receipt_path),'receipt_producer':'MAIN_AGENT_AFTER_CLOSED_WORKER_FAILURE_FROM_ORIGINAL_RAW_EVENTS_LINEAGE_NO_PHYSICS','old_tuple_defect_reproduced':True,'old_saved_JSON_receipt_equals_corrected_in_memory_tuple_receipt':True,'actual_adapter_calls':3,'expected_rejection_calls':1,'complete_receipt_stream_rehashes':2,'real_arm_restore_calls':1,'model_forward':0,'parameter_updates':0,'new_physics':0,'RNG_unchanged_by_reconciliation':True,'original_failed_job_preserved':True,'actual_policy_receipt_hard_safety':False,'original_worker_failure_cause':'PRESAMPLED_FILE_NOT_EXACT','parent_partial_safety_scope':'Parent aborted at frozen OUT0 by adapter assertion; no full parent safety qualification invented. Completed B and policy B children are original-qualified; missing parent full evidence remains engineering censor.','unix':time.time()}
    write_new(output/'MAIN_RECONCILIATION.json',review)
    envelope={'schema':'v8.root_bound_partial_pending_cancel.v1','original_final_pending_path':str((output/'PENDING_CHECKPOINTS.json').relative_to(P)),'original_final_pending_sha256':sha(output/'PENDING_CHECKPOINTS.json'),'all_sampling_groups_in_current_batch':[group],'all_actual_failure_artifacts_reviewed_for_hard_safety':True,'confirmed_hard_safety_attempts':[],'hard_safety_review_path':str((output/'MAIN_RECONCILIATION.json').relative_to(P)),'hard_safety_review_sha256':sha(output/'MAIN_RECONCILIATION.json'),'all_parent_failure_artifacts_retained':True}
    write_new(output/'CANCEL_ENVELOPE.json',envelope)
    print('CLOSED_JSON_IDENTITY_RECONCILIATION_PASS_ZERO_UPDATE',str(output.relative_to(P)))
if __name__=='__main__':main()
