"""Final disjoint physics + actual fits/diagnostics + honest metadata limits."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import time

P = Path(__file__).resolve().parents[1]
runpy.run_path(str(P / 'source/v7_accounting_v5.py'), run_name='__main__')
f = P / 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json'
d = json.loads(f.read_text())


def record(relative):
    path = P / relative
    return {'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'record': json.loads(path.read_text())}


d['stump_final_identity_and_time_adjudication'] = record('analysis/CAUSAL_STUMPS_FINAL_IDENTITY_DIAGNOSTIC_V2.json')
d['stump_retrospective_development_gate'] = record('freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json')
d['stump_target_identifiability_diagnostic'] = record('analysis/STUMP_TARGET_IDENTIFIABILITY_DIAGNOSTIC_V2.json')
d['new_simple_causal_stump_training']['new_deployed_selector'] = False
d['conditional_validation'] = {
    'V1': 'NOT_RUN_CFL_PROSPECTIVE_METADATA_GATE_NOT_MET',
    'V2': 'NOT_RUN_ORIGINAL_BENEFIT_LABELS_BOTH_ZERO_DEVELOPMENT_GATE_NOT_MET',
    'groups': ['CVNHS01', 'CVHNM01'], 'actual_new_physical_START': 0,
    'case_payloads_prepared_but_not_installed': True,
    'actual_policy_actions_selected_or_executed': 0,
    'analytic_if_threshold_exactly_equivalent': True,
    'original_CFL_NOT_TESTED_not_repaired_or_backfilled': True,
}
d['stump_pure_prediction_rechecks_explicit_diagnostics_only'] = {
    'final_admissible_identity_join': d['stump_final_identity_and_time_adjudication']['record']['pure_stump_prediction_rechecks'],
    'retrospective_development_gate': 4,
    'registered_target_identifiability_diagnostic': d['stump_target_identifiability_diagnostic']['record']['pure_stump_prediction_rechecks'],
    'these_are_not_neural_forward_calls_or_additional_fits': True,
    'not_a_universal_sum_of_all_pure_code_invocations': True,
}
d['metadata_limitations']['foreground_static_or_metadata_preflight_PID_persistence_gaps'].extend([
    'audit/FOREGROUND_METADATA_BUILDER_ERROR_20261026T2205.json',
    'agent_reviews/causal_stump_scope_v2b/REPORT.md',
    'audit/CFACTORL01_METADATA_REJECTION_DIAGNOSIS.json',
])
d['metadata_limitations'].update(
    foreground_readonly_tool_processes_not_all_individually_persisted=True,
    zero_START_preimport_worker_manifest_absent='HOLDSS01; no reconstructed worker SOURCE_MANIFEST',
    zero_START_interpreter_and_loaded_module_runtime_identity='NOT_FULLY_PROVEN; original traceback/frozen prelaunch/owned chain retained',
    missing_original_per_review_END_records_must_be_explicit_in_final_inventory=True,
    strict_perfect_PID_metadata_PASS_allowed=False,
)
d['bounded_review_metadata_overrun'] = {
    'branch': 'causal_stumps_v1/deadline_repair_v2',
    'registered_s': 600, 'actual_s_approximately': 624.6,
    'overrun_s_approximately': 24.6,
    'scope': 'Metadata sealing after finite pure tests; no model refit, env, training or physics',
    'evidence': 'agent_reviews/causal_stumps_v1/deadline_repair_v2/REPORT.md',
    'treated_as_complete_budget_compliance': False,
}
paths = [
    'agent_reviews/integral_audit/INTEGRAL_LEDGER_RESULTS.json',
    'agent_reviews/integral_audit/incremental_closed_v2/INTEGRAL_LEDGER_RESULTS.json',
    'agent_reviews/integral_audit/incremental_final_lstf_v3/INTEGRAL_LEDGER_RESULTS.json',
]
audits = [record(p) for p in paths]
sets = [set(r['id'] for r in a['record']['rows']) for a in audits]
assert all(a['record']['status'].startswith('PASS') for a in audits)
assert all(not sets[i].intersection(sets[j]) for i in range(len(sets)) for j in range(i))
events = [json.loads(x) for x in (P / 'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
starts = {e['id'] for e in events if e['event'] == 'START'}
ends = {e['id'] for e in events if e['event'] == 'END'}
union = set().union(*sets)
assert union == starts == ends
independent_new_native = sum(a['record']['independent_actual_new_native_steps'] for a in audits)
assert independent_new_native == d['actual_new_native_steps']
d['independent_integral_audits'] = {
    'reports': [{'path': a['path'], 'sha256': a['sha256'], 'audited': a['record']['audited']} for a in audits],
    'disjoint_audited_ID_counts': [len(s) for s in sets],
    'all_unique_physical_START_END_exactly_covered': True,
    'covered_ID_count': len(union), 'independent_actual_new_native_steps': independent_new_native,
    'all_partials_unranked': all(a['record']['all_partials_unranked'] for a in audits),
    'no_inherited_native_rows_recharged': True,
}
d['schema'] = 'ihear.resource_attempt_accounting.v6'
d['updated_unix'] = time.time()
d['accounting_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
if '--final' in sys.argv:
    assert not d['active_attempt_ids']
    d['state'] = 'RESEARCH_CLOSED_ACCOUNTING_COMPLETE_WITH_KNOWN_METADATA_GAPS'
t = f.with_suffix('.tmp')
t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
t.replace(f)
print('ACCOUNTING_V6', d['physical_START'], d['physical_END'], independent_new_native, 'disjoint', [len(s) for s in sets])
