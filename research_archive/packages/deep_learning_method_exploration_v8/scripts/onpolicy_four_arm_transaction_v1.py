"""Main-owned atomic four-arm checkpoint transactions. No physics dispatch.

Only init and commit are CLI mutations. Immutable generations preserve all
previous checkpoints; CURRENT.json is a pointer, never the checkpoint itself.
All four metadata preflights finish before any optimizer is called.
"""
from pathlib import Path
import argparse, copy, fcntl, hashlib, json, os, sys, time, traceback

P = Path(__file__).resolve().parents[1]
F = P / 'families/ppo_reward'
sys.path.insert(0, str(F))
from categorical_policy import digest, policy_sha256
from onpolicy_update_driver_v2 import OnPolicyArm, lift_three_to_five
from onpolicy_transaction_evidence_v1 import verify_original_proposals_and_receipts
ARMS = ['RF_RAW','PPO_RAW','RF_SCALED','PPO_SCALED']

def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p, obj):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:
        json.dump(obj,stream,indent=2,allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    fd=os.open(p.parent,os.O_RDONLY); os.fsync(fd); os.close(fd)
def atomic_pointer(p, obj):
    temporary=p.with_name(p.name+'.tmp.'+str(os.getpid()))
    write_new(temporary,obj); os.replace(temporary,p)
    fd=os.open(p.parent,os.O_RDONLY); os.fsync(fd); os.close(fd)
def require_closed(group):
    done=load(P/'jobs'/group/'WORKER_DONE.json')
    supervisor=load(P/'owned'/(group+'_SUPERVISOR_END.json'))
    assert done['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS', 'SAMPLING_WORKER_NOT_CLEANLY_COMPLETED'
    assert supervisor['state']=='STOP' and supervisor['worker_exit_code']==0 and not supervisor['survivors'], 'PHYSICAL_OWNER_NOT_CLOSED'
    assert (P/'owned'/(group+'_EXIT.json')).is_file(), 'MISSING_WORKER_EXIT'
    events=[json.loads(line) for line in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines() if json.loads(line).get('group')==group or json.loads(line).get('id','').startswith(group+'_')]
    starts=[ev for ev in events if ev['event']=='START']
    ends=[ev for ev in events if ev['event']=='END']
    assert len(starts)==len(ends)==10, 'EXPECTED_COLD_PARENT_B_AND_EIGHT_POLICY_ATTEMPTS'
    assert len({ev['id'] for ev in starts})==10
    for event in starts:
        joined=[end for end in ends if end['id']==event['id']]
        assert len(joined)==1 and joined[0].get('joined') is True and joined[0].get('returncode')==0, 'UNCLOSED_ACTUAL_ATTEMPT'
    assert load(P/'audit'/(group+'_PARENT_RAW_GATE.json'))['status']=='PASS', 'REAL_PARENT_B_RAW_GATE'
    return {'worker_done_sha256':sha(P/'jobs'/group/'WORKER_DONE.json'),'supervisor_end_sha256':sha(P/'owned'/(group+'_SUPERVISOR_END.json')),'attempt_ids':[ev['id'] for ev in starts]}

def approved(contract):
    document=load(contract)
    assert document['status']=='APPROVED_BY_MAIN_AGENT', 'MAIN_APPROVAL_REQUIRED'
    assert document['activation']==load(P/'ACTIVATION.json')['activation_id']
    assert time.time()<document['global_deadline_unix']
    for relative, expected in document['frozen_dependencies'].items():
        assert sha(P/relative)==expected, 'APPROVED_DEPENDENCY_CHANGED:'+relative
    return document

def restore(snapshot, contract_sha, hashes, dependency_sha):
    return OnPolicyArm.restore(snapshot,approved_contract_sha256=contract_sha,frozen_menu_sha256=hashes,categorical_dependency_sha256=dependency_sha)

def publish_generation(run, index, snapshots, metadata):
    final=run/('GENERATION_'+str(index).zfill(4))
    assert not final.exists(), 'REFUSE_CHECKPOINT_GENERATION_OVERWRITE'
    stage=run/('STAGING_'+str(index).zfill(4)+'_'+str(time.time_ns()))
    stage.mkdir(parents=True)
    manifest={}
    for arm in ARMS:
        path=stage/(arm+'.json'); write_new(path,snapshots[arm]); manifest[arm]={'path':str((final/path.name).relative_to(P)),'sha256':sha(path),'policy_sha256':policy_sha256(snapshots[arm]['policy'])}
    write_new(stage/'TRANSACTION.json',{**metadata,'generation_index':index,'checkpoints':manifest,'created_unix':time.time()})
    os.rename(stage,final)
    fd=os.open(run,os.O_RDONLY); os.fsync(fd); os.close(fd)
    pointer={'generation_index':index,'generation_directory':str(final.relative_to(P)),'transaction_sha256':sha(final/'TRANSACTION.json'),'checkpoints':manifest,'status':metadata['status']}
    atomic_pointer(run/'CURRENT.json',pointer)
    return pointer

def initialize_run(run, contract_path):
    document=approved(contract_path); contract_sha=sha(contract_path)
    assert not run.exists(), 'REFUSE_RUN_REINITIALIZATION_CLOCK_RESET'
    menu=load(P/document['menu_path']); parent_document=load(P/document['parent_checkpoint_path'])
    parent=parent_document['policy']; now=time.time()
    local_stop=min(now+document['local_window_s'],document['global_deadline_unix']-document['final_audit_reserve_s'])
    lifted=lift_three_to_five(parent,menu['action_contracts'],new_seed=document['policy_initialization_seed'])
    snapshots={}
    for arm in ARMS:
        obj=OnPolicyArm(copy.deepcopy(lifted),arm_id=arm,algorithm='PPO' if arm.startswith('PPO') else 'REINFORCE',gain=20. if arm.endswith('SCALED') else 1.,seed=document['sampling_seed'],approved_contract_sha256=contract_sha,expected_context_counts=document['expected_context_counts'],local_stop_unix=local_stop,frozen_menu_sha256=menu['full_recipe_sha256'],categorical_dependency_sha256=sha(F/'categorical_policy.py'))
        snapshots[arm]=obj.snapshot()
    run.mkdir(parents=True)
    write_new(run/'RUN_IDENTITY.json',{'schema':'v8.four_arm_run_identity.v1','activation':document['activation'],'start_unix':now,'local_stop_unix':local_stop,'global_deadline_unix':document['global_deadline_unix'],'approved_contract_path':str(contract_path.relative_to(P)),'approved_contract_sha256':contract_sha,'initialization':lifted['initialization'],'same_initial_weights':True,'sampling_seed_shared_independent_rng_objects':document['sampling_seed'],'initialization_count':1,'arm_constructor_count':4,'optimizer_updates':0,'physical_attempts':0})
    return publish_generation(run,0,snapshots,{'status':'COMMON_PARENT_INITIALIZED_NO_UPDATE','contract_sha256':contract_sha,'local_stop_unix':local_stop,'all_arms_committed_together':True})

def commit_run(run, pending_path):
    identity=load(run/'RUN_IDENTITY.json'); contract_path=P/identity['approved_contract_path']; document=approved(contract_path)
    assert sha(contract_path)==identity['approved_contract_sha256']
    current=load(run/'CURRENT.json')
    assert sha(P/current['generation_directory']/'TRANSACTION.json')==current['transaction_sha256']
    next_index=current['generation_index']+1
    assert not (run/('GENERATION_'+str(next_index).zfill(4))).exists(),'ORPHAN_GENERATION_REQUIRES_EXPLICIT_ZERO_UPDATE_RECOVERY'
    intent=run/('TRANSACTION_ATTEMPT_'+str(next_index).zfill(4)+'.json')
    assert not intent.exists(),'PRIOR_TRANSACTION_ATTEMPT_REQUIRES_EXPLICIT_REVIEW_NO_REPEAT_OPTIMIZER'
    envelope=load(pending_path)
    assert envelope['schema']=='v8.root_bound_two_job_pending.v1'
    original_path=P/envelope['original_final_pending_path']
    assert sha(original_path)==envelope['original_final_pending_sha256']
    pending=load(original_path); group=pending['job_group_evaluation_only']
    closed=require_closed(group)
    assert pending['stage']=='ALL_CURRENT_CONTEXT_SAMPLES_COLLECTED_NO_UPDATE'
    assert pending['parameter_updates_in_this_job']==0
    # The second job carries both contexts, including the first job's exact
    # pending snapshot. Verify every source job separately, not just the last.
    expected_groups=envelope.get('root_expected_sampling_groups')
    assert isinstance(expected_groups,list) and len(expected_groups)==2 and group==expected_groups[-1], 'EXPLICIT_TWO_CLOSED_JOB_BINDING_REQUIRED'
    jobs={g:require_closed(g) for g in expected_groups}
    assert len(set(expected_groups))==2
    first_config=load(P/'experiments'/(expected_groups[0]+'.json'))
    second_config=load(P/'experiments'/(expected_groups[1]+'.json'))
    first_pending_path=P/first_config['onpolicy_sampling']['output_directory']/'PENDING_CHECKPOINTS.json'
    first_pending=load(first_pending_path)
    assert first_pending['stage']=='ALL_CURRENT_CONTEXT_SAMPLES_COLLECTED_NO_UPDATE'
    assert first_pending['development_context_id_evaluation_only']!=pending['development_context_id_evaluation_only']
    assert original_path==P/second_config['onpolicy_sampling']['output_directory']/'PENDING_CHECKPOINTS.json'
    for item in second_config['onpolicy_sampling']['arm_inputs']:
        source=P/item['snapshot_path']; assert sha(source)==item['snapshot_sha256']
        assert load(source)==first_pending['snapshots'][item['arm_id']], 'SECOND_JOB_DID_NOT_RESUME_FIRST_JOB_EXACT_PENDING'
    for item in first_config['onpolicy_sampling']['arm_inputs']:
        assert item['snapshot_path']==current['checkpoints'][item['arm_id']]['path'] and item['snapshot_sha256']==current['checkpoints'][item['arm_id']]['sha256'], 'BATCH_DID_NOT_START_AT_CURRENT_GENERATION'
    menu=load(P/document['menu_path']); hashes=menu['full_recipe_sha256']; dep=sha(F/'categorical_policy.py')
    models={arm:restore(pending['snapshots'][arm],identity['approved_contract_sha256'],hashes,dep) for arm in ARMS}
    assert set(pending['snapshots'])==set(ARMS)
    seen=set(); all_receipts=[]; prior_snapshots={}
    for arm,obj in models.items():
        checkpoint=P/current['checkpoints'][arm]['path']; assert sha(checkpoint)==current['checkpoints'][arm]['sha256']
        old=load(checkpoint)
        prior_snapshots[arm]=old
        assert policy_sha256(obj.policy)==policy_sha256(old['policy'])
        assert obj.batch_id==old['batch_id'] and obj.finished_batches==old['finished_batches']
        for key in ['arm_id','algorithm','gain','expected_context_counts','contract_sha256','frozen_menu_sha256','categorical_dependency']:
            assert pending['snapshots'][arm][key]==old[key], 'ARM_CONFIGURATION_CHANGED:'+key
        prefix=first_pending['snapshots'][arm]['pending']
        assert obj.pending[:len(prefix)]==prefix, 'FINAL_PENDING_CHANGED_FIRST_CONTEXT_PROPOSALS_OR_RECEIPTS'
        assert obj.local_stop_unix==identity['local_stop_unix']==old['local_stop_unix']
        for proposal in obj.pending:
            ident=proposal['attempt_id']; assert ident not in seen, 'CROSS_ARM_REUSED_PHYSICAL_ATTEMPT'; seen.add(ident)
            assert any(ident in meta['attempt_ids'] for meta in jobs.values()), 'UNBOUND_POLICY_ATTEMPT'
            all_receipts.append(proposal.get('physical_result'))
        assert obj.seen_attempt_ids==set(old['seen_attempt_ids'])|{p['attempt_id'] for p in obj.pending}, 'PENDING_SEEN_SET_IDENTITY'
    assert len(seen)==16, 'EXACT_COMPLETE_CONTEXT_BALANCED_NEW_BATCH_REQUIRED'
    # Global hard safety wins over all censor reasons. No optimizer/forward
    # or cancellation is executed before examining all available receipts.
    hard=[r['attempt_id'] for r in all_receipts if isinstance(r,dict) and r.get('true_hard_safety_violation') is True]
    transaction_id='TX_'+str(current['generation_index']+1).zfill(4)+'_'+str(time.time_ns())
    if hard:
        write_new(run/(transaction_id+'_HARD_SAFETY_STOP.json'),{'status':'HARD_SAFETY_STOP_NO_UPDATE','attempt_ids':hard,'pending_path':str(pending_path.relative_to(P)),'parameter_updates':0}); raise ValueError('HARD_SAFETY_STOP_MAIN_AGENT_REVIEW')
    original_evidence=verify_original_proposals_and_receipts(P,[first_config,second_config],models,prior_snapshots=prior_snapshots)
    checks={}; errors={}
    for arm,obj in models.items():
        try: checks[arm]=obj.preflight_batch_metadata()
        except Exception as error: errors[arm]=str(error)
    censor=bool(errors or any(not check['admissible'] for check in checks.values()) or time.time()>=identity['local_stop_unix'])
    before={arm:copy.deepcopy(obj.policy['counters']) for arm,obj in models.items()}
    results={}
    write_new(intent,{'status':'ALL_PREFLIGHTS_DONE_BEFORE_ANY_UPDATE','transaction_id':transaction_id,'current_pointer':current,'pending_path':str(pending_path.relative_to(P)),'pending_sha256':sha(pending_path),'counter_before':before,'censor':censor,'created_unix':time.time(),'repeat_commit_must_not_rerun_optimizer':True})
    if censor:
        for arm,obj in models.items(): results[arm]=obj.cancel_pending_batch(group_transaction_id=transaction_id,reason='ALL_ARM_PREFLIGHT_OR_LOCAL_DEADLINE_CENSOR:'+json.dumps({'errors':errors,'preflights':checks},sort_keys=True))
        status='ALL_FOUR_CANCELLED_NO_UPDATE'
    else:
        # Updates mutate only these private copies; publishing follows only
        # after every arm succeeds. Exceptions preserve attempted compute.
        trial_models={arm:restore(obj.snapshot(),identity['approved_contract_sha256'],hashes,dep) for arm,obj in models.items()}
        try:
            for arm,obj in trial_models.items():
                results[arm]=obj.finish_batch()
                assert results[arm]['result']['status']=='COMPLETED_GENUINE_ON_POLICY_UPDATE', 'NONCOMPLETED_GROUP_UPDATE'
            models=trial_models
        except BaseException as error:
            write_new(run/(transaction_id+'_ABORTED_COMPUTATION.json'),{'status':'ABORTED_NO_GENERATION_COMMIT','error':str(error),'traceback':traceback.format_exc(),'partial_results':results,'attempted_private_copy_counters':{a:o.policy['counters'] for a,o in trial_models.items()},'before_counters':before,'all_physics_preserved_in_pending':str(pending_path.relative_to(P)),'created_unix':time.time()})
            raise
        status='ALL_FOUR_GENUINE_UPDATES_ATOMICALLY_COMMITTED'
    # Persist the complete computed state before publishing any generation.
    # A publish failure can be resumed from this file with zero new fitting.
    try:
        snapshots={arm:obj.snapshot() for arm,obj in models.items()}
        metadata={'status':status,'transaction_id':transaction_id,'previous_transaction_sha256':current['transaction_sha256'],'pending_input_path':str(pending_path.relative_to(P)),'pending_input_sha256':sha(pending_path),'original_final_pending_sha256':sha(original_path),'first_job_pending_sha256':sha(first_pending_path),'closed_jobs':jobs,'original_proposal_receipt_joins':original_evidence,'preflights':checks,'preflight_errors':errors,'counters_before':before,'results':results,'all_arms_committed_together':True,'best_checkpoint_selection':False,'first_completed_update_is_early':True,'endpoint_is_last_completed_aligned_generation':True}
        computation=run/('TRANSACTION_COMPUTATION_'+str(next_index).zfill(4)+'.json')
        write_new(computation,{'schema':'v8.completed_private_four_arm_computation.v1','generation_index':next_index,'previous_pointer':current,'intent_sha256':sha(intent),'snapshots':snapshots,'metadata':metadata,'created_unix':time.time(),'optimizer_must_not_run_on_recovery':True})
        metadata['durable_computation_output_path']=str(computation.relative_to(P));metadata['durable_computation_output_sha256']=sha(computation)
        return publish_generation(run,next_index,snapshots,metadata)
    except BaseException as error:
        write_new(run/(transaction_id+'_PUBLICATION_OR_SNAPSHOT_FAILURE.json'),{'status':'PUBLICATION_FAILED_REVIEW_DURABLE_COMPUTATION_NO_REFIT','error':str(error),'traceback':traceback.format_exc(),'final_counters':{a:o.policy['counters'] for a,o in models.items()},'before_counters':before,'intent_path':str(intent.relative_to(P)),'created_unix':time.time()})
        raise

def recover_publication(run):
    """Resume publishing already computed bytes. No policy construction/forward."""
    current=load(run/'CURRENT.json');next_index=current['generation_index']+1
    identity=load(run/'RUN_IDENTITY.json');contract=P/identity['approved_contract_path'];approved(contract)
    assert sha(contract)==identity['approved_contract_sha256']
    previous_transaction=P/current['generation_directory']/'TRANSACTION.json'
    assert sha(previous_transaction)==current['transaction_sha256']
    previous=load(previous_transaction)
    assert current['checkpoints']==previous['checkpoints'] and current['generation_index']==previous['generation_index'] and current['status']==previous['status']
    for item in current['checkpoints'].values():assert sha(P/item['path'])==item['sha256']
    intent=run/('TRANSACTION_ATTEMPT_'+str(next_index).zfill(4)+'.json')
    computation=run/('TRANSACTION_COMPUTATION_'+str(next_index).zfill(4)+'.json')
    output=load(computation);assert output['schema']=='v8.completed_private_four_arm_computation.v1'
    assert output['intent_sha256']==sha(intent) and output['previous_pointer']==current
    assert output['generation_index']==next_index
    final=run/('GENERATION_'+str(next_index).zfill(4));metadata=output['metadata']
    metadata['durable_computation_output_path']=str(computation.relative_to(P));metadata['durable_computation_output_sha256']=sha(computation)
    if not final.exists():return publish_generation(run,next_index,output['snapshots'],metadata)
    manifest=load(final/'TRANSACTION.json');assert manifest['durable_computation_output_sha256']==sha(computation)
    assert manifest['previous_transaction_sha256']==current['transaction_sha256']
    for arm,item in manifest['checkpoints'].items():
        path=P/item['path'];assert sha(path)==item['sha256'] and load(path)==output['snapshots'][arm]
    pointer={'generation_index':next_index,'generation_directory':str(final.relative_to(P)),'transaction_sha256':sha(final/'TRANSACTION.json'),'checkpoints':manifest['checkpoints'],'status':manifest['status']}
    atomic_pointer(run/'CURRENT.json',pointer)
    write_new(run/('RECOVERED_PUBLICATION_'+str(next_index).zfill(4)+'.json'),{'status':'EXISTING_FOUR_ARM_GENERATION_POINTER_RECOVERED','optimizer_calls':0,'model_forward':0,'unix':time.time(),'durable_computation_sha256':sha(computation)})
    return pointer

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('operation',choices=['init','commit','recover']); parser.add_argument('--run',required=True); parser.add_argument('--contract'); parser.add_argument('--pending'); args=parser.parse_args()
    run=(P/args.run).resolve(); assert run.is_relative_to(F.resolve())
    lock=(P/'owned/ONPOLICY_TRANSACTION.lock').open('a'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert time.time()<load(P/'ACTIVATION.json')['hard_stop_unix']
    result=initialize_run(run,(P/args.contract).resolve()) if args.operation=='init' else recover_publication(run) if args.operation=='recover' else commit_run(run,(P/args.pending).resolve())
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__': main()
