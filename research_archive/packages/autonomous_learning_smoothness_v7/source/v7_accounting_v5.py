"""Extend v4 accounting with simple fits and prospective sidecar costs."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import time

P = Path(__file__).resolve().parents[1]
runpy.run_path(str(P / 'source/v7_accounting_v4.py'), run_name='__main__')
f = P / 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json'
d = json.loads(f.read_text())
stump = P / 'agent_reviews/causal_stumps_v1/ACCOUNTING.json'
if stump.exists():
    a = json.loads(stump.read_text())
    d['new_simple_causal_stump_training'] = {
        'registration_id': 'SIMPLE_CAUSAL_QUALIFICATION_STUMPS_V1',
        'accounting_path': str(stump.relative_to(P)),
        'accounting_sha256': hashlib.sha256(stump.read_bytes()).hexdigest(),
        'counts_and_cost': a,
        'training_Human_parameter_contexts': 3,
        'independent_validation_not_implied_by_training_error': True,
        'JM_not_in_label_and_must_be_reported_separately': True,
        'deadline_repair_is_metadata_only_not_a_refit': True,
        'new_deployed_selector': False,
        'label_collection_physical_cost_already_charged_in_attempts': True,
    }
watchers = []
for ef in sorted((P / 'predictions/CAUSAL_STUMPS_V1').glob('*/WATCH_END.json')):
    e = json.loads(ef.read_text())
    sf = ef.with_name('WATCH_START.json')
    s = json.loads(sf.read_text())
    pf = ef.with_name('PREDICTION.json')
    watchers.append({
        'group': e['group'], 'START_path': str(sf.relative_to(P)),
        'END_path': str(ef.relative_to(P)), 'process': e['process'],
        'started_unix': s['started_unix'], 'ended_unix': e['ended_unix'],
        'wall_s_including_wait': e['wall_s'], 'status': e['status'],
        'prediction_admissible': e['prediction_admissible'],
        'source_sha256': s['source_sha256'],
        'model_sha256': s['expected_model_sha256'],
        'provisional_prediction_exists': pf.exists(),
        'actual_new_neural_calls': e['neural_calls'],
        'actual_new_physical_START': e['physical_START'],
        'actual_new_stump_fits': e['training_fits'],
        'deployment': False, 'actual_attempts_saved': 0,
    })
d['prospective_prediction_only_sidecars'] = watchers
d['prospective_sidecar_CPU_seconds'] = None
d['prospective_sidecar_CPU_limitation'] = 'Waiting wall is recorded separately; no total CPU-efficiency advantage inferred. Both fixed factorial menus remain fully charged.'
d['nonfree_labels_and_validation'] = {
    'all_complete_menus_physically_executed': True,
    'actual_simulated_physical_attempts_saved': 0,
    'real_hardware_attempts_saved_claim': 'NOT_TESTED; no hardware attempts',
    'no_counterfactual_replay_claimed_as_actual_savings': True,
}
cases = {}
for j in d['physical_supervisor_jobs']:
    if not j['physical_START']:
        continue
    c = json.loads((P / 'experiments' / (j['group'] + '.json')).read_text())
    cp = c.get('case_path', 'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json')
    case_hash = c.get('case_sha256') or hashlib.sha256((P / cp).read_bytes()).hexdigest()
    cases.setdefault(case_hash, {'case_path': cp, 'groups': []})['groups'].append(j['group'])
d['simulated_Human_parameter_instances_by_case_sha256'] = cases
d['parameter_instances_are_not_clinical_patients'] = True
for r in d['attempts']:
    result = P / 'attempts' / (r['id'] + '_RESULT.json')
    if r['kind'] != 'LEGAL_COLD_PARENT' and r['complete_task'] and not result.exists():
        r['orchestration_completion_status'] = 'COMPLETE_RAW_WITHOUT_CANDIDATE_RESULT_NO_SUCCESS_RANK'
        r['rank_allowed'] = False
d['metadata_limitations'] = {
    'all_registered_numerical_physics_agent_workers_require_PID_start_ticks_and_END': True,
    'foreground_static_or_metadata_preflight_PID_persistence_gaps': [
        'agent_reviews/out0_context_scope/REPORT.md',
        'audit/HOLDSS02_LABEL_RECOVERY_REGISTRATION.json',
    ],
    'tool_exit_receipts_preserved_but_not_a_reconstructed_PID_identity': True,
    'complete_PID_metadata_compliance_claim': False,
}
d['schema'] = 'ihear.resource_attempt_accounting.v5'
d['updated_unix'] = time.time()
d['accounting_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
if '--final' in sys.argv:
    assert not d['active_attempt_ids'] and not d['duplicate_START_ids'] and not d['duplicate_END_ids']
    assert not d['native_steps_with_pending_compute_records']
    assert all(j['ended_unix'] is not None and not j['survivors_at_END'] for j in d['physical_supervisor_jobs'])
    d['state'] = 'RESEARCH_CLOSED_ACCOUNTING_COMPLETE_WITH_KNOWN_METADATA_GAPS'
t = f.with_suffix('.tmp')
t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
t.replace(f)
print('ACCOUNTING_V5', d['physical_START'], d['physical_END'], d['actual_new_native_steps'], 'stumpfits', d.get('new_simple_causal_stump_training', {}).get('counts_and_cost', {}).get('simple_stump_fit_calls'), flush=True)
