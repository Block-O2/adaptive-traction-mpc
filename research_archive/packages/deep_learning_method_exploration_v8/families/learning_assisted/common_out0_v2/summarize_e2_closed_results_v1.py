"""Read-only closed E2 output aggregation. No model/NumPy/NPZ imports or calls."""
from pathlib import Path
from collections import defaultdict, Counter
import hashlib
import json
import math
import os
import resource
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def mean(values):
    return None if not values else math.fsum(values) / len(values)


def scope(row):
    return 'ALL_DEVELOPMENT' if row['fold'] == 'ALL_DEVELOPMENT' else 'LEAVE_CASE_OUT'


def aggregate(rows, by_case):
    groups = defaultdict(list)
    for row in rows:
        groups[(scope(row), row['domain'], row['method'], row['horizon_s'])].append(row)
    answer = []
    for (fold, domain, method, horizon), items in sorted(groups.items()):
        count = sum(r['observed_recipes'] for r in items)
        effects = {}
        for cost in ('JF', 'JM'):
            pairs = sum(r['observed_recipes'] - 1 for r in items)
            mae = math.fsum(r['cost_effects'][cost]['paired_MAE'] *
                           (r['observed_recipes'] - 1) for r in items) / pairs
            zero = math.fsum(r['cost_effects'][cost]['zero_effect_MAE'] *
                            (r['observed_recipes'] - 1) for r in items) / pairs
            non = sum(r['cost_effects'][cost]['true_nontie_count'] for r in items)
            correct = sum(r['cost_effects'][cost]['sign_correct_count'] for r in items)
            effects[cost] = dict(paired_MAE=mae, zero_effect_MAE=zero,
                skill_vs_zero=None if zero <= (1e-6 if cost == 'JF' else 1e-7) else 1. - mae / zero,
                true_nontie_count=non, true_tie_count=pairs - non,
                sign_correct_count=correct, sign_accuracy=None if non == 0 else correct / non)
        ranking = {k: sum(r['ranking'][k] for r in items)
                   for k in ('concordant', 'discordant', 'predicted_ties', 'true_ties')}
        n = ranking['concordant'] + ranking['discordant'] + ranking['predicted_ties']
        ranking['pairwise_accuracy'] = None if n == 0 else ranking['concordant'] / n
        qualifications = Counter();choice_B = 0;choice_delta = {'JF': [], 'JM': []}
        for row in items:
            qualifications[str(row['actual_original_full_qualification_of_choice_evaluation_only'])] += 1
            ids = by_case[row['case_sha256_evaluation_only']]
            assert len(ids) == row['observed_recipes']
            choice = row['hypothetical_window_min_choice'];choice_B += choice == row['B_attempt_id']
            position = ids.index(choice)
            for cost in ('JF', 'JM'):
                choice_delta[cost].append(row['paired_actual_' + cost + ('_N_s' if cost == 'JF' else '_Nm_s')][position])
        answer.append(dict(scope=fold, domain=domain, method=method, horizon_s=horizon,
            case_rows=len(items), actual_recipe_rows=count,
            target_semantics=items[0]['target_semantics'],
            channel_units=items[0]['channel_units'],
            cost_effects=effects, ranking=ranking,
            endpoint_channel_MAE_physical_units=[math.fsum(
                r['channel_MAE_physical_units'][k] * r['observed_recipes'] for r in items) / count
                for k in range(16)],
            hypothetical_choice_B_count=choice_B,
            hypothetical_choice_actual_mean_deltaJF=mean(choice_delta['JF']),
            hypothetical_choice_actual_mean_deltaJM=mean(choice_delta['JM']),
            hypothetical_window_regret_mean=mean([r['window_JF_regret'] for r in items]),
            original_full_qualification_of_choice_RETROSPECTIVE=dict(qualifications),
            negative_absolute_window_predictions={cost: sum(
                (r['negative_absolute_window_cost_predictions'] or {}).get(cost, 0) for r in items)
                for cost in ('JF', 'JM')},
            future_qualification_mask_used=False))
    return answer


def main():
    start = time.monotonic();cpu = time.process_time()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    out = HERE / 'fits/e2_v1'
    end = load(out / 'RUN_END.json');execution = load(HERE / 'FIT_E2_EXTERNAL_V1.execution.json')
    assert end['status'] == 'PASS_E2_MATCHED_TIME_DOMAIN_SOURCE_BOUND_DEVELOPMENT_ONLY'
    assert execution['exit_code'] == 0 and execution['all_observed_pid_startticks_closed']
    assert all(not Path('/proc', str(p['pid'])).exists() for p in execution['process_identities'])
    contract = load(HERE / 'FIT_E2_FROZEN_CONTRACT_V1.json')
    assert end['counters'] == contract['expected_success_counters']
    sources = load(HERE / 'FIT_E2_SOURCE_MANIFEST_V1.json')
    assert all(sha(ROOT / relative) == expected for relative, expected in sources['files_sha256'].items())
    assert sha(out / 'FROZEN_E2_BUNDLE.json') == end['frozen_bundle_sha256']
    index = load(HERE / 'data/fulltask_e2_v1/INDEX.json');by_case = defaultdict(list)
    for row in index['rows']:
        by_case[row['evaluation_only']['case_sha256']].append(row['id'])
    direct = load(out / 'DIRECT_HEAD_RESULTS.json')['rows']
    integrals = load(out / 'ABSOLUTE_WRENCH_INTEGRAL_RESULTS.json')
    assert len(direct) == 2880 and len(integrals['rows']) == 2240
    direct_summary = aggregate(direct, by_case)
    integral_summary = aggregate(integrals['rows'], by_case)
    del direct
    trajectory = defaultdict(lambda: dict(count=0, sums=[0.] * 16))
    with (out / 'TRAJECTORY_ERRORS.jsonl').open() as stream:
        for line in stream:
            record = json.loads(line)
            for row in record['rows']:
                for error in row['errors']:
                    key = (scope(record), record['domain'], record['method'], error['horizon_s'])
                    item = trajectory[key];item['count'] += 1
                    for k in range(16):item['sums'][k] += error['channel_MAE_to_h'][k]
    trajectory_summary = [dict(scope=k[0], domain=k[1], method=k[2], horizon_s=k[3],
        prediction_rows=v['count'], interval_channel_MAE_physical_units=[x / v['count'] for x in v['sums']])
        for k, v in sorted(trajectory.items())]
    mismatch = defaultdict(lambda: {'JF': [], 'JM': []})
    for row in integrals['cost_head_consistency']:
        key = (scope(row), row['domain'], row['method'], row['horizon_s'])
        for cost in ('JF', 'JM'):
            mismatch[key][cost].extend(abs(v) for v in row['delta' + cost + '_head_minus_integrated'])
    mismatch_summary = [dict(scope=k[0], domain=k[1], method=k[2], horizon_s=k[3],
        predicted_action_effect_head_minus_integrated_wrench_MAE={cost: mean(values) for cost, values in v.items()})
        for k, v in sorted(mismatch.items())]
    result = dict(schema='v8.E2.closed_actual_summary.v1',
        status='PASS_READONLY_AGGREGATION_NOT_NEW_PREDICTION',
        frozen_bundle_sha256=end['frozen_bundle_sha256'],
        fit_counters=end['counters'], fit_internal_resources={k: end[k] for k in ('wall_s', 'CPU_s', 'RSS_KiB')},
        direct_summary=direct_summary, absolute_wrench_integral_summary=integral_summary,
        trajectory_interval_summary=trajectory_summary, head_integral_effect_disagreement=mismatch_summary,
        head_integral_disagreement_averages_include_B_zero_effect=True,
        paired_integrals='NOT_APPLICABLE_NO_FUTURE_TRUE_B',
        full_qualification_retrospective_only=True,
        metadata_note='original monitor overwrote exited leaf cmdline with empty string; leaf1179955 under timeout1179954/startticks61732096 closed. No invented surviving process.',
        new_model_imports=0, new_predict_API_calls=0, new_fits=0, physics=0)
    result['summary_resources'] = dict(wall_seconds=time.monotonic() - start,
        CPU_seconds=time.process_time() - cpu, max_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    new(HERE / 'E2_ACTUAL_READONLY_SUMMARY_V1.json', result)
    artifacts = [p for p in out.iterdir() if p.is_file()]
    manifest = dict(schema='v8.E2.actual_artifact_manifest.v1',
        status='ACTUAL_COMPLETE_FROZEN_DEVELOPMENT_ONLY',
        files_sha256={str(p.relative_to(ROOT)): sha(p) for p in sorted(artifacts)},
        fit_approval_sha256=sha(HERE / 'FIT_E2_MAIN_APPROVAL_V1.json'),
        summary_sha256=sha(HERE / 'E2_ACTUAL_READONLY_SUMMARY_V1.json'),
        external_execution_sha256=sha(HERE / 'FIT_E2_EXTERNAL_V1.execution.json'),
        original_global_stop_unix=1793114740.0, source_and_data_unchanged=True,
        actual_fit_attempts=1, retries=0, real_validation_outcomes_used=False, physics=0)
    new(HERE / 'E2_ACTUAL_ARTIFACT_MANIFEST_V1.json', manifest)
    for kind, values in [('DIRECT', direct_summary), ('WRENCH_INTEGRAL', integral_summary)]:
        for row in values:
            if row['scope'] == 'LEAVE_CASE_OUT' and row['horizon_s'] == 19.03:
                print(json.dumps(dict(kind=kind, **row), ensure_ascii=False))
    print(json.dumps(dict(summary_sha256=sha(HERE / 'E2_ACTUAL_READONLY_SUMMARY_V1.json'),
        manifest_sha256=sha(HERE / 'E2_ACTUAL_ARTIFACT_MANIFEST_V1.json'),
        summary_resources=result['summary_resources'])))


if __name__ == '__main__':
    main()
