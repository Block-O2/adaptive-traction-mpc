"""Offline final cross-file assertions; never imports or starts physics."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package', type=Path, required=True)
p = parser.parse_args().package
checks = {}
bound = {}

def read(name):
    blob = (p / name).read_bytes()
    bound[name] = hashlib.sha256(blob).hexdigest()
    return json.loads(blob)

s = read('derived/REPORT_STATISTICS.json')
q = read('CROSS_PATIENT_QUALIFICATION.json')
m = read('LEARNING_DATA_MANIFEST.json')
e = read('CROSS_PATIENT_EXPERIMENT_RESULTS.json')
a = read('ATTEMPT_ACCOUNTING.json')
rows = {r['patient_id']: r for r in s['rows']}
qual = {r['patient_id']: r for r in q['rows']}
runs = {r['run_id']: r for r in m['runs']}
checks['all_12_registered_rows_retained'] = len(rows) == len(qual) == 12
checks['ten_valid_full_pairs'] = s['comparisons']['all_valid_pairs']['gain_denominator'] == 10
checks['eight_final_qualified_pairs'] = s['comparisons']['final_complete_qualified_pairs']['gain_denominator'] == 8
checks['new_only_denominators'] = s['comparisons']['new_patients_valid_pairs']['gain_denominator'] == 9 and s['comparisons']['new_patients_final_complete_qualified_pairs']['gain_denominator'] == 7
checks['qualified_identity_sets_equal'] = set(s['comparisons']['final_complete_qualified_pairs']['patient_ids']) == {pid for pid, r in qual.items() if r['independently_verified_qualified_pair'] is True}
checks['launcher_gate_pass'] = s['launcher_gate']['status'] == 'PASS'
checks['no_read_errors'] = not any(d.get('read_errors') for d in [s, q, m, e])
for pid in ['P05', 'P08']:
    r = rows[pid]
    checks[pid + '_motion_failure_not_promoted'] = r['full_integral_comparison_valid'] is True and r['final_complete_qualified_pair'] is False and qual[pid]['motion_relative'] == 'FAIL'
for pid in ['P06', 'P10']:
    r = rows[pid]
    h = r['H150']
    evidence = h['partial_raw_runtime_execution_evidence']
    checks[pid + '_full_metrics_null'] = r['full_integral_comparison_valid'] is False and r['gain_percent'] is None and h['J_F_N_s'] is None and h['moment_integral_Nm_s'] is None
    checks[pid + '_safety_prefix_motion_unevaluable'] = h['evidence_interpretation']['absolute_safety_display'] == 'PASS_OBSERVED_PREFIX_ONLY' and qual[pid]['motion_relative'] == 'NOT_EVALUABLE'
    checks[pid + '_ownership_not_promoted'] = evidence['independent_partial_native_ownership']['status'] == 'PARTIAL_RAW_OWNERSHIP_PASS' and evidence['independent_partial_native_ownership']['scientific_promotion'] is False and r['final_complete_qualified_pair'] is False
    checks[pid + '_fallback_commit_and_TRACK_separated'] = evidence['explicit_fallback_commit_event_observed'] is True and evidence['TRACK_receipt_mode_excludes_fallback_execution'] is False
    checks[pid + '_learning_prefix_only'] = runs[pid + '_H150']['causal_record_coverage'] == 'OBSERVED_PREFIX_DECISIONS'
checks['all_36_learning_runs_closed'] = len(runs) == 36 and all(r['start_end_closed'] for r in runs.values())
checks['no_false_dataset_completeness'] = m['complete_dataset_claimed'] is False and m['no_learning_success_claim'] is True
for key in ['schema_artifact', 'interval_telemetry_availability_audit']:
    item = m[key]
    blob = (p / item['package_relative_path']).read_bytes()
    checks[key + '_hash_match'] = item['exists'] is True and item['sha256'] == hashlib.sha256(blob).hexdigest()
checks['telemetry_all_run_selectors'] = all(r['interval_telemetry_audit_row']['row_id'] == ident for ident, r in runs.items())
checks['accounting_pass_closed_36'] = a['status'] == 'PASS' and a['START_count'] == a['END_count'] == 36 and a['all_physics_serial'] is True
result = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
          'source_sha256': bound, 'generated_utc': datetime.now(timezone.utc).isoformat(),
          'physics_starts': 0, 'frozen_evaluations_modified': False}
(p / 'audit/FINAL_AGGREGATE_VERIFICATION.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'checks': len(checks), 'failed': [k for k, v in checks.items() if not v]}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
