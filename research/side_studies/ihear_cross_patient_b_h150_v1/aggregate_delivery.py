"""Offline, failure-preserving aggregate delivery. Never imports or starts physics.

Run on the canonical package after (or during a clearly marked snapshot of)
serial execution. Only four aggregate JSON outputs are written. Original
evidence, frozen source, patient parameters and per-run reports are read-only.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import sys
import zipfile

sys.dont_write_bytecode = True


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False,
                                   allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


class Evidence:
    def __init__(self, package):
        self.package = Path(package).resolve()
        self.read_errors = []
        self.hash_cache = {}

    def read(self, relative, default=None):
        path = self.package / relative
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self.read_errors.append({'path': str(path), 'error': str(error)})
            return default

    def artifact(self, relative, role=None):
        path = self.package / relative
        relative = str(relative).replace('\\', '/')
        result = {'path': str(path), 'package_relative_path': relative,
                  'exists': path.is_file(), 'sha256': None, 'role': role}
        if not result['exists']:
            return result
        try:
            before = path.stat()
            key = (str(path), before.st_size, before.st_mtime_ns)
            if key not in self.hash_cache:
                h = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(4 * 2**20), b''):
                        h.update(block)
                after = path.stat()
                stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
                self.hash_cache[key] = (h.hexdigest() if stable else None, stable)
            digest, stable = self.hash_cache[key]
            result.update(size_bytes=before.st_size, sha256=digest,
                          stable_during_hash=stable)
        except OSError as error:
            result['read_error'] = str(error)
            self.read_errors.append({'path': str(path), 'error': str(error)})
        return result

    def events(self):
        path = self.package / 'ATTEMPTS.jsonl'
        if not path.exists():
            return []
        records = []
        with path.open(encoding='utf-8-sig') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as error:
                    self.read_errors.append({'path': str(path), 'line': line_number,
                                             'error': str(error)})
        return records

    def npz_inventory(self, relative):
        """Read .npy headers only; do not load large native/trajectory arrays."""
        path = self.package / relative
        if not path.exists():
            return None
        fields = {}
        try:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if not member.filename.endswith('.npy'):
                        continue
                    with archive.open(member) as stream:
                        if stream.read(6) != b'\x93NUMPY':
                            raise ValueError('Unexpected NPY magic')
                        major, minor = stream.read(2)
                        size = 2 if major == 1 else 4
                        header_size = struct.unpack('<H' if size == 2 else '<I', stream.read(size))[0]
                        if header_size > 2**20:
                            raise ValueError('Unexpectedly large NPY header')
                        raw = stream.read(header_size)
                        header = ast.literal_eval(raw.decode('utf-8' if major >= 3 else 'latin1').strip())
                        fields[member.filename[:-4]] = {
                            'shape': list(header['shape']), 'dtype': header['descr'],
                            'fortran_order': header['fortran_order'],
                            'npy_format': [major, minor],
                        }
            return {'status': 'HEADER_INVENTORY_ONLY', 'fields': fields,
                    'values_recomputed_here': False}
        except (OSError, ValueError, SyntaxError, zipfile.BadZipFile, struct.error) as error:
            self.read_errors.append({'path': str(path), 'error': str(error)})
            return {'status': 'UNREADABLE_OR_CURRENTLY_WRITING', 'error': str(error)}


def interpret_arm_evidence(row):
    """Make partial coverage and composite-causal failures explicit, additively."""
    row=row or {};axes=row.get('axes') or {};checks=axes.get('causal_execution_checks') or {}
    original=axes.get('original_evaluator') or {}
    scientific=original.get('scientific_validity') or {}
    observed=row.get('observed_prefix') or {};interventions=row.get('interventions') or {}
    complete=row.get('complete_task')
    scope=('FULL_COMPLETED_TASK' if complete is True else 'OBSERVED_PREFIX_ONLY' if complete is False else 'NOT_EVALUABLE')
    native=checks.get('native_receipt_ownership')
    return {
        'measurement_scope':scope,
        'absolute_safety_scope':scope,
        'absolute_safety_display':('PASS_OBSERVED_PREFIX_ONLY' if complete is False and axes.get('absolute_safety')=='PASS' else axes.get('absolute_safety')),
        'whole_task_safety_or_success_established':complete is True and axes.get('absolute_safety')=='PASS' and row.get('absolute_task_execution_qualified') is True,
        'observed_task_duration_s':observed.get('observed_task_duration_s'),
        'observed_prefix_force_integral_N_s':observed.get('observed_task_J_F_N_s'),
        'observed_prefix_moment_integral_Nm_s':observed.get('observed_task_moment_integral_Nm_s'),
        'prefix_integrals_are_full_task_metrics':False,
        'abort_reason':row.get('abort_reason'),
        'causal_execution_source_checks':checks,
        'original_scientific_validity_status':scientific.get('status'),
        'original_scientific_validity_reasons':scientific.get('reasons'),
        'native_receipt_ownership_source_check':native,
        'native_receipt_ownership_interpretation':('NOT_EVALUATED_BY_COMPLETE_MEASUREMENT; null is not receipt corruption evidence.' if native is None else 'Original composite ownership check; inspect its detailed receipt evidence before attributing a cause.'),
        'intervention_status':interventions.get('status'),
        'incomplete_task_missing_interventions':interventions.get('incomplete_task_missing_interventions'),
        'causal_failure_interpretation':'A failed scientific request/version/activation gate and an incomplete intervention plan are distinct from corrupted native receipts. Preserve original reasons; no corruption conclusion follows from the aggregate CAUSAL/EXECUTION_FAIL label alone.',
        'patient_model_invalid_inferred_from_task_abort':False,
        'coverage_note':'For an incomplete arm, passing safety conditions cover only recorded execution before abort. Full JF, gain and relative-motion qualification require the completed full task.',
    }


def summarize_arm(row, ident, arm, run_events, parent_done, static_valid):
    if row is not None:
        result = dict(row)
        result['evidence_interpretation'] = interpret_arm_evidence(row)
        # Preserve all axes but avoid duplicating the full original nested scorer.
        if isinstance(result.get('axes'), dict):
            result['axes'] = {k: v for k, v in result['axes'].items() if k != 'original_evaluator'}
        result['source_evaluation_path'] = f'reports/{ident}_CROSS_EVALUATION.json'
        result['evidence_status'] = 'OBSERVED_EVALUATION_REPORT'
        return result
    started = any(x.get('event') == 'START' for x in run_events)
    ended = any(x.get('event') == 'END' for x in run_events)
    if started:
        status = 'EXECUTION_ENDED_WITHOUT_EVALUATION' if ended else 'RUNNING_OR_INCOMPLETE_EVIDENCE'
    elif static_valid is False:
        status = 'NOT_RUN_STATIC_MODEL_OR_ASSEMBLY_REJECTED'
    elif parent_done and not parent_done.get('cold_commissioning_reached', False):
        status = 'NOT_RUN_PARENT_PRE_FORK_FAILURE'
    else:
        status = 'NOT_RUN_OR_NOT_YET_DISPATCHED'
    return {'id': ident, 'arm': arm, 'qualification': status,
            'evidence_status': status, 'evidence_level': None,
            'complete_task': None, 'integration': 'NOT_EVALUABLE',
            'axes': {'task': 'NOT_EVALUABLE', 'absolute_safety': 'NOT_EVALUABLE',
                     'causal_execution': 'NOT_EVALUABLE'},
            'labels': [], 'J_F_N_s': None, 'moment_integral_Nm_s': None,
            'motion_relative': 'NOT_EVALUABLE', 'absolute_task_execution_qualified': False,
            'missing_result_reason': status, 'source_evaluation_path': None}


def distribution(values):
    values = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return {'denominator': len(values), 'mean': statistics.mean(values) if values else None,
            'median': statistics.median(values) if values else None,
            'minimum': min(values) if values else None, 'maximum': max(values) if values else None,
            'positive': sum(v > 0 for v in values), 'zero': sum(v == 0 for v in values),
            'negative': sum(v < 0 for v in values), 'unit': 'percent'}


def separate_motion_contract(pair, h):
    """Classify original failed checks; never relax composite qualification."""
    comparison = h.get('motion_comparison')
    failures = None if not isinstance(comparison, dict) else comparison.get('failed_requirements')
    nonmotion = {'physical_task', 'causal_ownership'}
    interaction = {'moment_integral_Nm_s', 'force_peak_N', 'moment_peak_Nm'}
    kinematic_names = {'excursion', 'cumulative_dose', 'endpoint_phase_boundary',
                       'task_duration', 'OUTBOUND_duration', 'HOLD_duration', 'RETURN_duration', 'tracking'}
    comparable = bool(pair and pair.get('full_integral_comparison_valid') and pair.get('pair_identity_valid'))
    valid_b = bool(pair and pair.get('qualified_B_reference'))
    if not isinstance(failures, list):
        relative_failures = kinematic_failures = interaction_failures = nonmotion_failures = None
    else:
        relative_failures = [x for x in failures if x not in nonmotion]
        nonmotion_failures = [x for x in failures if x in nonmotion]
        interaction_failures = [x for x in failures if x in interaction]
        kinematic_failures = [x for x in failures if x in kinematic_names or str(x).startswith(
            ('velocity_deg_s/', 'acceleration_deg_s2/', 'jerk_deg_s3/'))]
    def status(items):
        if pair is not None and not valid_b:
            return 'NOT_EVALUABLE_INVALID_B'
        if not comparable or items is None:
            return 'NOT_EVALUABLE'
        return 'FAIL' if items else 'PASS'
    return {
        'source_composite_acceptance': None if not isinstance(comparison, dict) else comparison.get('acceptance_pass'),
        'source_failed_requirements': failures,
        'relative_contract_status': status(relative_failures),
        'relative_contract_failures': relative_failures,
        'kinematic_motion_status': status(kinematic_failures),
        'kinematic_motion_failures': kinematic_failures,
        'interaction_tradeoff_status': status(interaction_failures),
        'interaction_tradeoff_failures': interaction_failures,
        'task_execution_failures': nonmotion_failures,
        'rule': 'Original composite acceptance is preserved. physical_task and causal_ownership are excluded only from relative-motion attribution; force/moment compensation gates are separately identified, not removed from full qualification.',
    }


def execution_evidence(ev, ident):
    """Add raw runtime evidence without changing the frozen scorer's fields."""
    audit = ev.read(f'audit/{ident}_LEARNING_EXECUTION_EVIDENCE.json')
    summary = ev.read(f'source/results/{ident}/summary.json', {})
    arrays = (audit or {}).get('runtime_arrays', {})
    events = (summary.get('runtime') or {}).get('safe_fallback_events')
    summary_counts = dict(Counter(str(x.get('event', 'MISSING_EVENT_TYPE')) for x in events)) if isinstance(events, list) else None
    raw = ev.artifact(f'source/results/{ident}/runtime_artifacts.json.gz')
    if not raw['exists']:
        raw = ev.artifact(f'source/results/{ident}/runtime_artifacts.json')
    if not raw['exists'] or raw.get('sha256') is None:
        raw = None
    source_hashes = (audit or {}).get('source_hashes', {})
    matching_hash = None if raw is None else source_hashes.get(raw['path'])
    if matching_hash is None and raw is not None:
        matching = [value for key, value in source_hashes.items() if key.endswith(f'/{ident}/runtime_artifacts.json.gz') or key.endswith(f'/{ident}/runtime_artifacts.json')]
        matching_hash = matching[0] if len(matching) == 1 else None
    audit_matches = None if audit is None or raw is None or matching_hash is None else matching_hash == raw.get('sha256')
    # An absent/stale audit never supplies counts that could look like observed zero.
    authoritative_arrays = arrays if audit_matches is True else {}
    receipt = authoritative_arrays.get('command_receipts', {})
    receipt_audit = ev.read(f'audit/{ident}_RECEIPT_MODE_EVIDENCE.json')
    receipt_matches = None if receipt_audit is None or raw is None else receipt_audit.get('original_bytes_unchanged') is True and receipt_audit.get('original_sha256') == raw.get('sha256')
    receipt_modes = receipt_audit if receipt_matches is True else receipt
    fallback_counts = authoritative_arrays.get('safe_fallback_events', {}).get('categories', {}).get('event')
    if fallback_counts is None and receipt_matches is True:
        fallback_counts = receipt_audit.get('fallback_event_type_counts')
    partial_audit = ev.read(f'audit/{ident}_PARTIAL_NATIVE_OWNERSHIP.json')
    partial_hashes = (partial_audit or {}).get('source_hashes', {})
    partial_raw_hash = None if raw is None else partial_hashes.get(raw['path'])
    if partial_raw_hash is None:
        matches = [v for k,v in partial_hashes.items() if k.endswith(f'/{ident}/runtime_artifacts.json.gz') or k.endswith(f'/{ident}/runtime_artifacts.json')]
        partial_raw_hash = matches[0] if len(matches) == 1 else None
    partial_matches = None if partial_audit is None or raw is None or partial_raw_hash is None else partial_raw_hash == raw.get('sha256') and partial_audit.get('original_bytes_unchanged') is True
    partial_evidence = ({key:partial_audit.get(key) for key in ['status','complete_task','full_J_F_N_s','full_gain','scientific_promotion','native_rows',
        'task_native_intervals','actual_new_native_physics_steps','every_native_row_owned','exact_torque_checked','each_receipt_step_count_matches','interpretation']}
        if partial_matches is True else None)
    return {
        'evidence_status': 'RAW_ARCHIVE_HASH_MATCHED_OFFLINE_AUDIT' if audit_matches is True else 'AUDIT_RAW_HASH_MISMATCH' if audit_matches is False else 'RAW_EXECUTION_FIELD_AUDIT_NOT_AVAILABLE',
        'raw_archive_hash_matches_audit': audit_matches,
        'audit_artifact': ev.artifact(f'audit/{ident}_LEARNING_EXECUTION_EVIDENCE.json'),
        'causal_schema_verification': ev.artifact(f'derived/{ident}_CAUSAL_SCHEMA_VERIFICATION.json'),
        'receipt_mode_audit_artifact': ev.artifact(f'audit/{ident}_RECEIPT_MODE_EVIDENCE.json'),
        'receipt_mode_audit_raw_hash_matches': receipt_matches,
        'raw_summary_fallback_event_type_counts': summary_counts,
        'raw_runtime_fallback_event_type_counts': fallback_counts,
        'explicit_fallback_commit_event_observed': None if fallback_counts is None else fallback_counts.get('FALLBACK_COMMITTED', 0) > 0,
        'TRACK_receipt_mode_excludes_fallback_execution': False,
        'receipt_mode_counts_all_records': receipt.get('categories', {}).get('mode'),
        'applied_receipt_mode_counts': receipt_modes.get('applied_mode_counts'),
        'unapplied_receipt_mode_counts': receipt_modes.get('unapplied_mode_counts'),
        'applied_positive_step_mode_counts': receipt_modes.get('applied_positive_step_mode_counts'),
        'applied_native_steps_by_mode': receipt_modes.get('applied_native_steps_by_mode'),
        'request_outcome_counts': authoritative_arrays.get('requests', {}).get('categories', {}).get('outcome'),
        'splice_outcome_counts': authoritative_arrays.get('rolling_splice_events', {}).get('categories', {}).get('outcome'),
        'runtime_array_counts': {key: value.get('count') if value.get('present') is True else None for key, value in authoritative_arrays.items()},
        'partial_native_ownership_audit_artifact': ev.artifact(f'audit/{ident}_PARTIAL_NATIVE_OWNERSHIP.json'),
        'partial_native_ownership_audit_raw_hash_matches': partial_matches,
        'independent_partial_native_ownership': partial_evidence,
        'compact_fallbacks_is_authoritative': False,
        'interpretation': 'ESCAPE_ADMITTED is a certificate/admission event, not proof that fallback motion executed. Explicit FALLBACK_COMMITTED events are reported separately. TRACK receipts can track an escape/fallback reference and do not rule out fallback. Applied receipt modes describe command mode, not the complete runtime fallback state. Partial ownership PASS covers saved native evidence only and never promotes full-task qualification. Missing audits/counts stay null. Retained native-step totals include inherited prefixes; unique work belongs to ATTEMPT_ACCOUNTING.json.',
    }


def build(package):
    ev = Evidence(package)
    cohort = ev.read('VIRTUAL_PATIENT_COHORT.json')
    if not cohort or not isinstance(cohort.get('patients'), list):
        raise ValueError('A readable registered VIRTUAL_PATIENT_COHORT.json is required')
    events = ev.events()
    by_run = {}
    for event in events:
        by_run.setdefault(event.get('id'), []).append(event)
    active = [ident for ident, rows in by_run.items()
              if sum(x.get('event') == 'START' for x in rows) > sum(x.get('event') == 'END' for x in rows)]
    campaign_done = ev.read('SERIAL_CAMPAIGN_DONE.json')
    progress = ev.read('CAMPAIGN_PROGRESS.json', {})
    campaign_rows = (campaign_done or progress).get('rows', [])
    campaign_by_patient = {r['patient_id']: r for r in campaign_rows if 'patient_id' in r}
    static_summary = ev.read('STATIC_PATIENT_AUDIT.json', {})
    static_by_patient = {r['patient_id']: r for r in static_summary.get('records', []) if 'patient_id' in r}
    source = ev.artifact('EXECUTION_CODE_MANIFEST.json', 'frozen_execution_source')
    common = {'generated_utc': datetime.now(timezone.utc).isoformat(),
              'package_path': str(ev.package), 'physics_started_by_aggregation': 0,
              'training_performed': False, 'experiment': 'P0', 'P1_status': 'PROTOCOL_ONLY_NOT_RUN',
              'snapshot_status': 'EXECUTION_ACTIVE_OR_UNCLOSED' if active else 'NO_ACTIVE_STARTS_AT_SNAPSHOT',
              'active_or_unclosed_attempt_ids': active,
              'serial_campaign_done_present': campaign_done is not None,
              'cohort': ev.artifact('VIRTUAL_PATIENT_COHORT.json', 'preregistered_patient_identities'),
              'source_manifest': source,
              'evidence_note': 'Only observed evidence is aggregated; missing/failed/unrun patients remain. PHYSICAL_LEVEL1 is simulation evidence, not clinical proof.'}
    admissibility = []
    result_rows = []
    qualification_rows = []
    learning_patients = []
    learning_runs = []

    for patient in cohort['patients']:
        pid = patient['patient_id']
        plan = ev.read(f'{pid}_PLAN.json', {})
        done = ev.read(f'{pid}_DONE.json')
        static = ev.read(f'patients/{pid}/static/MODEL_STATIC_AUDIT.json', static_by_patient.get(pid, {}))
        static_valid = static.get('model_static_valid')
        fork = ev.read(f'audit/{pid}_FORK_CONTEXT.json')
        parent = ev.read(f'{pid}_PARENT_RESULT.json')
        parent_error = ev.read(f'reports/{pid}_parent_ERROR.json')
        pair = ev.read(f'reports/{pid}_PAIR_ANALYSIS.json') or ev.read(f'{pid}_COMPARISON.json')
        pair_gate = ev.read(f'{pid}_PAIR_GATE.json')
        fork_reached = fork is not None or bool(done and done.get('cold_commissioning_reached'))
        parent_events = by_run.get(pid + '_parent', [])
        parent_started = any(r.get('event') == 'START' for r in parent_events)
        parent_ended = any(r.get('event') == 'END' for r in parent_events)
        if static_valid is False:
            admission = 'MODEL_NOT_ADMISSIBLE'
            subtype = static.get('static_assembly', {}).get('category', static.get('status', 'STATIC_CHECK_FAILURE'))
        elif fork_reached:
            admission = 'OWN_COLD_COMMISSIONING_AND_TASK_FORK_REACHED'
            subtype = 'ORIGINAL_EXECUTION_PIPELINE_REACHED_SHARED_LEGAL_PREFIX'
        elif done or (parent_started and parent_ended):
            admission = 'P0_PRE_FORK_EXECUTION_FAILURE'
            subtype = 'INITIALIZATION_MAPPING_COMMISSIONING_OR_ADMISSION_NOT_DISAMBIGUATED'
        elif parent_started:
            admission = 'P0_INITIALIZATION_OR_COMMISSIONING_IN_PROGRESS_OR_INCOMPLETE'
            subtype = 'NO_FORK_EVIDENCE_YET'
        elif static_valid is True:
            admission = 'STATIC_ADMISSIBLE_PENDING_PHYSICAL_COMMISSIONING'
            subtype = campaign_by_patient.get(pid, {}).get('status', 'NOT_RUN_OR_PENDING')
        else:
            admission = 'STATIC_ADMISSIBILITY_NOT_EVALUABLE'
            subtype = 'MISSING_OR_UNREADABLE_STATIC_EVIDENCE'
        raw_error = (parent_error or {}).get('error') or (done or {}).get('error')
        admission_row = {
            'patient_id': pid, 'label': patient.get('label'),
            'future_learning_split': patient.get('future_learning_split'),
            'status': admission, 'subtype': subtype,
            'model_static_valid': static_valid,
            'cold_initialization_attempt_started': parent_started,
            'own_commissioning_pipeline_reached_task_fork': fork_reached,
            'commissioning_stability_independently_claimed': False,
            'full_parent_task_complete': None if parent is None else parent.get('complete_task'),
            'full_parent_qualification': None if parent is None else parent.get('qualification'),
            'raw_error': raw_error, 'raw_parent_error': parent_error,
            'parent_done': done, 'campaign_dispatch_record': campaign_by_patient.get(pid),
            'static_checks': static.get('checks'), 'static_assembly': static.get('static_assembly'),
            'case_sha256_registered': patient.get('case_sha256'),
            'static_case_semantic_sha256': static.get('case_sha256'),
            'model_xml_sha256': static.get('xml_sha256'),
            'evidence': {
                'static': ev.artifact(f'patients/{pid}/static/MODEL_STATIC_AUDIT.json'),
                'fork': ev.artifact(f'audit/{pid}_FORK_CONTEXT.json'),
                'runtime_identity': ev.artifact(f'audit/{pid}_RUNTIME_MODEL_IDENTITY.json'),
                'parent_result': ev.artifact(f'{pid}_PARENT_RESULT.json')},
            'interpretation': 'Pre-fork failure does not establish nonphysical Human parameters or an H150-specific failure. Static validity does not establish physical commissioning or task success.',
        }
        admissibility.append(admission_row)
        arms = {}
        for arm in ('B', 'H150'):
            ident = pid + '_' + arm
            row = (pair or {}).get(arm) or ev.read(f'reports/{ident}_CROSS_EVALUATION.json')
            arms[arm] = summarize_arm(row, ident, arm, by_run.get(ident, []), done, static_valid)
            arms[arm]['raw_runtime_execution_evidence'] = execution_evidence(ev, ident)
        motion_separation = separate_motion_contract(pair, arms['H150'])
        h = arms['H150']
        h['source_motion_relative'] = h.get('motion_relative')
        h['source_failure_labels'] = list(h.get('labels', []))
        h['source_qualification'] = h.get('qualification')
        h['motion_contract_separation'] = motion_separation
        h['motion_relative'] = motion_separation['relative_contract_status']
        h['labels'] = [x for x in h.get('labels', []) if x != 'MOTION_RELATIVE_FAIL']
        if h['motion_relative'] == 'FAIL':
            h['labels'].append('MOTION_RELATIVE_FAIL')
        if h.get('qualification') == 'MOTION_RELATIVE_FAIL' and h['motion_relative'] != 'FAIL':
            h['qualification'] = h['labels'][0] if h['labels'] else 'NOT_EVALUABLE'
        gain_valid = bool(pair and pair.get('full_integral_comparison_valid'))
        reported_qualified = bool(pair and pair.get('complete_qualified_H150'))
        independent = {}
        for arm in ('B', 'H150'):
            ident = pid + '_' + arm
            audit = ev.read(f'derived/{ident}_INDEPENDENT_FAILURE.json') or ev.read(f'derived/{ident}_INDEPENDENT.json')
            independent[arm] = None if audit is None else audit.get('status')
        independently_qualified = (reported_qualified and independent == {'B': 'PASS', 'H150': 'PASS'}
                                  and (pair_gate or {}).get('status') == 'PASS')
        result = {
            'patient_id': pid, 'label': patient.get('label'), 'experiment': 'P0',
            'physical_parameters': patient.get('physical'),
            'engineering_factors': patient.get('engineering_factors'),
            'future_learning_split': patient.get('future_learning_split'),
            'admissibility_status': admission, 'admissibility_subtype': subtype,
            'B': arms['B'], 'H150': arms['H150'],
            'pair_identity_valid': None if pair is None else pair.get('pair_identity_valid'),
            'pair_identity_checks': None if pair is None else pair.get('pair_identity_checks'),
            'pair_gate_status': None if pair_gate is None else pair_gate.get('status'),
            'full_integral_comparison_valid': gain_valid,
            'gain_fraction': (pair or {}).get('gain_fraction') if gain_valid else None,
            'gain_percent': (pair or {}).get('gain_percent') if gain_valid else None,
            'gain_N_s': (pair or {}).get('gain_N_s') if gain_valid else None,
            'qualified_B_reference': bool(pair and pair.get('qualified_B_reference')),
            'motion_relative': motion_separation['relative_contract_status'],
            'source_motion_relative': (pair or {}).get('motion_relative', 'NOT_EVALUABLE'),
            'motion_contract_separation': motion_separation,
            'complete_qualified_H150': reported_qualified,
            'independent_verification': independent,
            'independently_verified_qualified_pair': independently_qualified,
            'comparison_warning': (pair or {}).get('warning'),
            'comparison_error': (pair or {}).get('comparison_error'),
            'pair_analysis_source': ev.artifact(f'reports/{pid}_PAIR_ANALYSIS.json'),
            'parent_result_source': ev.artifact(f'{pid}_PARENT_RESULT.json'),
        }
        result_rows.append(result)
        qualification_rows.append({
            'patient_id': pid, 'admissibility_status': admission, 'admissibility_subtype': subtype,
            'B_qualification': arms['B'].get('qualification'),
            'H150_qualification': arms['H150'].get('qualification'),
            'B_axes': arms['B'].get('axes'), 'H150_axes': arms['H150'].get('axes'),
            'B_failure_labels': arms['B'].get('labels', []),
            'H150_failure_labels': arms['H150'].get('labels', []),
            'B_evidence_interpretation': arms['B'].get('evidence_interpretation'),
            'H150_evidence_interpretation': arms['H150'].get('evidence_interpretation'),
            'motion_relative': result['motion_relative'],
            'source_motion_relative': result['source_motion_relative'],
            'motion_contract_separation': motion_separation,
            'pair_identity_valid': result['pair_identity_valid'],
            'pair_gate_status': result['pair_gate_status'],
            'full_integral_comparison_valid': gain_valid,
            'complete_qualified_H150': reported_qualified,
            'independent_verification': independent,
            'independently_verified_qualified_pair': independently_qualified,
            'gain_percent': result['gain_percent'],
            'qualified_gain_percent': result['gain_percent'] if reported_qualified else None,
            'qualified_B_reference': result['qualified_B_reference'],
        })
        learning_patients.append({
            'patient_id': pid, 'label': patient.get('label'),
            'future_learning_split': patient.get('future_learning_split'),
            'current_study_outcomes_exposed': patient.get('current_study_outcomes_exposed'),
            'model_static_valid': static_valid, 'admissibility_status': admission,
            'case_sha256_registered': patient.get('case_sha256'),
            'model_xml_sha256': static.get('xml_sha256'),
            'artifacts': {
                'case': ev.artifact(patient['case_path'], 'OFFLINE_PATIENT_TRUTH'),
                'model_xml': ev.artifact(f'patients/{pid}/static/model.xml', 'OFFLINE_MODEL_IDENTITY'),
                'static_audit': ev.artifact(f'patients/{pid}/static/MODEL_STATIC_AUDIT.json'),
                'plan': ev.artifact(f'{pid}_PLAN.json', 'FROZEN_POLICY_IDENTITY'),
            }, 'training_used': False,
        })

        candidates = {x['id']: x for x in plan.get('arms', []) if 'id' in x}
        run_specs = [(pid + '_' + arm, arm, False) for arm in ('parent', 'B', 'H150')]
        expected_ids = {item[0] for item in run_specs}
        for ident, attempt_records in by_run.items():
            if ident in expected_ids or not isinstance(ident, str):
                continue
            if any(r.get('event') == 'START' and r.get('patient_id') == pid for r in attempt_records):
                suffix = ident.rsplit('_', 1)[-1]
                run_specs.append((ident, suffix if suffix in ('parent', 'B', 'H150') else 'OTHER', True))
        for ident, arm, supplementary in run_specs:
            evaluation = (ev.read(f'reports/{ident}_CROSS_EVALUATION.json') if supplementary
                          else parent if arm == 'parent' else arms[arm])
            run_events = by_run.get(ident, [])
            data = ev.read(f'output/{ident}_DATA.json', {})
            causal = ev.read(f'learning/{ident}_STATE_ACTION.json')
            causal_partial = ev.read(f'learning/{ident}_PARTIAL_STATE_ACTION.json')
            selected_causal = causal if causal is not None else causal_partial
            raw = ev.read(f'source/results/{ident}/summary.json', {})
            branch = data.get('branch_start') or (evaluation or {}).get('branch') or {}
            partial_compute = ev.read(f'output/{ident}_PARTIAL_COMPUTE.json')
            trace_inventory = ev.npz_inventory(f'source/results/{ident}/trace.npz')
            trace_fields = (trace_inventory or {}).get('fields', {})
            starts = [r for r in run_events if r.get('event') == 'START']
            ends = [r for r in run_events if r.get('event') == 'END']
            metric = data.get('metric', {})
            actual_steps = metric.get('actual_new_native_physics_steps')
            full_steps = metric.get('native_physics_steps')
            if actual_steps is None and arm == 'parent':
                actual_steps = full_steps
            if actual_steps is None and partial_compute:
                actual_steps = partial_compute.get('actual_new_native_physics_steps')
            physics_observed = (isinstance(actual_steps, (int, float)) and actual_steps > 0)
            independent_result = ev.read(f'derived/{ident}_INDEPENDENT_FAILURE.json') or ev.read(f'derived/{ident}_INDEPENDENT.json')
            artifact_paths = {
                'causal_state_action': f'learning/{ident}_STATE_ACTION.json',
                'partial_causal_state_action': f'learning/{ident}_PARTIAL_STATE_ACTION.json',
                'trace': f'source/results/{ident}/trace.npz',
                'summary': f'source/results/{ident}/summary.json',
                'config_snapshot': f'source/results/{ident}/config_snapshot.json',
                'runtime_artifacts_gzip': f'source/results/{ident}/runtime_artifacts.json.gz',
                'runtime_artifacts_json': f'source/results/{ident}/runtime_artifacts.json',
                'full_branch_data': f'output/{ident}_DATA.json',
                'metric': f'output/{ident}.json',
                'issued_reference': f'output/{ident}_ISSUED_REFERENCE.json',
                'reference_objects': f'output/{ident}_REFERENCE_OBJECTS.json',
                'optional_control_intent': f'output/{ident}_CONTROL_INTENT.json',
                'partial_compute': f'output/{ident}_PARTIAL_COMPUTE.json',
                'evaluation': f'reports/{ident}_CROSS_EVALUATION.json',
                'measured': f'reports/{ident}_MEASURED.json',
                'residual_native_ownership': f'reports/{ident}_EXECUTED_RESIDUAL_RECEIPTS.json',
                'native_truth_motion': f'motion_series/{ident}.npz',
                'independent_pass': f'derived/{ident}_INDEPENDENT.json',
                'independent_failure': f'derived/{ident}_INDEPENDENT_FAILURE.json',
                'execution_error': f'reports/{ident}_ERROR.json',
            }
            learning_runs.append({
                'run_id': ident, 'patient_id': pid, 'arm': arm,
                'future_learning_split': patient.get('future_learning_split'),
                'experiment': 'P0', 'training_used': False,
                'supplementary_attempt': supplementary,
                'counts_as_new_patient': False,
                'run_role': 'OWN_COLD_COMMISSIONING_AND_SHARED_PREFIX_PARENT' if arm == 'parent' else 'MATCHED_FROZEN_POLICY_ARM',
                'candidate_hash': None if arm == 'parent' else candidates.get(arm, {}).get('candidate_hash'),
                'case_sha256': patient.get('case_sha256'),
                'model_xml_sha256': static.get('xml_sha256'),
                'source_manifest_sha256': starts[0].get('source_sha256', starts[0].get('code_manifest_sha256')) if starts else None,
                'current_source_manifest_sha256': source.get('sha256'),
                'shared_parent_full_hash': branch.get('full_hash'),
                'start_events': starts, 'end_events': ends,
                'start_end_closed': len(starts) == len(ends) == 1,
                'attempt_started': bool(starts),
                'physical_execution_observed_from_step_counter': physics_observed,
                'physics_observation_caveat': 'False means no positive step counter was recovered, not proof of zero execution. START without steps is retained.',
                'actual_new_native_steps': actual_steps,
                'step_counter_basis': 'Declared metric or partial-compute counter; independent verified unique physics accounting is ATTEMPT_ACCOUNTING.json.',
                'full_cumulative_native_steps': full_steps,
                'native_rows_from_independent_audit': None if independent_result is None else independent_result.get('native_rows'),
                'native_count_source': None if independent_result is None else f'derived/{ident}_INDEPENDENT.json',
                'causal_decision_rows': None if selected_causal is None else len(selected_causal.get('causal_rows', [])),
                'causal_records_partial': None if selected_causal is None else causal is None or (evaluation or {}).get('complete_task') is False,
                'causal_file_is_partial_archive': None if selected_causal is None else causal is None,
                'causal_record_coverage': ('NO_CAUSAL_ARCHIVE' if selected_causal is None else 'OBSERVED_PREFIX_DECISIONS' if (evaluation or {}).get('complete_task') is False else 'FULL_COMPLETED_TASK_DECISIONS' if (evaluation or {}).get('complete_task') is True else 'TASK_COMPLETENESS_UNKNOWN'),
                'causal_truth_flags_all_false': None if not (selected_causal or {}).get('causal_rows') else all(r.get('truth_used') is False for r in selected_causal['causal_rows']),
                'trace_rows': (trace_fields.get('time_s', {}).get('shape') or [None])[0],
                'task_trace_rows': ((evaluation or {}).get('observed_prefix') or {}).get('task_samples'),
                'trace_inventory': trace_inventory,
                'complete_task': None if evaluation is None else evaluation.get('complete_task'),
                'integration_status': None if evaluation is None else evaluation.get('integration'),
                'qualification': None if evaluation is None else evaluation.get('qualification'),
                'failure_labels': [] if evaluation is None else evaluation.get('labels', []),
                'evidence_interpretation': (evaluation or {}).get('evidence_interpretation') or interpret_arm_evidence(evaluation),
                'summary_status': raw.get('status'),
                'partial_compute': partial_compute,
                'raw_runtime_execution_evidence': execution_evidence(ev, ident),
                'interval_telemetry_audit_row': {
                    'audit_package_relative_path': 'audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json',
                    'row_id': ident,
                    'interpretation': 'Read the hash-bound manifest-level interval telemetry audit for source hashes, terminal-boundary missingness, positive-duration interval coverage, and additive duration-weighted reductions. Frozen summary nulls are preserved and do not by themselves establish unavailable telemetry.',
                },
                'artifacts': {key: ev.artifact(value) for key, value in artifact_paths.items()},
                'truth_access': 'OFFLINE_EVALUATION_ONLY',
                'state_sampling': 'Original planning decision boundaries; post-fork in child files, shared prefix in original parent/full raw artifacts.',
                'native_ownership_validation': None if independent_result is None else independent_result.get('status'),
            })

    denominators = {
        'registered_patients': len(result_rows),
        'model_static_valid_patients': sum(r['model_static_valid'] is True for r in admissibility),
        'model_static_rejected_patients': sum(r['model_static_valid'] is False for r in admissibility),
        'model_static_unknown_patients': sum(r['model_static_valid'] is None for r in admissibility),
        'patients_with_parent_start': sum(r['cold_initialization_attempt_started'] for r in admissibility),
        'patients_own_commissioning_reached_fork': sum(r['own_commissioning_pipeline_reached_task_fork'] for r in admissibility),
        'patients_pre_fork_execution_failure': sum(r['status'] == 'P0_PRE_FORK_EXECUTION_FAILURE' for r in admissibility),
        'patients_with_both_arm_evaluation_reports': sum(all(r[a]['evidence_status'] == 'OBSERVED_EVALUATION_REPORT' for a in ('B', 'H150')) for r in result_rows),
        'full_integral_comparable_pairs': sum(r['full_integral_comparison_valid'] for r in result_rows),
        'qualified_B_patients': sum(r['B'].get('absolute_task_execution_qualified') is True for r in result_rows),
        'reported_complete_qualified_H150_patients': sum(r['complete_qualified_H150'] for r in result_rows),
        'independently_verified_complete_qualified_pairs': sum(r['independently_verified_qualified_pair'] for r in result_rows),
        'H150_motion_relative_fail_patients': sum(r['motion_relative'] == 'FAIL' for r in result_rows),
        'H150_kinematic_motion_fail_patients': sum(r['motion_contract_separation']['kinematic_motion_status'] == 'FAIL' for r in result_rows),
        'H150_interaction_tradeoff_fail_patients': sum(r['motion_contract_separation']['interaction_tradeoff_status'] == 'FAIL' for r in result_rows),
        'H150_source_composite_acceptance_fail_patients': sum(r['motion_contract_separation']['source_composite_acceptance'] is False for r in result_rows),
        'H150_invalid_B_reference_patients': sum(r['motion_relative'] == 'NOT_EVALUABLE_INVALID_B' for r in result_rows),
        'B_absolute_safety_fail_patients': sum(r['B'].get('axes', {}).get('absolute_safety') == 'FAIL' for r in result_rows),
        'H150_absolute_safety_fail_patients': sum(r['H150'].get('axes', {}).get('absolute_safety') == 'FAIL' for r in result_rows),
    }
    gains = {
        'all_valid_full_integral_pairs': distribution([r['gain_percent'] for r in result_rows if r['full_integral_comparison_valid']]),
        'reported_complete_qualified_pairs': distribution([r['gain_percent'] for r in result_rows if r['complete_qualified_H150']]),
        'independently_verified_complete_qualified_pairs': distribution([r['gain_percent'] for r in result_rows if r['independently_verified_qualified_pair']]),
        'weighting': 'Each patient identity receives equal weight; deterministic repetitions are not additional patients.',
        'unqualified_complete_integrals': 'Descriptive only; not a claim of acceptable or safe force improvement.',
    }
    enum_counts = {
        'admissibility': dict(Counter(r['status'] for r in admissibility)),
        'B_qualification': dict(Counter(str(r['B_qualification']) for r in qualification_rows)),
        'H150_qualification': dict(Counter(str(r['H150_qualification']) for r in qualification_rows)),
        'motion_relative': dict(Counter(r['motion_relative'] for r in qualification_rows)),
    }
    common['read_errors'] = ev.read_errors
    outputs = {
        'PATIENT_ADMISSIBILITY_RESULTS.json': dict(common, schema='IHEAR_PATIENT_ADMISSIBILITY_RESULTS_V1',
            rows=admissibility, denominators=denominators, enum_counts=enum_counts['admissibility']),
        'CROSS_PATIENT_EXPERIMENT_RESULTS.json': dict(common, schema='IHEAR_CROSS_PATIENT_EXPERIMENT_RESULTS_V1',
            rows=result_rows, denominators=denominators, gain_statistics_percent=gains,
            population_claim='EXPLORATORY_ENGINEERING_SENSITIVITY_NOT_CLINICAL_DISTRIBUTION'),
        'CROSS_PATIENT_QUALIFICATION.json': dict(common, schema='IHEAR_CROSS_PATIENT_QUALIFICATION_V1',
            rows=qualification_rows, denominators=denominators, enum_counts=enum_counts,
            rule='B self-relative motion is not absolute safety. Invalid B makes H150 relative motion not evaluable. All failures and missing runs retained.'),
        'LEARNING_DATA_MANIFEST.json': dict(common, schema='IHEAR_CROSS_PATIENT_LEARNING_DATA_MANIFEST_V1',
            status='OBSERVED_ARTIFACT_INVENTORY_NOT_TRAINING',
            schema_artifact=ev.artifact('LEARNING_DATA_SCHEMA.json'),
            interval_telemetry_availability_audit=ev.artifact('audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json', 'OFFLINE_VALID_INTERVAL_TELEMETRY_AVAILABILITY'),
            interval_telemetry_note='The additive audit distinguishes terminal-boundary NaNs from positive-duration applied-interval coverage, retains source hashes and receipt joins, and reports valid-interval peak/time-weighted RMS without filling missing samples or changing frozen reductions. Per-run scope and coverage must be read from its matching row; partial tasks remain partial.',
            patients=learning_patients, runs=learning_runs, denominators=denominators,
            expected_primary_run_count=3 * len(cohort['patients']),
            supplementary_attempt_count=sum(r['supplementary_attempt'] for r in learning_runs),
            split_note=cohort.get('future_split_note'),
            complete_dataset_claimed=False,
            dataset_completeness_note='This is an inventory snapshot, not a claim that every registered run, field, or native audit is complete. Inspect per-run missing artifacts, task/integration status, read errors, and attempt accounting.',
            patient_identity_is_split_unit=True,
            no_learning_success_claim=True,
            truth_firewall='Native Human states and generator parameters are offline only. Physical archive fields do not become online features without causal sensor provenance.',
            inventory_limit='Runtime archives hashed without bulk parsing; native row counts copied only from independent audit. Missing counts remain null.'),
    }
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, help='Optional separate output directory; defaults to package root')
    args = parser.parse_args()
    outputs = build(args.package)
    target = args.package if args.output is None else args.output
    for name, payload in outputs.items():
        write_json(target / name, payload)
    summary = outputs['CROSS_PATIENT_EXPERIMENT_RESULTS.json']
    print(json.dumps({'status': 'OFFLINE_AGGREGATION_COMPLETE', 'output': str(target.resolve()),
                      'denominators': summary['denominators'], 'physics_starts': 0,
                      'read_errors': len(summary['read_errors'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
