"""Offline evidence check for the preserved P06 aborted-arm reporting boundary."""
import argparse
import hashlib
import json
from pathlib import Path
import time
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(root,name):return json.loads((root/name).read_text())
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True);args=parser.parse_args();root=args.package
    admission=next(r for r in read(root,'PATIENT_ADMISSIBILITY_RESULTS.json')['rows'] if r['patient_id']=='P06')
    pair=next(r for r in read(root,'CROSS_PATIENT_EXPERIMENT_RESULTS.json')['rows'] if r['patient_id']=='P06')
    learning=next(r for r in read(root,'LEARNING_DATA_MANIFEST.json')['runs'] if r['run_id']=='P06_H150')
    report=next(r for r in read(root,'derived/REPORT_STATISTICS.json')['rows'] if r['patient_id']=='P06')
    source=read(root,'reports/P06_H150_CROSS_EVALUATION.json');partial=read(root,'audit/P06_H150_PARTIAL_NATIVE_OWNERSHIP.json')
    h=pair['H150'];scope=h['evidence_interpretation'];raw=h['raw_runtime_execution_evidence'];fallback=raw['raw_runtime_fallback_event_type_counts']
    expected_hash=next(v for k,v in partial['source_hashes'].items() if k.endswith('/reports/P06_H150_CROSS_EVALUATION.json'))
    checks={
        'all_children_joined':read(root,'P06_DONE.json')['all_children_joined'] is True,
        'static_valid_not_model_invalid':admission['model_static_valid'] is True and admission['status']=='OWN_COLD_COMMISSIONING_AND_TASK_FORK_REACHED',
        'full_force_and_moment_integrals_null':h['J_F_N_s'] is None and h['moment_integral_Nm_s'] is None,
        'gain_null_no_full_comparison':pair['gain_percent'] is None and pair['gain_N_s'] is None and pair['full_integral_comparison_valid'] is False,
        'valid_B_incomplete_H_motion_not_evaluable':pair['qualified_B_reference'] is True and h['complete_task'] is False and pair['motion_relative']=='NOT_EVALUABLE',
        'safety_is_observed_prefix_only':h['axes']['absolute_safety']=='PASS' and scope['absolute_safety_display']=='PASS_OBSERVED_PREFIX_ONLY',
        'prefix_preserved':abs(scope['observed_task_duration_s']-17.545)<1e-6 and scope['observed_prefix_force_integral_N_s']>0,
        'original_native_ownership_unknown_not_corrupt':scope['native_receipt_ownership_source_check'] is None,
        'original_scientific_request_failure_preserved':scope['causal_execution_source_checks']['scientific_request_version_age_valid'] is False and scope['original_scientific_validity_status']=='FAIL',
        'incomplete_intervention_separate':scope['incomplete_task_missing_interventions'] is True,
        'independent_partial_receipt_ownership_pass':raw['partial_native_ownership_audit_raw_hash_matches'] is True and raw['independent_partial_native_ownership']['status']=='PARTIAL_RAW_OWNERSHIP_PASS',
        'fallback_commit_stop_hold_preserved':all(fallback.get(k)==1 for k in ['FALLBACK_COMMITTED','FALLBACK_STOPPED','FALLBACK_HOLD']),
        'TRACK_does_not_exclude_fallback':raw['TRACK_receipt_mode_excludes_fallback_execution'] is False and raw['explicit_fallback_commit_event_observed'] is True,
        'learning_prefix_not_missing_or_full':learning['causal_record_coverage']=='OBSERVED_PREFIX_DECISIONS' and learning['causal_records_partial'] is True and learning['causal_decision_rows']>0,
        'report_full_integral_and_gain_null':report['H150']['J_F_N_s'] is None and report['gain_percent'] is None,
        'report_prefix_scope':report['H150']['absolute_safety_scope']=='OBSERVED_PREFIX_ONLY',
        'frozen_evaluation_unchanged':sha(root/'reports/P06_H150_CROSS_EVALUATION.json')==expected_hash,
    }
    result=dict(status='PASS' if all(checks.values()) else 'FAIL',patient_id='P06',arm='H150',checks=checks,
        original_abort_reason=source['abort_reason'],original_scientific_reasons=scope['original_scientific_validity_reasons'],fallback_events=fallback,
        original_frozen_evaluation_sha256=expected_hash,full_task_integral_and_gain=None,observed_prefix_duration_s=scope['observed_task_duration_s'],
        interpretation='Report handling only: preserves the aborted scientific failure and verified partial evidence without any full-task or model-invalid promotion.',
        new_physics_starts=0,training_performed=False,unix=time.time())
    path=root/'audit/P06_REPORT_HANDLING_AUDIT.json';path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':result['status'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v],'physics_starts':0}))
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
