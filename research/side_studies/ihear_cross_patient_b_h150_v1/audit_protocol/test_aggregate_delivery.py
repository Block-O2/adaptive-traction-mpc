"""Synthetic offline boundary checks; no physics, controller import or real outcomes."""
import importlib.util
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline_aggregate', ROOT / 'aggregate_delivery.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def put(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def arm(pid, name, qualified=True):
    return {'id': pid + '_' + name, 'arm': name, 'complete_task': True,
            'integration': 'PASS', 'absolute_task_execution_qualified': True,
            'qualification': 'COMPLETE_QUALIFIED_PASS' if qualified else 'MOTION_RELATIVE_FAIL',
            'labels': [] if qualified else ['MOTION_RELATIVE_FAIL'],
            'axes': {'task': 'PASS', 'absolute_safety': 'PASS', 'causal_execution': 'PASS'},
            'J_F_N_s': 100.0 if name == 'B' else 98.0, 'observed_prefix': {'task_samples': 3}}


with tempfile.TemporaryDirectory(prefix='ihear_offline_aggregate_synthetic_') as folder:
    root = Path(folder)
    patients = [{'patient_id': f'P{i:02d}', 'label': 'SYNTHETIC_TEST_ONLY',
                 'future_learning_split': 'DEVELOPMENT', 'case_path': f'patients/P{i:02d}/case.json',
                 'case_sha256': 'synthetic_not_real'} for i in range(5)]
    put(root, 'VIRTUAL_PATIENT_COHORT.json', {'patients': patients})
    put(root, 'EXECUTION_CODE_MANIFEST.json', {'files': {}})
    put(root, 'STATIC_PATIENT_AUDIT.json', {'records': [
        {'patient_id': p['patient_id'], 'model_static_valid': i != 2,
         'xml_sha256': 'synthetic_not_real'} for i, p in enumerate(patients)]})
    events = []
    for ident, pid in [('P00_parent', 'P00'), ('P00_B', 'P00'), ('P00_H150', 'P00'),
                       ('P01_parent', 'P01'), ('P04_B', 'P04'), ('P04_H150', 'P04'),
                       ('P04_repeat_H150', 'P04')]:
        events.extend([{'event': 'START', 'id': ident, 'patient_id': pid},
                       {'event': 'END', 'id': ident}])
    (root / 'ATTEMPTS.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in events))
    for pid, qualified in [('P00', False), ('P04', True)]:
        b = arm(pid, 'B'); h = arm(pid, 'H150', qualified)
        h['motion_comparison'] = {'acceptance_pass': qualified, 'failed_requirements': [] if qualified else ['excursion']}
        put(root, f'{pid}_COMPARISON.json', {'patient_id': pid, 'B': b, 'H150': h,
            'full_integral_comparison_valid': True, 'complete_qualified_H150': qualified,
            'gain_percent': 2.0, 'gain_fraction': .02, 'gain_N_s': 2.0,
            'motion_relative': 'PASS' if qualified else 'FAIL', 'qualified_B_reference': True,
            'pair_identity_valid': True})
        put(root, f'{pid}_PAIR_GATE.json', {'status': 'PASS'})
        put(root, f'audit/{pid}_FORK_CONTEXT.json', {'cold_commissioning_reached': True})
        put(root, f'{pid}_DONE.json', {'cold_commissioning_reached': True})
    for name in ['B', 'H150']:
        put(root, f'derived/P00_{name}_INDEPENDENT.json', {'status': 'PASS', 'native_rows': 20})
    put(root, 'P01_DONE.json', {'status': 'FAILED_PRESERVED', 'cold_commissioning_reached': False,
                             'error': 'SYNTHETIC_OBSERVER_MAPPING_REJECTED'})
    put(root, 'reports/P01_parent_ERROR.json', {'error': 'SYNTHETIC_OBSERVER_MAPPING_REJECTED'})
    npz = root / 'source/results/P00_B/trace.npz'
    npz.parent.mkdir(parents=True)
    header = repr({'descr': '<f8', 'fortran_order': False, 'shape': (3,)}) + '\n'
    payload = b'\x93NUMPY' + bytes([1, 0]) + struct.pack('<H', len(header)) + header.encode() + bytes(24)
    with zipfile.ZipFile(npz, 'w') as archive:
        archive.writestr('time_s.npy', payload)
    raw_path = root / 'source/results/P00_H150/runtime_artifacts.json.gz'
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b'SYNTHETIC_HASH_ONLY_NOT_A_RUNTIME_ARCHIVE')
    put(root, 'source/results/P00_H150/summary.json', {'runtime': {'safe_fallback_events': [{'event': 'ESCAPE_ADMITTED'}]}})
    put(root, 'audit/P00_H150_LEARNING_EXECUTION_EVIDENCE.json', {
        'source_hashes': {str(raw_path): hashlib.sha256(raw_path.read_bytes()).hexdigest()},
        'runtime_arrays': {
            'safe_fallback_events': {'present': True, 'count': 2, 'categories': {'event': {'ESCAPE_ADMITTED': 1, 'FALLBACK_COMMITTED': 1}}},
            'command_receipts': {'present': True, 'count': 4, 'categories': {'mode': {'TRACK': 2, 'STOP': 2}},
                                 'applied_mode_counts': {'TRACK': 2}, 'unapplied_mode_counts': {'STOP': 2},
                                 'applied_native_steps_by_mode': {'TRACK': 40}}}})
    outputs = module.build(root)
    results = outputs['CROSS_PATIENT_EXPERIMENT_RESULTS.json']
    denom = results['denominators']
    assert denom['registered_patients'] == 5
    assert denom['model_static_valid_patients'] == 4
    assert denom['model_static_rejected_patients'] == 1
    assert denom['patients_pre_fork_execution_failure'] == 1
    assert denom['full_integral_comparable_pairs'] == 2
    assert denom['reported_complete_qualified_H150_patients'] == 1
    assert denom['independently_verified_complete_qualified_pairs'] == 0
    assert denom['H150_motion_relative_fail_patients'] == 1
    assert denom['H150_kinematic_motion_fail_patients'] == 1
    safety_only = module.separate_motion_contract(
        {'full_integral_comparison_valid': True, 'pair_identity_valid': True, 'qualified_B_reference': True},
        {'motion_comparison': {'acceptance_pass': False, 'failed_requirements': ['physical_task', 'causal_ownership']}})
    assert safety_only['source_composite_acceptance'] is False
    assert safety_only['relative_contract_status'] == 'PASS'
    assert safety_only['kinematic_motion_failures'] == []
    assert len(safety_only['task_execution_failures']) == 2
    partial_scope = module.interpret_arm_evidence({'complete_task': False,
        'axes': {'absolute_safety': 'PASS', 'causal_execution': 'FAIL',
                 'causal_execution_checks': {'native_receipt_ownership': None, 'scientific_request_version_age_valid': False},
                 'original_evaluator': {'scientific_validity': {'status': 'FAIL', 'reasons': ['request_19:request_not_activated']}}},
        'observed_prefix': {'observed_task_duration_s': 17.545, 'observed_task_J_F_N_s': 1583.},
        'interventions': {'status': 'FAIL', 'incomplete_task_missing_interventions': True}})
    assert partial_scope['absolute_safety_display'] == 'PASS_OBSERVED_PREFIX_ONLY'
    assert partial_scope['native_receipt_ownership_source_check'] is None
    assert partial_scope['original_scientific_validity_reasons'] == ['request_19:request_not_activated']
    assert partial_scope['patient_model_invalid_inferred_from_task_abort'] is False
    raw_execution = results['rows'][0]['H150']['raw_runtime_execution_evidence']
    assert raw_execution['raw_archive_hash_matches_audit'] is True
    assert raw_execution['raw_runtime_fallback_event_type_counts'] == {'ESCAPE_ADMITTED': 1, 'FALLBACK_COMMITTED': 1}
    assert raw_execution['explicit_fallback_commit_event_observed'] is True
    assert raw_execution['TRACK_receipt_mode_excludes_fallback_execution'] is False
    assert raw_execution['applied_receipt_mode_counts'] == {'TRACK': 2}
    assert raw_execution['unapplied_receipt_mode_counts'] == {'STOP': 2}
    assert raw_execution['compact_fallbacks_is_authoritative'] is False
    admission = outputs['PATIENT_ADMISSIBILITY_RESULTS.json']['rows']
    assert admission[1]['status'] == 'P0_PRE_FORK_EXECUTION_FAILURE'
    assert admission[1]['raw_error'] == 'SYNTHETIC_OBSERVER_MAPPING_REJECTED'
    assert results['rows'][1]['H150']['qualification'] == 'NOT_RUN_PARENT_PRE_FORK_FAILURE'
    assert results['rows'][2]['gain_percent'] is None
    assert admission[3]['status'] == 'STATIC_ADMISSIBLE_PENDING_PHYSICAL_COMMISSIONING'
    manifest = outputs['LEARNING_DATA_MANIFEST.json']
    assert len(manifest['runs']) == 16 and manifest['supplementary_attempt_count'] == 1
    indexed = {r['run_id']: r for r in manifest['runs']}
    assert indexed['P00_B']['trace_rows'] == 3
    assert indexed['P00_B']['artifacts']['trace']['sha256']
    assert indexed['P04_repeat_H150']['counts_as_new_patient'] is False
    assert results['gain_statistics_percent']['all_valid_full_integral_pairs']['denominator'] == 2
    assert all(not obj['training_performed'] and obj['physics_started_by_aggregation'] == 0 for obj in outputs.values())
    for name, obj in outputs.items():
        module.write_json(root / 'outputs' / name, obj)
        json.loads((root / 'outputs' / name).read_text())
    report = {'status': 'PASS', 'scope': 'SYNTHETIC_TEST_ONLY_NOT_RESEARCH_RESULTS',
              'tests': ['static_vs_pre_fork_failure', 'missing_unrun_rows', 'motion_fail_retained',
                        'reported_vs_independent_qualification', 'supplementary_not_new_patient',
                        'npz_header_and_sha', 'json_serialization', 'gain_denominators',
                        'composite_task_causal_failures_separate_from_motion',
                        'certificate_events_separate_from_applied_receipt_modes',
                        'aborted_prefix_safety_and_causal_reason_scope',
                        'TRACK_mode_does_not_exclude_fallback_commit'],
              'physics_starts': 0, 'training': False}
    module.write_json(ROOT / 'audit_protocol/AGGREGATOR_SYNTHETIC_VALIDATION.json', report)
    print(json.dumps(report))
