"""主 Agent 授权的 A2 实际覆盖合并：0fit、0forward、0physics。"""
from pathlib import Path
import copy
import hashlib
import json
import os
import resource
import time
from causal_api import digest, finite, to_context25

P = Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
OUT = P / 'families/critic_value/coverage_risk_v2'
OLD_SHA = 'ea35953cf6e8775a7331a80febf1219b2d2d047677fb2cc57db6e8baf0773ed5'
GROUPS = ['V8CTX01', 'V8CTX02', 'V8CTX03', 'V8CTX04']
TAGS = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
MANIFEST = {}


def read(path):
    path = Path(path).resolve()
    assert path.is_relative_to(P.parent)
    raw = path.read_bytes()
    MANIFEST[str(path.relative_to(P.parent))] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def write(relative, value):
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def snapshot_identity(path):
    snap = read(path)
    return {'snapshot_full_hash': snap['hash'], 'native_hash': snap.get('native_hash'),
            'native_integration_sha256': snap.get('manifest', {}).get('native_integration', {}).get('sha256'),
            'snapshot_path': str(path.resolve().relative_to(P.parent))}


def main():
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    started, usage = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
    activation = read(P / 'ACTIVATION.json')
    assert time.time() < activation['hard_stop_unix']
    closure = {}
    # 四 owner 必须全部关闭后才打开任何其结果标签。
    for group in GROUPS:
        done = read(P / 'jobs' / group / 'WORKER_DONE.json')
        end = read(P / 'owned' / (group + '_SUPERVISOR_END.json'))
        exit_record = read(P / 'owned' / (group + '_EXIT.json'))
        assert done['status'] == 'PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'
        assert end['state'] == 'STOP' and end['worker_exit_code'] == 0 and end['survivors'] == []
        closure[group] = {'done': done['status'], 'supervisor_state': end['state'], 'worker_exit_code': 0, 'survivors': [], 'exit_record_exists': bool(exit_record)}
    old_path = P / 'families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json'
    assert hashlib.sha256(old_path.read_bytes()).hexdigest() == OLD_SHA
    old = read(old_path)
    menu_document = read(P / 'families/critic_value/freeze/FIVE_ACTION_MENU_V1.json')
    menu = menu_document['menu']
    assert [m['tag'] for m in menu] == TAGS
    hashes = {m['recipe_sha256'] for m in menu}
    assert len(hashes) == 5 and all(digest(m['action_recipe']) == m['recipe_sha256'] for m in menu)
    rows, excluded, parents = [], [], {}
    for source in old['rows']:
        if source.get('action_recipe_sha256') not in hashes:
            excluded.append({'id': source['id'], 'reason': 'INCOMPATIBLE_OR_MISSING_EXACT_RECIPE'})
            continue
        labels = source['labels_evaluation_only']
        if labels['complete'] is not True or not all(finite(labels.get(k)) for k in ['JF_N_s', 'JM_Nm_s']):
            excluded.append({'id': source['id'], 'reason': 'INCOMPLETE_COST_NOT_RANKED_OR_IMPUTED'})
            continue
        assert isinstance(labels['original_qualified'], bool)
        row = copy.deepcopy(source)
        row['schema'] = 'v8.a2.actual_recipe_row.v1'
        row['status'] = 'HISTORICAL_EXPOSED_DEVELOPMENT'
        row['cohort_evaluation_only'] = 'OLD_V2'
        row['context'] = to_context25(source['context'])
        row['action_tag_evaluation_only'] = next(m['tag'] for m in menu if m['recipe_sha256'] == row['action_recipe_sha256'])
        old_root = P.parent / 'autonomous_learning_smoothness_v7'
        parents.setdefault(row['group'], snapshot_identity(old_root / 'runtime/reports' / (row['group'] + '_B_SNAPSHOT.json')))
        row['parent_evaluation_only'] = parents[row['group']]
        rows.append(row)
    old_count = len(rows)
    for group in GROUPS:
        config = read(P / 'experiments' / (group + '.json'))
        sources = read(P / 'jobs' / group / 'SOURCE_MANIFEST.json')['files']
        assert [x['tag'] for x in config['actions']] == TAGS
        payload_path = P / 'history' / (group + '_PREFORK_CAUSAL_CONTEXT.json')
        context = to_context25(read(payload_path))
        parents[group] = snapshot_identity(P / 'runtime/reports' / (group + '_B_SNAPSHOT.json'))
        group_rows = []
        for entry, item in zip(config['actions'], menu):
            ident = group + '_' + entry['tag']
            path = P / 'attempts' / (ident + '_RESULT.json')
            result = read(path)
            assert result['id'] == ident and result['action'] == entry['action'] == item['action']
            assert result['complete'] is True and result.get('error') is None
            assert isinstance(result['qualified'], bool) and all(finite(result.get(k)) for k in ['JF', 'JM'])
            base = copy.deepcopy(config['B'] if entry['action']['family'] == 'B' else config['H150'])
            base.update(entry['action'].get('candidate_overrides', {}));base.pop('id', None)
            recipe = {'action': entry['action'], 'resolved_base_candidate': base,
                      'frozen_18d_sha256': sources['runtime/FROZEN_18D.json'],
                      'planner_source_sha256': {n: sources[n] for n in ['runtime/code/terminal_repair.py', 'source/acl2_modal_planner.py', 'source/acl2_modal_retimed.py', 'runtime/PARAMETER_MAP.json']}}
            assert recipe == item['action_recipe'] and digest(recipe) == item['recipe_sha256'], 'INCOMPATIBLE_EXACT_RECIPE:' + ident
            assert result['axes']['PHYSICAL_TASK_VALID'] == result['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'] == 'PASS'
            motion = result.get('motion_vs_B', {})
            row = {'schema': 'v8.a2.actual_recipe_row.v1', 'id': ident, 'group': group,
                   'status': 'V8_STOCK_ALREADY_EXPOSED_DEVELOPMENT', 'cohort_evaluation_only': 'CTX_COVERAGE',
                   'action_tag_evaluation_only': entry['tag'], 'context': context,
                   'action': entry['action'], 'action_json_sha256': digest(entry['action']),
                   'action_recipe': recipe, 'action_recipe_sha256': item['recipe_sha256'],
                   'continuation_policy': 'FULL_POLICY_COMMITMENT_WITH_FROZEN_SLOT_OVERRIDES',
                   'boundary': {'phase': 'OUTBOUND', 'slot': 0},
                   'labels_evaluation_only': {'JF_N_s': result['JF'], 'JM_Nm_s': result['JM'], 'complete': True,
                       'original_qualified': result['qualified'], 'motion_worst_ratio': result.get('worst_ratio'),
                       'motion_failed_requirements': motion.get('failed_requirements', []), 'original_axes': result['axes'],
                       'phase_cost': result.get('phase_cost'), 'tracking': result.get('tracking'), 'error': None,
                       'motion_details': motion},
                   'eligible_for_success_ranking': result['qualified'], 'parent_evaluation_only': parents[group],
                   'identity_evaluation_only': {'case_path': config['case_path'], 'case_sha256': config['case_sha256'],
                       'context_source_path': str(payload_path.relative_to(P.parent)), 'context_source_sha256': hashlib.sha256(payload_path.read_bytes()).hexdigest(),
                       'native_integration_sha256': parents[group]['native_integration_sha256']},
                   'historical_resource_evaluation_only': {'actual_new_native_steps': result['actual_new_native_steps'], 'wall_s': result['wall_s']},
                   'source_result': str(path.relative_to(P.parent))}
            rows.append(row);group_rows.append(row)
        baseline = group_rows[0]['labels_evaluation_only']
        assert baseline['original_qualified'] is True
        for row in group_rows:
            label = row['labels_evaluation_only']
            label['delta_JF_vs_B_N_s'] = label['JF_N_s'] - baseline['JF_N_s']
            label['delta_JM_vs_B_Nm_s'] = label['JM_Nm_s'] - baseline['JM_Nm_s']
    assert len(rows) - old_count == 20
    unique, duplicates = {}, []
    for row in rows:
        # 真实相同完整父状态的同 recipe 只计一个证据条目；不依动作别名增加样本。
        key = (row['parent_evaluation_only']['snapshot_full_hash'], row['action_recipe_sha256'])
        if key in unique:
            earlier = unique[key]
            assert earlier['labels_evaluation_only']['original_qualified'] == row['labels_evaluation_only']['original_qualified']
            assert abs(earlier['labels_evaluation_only']['JF_N_s'] - row['labels_evaluation_only']['JF_N_s']) < 1e-8
            duplicates.append({'id': row['id'], 'duplicate_of': earlier['id']})
        else:
            unique[key] = row
    rows = list(unique.values())
    summaries = []
    for group in sorted({r['group'] for r in rows}):
        records = [r for r in rows if r['group'] == group]
        assert len({digest(r['context']['features']) for r in records}) == 1
        split = 'PARENT_' + parents[group]['snapshot_full_hash']
        for row in records:
            row['split_parent_group_evaluation_only'] = split
        summaries.append({'group': group, 'split_parent_group': split, 'row_count': len(records),
            'qualified': sum(r['eligible_for_success_ranking'] for r in records),
            'feature25_sha256': digest(records[0]['context']['features']), 'quality_sha256': digest(records[0]['context']['quality']),
            'supported_actions': [r['action_tag_evaluation_only'] for r in records],
            'missing_actions_no_labels': [t for t in TAGS if not any(r['action_tag_evaluation_only'] == t for r in records)]})
    data = {'schema': 'v8.a2.actual_coverage_dataset.v1', 'menu': menu, 'rows': rows, 'groups': summaries,
            'old_dataset_sha256': OLD_SHA, 'old_supported_complete_rows': old_count, 'new_ctx_unique_complete_rows': 20,
            'development_only': True, 'sealed_interpolation_validation_read': False,
            'labels_not_actor_inputs': True, 'partial_cost_imputation': False, 'future_qualification_mask_allowed': False,
            'original_qualification_thresholds_changed': False, 'parent_and_history_B_excluded': True,
            'same_patient_or_parameter_family_not_population_iid': True, 'new_fits': 0, 'new_physics': 0}
    write('data/ACTUAL_COVERAGE_DATASET_V1.json', data)
    write('analysis/DATA_MERGE_AUDIT_V1.json', {'closure': closure, 'old_accepted': old_count,
        'ctx_accepted': 20, 'rows_after_true_parent_recipe_dedup': len(rows), 'excluded': excluded,
        'duplicates': duplicates, 'groups': summaries, 'parent_identities': parents,
        'exact_feature25_aliases': [[g['group'] for g in summaries if g['feature25_sha256'] == h] for h in sorted({g['feature25_sha256'] for g in summaries}) if sum(g['feature25_sha256'] == h for g in summaries) > 1],
        'first_schema_probe_failed': 'provenance 字段不存在，已改用 identity_evaluation_only；原文件未改，0fit',
        'new_fits': 0, 'new_model_forward': 0, 'new_physics': 0})
    used = resource.getrusage(resource.RUSAGE_SELF)
    write('data/SOURCE_MANIFEST_V1.json', {'source_files': MANIFEST, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'causal_api_sha256': hashlib.sha256((Path(__file__).parent / 'causal_api.py').read_bytes()).hexdigest(),
        'resources': {'wall_s': time.monotonic() - started, 'cpu_user_s': used.ru_utime - usage.ru_utime,
        'cpu_system_s': used.ru_stime - usage.ru_stime, 'peak_RSS_KiB': used.ru_maxrss, 'single_cpu_affinity': sorted(os.sched_getaffinity(0)),
        'python_bytecode_disabled': bool(os.environ.get('PYTHONDONTWRITEBYTECODE')), 'new_fit_or_forward': 0, 'new_physics': 0},
        'dataset_sha256': hashlib.sha256((OUT / 'data/ACTUAL_COVERAGE_DATASET_V1.json').read_bytes()).hexdigest()})
    print(json.dumps({'old_rows': old_count, 'ctx_rows': 20, 'merged_rows': len(rows), 'contexts': len(summaries),
        'qualified': sum(r['eligible_for_success_ranking'] for r in rows), 'data_sha256': hashlib.sha256((OUT / 'data/ACTUAL_COVERAGE_DATASET_V1.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
