"""Final accounting presentation: original records + explicit reconciliation."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import time

P = Path(__file__).resolve().parents[1]
f = P / 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json'
backup = P / 'audit/RESOURCE_ACCOUNTING_PRE_FINAL_V6.json'
if not backup.exists():
    backup.write_bytes(f.read_bytes())
runpy.run_path(str(P / 'source/v7_accounting_v6.py'), run_name='__main__')
d = json.loads(f.read_text())


def ref(relative):
    q = P / relative
    return {'path': relative, 'sha256': hashlib.sha256(q.read_bytes()).hexdigest()}


classification = json.loads((P / 'analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V1.json').read_text())
d['candidate_physical_and_worker_status_reconciliation'] = {
    **ref('analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V1.json'),
    'counts': classification['candidate_classifications'],
    'original_worker_fields_preserved_not_reinterpreted_as_motion_failure': True,
    'physical_complete_engineering_unknown_qualification_ids': ['DEVRC01_B', 'HOLDSS01_B'],
    'HOLDSS01_B_authoritative_START_group': 'HOLDSS02',
    'candidate_START': 144, 'cold_parent_START': 26,
    'physical_aborted_candidates': 13, 'engineering_prefix_partial_parents': 4,
    'complete_raw_with_engineering_failure_never_success_ranked': True,
}
d['canonical_final_evidence'] = {
    **ref('analysis/evidence_final_v4/ALL_CANDIDATE_EVIDENCE.json'),
    'unique_candidate_rows': 144,
    'v3_151_rows_144_IDs_seven_duplicate_descriptor_rows_preserved': True,
    'descriptor_inventory': ref('analysis/evidence_final_v4/CONFIG_ALIAS_INVENTORY.json'),
    'no_negative_or_partial_attempt_removed': True,
}
d['LS_terminal_factor_effective_action_alias'] = {
    **ref('analysis/LSTF01_ALIAS_CLASSIFICATION_V2.json'),
    'factor1_vs_old_NO_T5_actual_reference_physics_native_receipts_exact': True,
    'strict_schedule_label_difference_preserved': True,
    'new_effective_physical_exploration_from_factor1': False,
    'actual_attempt_fully_charged': True,
}
d['owned_final_recorded_scope'] = ref('audit/OWNED_FINAL_V1.json')
d['review_original_metadata_gaps_and_current_adapters'] = ref('audit/review_closure_adapters_v1/ADAPTER_INDEX.json')
d['final_scientific_claim_review'] = ref('agent_reviews/final_scientific_claim_scope/END.json')
d['accepted_claim_wording_edits'] = ref('audit/MAIN_ACCEPTED_FINAL_SCIENTIFIC_WORDING_EDITS.json')
d['CPU_accounting']['training_cost_scope_clarification'] = (
    'GP/quad approximately .131 CPU seconds is the combined fitting/proposal process, including kernel/LS solves and head queries; '
    'stump approximately .335 CPU seconds includes data extraction and fitting. Neither includes physical label collection. '
    'Unknown aggregate host core-seconds remain null, not zero.'
)
d['metadata_limitations']['original_missing_review_ENDs'] = ['history', 'local_surrogate']
d['metadata_limitations']['original_nonstandard_review_output_manifests'] = ['causal_human_interface', 'interface', 'terminal_rule']
d['metadata_limitations']['current_main_receipts_are_not_reconstructed_historical_ENDs'] = True
d['metadata_limitations']['foreground_static_or_metadata_preflight_PID_persistence_gaps'].append('agent_reviews/final_metadata_inventory/PREPARATION_AUDIT.json')
d['science_ended_unix'] = max(j['ended_unix'] for j in d['physical_supervisor_jobs'])
d['scientific_phase_elapsed_seconds'] = d['science_ended_unix'] - d['T0_unix']
d['actual_attempts_saved'] = 0
d['actual_general_patient_or_hardware_results'] = 0
d['schema'] = 'ihear.resource_attempt_accounting.v7'
d['accounting_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
d['updated_unix'] = time.time()
if '--final' in sys.argv:
    assert d['physical_START'] == d['physical_END'] == 170 and d['actual_new_native_steps'] == 12997720
    assert not d['active_attempt_ids']
    d['state'] = 'RESEARCH_PHYSICS_CLOSED_FINAL_ACCOUNTING_WITH_DOCUMENTED_METADATA_LIMITATIONS'
t = f.with_suffix('.tmp')
t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
t.replace(f)
print('ACCOUNTING_V7', d['physical_START'], d['physical_END'], d['actual_new_native_steps'], classification['candidate_classifications'])
