"""Failure-preserving, offline cross-patient evaluation; never starts physics.

The original measurement arithmetic is retained. Only its final promotion
assertion is removed in memory so a completed but unsafe run remains measurable.
Original controller, plant, metric formula and motion thresholds are unchanged.
"""
from pathlib import Path
import ast
import hashlib
import importlib.util
import inspect
import json
import os
import sys
import traceback

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.dont_write_bytecode = True
import numpy as np

P = Path(__file__).resolve().parent
_am = None
_measure = None
_REMOVED_ASSERT = "assert a['axes']['PHYSICAL_TASK_VALID']=='PASS' and line['status']=='PASS','PHYSICAL_OR_OWNERSHIP_FAILURE';"
TASK_KEYS = ('summary_complete', 'transition_order', 'phase_timeouts', 'true_goal_dwell', 'true_return')
SAFETY_KEYS = ('force', 'moment', 'human_acceleration', 'human_speed', 'robot_speed',
               'torque', 'no_human_rom_violation', 'no_shank_table_contact',
               'true_clearance', 'session_clearance', 'measured_sleeve_clearance')


def configure(package_path):
    global P, _am, _measure
    P = Path(package_path).resolve()
    for part in ('code', 'control', 'deps'):
        path = str(P / part)
        if path not in sys.path:
            sys.path.insert(0, path)
    _am = _measure = None


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def put(name, value):
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temp.replace(path)


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def _original():
    global _am, _measure
    if _am is not None:
        return _am, _measure
    configure(P)
    import analyze_matched as am
    import explore_common as ec
    am.S = ec.S = P
    source = inspect.getsource(am.measure)
    assert source.count(_REMOVED_ASSERT) == 1, 'ORIGINAL_MEASURE_ASSERTION_CHANGED'
    adapted = source.replace(_REMOVED_ASSERT, '')
    namespace = dict(am.__dict__)
    namespace['S'] = P
    exec(compile(adapted, '<cross-patient measurement promotion assertion removed>', 'exec'), namespace)
    _am, _measure = am, namespace['measure']
    put('audit/EVALUATION_ADAPTER.json', dict(
        original_file=str(Path(inspect.getfile(am)).resolve()), original_sha256=sha(inspect.getfile(am)),
        original_function_sha256=hashlib.sha256(source.encode()).hexdigest(),
        adapted_function_sha256=hashlib.sha256(adapted.encode()).hexdigest(),
        exact_removed_text=_REMOVED_ASSERT, change='remove final promotion assertion only',
        thresholds_or_arithmetic_changed=False, physics_started=False))
    return _am, _measure


def _status(checks):
    if any(v is False for v in checks.values()):
        return 'FAIL'
    if not checks or any(v is None for v in checks.values()):
        return 'NOT_EVALUABLE'
    return 'PASS'


def _axes(summary, metric, measured, complete):
    audit = metric.get('physical_audit', {})
    evaluator = audit.get('unchanged_evaluator', {})
    physical = evaluator.get('physical_task_result', {})
    conditions = physical.get('scorer_v2_common_conditions', {})
    if not conditions:
        conditions = evaluator.get('raw_scorer_v2', {}).get('conditions', {})
    transitions = summary.get('task', {}).get('phase_transitions', [])
    order = [r.get('to') for r in transitions]
    task = {k: conditions.get(k) for k in TASK_KEYS}
    task['summary_complete'] = complete
    # Missing native task conditions are unknown, never inferred from self-motion.
    if task['transition_order'] is None:
        task['transition_order'] = order == ['HOLD', 'RETURN', 'COMPLETE'] or order == ['OUTBOUND', 'HOLD', 'RETURN', 'COMPLETE']
    safety = {k: conditions.get(k) for k in SAFETY_KEYS}
    safety.update(finite_native=physical.get('finite_native'), finite_trace=physical.get('finite_trace'))
    execution = dict(
        native_receipt_ownership=None if measured is None else measured.get('axes', {}).get('SCIENTIFIC_EXECUTION_CAUSAL_VALID') == 'PASS',
        scientific_request_version_age_valid=None if 'scientific_validity' not in evaluator else evaluator['scientific_validity'].get('status') == 'PASS',
        online_certificates_valid=audit.get('online_certificates_valid'),
        activation_certificates_valid=physical.get('activation_certificates_valid'),
        reference_boundary_C2=physical.get('reference_boundary_C2'),
        case_hash=conditions.get('case_hash'))
    return dict(task=_status(task), absolute_safety=_status(safety), causal_execution=_status(execution),
                task_checks=task, absolute_safety_checks=safety, causal_execution_checks=execution,
                original_combined_physical_pass=audit.get('pass_'),
                original_combined_task_valid=metric.get('task_valid'),
                original_matched_timing_valid=metric.get('matched_timing_valid'),
                evaluator_physical_reasons=physical.get('reasons', []),
                original_evaluator=evaluator)


def intervention_audit(summary, arm, candidate=None):
    fields = {'T': 'terminal_duration_intervention', 'D': 'second_round_posture',
              'ER': 'early_return_duration', 'H150': 'terminal_hip_timing'}
    rows = {k: [] for k in fields}
    for record in summary.get('learning_records', []):
        screen = record.get('selected_plan', {}).get('execution_screen', {})
        for key, field in fields.items():
            if field in screen:
                rows[key].append(dict(metadata=screen[field], activated=record.get('selected_plan_activated'),
                                      decision_index=record.get('decision_index'),
                                      start_time_s=record.get('start_time_s'), end_time_s=record.get('end_time_s')))
    if arm == 'B':
        return dict(status='PASS' if not any(rows.values()) else 'FAIL', expected_no_interventions=True, rows=rows)
    expected = {'D': 2, 'ER': 2, 'H150': 1}
    counts = {key: len(value) for key, value in rows.items()}
    checks = {'T_present': counts['T'] >= 1}
    for key, count in expected.items():
        checks[key + '_count'] = counts[key] == count
    for key, values in rows.items():
        checks[key + '_accepted_and_activated'] = bool(values) and all(
            x['metadata'].get('status') == 'ACCEPTED' and x['activated'] is True for x in values)
    for key, expected_values in [('D', [(0.3, -0.3)] * 2), ('ER', [1.1, 1.2]), ('H150', [1.5])]:
        actual = [tuple(x['metadata'].get('delta_deg', [])) if key == 'D' else x['metadata'].get('duration_factor') for x in rows[key]]
        checks[key + '_frozen_values'] = actual == expected_values
    checks['T_frozen_factor'] = bool(rows['T']) and all(
        (x['metadata'].get('terminal_contract') or {}).get('factor') == 1.5 for x in rows['T'])
    return dict(status=_status(checks), counts=counts, checks=checks, rows=rows,
                candidate_hash=None if candidate is None else candidate.get('candidate_hash'),
                caveat='Acceptance and activated segment checked here; exact native command ownership checked separately.')


def _raw_observed(ident):
    folder = P / 'source/results' / ident
    path = folder / 'trace.npz'
    result = dict(trace_exists=path.exists(), scope='OBSERVED_PREFIX_ONLY_UNLESS_FULL_INTEGRATION_VALID')
    if not path.exists():
        return result
    with np.load(path) as z:
        stage = z['stage']
        selected = stage == 'TASK'
        t = z['time_s'][selected]
        result.update(task_samples=len(t), stages={str(x): int(np.sum(stage == x)) for x in np.unique(stage)},
                      trace_sha256=sha(path), trace_fields=list(z.files))
        if len(t) < 2:
            return result
        dt = np.diff(t)
        f = np.linalg.norm(z['physical_cuff_force_world_n'][selected], axis=1)
        m = np.linalg.norm(z['physical_cuff_moment_world_nm'][selected], axis=1)
        duration = float(np.sum(dt))
        result.update(first_task_physics_s=float(t[0]), last_task_physics_s=float(t[-1]),
                      observed_task_duration_s=duration, observed_task_J_F_N_s=float(f[:-1] @ dt),
                      observed_task_moment_integral_Nm_s=float(m[:-1] @ dt),
                      force_peak_N=float(np.max(f)), moment_peak_Nm=float(np.max(m)),
                      force_time_RMS_N=float(np.sqrt((f[:-1]**2 @ dt)/duration)) if duration > 0 else None,
                      moment_time_RMS_Nm=float(np.sqrt((m[:-1]**2 @ dt)/duration)) if duration > 0 else None,
                      force_sample_RMS_N=float(np.sqrt(np.mean(f*f))),
                      nondecreasing_time=bool(np.all(dt >= -1e-12)),
                      max_tick_s=float(np.max(dt)), left_integral_method='5 ms TASK trace, f[:-1] dot diff(t), duplicate timestamps carry zero weight')
        for name in z.files:
            if any(token in name for token in ('torque', 'allocator', 'allocated_wrench', 'actuator_command')):
                x = z[name]
                if x.ndim and x.shape[0] == len(stage) and x.dtype.kind in 'fiu':
                    y = x[selected]
                    if y.size:
                        result.setdefault('torque_allocator', {})[name] = dict(max_abs=np.max(abs(y), axis=0), rms=np.sqrt(np.mean(y*y, axis=0)))
    return clean(result)


def _extra_motion(ident, case):
    path = P / 'motion_series' / (ident + '.npz')
    if not path.exists():
        return None
    with np.load(path) as z:
        q = np.rad2deg(z['true_q_rad']); v = np.rad2deg(z['true_dq_rad_s'])
        a = np.rad2deg(z['acceleration_rad_s2']); phase = z['phase']; t = z['time_s']
        result = dict(source='evaluation-only native Human truth at 0.25 ms',
                      velocity_total_variation_deg_s=np.sum(abs(np.diff(v, axis=0)), axis=0),
                      acceleration_total_variation_deg_s2=np.sum(abs(np.diff(a, axis=0)), axis=0),
                      q_min_deg=np.min(q, axis=0), q_max_deg=np.max(q, axis=0),
                      native_dt_min_s=float(np.min(np.diff(t))), native_dt_max_s=float(np.max(np.diff(t))))
        if case is not None:
            target = case['task']; start = np.asarray(target['start_deg']); goal = np.asarray(target['goal_deg'])
            outbound = q[phase == 'OUTBOUND']; ret = q[phase == 'RETURN']
            result.update(outbound_target_deg=goal, return_target_deg=start,
                          full_return_minimum_deg=np.min(ret, axis=0),
                          full_return_maximum_deg=np.max(ret, axis=0),
                          outbound_overshoot_from_nominal_goal_deg=np.maximum(0., np.max(outbound, axis=0)-goal),
                          return_undershoot_from_nominal_start_deg=np.maximum(0., start-np.min(ret, axis=0)),
                          return_terminal_signed_error_deg=ret[-1]-start,
                          actual_endpoint_deg=q[-1])
            with np.load(P / 'source/results' / ident / 'trace.npz') as trace:
                task = trace['stage'] == 'TASK'
                issued_return = np.rad2deg(trace['reference_q_rad'][task][-1])
                outbound_mask = task & (trace['task_phase'] == 'OUTBOUND')
                issued_outbound = np.rad2deg(trace['reference_q_rad'][outbound_mask][-1])
            result.update(final_issued_return_reference_deg=issued_return,
                          final_issued_outbound_reference_deg=issued_outbound,
                          return_undershoot_deg=np.maximum(0., issued_return-np.min(ret, axis=0)),
                          outbound_overshoot_deg=np.maximum(0., np.max(outbound, axis=0)-issued_outbound),
                          return_terminal_error_from_issued_reference_deg=ret[-1]-issued_return,
                          overshoot_definition='Actual extrema minus final issued reference of that phase; nominal task-target deviations separately retained.')
    return clean(result)


def evaluate_run(ident, arm='B', case=None, candidate=None):
    folder = P / 'source/results' / ident
    summary = read(folder / 'summary.json', {})
    metric = read(P / 'output' / (ident + '.json'), {})
    data = read(P / 'output' / (ident + '_DATA.json'), {})
    complete = summary.get('status') == 'COMPLETE' and any(
        x.get('to') == 'COMPLETE' for x in summary.get('task', {}).get('phase_transitions', []))
    measured = None; error = None; integration = 'NOT_EVALUABLE'
    if complete:
        try:
            _, measure = _original()
            measured = measure(ident)
            integration = 'PASS' if measured['phase_cost']['status'] == 'COMPLETE_RAW_CLOSURE_PASS' else 'FAIL'
        except Exception as exc:
            error = dict(error=str(exc), traceback=traceback.format_exc())
            # A completed raw rollout can fail numeric/ownership verification.
            # Never replace that failure with a cached or partial successful metric.
            integration = 'FAIL'
    observed = _raw_observed(ident)
    axes = _axes(summary, metric, measured, complete)
    intervention = intervention_audit(summary, arm, candidate)
    if measured is not None and arm == 'H150':
        lineage = read(P / 'reports' / (ident + '_EXECUTED_RESIDUAL_RECEIPTS.json'), {})
        owners = {r.get('decision_index'): r for r in lineage.get('rows', [])}
        for kind, records in intervention['rows'].items():
            for record in records:
                record['receipt_owned_native_steps'] = owners.get(record['decision_index'], {}).get('actual_native_steps', 0)
            intervention['checks'][kind + '_native_execution'] = bool(records) and all(r['receipt_owned_native_steps'] > 0 for r in records)
        intervention['status'] = _status(intervention['checks'])
    if arm == 'H150' and not complete and intervention['status'] == 'FAIL':
        intervention['incomplete_task_missing_interventions'] = True
    labels = []
    if axes['task'] == 'FAIL': labels.append('TASK_FAIL')
    if axes['absolute_safety'] == 'FAIL': labels.append('ABSOLUTE_SAFETY_FAIL')
    if axes['causal_execution'] == 'FAIL' or (complete and intervention['status'] == 'FAIL'):
        labels.append('CAUSAL/EXECUTION_FAIL')
    if integration == 'FAIL': labels.append('NUMERICAL_VERIFICATION_FAIL')
    row = dict(id=ident, arm=arm, evidence_level='PHYSICAL_LEVEL1', complete_task=complete,
               axes=axes, integration=integration, labels=labels,
               J_F_N_s=measured['J_F_N_s'] if measured is not None and integration == 'PASS' else None,
               moment_integral_Nm_s=measured['moment_integral_Nm_s'] if measured is not None and integration == 'PASS' else None,
               measured_path='reports/' + ident + '_MEASURED.json' if measured is not None else None,
               phase_cost=None if measured is None else measured['phase_cost'],
               phase_durations=metric.get('phase_durations'),
               branch=data.get('branch_start'), actual_new_native_steps=data.get('metric', metric).get('actual_new_native_physics_steps'),
               observed_prefix=observed, interventions=intervention,
               motion_extra=_extra_motion(ident, case) if measured is not None else None,
               motion_relative='NOT_APPLICABLE_SELF_REFERENCE' if arm == 'B' else 'PENDING_PAIRED_B',
               failure=error, abort_reason=summary.get('abort_reason', summary.get('task', {}).get('abort_reason')),
               fallbacks=summary.get('fallback_events', []),
               partial_compute=read(P / 'output' / (ident + '_PARTIAL_COMPUTE.json')),
               child_error=read(P / 'reports' / (ident + '_ERROR.json')))
    row['absolute_task_execution_qualified'] = (complete and integration == 'PASS' and
        all(axes[k] == 'PASS' for k in ('task', 'absolute_safety', 'causal_execution')) and intervention['status'] == 'PASS')
    if arm == 'B' and row['absolute_task_execution_qualified']:
        row['qualification'] = 'COMPLETE_QUALIFIED_PASS'
    else:
        row['qualification'] = labels[0] if labels else 'NOT_EVALUABLE'
    put('reports/' + ident + '_CROSS_EVALUATION.json', row)
    return clean(row)


def compare_pair(patient_id, b, h):
    identity = dict(full_hash=False, patient_id=False, case_sha256=False, model_xml_sha256=False)
    if b.get('branch') and h.get('branch'):
        for field in identity:
            identity[field] = bool(b['branch'].get(field) and b['branch'].get(field) == h['branch'].get(field))
        identity['patient_id'] = identity['patient_id'] and b['branch']['patient_id'] == patient_id
    paired = all(identity.values())
    raw_complete = paired and all(x['complete_task'] and x['integration'] == 'PASS' for x in (b, h))
    baseline_qualified = b['absolute_task_execution_qualified']
    comparison = None; comparison_error = None
    if raw_complete:
        try:
            am, _ = _original()
            comparison = am.compare(read(P / h['measured_path']), read(P / b['measured_path']))
        except Exception as exc:
            comparison_error = dict(error=str(exc), traceback=traceback.format_exc())
    motion = ('PASS' if comparison['acceptance_pass'] else 'FAIL') if comparison is not None and baseline_qualified else 'NOT_EVALUABLE_INVALID_B' if not baseline_qualified else 'NOT_EVALUABLE'
    h['motion_relative'] = motion
    h['motion_comparison'] = comparison
    h['motion_comparison_qualified_interpretation'] = baseline_qualified and paired
    if motion == 'FAIL' and 'MOTION_RELATIVE_FAIL' not in h['labels']:
        h['labels'].append('MOTION_RELATIVE_FAIL')
    if not paired:
        for x in (b, h):
            if 'CAUSAL/EXECUTION_FAIL' not in x['labels']: x['labels'].append('CAUSAL/EXECUTION_FAIL')
            x['pair_identity_valid'] = False
    qualified = raw_complete and baseline_qualified and h['absolute_task_execution_qualified'] and motion == 'PASS'
    h['qualification'] = 'COMPLETE_QUALIFIED_PASS' if qualified else (h['labels'][0] if h['labels'] else 'NOT_EVALUABLE')
    gain = ((b['J_F_N_s']-h['J_F_N_s'])/b['J_F_N_s']) if raw_complete and b['J_F_N_s'] > 0 else None
    result = dict(patient_id=patient_id, experiment='P0', B=b, H150=h, pair_identity_valid=paired,
                  pair_identity_checks=identity,
                  full_integral_comparison_valid=raw_complete, qualified_B_reference=baseline_qualified,
                  gain_fraction=gain, gain_percent=None if gain is None else 100*gain,
                  gain_N_s=None if gain is None else b['J_F_N_s']-h['J_F_N_s'],
                  relative_gain_is_qualified=qualified, motion_relative=motion,
                  complete_qualified_H150=qualified, comparison_error=comparison_error,
                  warning=None if baseline_qualified else 'B is not a qualified task/safety/execution reference; raw complete-task gain may be descriptive only.')
    put('reports/' + patient_id + '_PAIR_ANALYSIS.json', result)
    for x in (b, h): put('reports/' + x['id'] + '_CROSS_EVALUATION.json', x)
    return clean(result)


def independent_verify(ident):
    """Run original arithmetic and ownership checker without importing physics."""
    path = P / 'control/independent_recompute.py'
    spec = importlib.util.spec_from_file_location('_cross_independent_arithmetic', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.P = P
    try:
        result = module.measure(ident)
    except Exception as exc:
        result = dict(id=ident, status='FAIL', error=str(exc), traceback=traceback.format_exc(),
                      new_physical_starts=0, evidence='RAW_INDEPENDENT_ARITHMETIC_FAILURE_PRESERVED')
        put('derived/' + ident + '_INDEPENDENT_FAILURE.json', result)
    return clean(result)


if __name__ == '__main__':
    configure(P)
    if len(sys.argv) > 2 and sys.argv[1] == '--independent':
        print(json.dumps(independent_verify(sys.argv[2]), ensure_ascii=False))
    else:
        raise SystemExit('Offline module; use evaluate_run/compare_pair or --independent IDENT')
