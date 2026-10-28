"""Metadata-only committed G0/G1 inventory; external batch02 remains untouched."""
from pathlib import Path
import hashlib
import json
import os
import resource
import signal
import time

P=Path(__file__).resolve().parents[1]
F='families/ppo_reward/continuous_scale_v1/'
RUN=F+'real_runs/GENUINE_BETA_V1/'
ARMS=['BETA_RF_RAW','BETA_PPO_RAW','BETA_RF_SCALED','BETA_PPO_SCALED']
PREFIX='families/critic_value/analysis/beta02l_prefix_trace_v1/PREFIX_TRACE_REVIEW_V1.json'
CHAIN='families/critic_value/analysis/beta_committed_pending_metadata_v2/RESULT.json'


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(relative):return hashlib.sha256((P/relative).read_bytes()).hexdigest()
def load(relative):return json.loads((P/relative).read_text())
def ref(relative):return dict(path=relative,sha256=sha(relative))


def new(relative,value):
    with (P/relative).open('x') as stream:json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


def main():
    started=time.monotonic();cpu=time.process_time()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('BETA_ENDPOINT_METADATA_CAP')));signal.alarm(60)
    assert 1793095035.1283<time.time()<1793112340.0-3600
    assert sha(CHAIN)=='31327a6941a66049d9b8140ebc4cb0d518ced3c8a211f7a327d1d470e2bd77cf'
    checked=load(CHAIN);assert checked['status']=='METADATA_CHAIN_PASS_NO_SECOND_BATCH_UPDATE' and not checked['failed_checks'] and len(checked['checks'])==142
    assert sha(PREFIX)=='d15d9d623fcda633530d7be702804dbce49ffb3d6ed63fb7188fcfa505b2113d'
    prefix=load(PREFIX);unknown=['human_acceleration','session_clearance','measured_sleeve_clearance']
    assert prefix['unresolved_gates']==unknown and prefix['global_prefix_11hard_false_established'] is None
    before_current=(P/(RUN+'CURRENT.json')).read_bytes()
    assert hashlib.sha256(before_current).hexdigest()=='32fad6c15976baa7f40f4391db9f1afe0472d452c3cad0afff54f3c866291161'
    pointer=json.loads(before_current);assert pointer['generation_index']==1 and pointer['status']=='READY_ALL_FOUR_UPDATED'
    assert sorted(path.name for path in (P/RUN).glob('GENERATION_*') if path.is_dir())==['GENERATION_0000','GENERATION_0001']
    transaction_inventory=[];transactions={}
    for index in [0,1]:
        relative=RUN+'GENERATION_'+str(index).zfill(4)+'/TRANSACTION.json';tx=load(relative)
        assert tx['generation_index']==index and tx['all_four_published_together'] is True
        transaction_inventory.append(dict(generation_index=index,transaction=ref(relative)));transactions[index]=tx
        for arm,item in tx['checkpoints'].items():
            assert sha(item['path'])==item['sha256'];snapshot=load(item['path'])
            assert snapshot['pending']==[] and digest(snapshot)==item['object_sha256']
    assert transaction_inventory[1]['transaction']['sha256']==pointer['transaction_sha256']=='c34461c586ad4279a6967cf898860105f9f27c59e2bedac415467ca64800502a'
    assert pointer['checkpoints']==transactions[1]['checkpoints']
    bundle_path=RUN+'sampling/V8BETA02L/PENDING_CHECKPOINTS.json';bundle=load(bundle_path)
    assert bundle['stage']=='OWNER_STOPPED_PENDING_PRESERVED_NO_UPDATE' and bundle['parameter_updates_in_this_job']==0
    originals={RUN+'CURRENT.json':hashlib.sha256(before_current).hexdigest(),bundle_path:sha(bundle_path)}
    pending=[]
    for arm in ARMS:
        snapshot_path=RUN+'sampling/V8BETA02L/'+arm+'_PENDING.json';snapshot=load(snapshot_path)
        assert snapshot==bundle['snapshots'][arm];originals[snapshot_path]=sha(snapshot_path)
        committed=load(pointer['checkpoints'][arm]['path'])
        for key in ['optimizer','finished_batches']:assert snapshot[key]==committed[key],(arm,key)
        assert {key:value for key,value in snapshot['policy'].items() if key!='counters'}=={key:value for key,value in committed['policy'].items() if key!='counters'}
        assert snapshot['policy']['counters']['parameter_updates']==committed['policy']['counters']['parameter_updates']
        assert snapshot['policy']['counters']['score_evaluations']==committed['policy']['counters']['score_evaluations']
        for proposal in snapshot['pending']:
            receipt=proposal['physical_receipt'];assert receipt['true_hard_safety_violation'] is False
            pending.append(dict(arm_id=arm,attempt_id=proposal['attempt_id'],proposal_identity_sha256=proposal['proposal_identity_sha256'],
                original_snapshot_sha256=sha(snapshot_path),snapshot_object_sha256=digest(snapshot),
                original_qualified=receipt['original_qualified'],true_hard_safety_violation=False))
    assert len(pending)==9 and len({item['proposal_identity_sha256'] for item in pending})==9
    owners=[];owner_evidence={}
    for group in ['V8BETA01H','V8BETA01L','V8BETA02H','V8BETA02L']:
        ending_rel='owned/'+group+'_SUPERVISOR_END.json';begin_rel='owned/'+group+'_SUPERVISOR.json'
        ending=load(ending_rel);begin=load(begin_rel);assert ending['survivors']==[] and ending['state']=='STOP'
        owner_evidence[ending_rel]=sha(ending_rel);owner_evidence[begin_rel]=sha(begin_rel)
        identities=list(ending['known_owned'].values())+[begin['identity']]
        for identity in identities:
            if identity is None:continue
            path=Path('/proc')/str(identity['pid'])/'stat';now_ticks=int(path.read_text().rsplit(')',1)[1].split()[19]) if path.exists() else None
            assert now_ticks!=identity['start_ticks'],'ORIGINAL_TRAINING_PROCESS_STILL_LIVE'
            owners.append(dict(group=group,pid=identity['pid'],original_start_ticks=identity['start_ticks'],
                now_start_ticks=now_ticks,original_closed=True))
    owner_rel='freeze/BETA_ALL_TRAINING_OWNER_CLOSURE_V1.json'
    tip_rel='freeze/BETA_COMMITTED_TIP_G1_EXACT_V1.json'
    quarantine_rel='freeze/BETA_EXTERNAL_BATCH02_QUARANTINE_V1.json'
    review_rel='freeze/BETA_COMMITTED_ENDPOINT_MAIN_SCOPE_REVIEW_V2.json'
    inventory_rel='freeze/BETA_COMMITTED_ENDPOINT_ACTUAL_INVENTORY_V2.json'
    outputs=[owner_rel,tip_rel,quarantine_rel,review_rel,inventory_rel]
    assert all(not (P/relative).exists() for relative in outputs)
    new(owner_rel,dict(status='ALL_KNOWN_TRAINING_OWNERS_EXITED',checked_unix=time.time(),survivors=[],
        all_original_PID_startticks_exited=True,processes=owners,original_evidence_files_sha256=owner_evidence,
        scope='Four actual physical sampling jobs and their supervisors; durable helper CLI closure separately recorded in committed batch01 root transition.'))
    with (P/tip_rel).open('xb') as stream:stream.write(before_current)
    quarantine=load(F+'BETA_ENDPOINT_QUARANTINE_TEMPLATE_REVIEW_ONLY_V1.json')
    quarantine.update(status='EXTERNAL_BATCH02_PENDING_UNRESOLVED_UNMODIFIED_NOT_ENDPOINT',
        external_pending_identity_inventory=pending,all_owner_closure_review=ref(owner_rel),reviewer='MAIN_AGENT',frozen_unix=time.time(),
        source_only_template_has_no_execution_authority=False,original_snapshot_files_sha256=originals,
        committed_pending_independent_review=ref(CHAIN))
    new(quarantine_rel,quarantine)
    batch01='audit/BETA_BATCH01_MAIN_CLOSURE_REVIEW_V2.json'
    metadata_evidence={**owner_evidence,CHAIN:sha(CHAIN),PREFIX:sha(PREFIX),batch01:sha(batch01),
        'audit/BETA_BATCH01_ROOT_TRANSITION_END_V3.json':sha('audit/BETA_BATCH01_ROOT_TRANSITION_END_V3.json')}
    scope=dict(generation_indices=[0,1],true_hard_safety_violation=False,all_committed_checkpoints_have_no_pending=True,
        original_complete_receipts_raw_scorer_checks_reviewed=True,excludes_external_batch02_pending=True,
        committed_batch01_closure=ref(batch01),reviewed_G1_transaction_sha256=transaction_inventory[1]['transaction']['sha256'])
    review=dict(schema='v8.beta_committed_endpoint_scope_review.v2',status='SAFE_COMMITTED_ENDPOINT_SCOPE_EXTERNAL_BATCH02_UNRESOLVED',
        frozen_unix=time.time(),whole_training_hard_status='UNKNOWN_EXTERNAL_BATCH02_UNRESOLVED',endpoint_transaction_scope=scope,
        endpoint_selected_by_outcome_or_best_seed=False,quarantine=ref(quarantine_rel),physical_dispatch_authority_granted=False,
        metadata_evidence_files_sha256=metadata_evidence,committed_generation_inventory_object_sha256=digest(transaction_inventory),
        latest_actual_committed_generation_index=1,frozen_committed_pointer_snapshot=ref(tip_rel),
        role_generation_indices=dict(PARENT=0,FIRST_COMPLETED=1,LAST_COMPLETED=1))
    new(review_rel,review)
    roles=[]
    for role,index in [('PARENT',0),('FIRST_COMPLETED',1),('LAST_COMPLETED',1)]:
        models=[]
        for arm in ARMS:
            item=transactions[index]['checkpoints'][arm];checkpoint=load(item['path'])
            models.append(dict(arm_id=arm,path=item['path'],sha256=item['sha256'],policy_behavior_sha256=checkpoint['policy_behavior_sha256']))
        roles.append(dict(role=role,generation_index=index,checkpoints=models))
    axis=F+'FROZEN_AXIS_GATE1_V1.json'
    inventory=dict(schema='v8.beta_committed_endpoint_inventory.v2',status='COMMITTED_G0_G1_ONLY_WITH_EXTERNAL_UNRESOLVED_QUARANTINE',
        arm_ids=ARMS,roles=roles,policy_location=['policy'],complete_committed_generation_transaction_inventory=transaction_inventory,
        root_endpoint_scope_review=ref(review_rel),quarantine=ref(quarantine_rel),axis=ref(axis),axis_object_sha256=digest(load(axis)),
        normalization_source=ref('families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json'),
        A3_adapter_manifest=ref('families/critic_value/coverage_state_v3/LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json'))
    new(inventory_rel,inventory)
    assert (P/(RUN+'CURRENT.json')).read_bytes()==before_current
    for relative,expected in originals.items():assert sha(relative)==expected
    new('audit/BETA_COMMITTED_ENDPOINT_FREEZE_END_V2.json',dict(status='METADATA_FROZEN_COMMITTED_ENDPOINTS_EXTERNAL_QUARANTINE_UNCHANGED',
        created_unix=time.time(),outputs={relative:sha(relative) for relative in outputs},
        external_pending=9,external_published_updates=0,whole_training_hard_status='UNKNOWN',
        wall_s=time.monotonic()-started,cpu_s=time.process_time()-cpu,model_imports=0,forwards=0,fit=0,RNG_draws=0,new_physics=0))
    print(json.dumps(dict(inventory=ref(inventory_rel),external_pending=9,whole_training_hard_status='UNKNOWN_NO_CANCEL')),flush=True)


if __name__=='__main__':main()
