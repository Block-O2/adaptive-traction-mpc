"""Separate physical equivalence from strict schedule-label identity."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
f = P / 'analysis/LSTF01_CLOSURE_AND_ALIAS_DIAGNOSTIC_V1.json'
d = json.loads(f.read_text())
for rel, expected in d['input_sha256'].items():
    assert hashlib.sha256((P / rel).read_bytes()).hexdigest() == expected
e = d['F100_vs_previous_NO_T5_original_compare_raw']
assert e['status'] == 'FAIL' and e['errors'] == ['TRACE:selected_schedule_label']
physical = ['time_s', 'stage', 'evaluation_only_human_state_rad_rad_s', 'cr12_actuator_command_nm']
reference = ['time_s', 'reference_q_rad', 'reference_dq_rad_s']
assert all(e['trace_fields'][k] for k in physical + reference)
assert all(v for k, v in e['trace_fields'].items() if k != 'selected_schedule_label')
out = {
    'status': 'COMPLETE_PHYSICAL_ALIAS_STRICT_LABEL_DIFFERENCE_RETAINED',
    'created_unix': time.time(), 'supersedes_only': 'V1.F100_new_effective_physical_exploration',
    'reason_for_revision': 'Strict raw identity includes selected_schedule_label; its failure alone is insufficient to infer a different physical action.',
    'original_compare_raw_status_unchanged': 'FAIL',
    'strict_difference_only': 'TRACE:selected_schedule_label',
    'all_other_trace_fields_exact': True,
    'native_states_and_scientific_command_receipts_exact': True,
    'actual_physical_trace_exact': True, 'actual_reference_trace_exact': True,
    'F100_new_effective_physical_exploration': False,
    'physical_attempt_fully_charged': True, 'new_independent_state': False,
    'original_unqualified_result_unchanged': True, 'new_env_model_train_physics': 0,
    'V1_path': str(f.relative_to(P)), 'V1_sha256': hashlib.sha256(f.read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
dest = P / 'analysis/LSTF01_ALIAS_CLASSIFICATION_V2.json'
with dest.open('x') as stream:
    stream.write(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
with (P / 'RESEARCH_DECISIONS.jsonl').open('a') as stream:
    stream.write(json.dumps({'event': 'CORRECT_DERIVED_ALIAS_CLASSIFICATION', 'unix': time.time(),
                             'id': 'LSTF01_F100_VS_OLD_NO_T5', 'details': str(dest.relative_to(P)),
                             'strict_schedule_label_diff_not_new_physical_action': True,
                             'V1_preserved_not_overwritten': True, 'all_original_failures_and_costs_retained': True}) + '\n')
print('F100_PHYSICAL_REFERENCE_NATIVE_RECEIPT_ALIAS; STRICT_SELECTED_SCHEDULE_LABEL_DIFF')
