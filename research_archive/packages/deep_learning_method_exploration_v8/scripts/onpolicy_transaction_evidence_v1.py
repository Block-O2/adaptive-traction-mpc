"""Zero-forward original-file joins for main-owned on-policy transactions."""
from pathlib import Path
import copy,hashlib,json
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def verify_original_proposals_and_receipts(package,configs,models,*,prior_snapshots,allow_missing_receipts=False):
    P=Path(package);events={};ids=set();proof=[]
    for raw in (P/'runtime/ATTEMPTS.jsonl').read_bytes().splitlines():
        event=json.loads(raw)
        if event.get('event') in ['START','END']:
            key=(event['id'],event['event'])
            assert key not in events,'DUPLICATE_ACTUAL_EVENT'
            events[key]=(event,hashlib.sha256(raw).hexdigest())
    for arm,obj in models.items():
        previous_rng=prior_snapshots[arm]['rng']
        for proposal in obj.pending:
            ident=proposal['attempt_id'];assert ident not in ids,'CROSS_ARM_ATTEMPT_REUSE';ids.add(ident)
            matches=[config for config in configs if ident.startswith(config['group']+'_OP_'+arm+'_')]
            assert len(matches)==1,'PROPOSAL_NOT_ROUTED_TO_EXACT_ARM_JOB'
            config=matches[0];spec=config['onpolicy_sampling'];tag=ident.removeprefix(config['group']+'_')
            assert proposal['context_group_evaluation_only']==spec['development_context_id']
            assert digest(proposal['rng_before'])==digest(previous_rng),'SAMPLING_RNG_CHAIN_BROKEN'
            previous_rng=proposal['rng_after']
            baseline=P/spec['output_directory']/'B_BASELINE_RECEIPT.json'
            assert proposal['baseline_evaluation_only']==load(baseline),'PROPOSAL_BASELINE_NOT_ORIGINAL_SAVED_B_RECEIPT'
            original=copy.deepcopy(proposal);receipt=original['physical_result'];original['physical_result']=None
            source=P/spec['output_directory']/(tag+'_PROPOSAL.json')
            assert load(source)==original,'PENDING_PROPOSAL_NOT_ORIGINAL_PRESAMPLED_FILE'
            identity=original.pop('proposal_identity_sha256');assert digest(original)==identity
            if receipt is None:
                assert allow_missing_receipts,'MISSING_CURRENT_PHYSICAL_RECEIPT'
                proof.append({'id':ident,'proposal_sha256':sha(source),'receipt_status':'MISSING_CENSORED_PRESERVED','actual_start_present':(ident,'START') in events,'actual_end_present':(ident,'END') in events});continue
            receipt_path=P/spec['output_directory']/(tag+'_PHYSICAL_RECEIPT.json');saved=load(receipt_path)
            required=('attempt_start_sha256','attempt_end_sha256','result_source_sha256','native_ownership_sha256','applied_reference_receipt_stream_sha256')
            errors=['MISSING_PHYSICAL_IDENTITY:'+key for key in required if not saved.get(key)]
            if not isinstance(saved.get('actual_new_native_steps'),int) or saved['actual_new_native_steps']<=0:errors.append('NO_ACTUAL_NEW_NATIVE_STEPS')
            assert receipt=={**saved,'driver_receipt_errors':errors},'ATTACHED_RECEIPT_NOT_ORIGINAL_SAVED_FILE'
            for kind,field in [('START','attempt_start_sha256'),('END','attempt_end_sha256')]:
                event,raw_sha=events[(ident,kind)]
                assert digest(event)==saved[field]
                assert saved['events_original_records_and_hash_scopes'][kind]=={'record':event,'raw_line_without_newline_sha256':raw_sha,'canonical_record_sha256':digest(event)}
                if kind=='START':assert event['config_sha256']==sha(P/'experiments'/(config['group']+'.json'))
            result=P/'attempts'/(ident+'_RESULT.json');assert sha(result)==saved['result_source_sha256']
            owner=saved['ownership_source'].get('path')
            if owner is not None:assert sha(P/owner)==saved['native_ownership_sha256']
            scope=saved['applied_stream_scope']
            if scope['container_sha256'] is not None:assert sha(P/scope['path'])==scope['container_sha256']
            prediction=load(P/'predictions'/(ident+'.json'))
            assert prediction['proposal_file_sha256']==sha(source) and prediction['proposal_identity_sha256']==identity
            assert prediction['created_unix']<=events[(ident,'START')][0]['unix']
            proof.append({'id':ident,'proposal_sha256':sha(source),'physical_receipt_sha256':sha(receipt_path),'original_result_sha256':sha(result),'actual_start_and_end_verified':True})
        assert digest(obj.rng.getstate())==digest(previous_rng),'FINAL_SAMPLING_RNG_NOT_PENDING_CHAIN_ENDPOINT'
    return proof
