"""Read completed F1 JSON only; no model imports, predictions, fitting or raw reads."""
import hashlib
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'fits/f1_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def response(rows):
    buckets = defaultdict(list)
    for row in rows:
        fold = 'ALL_DEVELOPMENT' if row['fold'] == 'ALL_DEVELOPMENT' else 'CASE_LOCO'
        buckets[fold, row['method'], row['horizon_s']].append(row)
    result = []
    for (fold, method, horizon), group in sorted(buckets.items()):
        n = sum(r['observed_recipes'] - 1 for r in group)
        effects = {}
        for name in ('JF', 'JM'):
            mae = sum(r['cost_effects'][name]['paired_MAE'] * (r['observed_recipes'] - 1) for r in group) / n
            zero = sum(r['cost_effects'][name]['zero_effect_MAE'] * (r['observed_recipes'] - 1) for r in group) / n
            counts = {k: sum(r['cost_effects'][name][k] for r in group) for k in
                      ('true_nontie_count', 'true_tie_count', 'sign_correct_count', 'predicted_tie_count')}
            effects[name] = dict(paired_MAE=mae, zero_effect_MAE=zero,
                                 skill_vs_zero=None if zero <= (1e-6 if name == 'JF' else 1e-7) else 1 - mae / zero,
                                 sign_accuracy=None if not counts['true_nontie_count'] else counts['sign_correct_count'] / counts['true_nontie_count'], **counts)
        rank = {k: sum(r['ranking'][k] for r in group) for k in ('concordant', 'discordant', 'predicted_ties', 'true_ties')}
        rank['pairwise_accuracy_true_nonties'] = rank['concordant'] / (rank['concordant'] + rank['discordant'] + rank['predicted_ties'])
        result.append(dict(fold=fold, method=method, horizon_s=horizon, cases=len(group), observed_nonB_contrasts=n,
                           effects=effects, ranking=rank,
                           mean_window_JF_regret=statistics.mean(r['window_JF_regret'] for r in group),
                           max_window_JF_regret=max(r['window_JF_regret'] for r in group),
                           retrospective_original_full_qualified_choices=sum(r['actual_original_full_qualification_of_choice_evaluation_only'] for r in group),
                           choices=[r['hypothetical_window_min_choice'] for r in group],
                           channel_MAE_case_mean=[statistics.mean(r['channel_MAE_physical_units'][i] for r in group) for i in range(16)],
                           negative_absolute_window_cost_predictions={k: sum((r['negative_absolute_window_cost_predictions'] or {}).get(k, 0) for r in group) for k in ('JF', 'JM')}))
    return result


def main():
    started = time.monotonic()
    receipt = load(OUT / 'RUN_END.json')
    assert receipt['status'] == 'PASS_FIXED_F1_253_SOLVES_DEVELOPMENT_ONLY'
    assert not (OUT / 'RUN_FAILED.json').exists()
    artifacts = {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    direct = load(OUT / 'DIRECT_RESPONSE_RESULTS.json')
    curves = load(OUT / 'CURVE_RESPONSE_RESULTS.json')
    curve_error_groups = defaultdict(list)
    for line in (OUT / 'CURVE_ERRORS.jsonl').read_text().splitlines():
        record = json.loads(line)
        fold = 'ALL_DEVELOPMENT' if record['fold'] == 'ALL_DEVELOPMENT' else 'CASE_LOCO'
        for row in record['rows']:
            assert row['future_state_reference_wrench_feedback'] is False
            for error in row['errors']:
                curve_error_groups[fold, record['method'], error['horizon_s']].append(error)
    error_summary = []
    for (fold, method, horizon), errors in sorted(curve_error_groups.items()):
        error_summary.append(dict(fold=fold, method=method, horizon_s=horizon, physical_trials=len(errors),
                                 mean_time_channel_MAE=[statistics.mean(e['channel_MAE'][i] for e in errors) for i in range(14)],
                                 mean_endpoint_abs_error=[statistics.mean(e['endpoint_abs_error'][i] for e in errors) for i in range(14)],
                                 mean_window_cost_abs_error=[statistics.mean(abs(e['predicted_window_JF_JM'][i] - e['actual_window_JF_JM'][i]) for e in errors) for i in range(2)]))
    consistency = defaultdict(list)
    for row in curves['cost_consistency']:
        fold = 'ALL_DEVELOPMENT' if row['fold'] == 'ALL_DEVELOPMENT' else 'CASE_LOCO'
        consistency[fold, row['horizon_s']].append(row)
    consistency_summary = []
    for (fold, horizon), group in sorted(consistency.items()):
        consistency_summary.append(dict(fold=fold, horizon_s=horizon,
            nonB_mean_abs_deltaJF_direct_minus_integrated_curve=statistics.mean(abs(v) for r in group for v in r['deltaJF_direct_minus_integrated_curve'][1:]),
            nonB_mean_abs_deltaJM_direct_minus_integrated_curve=statistics.mean(abs(v) for r in group for v in r['deltaJM_direct_minus_integrated_curve'][1:])))
    index = load(HERE / 'data/build_v1/INDEX.json')
    id_to_recipe = {r['id']: r['input']['recipe_index'] for r in index['rows']}
    early_truth = []
    for r in direct['rows']:
        if r['fold'] != 'ALL_DEVELOPMENT' or r['method'] != 'ACTION_BLIND39_ABSOLUTE':
            continue
        prefix = r['B_attempt_id'].removesuffix('_B') + '_'
        ids = [row['id'] for row in index['rows'] if row['id'].startswith(prefix)]
        early_truth.append(dict(group=r['group_evaluation_only'], horizon_s=r['horizon_s'],
                                observed_attempt_ids=ids, deltaJF=r['paired_actual_JF_N_s'],
                                deltaJM=r['paired_actual_JM_Nm_s']))
    assert artifacts == {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    summary = dict(schema='v8.E.closed_F1_readonly_summary.v2', supersedes_v1_reason='Original score_response arrays preserve INDEX order; V1 supplemental actual_action_delta_labels attached sorted recipe IDs. V2 uses original row order. All numeric aggregated metrics and original fit artifacts unchanged', status='READ_ONLY_COMPLETED_OUTPUT_ANALYSIS',
                   fit_execution_receipt=receipt, external_fit_resources=dict(wall_s=4.16, user_s=3.49, sys_s=.34, RSS_KiB=205684, exit_code=0),
                   artifact_files_sha256=artifacts, direct=response(direct['rows']), curve=response(curves['rows']),
                   curve_errors=error_summary, direct_vs_curve=consistency_summary, actual_action_delta_labels=early_truth,
                   population_scope='48 old physical action traces, ten same-parent contexts and ten distinct case SHA; nine complete five-recipe menus, one observed three-recipe menu; two missing recipes unknown',
                   limitations=['CASE_LOCO is synthetic case development diagnosis, not clinical patient validation',
                                'All-development metrics are in-sample', 'Retrospective full qualification is evaluated only after window choice and never used as a mask',
                                'Curve has fixed OUT0 and public time only; no observed future feedback, not a validated Markov simulator',
                                'No F2, extra inference, model selection, refit, physics, raw or sealed reads in this summary'],
                   readonly_analysis_wall_s=time.monotonic() - started)
    save(HERE / 'F1_ACTUAL_RESULTS_SUMMARY_V2.json', summary)
    save(HERE / 'F1_ACTUAL_OUTPUT_MANIFEST_V2.json', dict(schema='v8.E.F1_actual_output_manifest.v1',
         fit_approval_sha256=sha(HERE / 'FIT_F1_MAIN_APPROVAL_V1.json'),
         source_manifest_sha256=sha(HERE / 'FIT_F1_SOURCE_MANIFEST_V1.json'),
         actual_dataset_manifest_sha256=sha(HERE / 'data/build_v1/DATASET_MANIFEST.json'),
         artifacts_relative_to_fits_f1_v1=artifacts, readonly_summary_sha256=sha(HERE / 'F1_ACTUAL_RESULTS_SUMMARY_V2.json'),
         summary_source_sha256=sha(Path(__file__)), actor_init_forward_fit_physics_in_summary=0))
    print(json.dumps(dict(summary_sha256=sha(HERE / 'F1_ACTUAL_RESULTS_SUMMARY_V2.json'),
                          manifest_sha256=sha(HERE / 'F1_ACTUAL_OUTPUT_MANIFEST_V2.json'),
                          analysis_wall_s=time.monotonic() - started)))


if __name__ == '__main__':
    main()
