"""Preserve and summarize the stopped formal zero-value baseline attempt."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'stages/stage5_personalized_motion_learning'
RUN = STAGE / 'results/zero_value_30rep_baseline_v1/formal_session_01'
DOC = STAGE / 'docs/zero_value_30rep_baseline_v1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(name, obj):
    (DOC / name).write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def desc(values):
    v = [float(x) for x in values]
    return {'n': len(v), 'mean': statistics.mean(v), 'median': statistics.median(v),
            'std_sample': statistics.stdev(v) if len(v) > 1 else None,
            'variance_sample': statistics.variance(v) if len(v) > 1 else None,
            'minimum': min(v), 'maximum': max(v)}


def finite(obj):
    if isinstance(obj, dict):
        return all(finite(x) for x in obj.values())
    if isinstance(obj, list):
        return all(finite(x) for x in obj)
    return not isinstance(obj, float) or math.isfinite(obj)


def main():
    result = json.loads((RUN / 'session_result.json').read_text())
    rows = json.loads((RUN / 'per_repetition.json').read_text())
    assert result['failure'] == 'rep_07:scorer_v2'
    assert len(rows) == 7 and [r['repetition_index'] for r in rows] == list(range(1, 8))
    assert all(finite(r) and r['status'] == 'COMPLETE' for r in rows)
    assert all(r['physical'] == r['scientific'] == 'PASS' for r in rows)
    assert all(r['scorer_v2'] is True for r in rows[:6])
    assert rows[6]['scorer_v2'] is False and rows[6]['gate_reasons'] == ['scorer_v2']
    assert all(all(v is True for v in r['boundary_audit'].values() if isinstance(v, bool))
               and all(r['boundary_audit']['fresh_transient_objects'].values()) for r in rows)
    assert all(b > a for a, b in zip(
        [r['human_model_sequence_after'] for r in rows],
        [r['human_model_sequence_after'] for r in rows][1:]))
    assert all(r['inter_rep_boundary_after'] is not None for r in rows[:6])
    assert rows[6].get('inter_rep_boundary_after') is None

    scores = [json.loads((RUN / f'rep_{i:02d}/MODE_AWARE_RESULT_V2.json').read_text())
              for i in range(1, 8)]
    assert all(x['physical_task_result']['status'] == 'PASS' and
               x['scientific_validity']['status'] == 'PASS' for x in scores)
    conditions = scores[-1]['raw_scorer_v2']['conditions']
    assert [k for k, v in conditions.items() if not v] == ['plan_age']
    ages = [x['raw_scorer_v2']['maximum_plan_activation_age_ms'] for x in scores]
    assert ages[-1] > 100 and all(x < 100 for x in ages[:6])

    decision_count = unscored_count = 0
    for i, row in enumerate(rows, 1):
        decisions = json.loads((RUN / f'rep_{i:02d}/zero_value_waypoint_decisions.json').read_text())
        assert len(decisions) == row['number_of_waypoint_decisions']
        for d in decisions:
            assert d['learned_value'] == 0 and d['RL'] == 'OFF'
            decision_count += 1
            for c in d['candidate_set']:
                if c['evaluated']:
                    assert c['learned_value'] == 0
                else:
                    assert c['learned_value'] is None and c['short_term_total_cost'] is None
                    unscored_count += 1

    checkpoints = json.loads((RUN / 'session_checkpoints_manifest.json').read_text())
    assert len(checkpoints) == 6
    for i, item in enumerate(checkpoints, 1):
        assert item['repetition_index'] == i and sha(RUN / item['path']) == item['sha256']
    raw = json.loads((RUN / 'raw_data_manifest.json').read_text())
    for path, expected in raw.items():
        assert sha(RUN / path) == expected, path

    task = [r['J_F_task_n_s'] for r in rows]
    session = [r['J_F_session_n_s'] for r in rows]
    beta = [np.asarray(r['human_model_after']['beta'], float) for r in rows]
    residual = [np.asarray(r['human_model_after']['state_residual_weights_nm'], float) for r in rows]
    sequences = [tuple(r['waypoint_sequence']) for r in rows]
    boundary = [r['inter_rep_boundary_after'] for r in rows[:6]]
    variability = {
        'schema': 'zero_value_30rep_baseline_variability_v1',
        'status': 'INCOMPLETE_NOT_A_30REP_BASELINE_ESTIMATE',
        'accepted_repetitions': 6, 'failed_repetition': 7,
        'early_rep_1_to_5_J_F_task_n_s': desc(task[:5]),
        'late_rep_6_to_30': None,
        'observed_rep_1_to_7_adjacent_delta_J_F_task_n_s': np.diff(task).tolist(),
        'observed_rep_1_to_7_adjacent_delta_J_F_task_summary_n_s': desc(np.diff(task)),
        'accepted_rep_1_to_6_adjacent_delta_J_F_task_n_s': np.diff(task[:6]).tolist(),
        'accepted_rep_1_to_6_adjacent_abs_delta_J_F_task_summary_n_s': desc(np.abs(np.diff(task[:6]))),
        'waypoint_unique_sequence_count_observed': len(set(sequences)),
        'waypoint_adjacent_change_count_observed': sum(a != b for a, b in zip(sequences, sequences[1:])),
        'model_beta_rep1_to_7_l2_observed': float(np.linalg.norm(beta[-1]-beta[0])),
        'model_residual_rep1_to_7_l2_observed': float(np.linalg.norm(residual[-1]-residual[0])),
    }
    save('BASELINE_VARIABILITY_SUMMARY.json', variability)
    save('HUMAN_MODEL_PROGRESSION.json', [
        {'rep': i, 'start': r['human_model_at_task_start'], 'end': r['human_model_after']}
        for i, r in enumerate(rows, 1)])
    save('WAYPOINT_PROGRESSION.json', [
        {'rep': i, 'sequence': r['waypoint_sequence'], 'decision_count': r['number_of_waypoint_decisions']}
        for i, r in enumerate(rows, 1)])
    save('BOUNDARY_TIMING_SUMMARY.json', {
        'status': 'PARTIAL_SIX_BOUNDARIES',
        'settle_duration_s': desc([b['settle_duration_s'] for b in boundary]),
        'hold_duration_s': desc([b['hold_duration_s'] for b in boundary]),
        'abnormal_after_repetitions_over_0p05_s': [i for i, b in enumerate(boundary, 1)
            if b['settle_duration_s'] + b['hold_duration_s'] > 0.05],
        'rep7_following_boundary': None,
    })
    save('PER_REPETITION.json', rows)
    with (DOC / 'PER_REPETITION.csv').open('w', newline='') as f:
        cols = ['repetition_index', 'status', 'physical', 'scientific', 'scorer_v2',
                'J_F_task_n_s', 'J_F_session_n_s', 'peak_force_n', 'peak_moment_nm',
                'moment_integral_nm_s', 'completion_time_s', 'human_model_sequence_after',
                'number_of_waypoint_decisions']
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows({k: r[k] for k in cols} for r in rows)
    save('RAW_DATA_MANIFEST.json', raw)
    save('SESSION_CHECKPOINTS_MANIFEST.json', checkpoints)
    save('PRODUCTION_FINGERPRINT.json', {
        'frozen_618_file_fingerprint': '56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb',
        'validated_repetition_boundary_runtime_sha256': sha(STAGE / 'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py'),
        'validated_session_state_sha256': sha(STAGE / 'src/traction_mpc_stage5/full3d_adaptive_integration_v1/session_state.py'),
        'baseline_harness_sha256': sha(STAGE / 'scripts/high_rom_v1/run_zero_value_30rep_baseline.py'),
        'checkpoint_helper_sha256': sha(STAGE / 'scripts/high_rom_v1/zero_value_30rep_checkpoint.py'),
        'contract_sha256': sha(DOC / 'ZERO_VALUE_30REP_BASELINE_CONTRACT.json'),
    })
    save('STATE.json', {
        'schema': 'zero_value_30rep_baseline_state_v1',
        'status': 'ZERO_VALUE_30REP_BASELINE_FAIL',
        'reason': 'Rep 7 raw scorer-v2 plan_age failed: 1660.051796 ms >= frozen 100 ms limit',
        'raw_harness_status': result['status'],
        'repetitions_attempted': 7, 'repetitions_all_gates_passed': 6,
        'planned_repetitions': 30, 'checkpoint_count': 6,
        'raw_manifest_entry_count': len(raw), 'zero_value_decision_count': decision_count,
        'unscored_candidate_count': unscored_count,
        'scientific_variables_changed': [], 'source_head': 'f0d87e386caeaf88ddc0f52c5c8335e8efa71098',
        'commit_and_push_condition_met': False,
    })
    table = '\n'.join(
        f"| {i} | {r['J_F_task_n_s']:.6f} | {r['J_F_session_n_s']:.6f} | "
        f"{r['peak_force_n']:.6f} | {r['peak_moment_nm']:.6f} | {ages[i-1]:.3f} | "
        f"{r['human_model_sequence_after']} | {'PASS' if r['scorer_v2'] else 'FAIL'} |"
        for i, r in enumerate(rows, 1))
    report = f'''# Zero-value 30-repetition baseline v1 — stopped formal attempt

Final status: **ZERO_VALUE_30REP_BASELINE_FAIL**. One formal continuous session attempted Rep 1–7; Rep 1–6 passed all required gates, and Rep 7 completed the task with physical and Scientific Simulation PASS but **raw scorer-v2 FAIL**. The frozen stop rule ended the session before Rep 8. No second formal session or targeted repeat was run. The original harness result says `ZERO_VALUE_30REP_BASELINE_PARTIAL` because it counted completed task records; it is retained unchanged. This report adjudicates the failed required gate as FAIL.

Frozen source HEAD `f0d87e386caeaf88ddc0f52c5c8335e8efa71098`; frozen 618-file production fingerprint `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`. The validated boundary runtime has its separately recorded SHA in `PRODUCTION_FINGERPRINT.json`. One registered low-ROM ordinary case and unchanged options/seed were used on Y9000P Ubuntu WSL2. No controller, objective, Human dynamics, safety threshold or scientific configuration changed.

| Rep | J_F_task (N s) | J_F_session (N s) | Peak force (N) | Peak moment (N m) | Max plan age (ms) | Human version | Scorer-v2 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
{table}

The sole failed scorer-v2 condition in Rep 7 is `plan_age`: maximum source-to-activation wall age **{ages[-1]:.3f} ms**, versus the unchanged **100 ms** raw-scorer threshold. Rep 1–6 maxima were {min(ages[:6]):.3f}–{max(ages[:6]):.3f} ms. All other raw scorer conditions passed. The mode-aware Scientific Simulation validity remained PASS because its simulation-time chronology, version and receipt checks passed; physical validity also remained PASS. Raw scorer-v2 PASS was explicitly required by the frozen baseline contract, so the session cannot be promoted. This is a measured gate failure, not a logging defect. The raw scorer result and its wall-time criterion were not edited after observation.

Rep 1–5 mean J_F_task was **{statistics.mean(task[:5]):.6f} N s**. A Rep 6–30 late-phase mean, variance and relative change cannot be computed: only Rep 6 passed before the Rep 7 failure. The 7 observed task/session values and first-six accepted adjacent differences are retained in `PER_REPETITION.csv` and `BASELINE_VARIABILITY_SUMMARY.json`; they are not a complete natural-variability estimate.

Human model version increased from {rows[0]['human_model_sequence_after']} after Rep 1 to {rows[-1]['human_model_sequence_after']} after Rep 7, with no reset detected. The seven observed repetitions used {len(set(sequences))} waypoint sequence pattern(s). All {decision_count} decisions kept learned value zero; {unscored_count} unscored candidate records used explicit null score/value semantics. The six outgoing boundaries settled in 0 s and held for 0.005 s each; none exceeded 0.05 s. Native state continuity and fresh episode lifecycle checks passed through Rep 7. Rep 7 has no outgoing boundary because the session stopped.

The **six** end-of-repetition checkpoints and **{len(raw)}** raw-file hashes were reverified. Rep 7 has no promotable checkpoint. Large trajectories and checkpoint payloads remain in Git-ignored local results; compact manifests, model and waypoint progression, boundary timings, and per-repetition data are in this directory. Since 30/30 did not pass, the requested commit/push condition was not met. A waypoint headroom study should **not** use this attempt as its complete 30-repetition baseline; first decide a new, separately frozen protocol for the scorer-v2 wall-age criterion.
'''
    (DOC / 'ZERO_VALUE_30REP_BASELINE_REPORT.md').write_text(report)
    print(json.dumps({'status': 'ZERO_VALUE_30REP_BASELINE_FAIL', 'attempted': 7,
                      'accepted': 6, 'checkpoints': len(checkpoints),
                      'raw_manifest_entries': len(raw)}))


if __name__ == '__main__':
    main()
