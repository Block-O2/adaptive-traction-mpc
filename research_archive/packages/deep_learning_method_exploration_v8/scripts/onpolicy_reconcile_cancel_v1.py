"""Explicit closed-owner partial-batch cancellation. Never forwards/updates.

The main agent supplies an envelope pointing at the LAST preserved pending
bundle and every sampling group that consumed physics in this batch. Missing
receipt data stays missing and all attempt/raw costs remain in the ledger.
"""
from pathlib import Path
import argparse,fcntl,json,time
import onpolicy_four_arm_transaction_v1 as tx
from onpolicy_transaction_evidence_v1 import verify_original_proposals_and_receipts
P=tx.P
def cancel(run,envelope_path,reason):
    assert reason,'EXPLICIT_SCIENTIFIC_OR_ENGINEERING_CENSOR_REASON'
    identity=tx.load(run/'RUN_IDENTITY.json');contract=P/identity['approved_contract_path'];doc=tx.approved(contract)
    assert tx.sha(contract)==identity['approved_contract_sha256']
    current=tx.load(run/'CURRENT.json');assert tx.sha(P/current['generation_directory']/'TRANSACTION.json')==current['transaction_sha256']
    envelope=tx.load(envelope_path);assert envelope['schema']=='v8.root_bound_partial_pending_cancel.v1'
    source=P/envelope['original_final_pending_path'];assert tx.sha(source)==envelope['original_final_pending_sha256']
    bundle=tx.load(source);groups=envelope['all_sampling_groups_in_current_batch'];assert 1<=len(groups)<=2 and len(set(groups))==len(groups)
    assert bundle['job_group_evaluation_only']==groups[-1]
    closed={};configs=[]
    events=[json.loads(line) for line in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
    for group in groups:
        supervisor=tx.load(P/'owned'/(group+'_SUPERVISOR_END.json'));assert supervisor['state']=='STOP' and not supervisor['survivors']
        assert (P/'owned'/(group+'_EXIT.json')).is_file();done=tx.load(P/'jobs'/group/'WORKER_DONE.json')
        starts=[e for e in events if e['event']=='START' and e['id'].startswith(group+'_')]
        ends=[e for e in events if e['event']=='END' and e['id'].startswith(group+'_')]
        assert len(starts)==len(ends) and starts
        for event in starts:
            matches=[e for e in ends if e['id']==event['id']];assert len(matches)==1 and matches[0].get('joined') is True
        config=tx.load(P/'experiments'/(group+'.json'));configs.append(config)
        assert config['onpolicy_sampling']['output_directory'] in str(source.relative_to(P)) or group!=groups[-1]
        closed[group]={'supervisor_sha256':tx.sha(P/'owned'/(group+'_SUPERVISOR_END.json')),'worker_done_sha256':tx.sha(P/'jobs'/group/'WORKER_DONE.json'),'worker_status':done['status'],'actual_attempt_ids':[e['id'] for e in starts],'worker_exit_code':supervisor['worker_exit_code']}
    menu=tx.load(P/doc['menu_path']);dependency=tx.sha(tx.F/'categorical_policy.py')
    models={arm:tx.restore(bundle['snapshots'][arm],identity['approved_contract_sha256'],menu['full_recipe_sha256'],dependency) for arm in tx.ARMS}
    prior_snapshots={}
    assert set(bundle['snapshots'])==set(tx.ARMS)
    first_config=configs[0]
    for item in first_config['onpolicy_sampling']['arm_inputs']:
        assert item['snapshot_path']==current['checkpoints'][item['arm_id']]['path'] and item['snapshot_sha256']==current['checkpoints'][item['arm_id']]['sha256']
    if len(groups)==2:
        first_source=P/first_config['onpolicy_sampling']['output_directory']/'PENDING_CHECKPOINTS.json';first=tx.load(first_source)
        assert first['stage']=='ALL_CURRENT_CONTEXT_SAMPLES_COLLECTED_NO_UPDATE'
        for item in configs[1]['onpolicy_sampling']['arm_inputs']:
            path=P/item['snapshot_path'];assert tx.sha(path)==item['snapshot_sha256'] and tx.load(path)==first['snapshots'][item['arm_id']]
        for arm in tx.ARMS:
            prefix=first['snapshots'][arm]['pending'];assert bundle['snapshots'][arm]['pending'][:len(prefix)]==prefix
    for arm,obj in models.items():
        oldpath=P/current['checkpoints'][arm]['path'];assert tx.sha(oldpath)==current['checkpoints'][arm]['sha256'];old=tx.load(oldpath)
        prior_snapshots[arm]=old
        for key in ['arm_id','algorithm','gain','expected_context_counts','contract_sha256','frozen_menu_sha256','categorical_dependency','batch_id','finished_batches','local_stop_unix','batch_policy_sha256']:
            assert bundle['snapshots'][arm][key]==old[key], 'CANCEL_CURRENT_GENERATION_CONFIGURATION_MISMATCH:'+key
        assert tx.policy_sha256(obj.policy)==tx.policy_sha256(old['policy'])
        assert obj.policy['counters']['parameter_updates']==old['policy']['counters']['parameter_updates']
        assert obj.seen_attempt_ids==set(old['seen_attempt_ids'])|{p['attempt_id'] for p in obj.pending}
    hard=[p['attempt_id'] for obj in models.values() for p in obj.pending if isinstance(p.get('physical_result'),dict) and p['physical_result'].get('true_hard_safety_violation') is True]
    # Original saved failure RESULT/DATA must be reviewed by main separately
    # when a receipt is absent. The signed envelope records that review.
    assert envelope.get('all_actual_failure_artifacts_reviewed_for_hard_safety') is True,'MAIN_REVIEW_OF_MISSING_RECEIPTS_REQUIRED'
    if hard or envelope.get('confirmed_hard_safety_attempts'):
        tx.write_new(run/('CANCEL_REFUSED_HARD_'+str(time.time_ns())+'.json'),{'status':'HARD_SAFETY_STOP_NO_UPDATE','attempts':hard+envelope.get('confirmed_hard_safety_attempts',[]),'forward':0,'parameter_updates':0});raise ValueError('HARD_SAFETY_STOP_MAIN_AGENT_REVIEW')
    proof=verify_original_proposals_and_receipts(P,configs,models,prior_snapshots=prior_snapshots,allow_missing_receipts=True)
    transaction_id='CANCEL_'+str(time.time_ns());results={}
    for arm,obj in models.items():results[arm]=obj.cancel_pending_batch(group_transaction_id=transaction_id,reason=reason)
    return tx.publish_generation(run,current['generation_index']+1,{a:o.snapshot() for a,o in models.items()},{'status':'PARTIAL_BATCH_ALL_FOUR_CANCELLED_ZERO_FORWARD_ZERO_UPDATE','transaction_id':transaction_id,'reason':reason,'previous_transaction_sha256':current['transaction_sha256'],'envelope_path':str(envelope_path.relative_to(P)),'envelope_sha256':tx.sha(envelope_path),'original_pending_sha256':tx.sha(source),'closed_owners_and_all_spent_attempts':closed,'original_proposal_receipt_joins':proof,'results':results,'sampling_rng_and_seen_ids_not_rewound':True,'all_physical_costs_preserved':True,'forward_in_cancellation':0,'parameter_updates_in_cancellation':0})
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--envelope',required=True);p.add_argument('--reason',required=True);a=p.parse_args()
    lock=(P/'owned/ONPOLICY_TRANSACTION.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert time.time()<tx.load(P/'ACTIVATION.json')['hard_stop_unix']
    assert (P/a.run).resolve().is_relative_to(tx.F.resolve())
    print(json.dumps(cancel(P/a.run,P/a.envelope,a.reason),sort_keys=True))
if __name__=='__main__':main()
