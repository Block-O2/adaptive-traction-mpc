"""Retained timing headroom and one new failed-prefix raw provenance."""
from extension_common import *
from collections import Counter

def main():
    guard(1800);begin=time.time()
    from accounting import rows as attempt_rows
    from physics_provenance_audit import audit_one
    from analyze_timing import header_requests
    from causal_timing_report import quantile
    original=json.loads((FIRST_DELIVERY/'evidence/reports/HOST_QUALIFICATION_SUMMARY.json').read_text())
    evidence=[]
    for run in original['rows']:
        for request in run['full_timelines']:
            capture=request.get('sensor_capture_ns',request.get('source_capture_ns'));native=request.get('request_ns');finish=request.get('compute_finish_ns');collected=request.get('result_collected_ns');validation=request.get('validation_start_ns');actual=request.get('activation_ns');effective=request.get('effective_activation_ns')
            terminal=request.get('disposition_ns') or actual
            if capture is None:continue
            parts={}
            for key,a,b in [('capture_to_request',capture,native),('request_to_compute_finish',native,finish),('compute_finish_to_main_collect',finish,collected),('main_collect_to_validation',collected,validation),('validation_to_actual_write',validation,actual)]:
                if a is not None and b is not None and b>=a:parts[key]=(b-a)/1e6
            stamps=[('request',native),('compute_finish',finish),('main_collect',collected),('validation_start',validation),('actual_write',max(actual,effective or actual) if actual is not None else None)]
            checkpoints={name:55-(stamp-capture)/1e6 for name,stamp in stamps if stamp is not None and (terminal is None or stamp<=terminal)}
            after_terminal={name:stamp for name,stamp in stamps if stamp is not None and terminal is not None and stamp>terminal}
            evidence.append(dict(id=run['id'],method=run['method'],stage=request['stage'],request_id=request['request_id'],outcome=request['outcome'],durations_ms=parts,strict55_remaining_ms=checkpoints,post_disposition_checkpoint_ns=after_terminal,terminal_age_ms=None if terminal is None else (terminal-capture)/1e6,earliest_recorded_budget_exhaustion=next((name for name in ('request','compute_finish','main_collect','validation_start','actual_write') if name in checkpoints and checkpoints[name]<=0),None)))
    groups={}
    for method in ('M0','M2'):
      for stage in sorted({r['stage'] for r in evidence if r['method']==method}):
        selected=[r for r in evidence if r['method']==method and r['stage']==stage]
        groups[method+'/'+stage]=dict(requests=len(selected),checkpoint_coverage={name:sum(name in r['strict55_remaining_ms'] for r in selected) for name in ('request','compute_finish','main_collect','validation_start','actual_write')},first_recorded_budget_exhaustion=dict(Counter(r['earliest_recorded_budget_exhaustion'] or 'NOT_EXHAUSTED_AT_RECORDED_CHECKPOINTS' for r in selected)),durations_ms={name:quantile([r['durations_ms'][name] for r in selected if name in r['durations_ms']]) for name in sorted({k for r in selected for k in r['durations_ms']})})
    assert len(evidence)==339 and sum(r['stage']=='TASK' for r in evidence)==75
    id='325_NOON_B_ACTIVATION_CAPTURE';result=json.loads((STUDY/'output'/(id+'_RESULT.json')).read_text());partial=STUDY/'output'/(id+'_PARTIAL_COMPUTE.json');metric=json.loads(partial.read_text()) if partial.exists() else result.get('metric',{})
    account=dict(actual_new_native_steps=metric.get('actual_new_native_physics_steps'))
    raw=audit_one(id,result,account,lambda:guard(900));assert raw['status']=='PASS',raw
    artifact=STUDY/'source/results'/id/'runtime_artifacts.json.gz';requests=header_requests(artifact)
    attempts=attempt_rows();starts=[r for r in attempts if r['event']=='START'];ends=[r for r in attempts if r['event']=='END'];assert len(starts)==len(ends)==160
    old_raw=json.loads((FIRST_DELIVERY/'evidence/reports/RAW_PHYSICS_PROVENANCE_AUDIT.json').read_text());old_compute=json.loads((FIRST_DELIVERY/'evidence/reports/AUDIT_COMPUTE_RECONCILIATION.json').read_text())
    total=old_compute['authoritative_total_actual_new_native_steps']+raw['native_step_count']
    capture=json.loads((EXT/'ACTIVATION_INPUT_MANIFEST.json').read_text());replay=json.loads((EXT/'ACTIVATION_REPLAY.json').read_text())
    new=dict(id=id,classification='PAID_INSTRUMENTATION_DIAGNOSTIC_NOT_QUALIFICATION',seed=result['inputs']['seed'],same_seed_reference='324_NATIVE_B_ROUTE_cold_4',causal_pairing_claim=False,worker_status=result['status'],error=result.get('error'),traceback=result.get('traceback'),result_sha256=sha(STUDY/'output'/(id+'_RESULT.json')),raw_provenance=raw,native_requests=requests,captures=len(capture['rows']),capture_elapsed_ms=quantile([r['capture_ms'] for r in capture['rows']]),actual_original_with_nested_capture_ms=quantile([r['original_with_nested_capture_ms'] for r in capture['rows']]),task_requests=sum(r['stage']=='TASK' for r in requests),full_valid=False,learning_execution=0,phase_coverage=dict(Counter(r['phase'] for r in capture['rows'])),captured_record_replay_mismatches=replay['captured_final_record_mismatches'],budget_after=0)
    register_imports('BACKLOG_AUDIT')
    old=EXT/'BACKLOG_AND_RAW_AUDIT.json'
    if old.exists():shutil.copy2(old,EXT/('BACKLOG_AND_RAW_AUDIT_HISTORY_'+sha(old)+'.json'))
    out=dict(status='RETAINED_HEADROOM_AND_160TH_RAW_RECONCILED',retained_host_attempts=original['attempts'],retained_all_request_rows=len(evidence),retained_task_request_rows=sum(r['stage']=='TASK' for r in evidence),retained_pre_task_request_rows=sum(r['stage']!='TASK' for r in evidence),rows=evidence,groups=groups,new_diagnostic=new,cumulative_attempts=160,ended_attempts=160,authoritative_total_native_steps=total,authoritative_total_physics_seconds=total*.00025,authoritative_total_with_inter_rep=True,base_raw_manifest_sha256=sha(FIRST_DELIVERY/'evidence/reports/RAW_PHYSICS_PROVENANCE_AUDIT.json'),base_compute_sha256=sha(FIRST_DELIVERY/'evidence/reports/AUDIT_COMPUTE_RECONCILIATION.json'),base_raw_status=old_raw['status'],new_raw_status=raw['status'],physics_attempts_added_by_audit=0,Q_updates=0,wall_seconds=time.time()-begin,interpretation='Stage-aware negative checkpoint headroom localizes where retained source-age budget was already consumed; missing checkpoints stay censored. No interval is subtracted to predict successful deployment. Original 73-run qualification denominator is frozen; the 160th diagnostic failure is separate. Original all-159 raw provenance plus this audited disjoint new epoch yield the extended authoritative total. Failed physical costs remain unranked.')
    save(EXT/'BACKLOG_AND_RAW_AUDIT.json',out)
    print(json.dumps(dict(status=out['status'],groups=groups,new_diagnostic={k:new[k] for k in ('worker_status','error','captures','task_requests','phase_coverage','capture_elapsed_ms','captured_record_replay_mismatches')},new_native_steps=raw['native_step_count'],total_native_steps=total)))

if __name__=='__main__':main()
