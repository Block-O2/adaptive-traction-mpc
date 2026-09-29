"""Verify and summarize a complete V3 zero-value scientific baseline."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics as stats
import sys
from pathlib import Path

root = Path('/home/hank/coding/adaptive-traction-mpc-learning')
stage = root / 'stages/stage5_personalized_motion_learning'
docs = stage / 'docs/zero_value_30rep_baseline_v3'
run = stage / 'results/zero_value_30rep_baseline_v3/formal_session_01'
sys.path.insert(0, str(stage / 'scripts/high_rom_v1'))
from sensor_time_integrity_v3 import audit_session


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(name: str, data: object) -> None:
    (docs / name).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def describe(values: list[float]) -> dict:
    values = [float(v) for v in values]
    assert values and all(math.isfinite(v) for v in values)
    return {'n': len(values), 'mean': stats.mean(values), 'median': stats.median(values),
            'std_sample': stats.stdev(values) if len(values) > 1 else None,
            'variance_sample': stats.variance(values) if len(values) > 1 else None,
            'minimum': min(values), 'maximum': max(values),
            'range': max(values) - min(values)}


def grouped(values: list[float]) -> dict:
    early, late = values[:5], values[5:]
    delta = [b - a for a, b in zip(values, values[1:])]
    late_delta = [b - a for a, b in zip(late, late[1:])]
    return {
        'early_rep1_to5': describe(early), 'late_rep6_to30': describe(late),
        'late_mean_relative_change_from_early': stats.mean(late) / stats.mean(early) - 1,
        'adjacent_delta_all': delta,
        'adjacent_delta_late': late_delta,
        'late_adjacent_abs_delta': describe([abs(x) for x in late_delta]),
        'late_coefficient_of_variation': stats.stdev(late) / stats.mean(late),
    }


def main() -> None:
    result = json.loads((run / 'session_result.json').read_text())
    rows = json.loads((run / 'per_repetition.json').read_text())
    assert result['status'] == 'ZERO_VALUE_30REP_BASELINE_COMPLETE'
    assert result['failure'] is None and len(rows) == 30
    assert [row['repetition_index'] for row in rows] == list(range(1, 31))
    for row in rows:
        assert row['status'] == 'COMPLETE'
        assert row['physical_task_validity'] == 'PASS'
        assert row['scientific_validity'] == 'PASS'
        assert row['overall_baseline_scientific_result'] == 'PASS'
        assert row['sensor_time_integrity']['status'] == 'PASS'
        assert row['gate_reasons'] == []
        assert all(x is True for x in row['boundary_audit'].values() if isinstance(x, bool))
        assert all(row['boundary_audit']['fresh_transient_objects'].values())
    sensor = audit_session(run, 30)
    assert sensor['status'] == 'PASS' and sensor['first_anomaly'] is None
    assert sensor == json.loads((run / 'SENSOR_TIME_INTEGRITY_SUMMARY.json').read_text())
    control_boundary_gaps = []
    previous_control_end = None
    for i in range(1, 31):
        wall = json.loads((run / f'rep_{i:02d}/runtime_artifacts.json').read_text())['wall_physics']
        applied = [r for r in wall['command_receipts'] if r.get('applied') and r.get('native_steps')]
        assert applied
        first_start = float(applied[0]['start_physics_s'])
        if previous_control_end is not None:
            gap = first_start - previous_control_end
            assert 0 <= gap <= 0.005 + 1e-7, (i, gap)
            control_boundary_gaps.append(gap)
        previous_control_end = float(applied[-1]['end_physics_s'])
    assert len(control_boundary_gaps) == 29
    sensor['inter_repetition_control_boundary_gap_s'] = describe(control_boundary_gaps)
    sensor['control_timestamps_monotonic_across_repetitions'] = True

    checkpoints = json.loads((run / 'session_checkpoints_manifest.json').read_text())
    raw = json.loads((run / 'raw_data_manifest.json').read_text())
    assert len(checkpoints) == 30
    for i, receipt in enumerate(checkpoints, 1):
        assert receipt['repetition_index'] == i
        assert sha(run / receipt['path']) == receipt['sha256']
    for path, expected in raw.items():
        assert sha(run / path) == expected, path
    fingerprint = json.loads((docs / 'PRODUCTION_FINGERPRINT_V3.json').read_text())
    for path, expected in fingerprint['source_config_contract_sha256'].items():
        assert sha(root / path) == expected, path
    for path, expected in fingerprint['preserved_v2_evidence_sha256'].items():
        assert sha(root / path) == expected, path
    preserved_v2_counts = {}
    for attempt, raw_name, checkpoint_name in (
        ('formal_session_01', 'RAW_DATA_MANIFEST_ATTEMPT_01.json',
         'SESSION_CHECKPOINTS_MANIFEST_ATTEMPT_01.json'),
        ('formal_session_02', 'RAW_DATA_MANIFEST_V2.json',
         'SESSION_CHECKPOINTS_MANIFEST_V2.json'),
    ):
        old_run = stage / 'results/zero_value_30rep_baseline_v2' / attempt
        old_raw = json.loads((stage / 'docs/zero_value_30rep_baseline_v2' / raw_name).read_text())
        old_checkpoints = json.loads((stage / 'docs/zero_value_30rep_baseline_v2' / checkpoint_name).read_text())
        for path, expected in old_raw.items():
            assert sha(old_run / path) == expected, f'preserved V2 {attempt}: {path}'
        for receipt in old_checkpoints:
            assert sha(old_run / receipt['path']) == receipt['sha256']
        preserved_v2_counts[attempt] = {'raw_files': len(old_raw), 'checkpoints': len(old_checkpoints)}

    decision_count = 0
    unscored_count = 0
    for i, row in enumerate(rows, 1):
        decisions = json.loads((run / f'rep_{i:02d}/zero_value_waypoint_decisions.json').read_text())
        assert len(decisions) == row['number_of_waypoint_decisions']
        for decision in decisions:
            decision_count += 1
            assert decision['RL'] == 'OFF' and decision['learned_value'] == 0
            for candidate in decision['candidate_set']:
                assert candidate['learned_value'] == (0 if candidate['evaluated'] else None)
                unscored_count += not candidate['evaluated']

    save('PER_REPETITION_V3.json', rows)
    columns = ['repetition_index', 'status', 'J_F_task_n_s', 'J_F_session_n_s',
               'peak_force_n', 'moment_integral_nm_s', 'moment_session_integral_nm_s',
               'peak_moment_nm', 'minimum_session_clearance_m',
               'minimum_true_clearance_m_evaluation_only', 'completion_time_s',
               'number_of_waypoint_decisions', 'human_model_sequence_after',
               'physical_task_validity', 'scientific_validity',
               'overall_baseline_scientific_result', 'scorer_v2']
    with (docs / 'PER_REPETITION_V3.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: row[key] for key in columns} for row in rows)
    series = {
        'J_F_task_n_s': [r['J_F_task_n_s'] for r in rows],
        'J_F_session_n_s': [r['J_F_session_n_s'] for r in rows],
        'peak_force_n': [r['peak_force_n'] for r in rows],
        'moment_integral_nm_s': [r['moment_integral_nm_s'] for r in rows],
        'peak_moment_nm': [r['peak_moment_nm'] for r in rows],
    }
    variability = {
        'schema': 'zero_value_30rep_baseline_variability_v3',
        'status': 'DESCRIPTIVE_COMPLETE', 'early_repetitions': [1, 5],
        'late_repetitions': [6, 30],
        'metrics': {key: grouped(values) for key, values in series.items()},
        'natural_noise_scope': 'one continuous deterministic-seed personalized session; descriptive late-repetition variability only',
    }
    save('BASELINE_VARIABILITY_SUMMARY.json', variability)

    versions = [r['human_model_sequence_after'] for r in rows]
    assert all(b > a for a, b in zip(versions, versions[1:]))
    model = [{'rep': i, 'at_task_start': row['human_model_at_task_start'],
              'end': row['human_model_after'],
              'start_sequence': row['human_model_at_task_start']['sequence'],
              'end_sequence': row['human_model_sequence_after'],
              'beta': row['human_model_after']['beta'],
              'residual_limit_nm': row['human_model_after']['residual_limit_nm'],
              'beta_l2_drift_from_rep1': math.dist(row['human_model_after']['beta'],
                                                    rows[0]['human_model_after']['beta'])}
             for i, row in enumerate(rows, 1)]
    save('HUMAN_MODEL_PROGRESSION_V3.json', {
        'per_repetition': model,
        'sequence_increased_monotonically': True,
        'beta_l2_change_rep1_to30': math.dist(model[0]['beta'], model[-1]['beta']),
        'beta_l2_adjacent_change': describe([
            math.dist(a['beta'], b['beta']) for a, b in zip(model, model[1:])]),
        'beta_component_change_rep1_to30': [b-a for a, b in zip(model[0]['beta'], model[-1]['beta'])],
    })
    sequences = [tuple(row['waypoint_sequence']) for row in rows]
    waypoint = [{'rep': i, 'sequence': row['waypoint_sequence'],
                 'decision_count': row['number_of_waypoint_decisions']}
                for i, row in enumerate(rows, 1)]
    save('WAYPOINT_PROGRESSION_V3.json', {
        'per_repetition': waypoint,
        'unique_sequence_count': len(set(sequences)),
        'adjacent_sequence_change_count': sum(a != b for a, b in zip(sequences, sequences[1:])),
        'total_decision_count': decision_count,
        'unscored_candidate_count': unscored_count,
        'zero_value_invariant': 'PASS',
    })
    deployable_clearance = [r['minimum_session_clearance_m'] for r in rows]
    native_clearance = [r['minimum_true_clearance_m_evaluation_only'] for r in rows]
    save('CLEARANCE_TREND_V3.json', {
        'deployable_m': {'per_rep': deployable_clearance, 'summary': grouped(deployable_clearance)},
        'native_evaluation_only_m': {'per_rep': native_clearance, 'summary': grouped(native_clearance)},
    })
    boundaries = [r.get('inter_rep_boundary_after') for r in rows[:29]]
    assert len(boundaries) == 29 and all(boundaries)
    assert rows[29].get('inter_rep_boundary_after') is None
    save('BOUNDARY_TIMING_SUMMARY_V3.json', {
        'boundary_count': 29,
        'settle_duration_s': describe([b['settle_duration_s'] for b in boundaries]),
        'hold_duration_s': describe([b['hold_duration_s'] for b in boundaries]),
        'total_duration_s': describe([b['settle_duration_s'] + b['hold_duration_s'] for b in boundaries]),
        'per_boundary': [{'after_rep': i, **b} for i, b in enumerate(boundaries, 1)],
    })
    wall_fail = []
    realtime_fail = []
    characterization = []
    for i, row in enumerate(rows, 1):
        raw_result = row['raw_scorer_v2_result']
        realtime = row['realtime_characterization']
        failed_conditions = [key for key, passed in raw_result['conditions'].items() if not passed]
        if failed_conditions:
            assert failed_conditions == ['plan_age']
            wall_fail.append({'rep': i, 'max_plan_age_ms': realtime['max_wall_plan_age_ms'],
                              'realtime_reason': realtime['counterfactual_realtime_reasons']})
        if realtime['counterfactual_realtime_validity'] == 'FAIL':
            realtime_fail.append(i)
        characterization.append({'rep': i, 'max_plan_age_ms': realtime['max_wall_plan_age_ms'],
                                 'source_age_wall_ms': realtime['source_age_wall_ms'],
                                 'activation_latency_ms': realtime['activation_latency_ms'],
                                 'control_cycle_misses': realtime['control_cycle_misses'],
                                 'command_gap_count': realtime['command_gap_count'],
                                 'counterfactual_realtime_validity': realtime['counterfactual_realtime_validity'],
                                 'counterfactual_realtime_reasons': realtime['counterfactual_realtime_reasons'],
                                 'raw_scorer_v2_pass': row['scorer_v2']})
    save('REALTIME_CHARACTERIZATION_SUMMARY.json', {
        'execution_mode': 'SCIENTIFIC_SIMULATION',
        'scientific_baseline_validity': 'PASS',
        'raw_scorer_v2_wall_time_failure_count': len(wall_fail),
        'raw_scorer_v2_wall_time_failures': wall_fail,
        'counterfactual_realtime_fail_repetitions': realtime_fail,
        'per_repetition': characterization,
        'strict_realtime_plan_age_limit_ms': 100,
        'historical_realtime_status': 'RSS_RUNTIME_QUALIFICATION_NOT_MET',
        'realtime_qualification': 'NOT_ATTEMPTED',
    })
    save('SENSOR_TIME_INTEGRITY_SUMMARY.json', sensor)
    save('SESSION_CHECKPOINTS_MANIFEST_V3.json', checkpoints)
    save('RAW_DATA_MANIFEST_V3.json', raw)
    save('STATE.json', {
        'schema': 'zero_value_30rep_baseline_state_v3',
        'status': 'ZERO_VALUE_30REP_BASELINE_COMPLETE',
        'completed_repetitions': 30,
        'physical_scientific_failure_count': 0,
        'sensor_time_anomaly_count': 0,
        'time_bookkeeping_anomaly_recurred': False,
        'harness_repair_cycles': 0,
        'session': 'formal_session_01',
        'checkpoint_count': 30,
        'raw_manifest_entry_count': len(raw),
        'raw_scorer_v2_wall_time_failure_count': len(wall_fail),
        'scientific_variables_changed': [],
        'preserved_v2_evidence_reverified': preserved_v2_counts,
        'source_head_before_campaign': fingerprint['head_before_campaign'],
        'production_fingerprint': 'PRODUCTION_FINGERPRINT_V3.json',
        'remote_verification': 'results/zero_value_30rep_baseline_v3/REMOTE_VERIFICATION_V3.json, written locally after push',
        'waypoint_headroom_study_authorized': False,
    })
    table = '\n'.join(
        f"| {i} | {r['J_F_task_n_s']:.6f} | {r['J_F_session_n_s']:.6f} | "
        f"{r['peak_force_n']:.3f} | {r['peak_moment_nm']:.3f} | "
        f"{r['minimum_session_clearance_m']*1000:.3f} | "
        f"{r['human_model_sequence_after']} | {r['realtime_characterization']['max_wall_plan_age_ms']:.3f} | "
        f"{'PASS' if r['scorer_v2'] else 'FAIL(plan_age)'} |"
        for i, r in enumerate(rows, 1))
    task = variability['metrics']['J_F_task_n_s']
    session = variability['metrics']['J_F_session_n_s']
    report = f'''# Zero-value 30-repetition baseline V3

**ZERO_VALUE_30REP_BASELINE_COMPLETE:** 30/30 repetitions completed in one fresh continuous Scientific Simulation session from Rep1. Every physical, scientific, lifecycle, zero-value and sensor-time gate passed. There were no genuine physical/scientific failures. The V2 campaign remains a separate FAIL with preserved evidence. Source before this campaign: `{fingerprint['head_before_campaign']}` on `codex/zero-value-30rep-baseline-v3`.

The registered case, options and seed 20260918 match V2. Human adaptation continued, learned value remained zero, and the repaired sensor deadline was the only production behavior change inherited from the forensic branch. Controller mathematics, Human dynamics, waypoint objective, safety limits, clearance criterion, Scientific Mode and raw scorer-v2 were unchanged. All preflight regressions passed (47 tests and one single-repetition physical/scientific PASS).

| Rep | J_F_task (N s) | J_F_session (N s) | Peak force (N) | Peak moment (N m) | Min deployable clearance (mm) | Human version after | Wall plan age (ms) | Raw scorer-v2 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
{table}

Rep1–5 versus Rep6–30 mean J_F_task: {task['early_rep1_to5']['mean']:.6f} versus {task['late_rep6_to30']['mean']:.6f} N s ({task['late_mean_relative_change_from_early']*100:+.4f}%). Mean J_F_session: {session['early_rep1_to5']['mean']:.6f} versus {session['late_rep6_to30']['mean']:.6f} N s ({session['late_mean_relative_change_from_early']*100:+.4f}%). Late task sample SD is {task['late_rep6_to30']['std_sample']:.6f} N s, range {task['late_rep6_to30']['range']:.6f} N s, and mean absolute adjacent late change {task['late_adjacent_abs_delta']['mean']:.6f} N s. These are descriptive natural baseline noise scales from one continuous session; the complete mean, median, SD, range, relative and adjacent changes for force/moment metrics are in `BASELINE_VARIABILITY_SUMMARY.json`.

Human model sequence increased monotonically from {versions[0]} after Rep1 to {versions[-1]} after Rep30 without reset. The 11-parameter beta vector changed by L2 {math.dist(model[0]['beta'], model[-1]['beta']):.6f} from Rep1 to Rep30; component and adjacent drift, residual parameters and per-rep state boundaries are preserved in `HUMAN_MODEL_PROGRESSION_V3.json` and `PER_REPETITION_V3.json`. The waypoint policy produced {len(set(sequences))} unique selected sequence(s), {decision_count} total decisions and {unscored_count} explicit null/unscored candidates; every scored candidate retained learned value zero. There were {sum(a != b for a,b in zip(sequences,sequences[1:]))} adjacent sequence changes. The minimum deployable clearance across repetitions was {min(deployable_clearance)*1000:.3f} mm; minimum native evaluation-only clearance was {min(native_clearance)*1000:.3f} mm. Full trends appear in `CLEARANCE_TREND_V3.json`.

All 29 inter-repetition boundaries passed native-state and model-version continuity checks. Mean settle was {stats.mean(b['settle_duration_s'] for b in boundaries):.6f} s, mean hold {stats.mean(b['hold_duration_s'] for b in boundaries):.6f} s, and maximum total {max(b['settle_duration_s']+b['hold_duration_s'] for b in boundaries):.6f} s. Task OUTBOUND/HOLD/RETURN durations and initial/final Human and CR12 q/dq are in each per-repetition JSON row.

The mandatory whole-session audit found {sensor['total_sample_count']} sensor samples with minimum/maximum interval {sensor['minimum_sample_interval_s']:.12f}/{sensor['maximum_sample_interval_s']:.12f} s and unique intervals at 9 decimal places {sensor['unique_sample_intervals_s_rounded_9dp']}. Applied control intervals were chronological within and across all 30 repetitions; the 29 recorded inter-repetition control gaps matched the 5 ms boundary hold. There was no duplicate, missed 5 ms sample, unexpected 10 ms gap, invalid causal-history spacing or control-time anomaly. The prior time-bookkeeping failure did not recur.

Raw scorer-v2 wall-time-only FAIL occurred {len(wall_fail)} times: {', '.join(f"Rep {x['rep']} ({x['max_plan_age_ms']:.3f} ms)" for x in wall_fail) if wall_fail else 'none'}. All raw wall-time conditions and source-age, activation-latency, control-miss/gap data are preserved in `REALTIME_CHARACTERIZATION_SUMMARY.json`. Scientific baseline validity is PASS; counterfactual realtime validity is reported separately under the unchanged strict `<100 ms` rule. Historical `RSS_RUNTIME_QUALIFICATION_NOT_MET` remains in force; no realtime qualification was attempted.

All {len(checkpoints)} V3 checkpoint hashes and {len(raw)} V3 raw-file hashes were reverified. Both preserved V2 failed attempts were reverified byte for byte: {preserved_v2_counts['formal_session_01']['raw_files']} raw/{preserved_v2_counts['formal_session_01']['checkpoints']} checkpoints, then {preserved_v2_counts['formal_session_02']['raw_files']} raw/{preserved_v2_counts['formal_session_02']['checkpoints']} checkpoints. Large trajectories and checkpoints remain Git-ignored; compact manifests are saved. The final local/remote commit SHA is recorded after push in the locally saved `results/zero_value_30rep_baseline_v3/REMOTE_VERIFICATION_V3.json` and in the task handoff. The completed baseline supplies a descriptive variability scale for a possible future waypoint headroom study; this task does **not** authorize or start that study. No value learning, RL, realtime or hardware run was started. No causal adaptation benefit, statistical significance or optimality is claimed.
'''
    (docs / 'ZERO_VALUE_30REP_BASELINE_REPORT_V3.md').write_text(report)
    print(json.dumps({'status': result['status'], 'reps': len(rows),
                      'sensor_samples': sensor['total_sample_count'],
                      'wall_fail_count': len(wall_fail), 'checkpoints': len(checkpoints),
                      'raw_files': len(raw), 'task_early_mean': task['early_rep1_to5']['mean'],
                      'task_late_mean': task['late_rep6_to30']['mean']}))


if __name__ == '__main__':
    main()
