"""Verify and report both preserved failed V2 attempts without changing raw data."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'stages/stage5_personalized_motion_learning'
DOC = STAGE / 'docs/zero_value_30rep_baseline_v2'
RUN = STAGE / 'results/zero_value_30rep_baseline_v2/formal_session_02'
sys.path[:0] = [str(STAGE / 'src'),
                str(ROOT / 'stages/stage4_adaptive_control/src'),
                str(ROOT / 'stages/stage3_full3d/src')]
from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import zero_value_decision_rows


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(name, obj):
    (DOC / name).write_text(json.dumps(obj, indent=2, sort_keys=True,
                                      allow_nan=False) + '\n')


def desc(values):
    v = [float(x) for x in values]
    if not v or not all(math.isfinite(x) for x in v):
        raise ValueError('invalid descriptive data')
    return {'n': len(v), 'mean': statistics.mean(v), 'median': statistics.median(v),
            'std_sample': statistics.stdev(v) if len(v) > 1 else None,
            'variance_sample': statistics.variance(v) if len(v) > 1 else None,
            'minimum': min(v), 'maximum': max(v)}


def finite_tree(obj):
    if isinstance(obj, dict):
        return all(finite_tree(v) for v in obj.values())
    if isinstance(obj, list):
        return all(finite_tree(v) for v in obj)
    return not isinstance(obj, float) or math.isfinite(obj)


def main():
    result = json.loads((RUN / 'session_result.json').read_text())
    rows = json.loads((RUN / 'per_repetition.json').read_text())
    if (result['status'] != 'ZERO_VALUE_30REP_BASELINE_FAIL'
            or len(rows) != 13 or [r['repetition_index'] for r in rows] != list(range(1, 14))):
        raise RuntimeError('unexpected stopped V2 result')
    if not all(r['status'] == 'COMPLETE' and r['overall_baseline_scientific_result'] == 'PASS'
               and r['physical_task_validity'] == 'PASS'
               and r['scientific_validity'] == 'PASS' and not r['gate_reasons']
               and finite_tree(r) for r in rows):
        raise RuntimeError('accepted first 13 repetition records invalid')
    if not all(all(v is True for v in r['boundary_audit'].values() if isinstance(v, bool))
               and all(r['boundary_audit']['fresh_transient_objects'].values()) for r in rows):
        raise RuntimeError('observed lifecycle audit failure before Rep 14')
    versions = [r['human_model_sequence_after'] for r in rows]
    if not all(b > a for a, b in zip(versions, versions[1:])):
        raise RuntimeError('Human model version reset in accepted prefix')
    boundary = [r.get('inter_rep_boundary_after') for r in rows]
    if any(x is None for x in boundary):
        raise RuntimeError('missing outgoing boundary in accepted prefix')

    launch14 = json.loads((RUN / 'rep_14/HIGH_ROM_CASE_RESULT.json').read_text())
    summary14 = json.loads((RUN / 'rep_14/summary.json').read_text())
    mode14 = json.loads((RUN / 'rep_14/MODE_AWARE_RESULT_V2.json').read_text())
    expected_abort = 'LOW_LEVEL_EXECUTION:INCREMENTAL_CLEARANCE_LOST_ALIGNED_CAUSAL_HISTORY'
    if (launch14['status'] != 'ABORTED' or launch14['abort_reason'] != expected_abort
            or summary14['status'] != 'ABORTED' or summary14['abort_reason'] != expected_abort
            or mode14['physical_task_result']['status'] != 'FAIL'
            or mode14['scientific_validity']['status'] != 'FAIL'):
        raise RuntimeError('Rep 14 real abort not proven')
    failed_decisions = zero_value_decision_rows(summary14['decisions'])
    for decision in failed_decisions:
        for candidate in decision['candidate_set']:
            if not candidate['evaluated']:
                candidate['learned_value'] = None
    save('REP_14_ZERO_VALUE_DECISIONS.json', failed_decisions)
    save('REP_14_FAILURE.json', {
        'repetition_index': 14,
        'status': launch14['status'],
        'abort_reason': expected_abort,
        'physical_task_validity': mode14['physical_task_result']['status'],
        'physical_reasons': mode14['physical_task_result']['reasons'],
        'scientific_validity': mode14['scientific_validity']['status'],
        'scientific_reasons': mode14['scientific_validity']['reasons'],
        'raw_scorer_v2_pass': mode14['raw_scorer_v2']['pass'],
        'raw_scorer_v2_failed_conditions': [k for k, v in mode14['raw_scorer_v2']['conditions'].items() if not v],
        'maximum_wall_plan_age_ms': mode14['raw_scorer_v2']['maximum_plan_activation_age_ms'],
        'waypoint_decisions_before_abort': len(failed_decisions),
        'harness_followup_exception': result['failure'],
        'classification': 'genuine controller/scientific abort; no restart',
    })
    # Verify the preserved Rep 13 -> Rep 14 native-state boundary.
    b13 = json.loads((RUN / 'boundary_13_to_14.json').read_text())
    a14 = json.loads((RUN / 'rep_14/runtime_artifacts.json').read_text())
    native14 = a14['wall_physics']['initial_native_boundary_evaluation_only']
    if (not np.array_equal(b13['terminal_native_qpos_evaluation_only'],
                           rows[-1]['final_native_state_evaluation_only']['qpos'])
            or not np.array_equal(b13['settled_native_qpos_evaluation_only'],
                                  native14['qpos_evaluation_only'])
            or not np.array_equal(b13['settled_native_qvel_evaluation_only'],
                                  native14['qvel_evaluation_only'])):
        raise RuntimeError('Rep 13 -> 14 physical boundary discontinuity')

    raw = json.loads((RUN / 'raw_data_manifest.json').read_text())
    checkpoints = json.loads((RUN / 'session_checkpoints_manifest.json').read_text())
    if len(checkpoints) != 13:
        raise RuntimeError('checkpoint count invalid')
    for i, item in enumerate(checkpoints, 1):
        if item['repetition_index'] != i or sha(RUN / item['path']) != item['sha256']:
            raise RuntimeError(f'checkpoint hash mismatch at rep {i}')
    for path, expected in raw.items():
        if sha(RUN / path) != expected:
            raise RuntimeError(f'raw hash mismatch: {path}')
    save('RAW_DATA_MANIFEST_V2.json', raw)
    save('SESSION_CHECKPOINTS_MANIFEST_V2.json', checkpoints)

    task = [r['J_F_task_n_s'] for r in rows]
    session = [r['J_F_session_n_s'] for r in rows]
    sequences = [tuple(r['waypoint_sequence']) for r in rows]
    ages = [r['realtime_characterization']['max_wall_plan_age_ms'] for r in rows]
    raw_wall_fails = [{'rep': r['repetition_index'], 'plan_age_ms': age}
                      for r, age in zip(rows, ages) if r['scorer_v2'] is False]
    counterfactual_fails = [r['repetition_index'] for r in rows
        if r['realtime_characterization']['counterfactual_realtime_validity'] == 'FAIL']
    decision_count = 0
    unscored_count = 0
    for i, row in enumerate(rows, 1):
        decisions = json.loads((RUN / f'rep_{i:02d}/zero_value_waypoint_decisions.json').read_text())
        if len(decisions) != row['number_of_waypoint_decisions']:
            raise RuntimeError(f'decision count mismatch rep {i}')
        for d in decisions:
            decision_count += 1
            if d['learned_value'] != 0 or d['RL'] != 'OFF':
                raise RuntimeError(f'value invariant failed rep {i}')
            for candidate in d['candidate_set']:
                if candidate['evaluated']:
                    if candidate['learned_value'] != 0:
                        raise RuntimeError('nonzero candidate learned value')
                else:
                    unscored_count += 1
                    if candidate['learned_value'] is not None:
                        raise RuntimeError('unscored candidate value not null')
    save('PER_REPETITION_V2.json', rows)
    cols = ['repetition_index', 'status', 'physical_task_validity',
            'scientific_validity', 'overall_baseline_scientific_result',
            'scorer_v2', 'J_F_task_n_s', 'J_F_session_n_s', 'peak_force_n',
            'moment_integral_nm_s', 'peak_moment_nm', 'completion_time_s',
            'minimum_session_clearance_m', 'human_model_sequence_after',
            'number_of_waypoint_decisions']
    with (DOC / 'PER_REPETITION_V2.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=cols)
        writer.writeheader()
        writer.writerows({key: row[key] for key in cols} for row in rows)
    save('BASELINE_VARIABILITY_SUMMARY.json', {
        'schema': 'zero_value_30rep_baseline_variability_v2',
        'status': 'INCOMPLETE_NOT_A_30REP_BASELINE_ESTIMATE',
        'accepted_repetitions': 13, 'failed_repetition': 14,
        'early_rep1_to5_J_F_task_n_s': desc(task[:5]),
        'early_rep1_to5_J_F_session_n_s': desc(session[:5]),
        'observed_rep6_to13_J_F_task_n_s': desc(task[5:]),
        'observed_rep6_to13_J_F_session_n_s': desc(session[5:]),
        'late_rep6_to30': None,
        'accepted_adjacent_delta_J_F_task_n_s': np.diff(task).tolist(),
        'accepted_adjacent_delta_J_F_session_n_s': np.diff(session).tolist(),
        'accepted_adjacent_abs_delta_J_F_task_n_s': desc(np.abs(np.diff(task))),
        'waypoint_unique_sequence_count_observed': len(set(sequences)),
        'waypoint_adjacent_change_count_observed': sum(a != b for a, b in zip(sequences, sequences[1:])),
    })
    save('REALTIME_CHARACTERIZATION_SUMMARY.json', {
        'schema': 'zero_value_30rep_realtime_characterization_v2',
        'status': 'PARTIAL_13_ACCEPTED_PLUS_REP14_ABORT',
        'execution_mode': 'SCIENTIFIC_SIMULATION',
        'raw_scorer_v2_wall_time_failures_in_accepted_prefix': raw_wall_fails,
        'raw_scorer_v2_wall_time_failure_count_in_accepted_prefix': len(raw_wall_fails),
        'counterfactual_realtime_fail_repetitions': counterfactual_fails,
        'maximum_wall_plan_age_ms_in_accepted_prefix': max(ages),
        'per_repetition_wall_plan_age_ms': ages,
        'rep14_raw_scorer_failure_is_physical_or_terminal': True,
        'strict_realtime_plan_age_limit_ms': 100,
        'realtime_qualification': 'NOT_ATTEMPTED',
    })
    save('HUMAN_MODEL_PROGRESSION_V2.json', [
        {'rep': i, 'start': row['human_model_at_task_start'], 'end': row['human_model_after']}
        for i, row in enumerate(rows, 1)])
    save('WAYPOINT_PROGRESSION_V2.json', [
        {'rep': i, 'sequence': row['waypoint_sequence'],
         'number_of_decisions': row['number_of_waypoint_decisions']}
        for i, row in enumerate(rows, 1)])
    durations = [b['settle_duration_s'] + b['hold_duration_s'] for b in boundary]
    save('BOUNDARY_TIMING_SUMMARY_V2.json', {
        'observed_boundary_count': len(boundary),
        'settle_duration_s': desc([b['settle_duration_s'] for b in boundary]),
        'hold_duration_s': desc([b['hold_duration_s'] for b in boundary]),
        'total_duration_s': desc(durations),
        'abnormal_after_repetition_over_0p05_s': [i for i, d in enumerate(durations, 1) if d > 0.05],
        'rep13_to14_physical_state_continuous': True,
    })
    save('PRODUCTION_FINGERPRINT_V2.json', {
        'v1_negative_checkpoint': '22c6859214256a46e75d47ad153ed9be3c3a2f72',
        'frozen_618_file_fingerprint': '56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb',
        'validated_boundary_runtime_sha256': sha(STAGE / 'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py'),
        'unchanged_mode_aware_evaluator_sha256': sha(STAGE / 'scripts/high_rom_v1/evaluate_execution_mode.py'),
        'unchanged_raw_scorer_sha256': sha(STAGE / 'scripts/high_rom_v1/summarize_phase_b.py'),
        'baseline_v2_harness_sha256': sha(STAGE / 'scripts/high_rom_v1/run_zero_value_30rep_baseline_v2.py'),
        'baseline_v2_acceptance_sha256': sha(STAGE / 'scripts/high_rom_v1/baseline_acceptance_v2.py'),
        'baseline_v2_accounting_sha256': sha(STAGE / 'scripts/high_rom_v1/baseline_accounting_v2.py'),
        'baseline_v2_contract_sha256': sha(DOC / 'ZERO_VALUE_30REP_BASELINE_CONTRACT_V2.json'),
    })
    save('STATE.json', {
        'schema': 'zero_value_30rep_baseline_state_v2',
        'status': 'ZERO_VALUE_30REP_BASELINE_FAIL',
        'reason': expected_abort,
        'accepted_repetitions': 13, 'failed_repetition': 14,
        'planned_repetitions': 30,
        'harness_repair_cycles': 1,
        'attempts': ['formal_session_01', 'formal_session_02'],
        'checkpoint_count_latest_attempt': 13,
        'raw_manifest_entry_count_latest_attempt': len(raw),
        'scientific_variables_changed': [],
        'true_scientific_or_physical_failure': True,
        'commit_and_push_condition_met': False,
    })
    table = '\n'.join(
        f"| {i} | {r['J_F_task_n_s']:.6f} | {r['J_F_session_n_s']:.6f} | "
        f"{r['peak_force_n']:.3f} | {r['peak_moment_nm']:.3f} | "
        f"{r['human_model_sequence_after']} | {ages[i-1]:.3f} | "
        f"{'PASS' if r['scorer_v2'] else 'FAIL(plan_age)'} |"
        for i, r in enumerate(rows, 1))
    wall_text = (', '.join(f"Rep {x['rep']} ({x['plan_age_ms']:.3f} ms)"
                           for x in raw_wall_fails) if raw_wall_fails else 'none')
    report = f'''# Zero-value 30-repetition baseline V2 — stopped formal campaign

Final status: **ZERO_VALUE_30REP_BASELINE_FAIL**. Replacement attempt `formal_session_02` accepted Rep 1–13 in one continuous Scientific Simulation session. Rep 14 aborted in OUTBOUND with **`{expected_abort}`**. Its physical validity, scientific validity and raw scorer-v2 are all FAIL; this is a genuine controller/scientific stop condition. Rep 15–30 were not run. No further repair or restart was attempted.

The earlier V2 `formal_session_01` stopped at Rep 11 due a fixed-interval force bookkeeping defect, documented in `V2_REPAIR_01.md` with 113 raw hashes and 10 checkpoint hashes preserved. One permitted harness repair passed 18 regression tests; `formal_session_02` restarted fresh at Rep 1. The V1 failed baseline remains preserved at local commit `22c6859214256a46e75d47ad153ed9be3c3a2f72`.

Frozen source ancestry `f0d87e386caeaf88ddc0f52c5c8335e8efa71098`; production fingerprint `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`. The validated boundary/runtime and V2 harness hashes appear in `PRODUCTION_FINGERPRINT_V2.json`. The same registered case, options and seed ran on Y9000P Ubuntu WSL2. Controller mathematics, Human dynamics, waypoint objective, Scientific scheduler semantics and safety thresholds were not changed.

| Rep | J_F_task (N s) | J_F_session (N s) | Peak force (N) | Peak moment (N m) | Human version after | Wall plan age (ms) | Raw scorer-v2 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
{table}

Rep 14 has no accepted J_F_task/J_F_session value: it aborted after {summary14['task']['physics_duration_s']:.6f} s of OUTBOUND. The raw session result reports an evaluation exception from a duplicate ABORTED terminal timestamp; the preserved launch and summary both give the earlier true abort reason. The exception did not cause the physical/scientific failure. `REP_14_FAILURE.json` records both events; raw data was not rewritten.

Rep 1–5 mean task cost was **{statistics.mean(task[:5]):.6f} N s**. The observed Rep 6–13 task mean was **{statistics.mean(task[5:]):.6f} N s**, but Rep 6–30 late-phase mean, variance and relative change cannot be estimated. `BASELINE_VARIABILITY_SUMMARY.json` labels the 13-repetition prefix incomplete; it is not a 30-repetition natural-variability baseline or a headroom threshold.

Human model version increased monotonically from {versions[0]} after Rep 1 to {versions[-1]} after Rep 13 without reset. The accepted prefix had {len(set(sequences))} unique waypoint sequence pattern(s). All {decision_count} accepted-rep decisions kept learned value zero, with {unscored_count} explicitly null/unscored candidates; {len(failed_decisions)} additional zero-value decisions are preserved for aborted Rep 14. Thirteen outgoing settle/hold boundaries completed, including the physically continuous Rep 13→14 transition. Their mean settle was {statistics.mean(b['settle_duration_s'] for b in boundary):.6f} s and mean hold {statistics.mean(b['hold_duration_s'] for b in boundary):.6f} s; maximum total was {max(durations):.6f} s.

Raw scorer-v2 wall-time-only FAIL among accepted repetitions occurred {len(raw_wall_fails)} time(s): {wall_text}. Maximum accepted-prefix wall plan age was {max(ages):.3f} ms. Those events remain counterfactual realtime failures under the unchanged strict `<100 ms` rule but did not contaminate scientific trajectories. Rep 14's raw scorer failure has physical/terminal causes and is not reclassified as wall-only.

All {len(checkpoints)} latest-attempt checkpoint hashes and {len(raw)} raw-file hashes were reverified. Large trajectories/checkpoints remain Git-ignored. Compact manifests, per-repetition CSV/JSON, model/waypoint progression, boundary and realtime summaries are saved here. The 30/30 completion condition was not met, so no V2 commit or push was made; remote V2 SHA does not exist. **Do not enter waypoint headroom study from this failed baseline.** No value learning, RL or hardware work was started.
'''
    (DOC / 'ZERO_VALUE_30REP_BASELINE_REPORT_V2.md').write_text(report)
    print(json.dumps({'status': 'ZERO_VALUE_30REP_BASELINE_FAIL',
                      'accepted': 13, 'failed_rep': 14,
                      'raw_wall_fails_accepted': len(raw_wall_fails),
                      'checkpoints': len(checkpoints), 'raw_files': len(raw)}))


if __name__ == '__main__':
    main()
