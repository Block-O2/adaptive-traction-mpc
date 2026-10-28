"""Source-only V2 integration hook; no entrypoint, fit or physics at import.

Call ONLY from a separately reviewed V2 copy of the stage owner after existing
T3 children have ended/joined and BEFORE the final control(b). V1 remains intact.
This hook can only freeze a CPU decision; it never dispatches a physical task.
"""
from pathlib import Path
import signal,time
from c2b_component_selector_v2 import abstain,digest,fit_select
from c2b_evidence_bundle_v2 import EvidenceError,build_bundle,sha


def select_freeze_for_live_owner(owner,b,*,root,group,config,original_quiesce,
                                 original_compare_raw,emit_frozen,stop_check):
    """Future parent-approved API, one CPU <=120s including evidence extraction.

    emit_frozen(kind, JSON) is the authorized new V2 owner's existing writer;
    stop_check preserves its original hard deadline/resource/STOP guards.
    A proposal is not execution. Any subsequent actual fork needs separate
    physical approval, original START/END/cleanup and incremental accounting.
    """
    if config.get('c2b_component_bo_v2_fit_authorized') is not True:
        return abstain('V2_PARENT_FIT_AUTHORIZATION_MISSING',fits_executed=0)
    approval=config.get('c2b_component_bo_v2_fit_approval_id')
    if not approval:return abstain('V2_APPROVAL_ID_MISSING',fits_executed=0)
    if owner.stage!=3 or owner.child is not None or owner.count.get('OUTBOUND')!=0 or b['task_state'].phase.value!='OUTBOUND':
        return abstain('HOOK_NOT_AT_UNADVANCED_T3_OUT0_OWNER',fits_executed=0)
    source_keys=['families/history_conditioned/C2B_COMPONENT_BO_CONTRACT_V2.json',
        'families/history_conditioned/c2b_component_selector_v2.py',
        'families/history_conditioned/c2b_evidence_bundle_v2.py',
        'families/history_conditioned/continuous_bo_owner_hook_v2.py']
    source_hashes={}
    for key in source_keys:
        actual=sha(Path(root)/key)
        if config.get('frozen_artifacts',{}).get(key)!=actual:raise EvidenceError('V2_SOURCE_NOT_PROSPECTIVELY_FROZEN:'+key)
        source_hashes[key]=actual
    original_quiesce(b);stop_check()
    before=owner.manifest(b)
    state=dict(stage=3,phase='OUTBOUND',slot=0,full_snapshot_sha256=before['hash'],
        live_quiescent=True,native_advanced_since_snapshot=False)
    began=time.monotonic();cpu=time.process_time();previous=signal.getitimer(signal.ITIMER_REAL);receipts=[]
    # Do not reset the old owner's running timeout or the campaign clock.
    budget=min(120.,previous[0]) if previous[0]>0. else 120.
    signal.setitimer(signal.ITIMER_REAL,budget)
    def guard():
        stop_check()
        if time.monotonic()-began>=budget or time.process_time()-cpu>=120.:raise TimeoutError('V2_EXTRACTION_FIT_SELECT_BUDGET')
    def receipt(row):
        receipts.append(row);emit_frozen('C2B_V2_FIT_RECEIPT_'+str(row['index']).zfill(3),row)
    try:
        bundle=build_bundle(root,group,owner.stage_prefix,owner_state=state,compare_raw=original_compare_raw,
            expected_compare_source_sha256=sha(original_compare_raw.__code__.co_filename))
        guard()
        decision=fit_select(bundle,parent_fit_approval=dict(authorized=True,approval_id=approval,
            dataset_class='REAL_CURRENT_T3',contract_sha256=source_hashes[source_keys[0]]),wall_cap_s=min(120.,budget-(time.monotonic()-began)),on_fit_receipt=receipt)
        guard();original_quiesce(b);after=owner.manifest(b)
        if after['hash']!=before['hash']:raise EvidenceError('CPU_SELECTION_MUTATED_LIVE_PARENT')
        decision.update(source_sha256=source_hashes,owner_before_hash=before['hash'],owner_after_hash=after['hash'],
            input_sha256=digest(bundle),freeze_before_any_new_candidate_START=True,extraction_plus_fit_wall_s=time.monotonic()-began,
            extraction_plus_fit_cpu_s=time.process_time()-cpu,proposal_not_execution=True)
        emit_frozen('C2B_V2_OBSERVATION_BUNDLE',bundle)
        emit_frozen('C2B_V2_DECISION',decision)
        return decision
    except (EvidenceError,TimeoutError) as exc:
        if isinstance(exc,TimeoutError):
            stop_check()
            if previous[0]>0. and previous[0]<=120.:raise
        original_quiesce(b)
        if owner.manifest(b)['hash']!=before['hash']:raise EvidenceError('ABSTAIN_PATH_MUTATED_LIVE_PARENT') from exc
        result=abstain('EVIDENCE_OR_LOCAL_BUDGET_GATE:'+str(exc),fit_matrix_solves=len(receipts),fit_receipts=receipts,
            extraction_plus_fit_wall_s=time.monotonic()-began,extraction_plus_fit_cpu_s=time.process_time()-cpu,new_candidate_not_dispatched=True)
        emit_frozen('C2B_V2_ABSTAIN',result);return result
    finally:
        elapsed=time.monotonic()-began
        signal.setitimer(signal.ITIMER_REAL,max(1e-6,previous[0]-elapsed),previous[1]) if previous[0]>0. else signal.setitimer(signal.ITIMER_REAL,0.)
