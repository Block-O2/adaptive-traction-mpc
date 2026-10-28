"""经主 Agent 批准的只读历史提取；不训练、不导入仿真、不执行历史源码。"""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import os
import resource
import time

ROOT = Path('/home/hank/ihear-lab')
OUT = ROOT / 'deep_learning_method_exploration_v8/families/critic_value'
OLD = ROOT / 'autonomous_learning_smoothness_v7'
GROUPS = ['EARLYN01', 'EARLYL01', 'EARLYH01', 'CFACTORH01', 'CFACTORL01', 'HOLDSS03']
BETA = ['a_inertia_combination', 'b_distal_inertia_combination', 'd_mass_length_com_combination', 'g1_proximal_gravity_combination', 'g2_distal_gravity_combination', 'k1_passive_stiffness', 'k2_passive_stiffness', 'rho1_stiffness_rest_combination', 'rho2_stiffness_rest_combination', 'bv1_viscous_damping', 'bv2_viscous_damping']
FEATURES = ['estimated_beta_' + n for n in BETA] + ['estimated_geometry_' + n for n in ['hip_plane_x', 'hip_plane_z', 'thigh_length', 'knee_to_cuff_distance']] + ['residual_weight_' + j + '_' + n for j in ['hip', 'knee'] for n in ['constant', 'q_hip_normalized', 'q_knee_normalized', 'dq_hip_bounded', 'dq_knee_bounded']]
MANIFEST = {}


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def read(path):
    path = path.resolve()
    assert path.is_relative_to(OLD), path
    raw = path.read_bytes()
    MANIFEST[str(path.relative_to(ROOT))] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def write(rel, x):
    path = OUT / rel
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), '禁止覆盖提取结果：' + str(path)
    path.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def context(payload):
    names, vals = payload['feature_names'], payload['features']
    f = dict(zip(names, vals))
    body = {k: v for k, v in payload.items() if k != 'causal_payload_sha256'}
    checksum = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    checks = {
        'payload_checksum': checksum == payload['causal_payload_sha256'],
        'legacy_shape_77': len(names) == len(vals) == len(set(names)) == 77,
        'legacy_remains_invalid': payload['model_vector_valid'] is False,
        'subset25_finite': all(finite(f.get(n)) for n in FEATURES),
        'out0_boundary': payload['phase'] == 'OUTBOUND' and f['decision_slot'] == 0 and abs(payload['task_s']) < 1e-9,
        'no_truth_future': payload['hidden_or_future_inputs_used'] is False,
        'capture_read_only': payload['model_prediction_or_observe_calls'] == 0,
        'before_selection': payload['capture_position'] == 'parent request boundary BEFORE fork loop/candidate selection/control mutation',
        'missing_preserved': payload['causality_errors'] == ['capture_is_not_registered_OUT1_boundary'],
        'quality_complete': payload['quality_missing'] == {} and all(finite(v) for v in payload['quality'].values()),
    }
    assert all(checks.values()), checks
    values = [f[n] for n in FEATURES]
    return {'schema': 'v8.recipe_context.commissioning25.v1', 'feature_names': FEATURES, 'features': values,
            'quality': payload['quality'], 'quality_warning_names': [n for n, v in payload['quality'].items() if (n.startswith('last_attempt_conditional_frozen_') or n in ['last_attempt_bound_hit', 'last_attempt_rate_limit_hit']) and v == 1],
            'subset_numeric_identity_sha256': digest({'feature_names': FEATURES, 'features': values, 'quality': payload['quality']}),
            'legacy77d_valid': False, 'legacy_missing': payload['missing_model_groups'], 'checks': checks,
            'fit_absolute_timestamp': None, 'availability_scope': '已审 OUT0 用途限定 commissioning25；QA 保留；不是原运动资格或完整状态充分性证明'}


def summarize_parent(group):
    """父身份作为评价元数据；不输入模型。优先实际 fork 前缀证据。"""
    files = [OLD / 'history' / (group + '_parent_FORK_CAUSAL.json'), OLD / 'history' / (group + '_parent_COMMON_POLICY_INPUTS.json')]
    found = []
    for path in files:
        if path.exists():
            x = read(path)
            found.append({'source': str(path.relative_to(ROOT)), 'identity': x})
    return found


def main():
    begin = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rows, groups, identities = [], [], []
    for g in GROUPS:
        config = read(OLD / 'experiments' / (g + '.json'))
        payload = read(OLD / 'history' / (g + '_PREFORK_CAUSAL_CONTEXT.json'))
        ctx = context(payload)
        parent_records = summarize_parent(g)
        group_rows = []
        for entry in config['actions']:
            tag = entry['tag']
            path = OLD / 'attempts' / (g + '_' + tag + '_RESULT.json')
            if not path.exists():
                rows.append({'id': g + '_' + tag, 'group': g, 'status': 'NOT_RUN_OR_MISSING_RESULT', 'action': entry['action'], 'eligible_for_success_ranking': False})
                continue
            r = read(path)
            assert r['action'] == entry['action'], (g, tag, '配置与实际结果动作不同')
            m = read(OLD / r['metrics_path']) if r.get('metrics_path') else None
            native_path = OLD / 'analysis/native_metrics' / (r['id'] + '.json')
            native = read(native_path) if native_path.exists() else None
            snap_path = OLD / 'runtime/reports' / (r['id'] + '_SNAPSHOT.json')
            snap = read(snap_path) if snap_path.exists() else None
            integration = None if snap is None else snap.get('manifest', {}).get('native_integration', {}).get('sha256')
            if integration: identities.append((g, integration))
            # 全 recipe JSON 包含 planner、slot、激活时点和候选覆盖；tag 不作模型输入。
            action = r['action']
            labels = {'JF_N_s': r.get('JF'), 'JM_Nm_s': r.get('JM'), 'complete': r.get('complete', False),
                      'original_qualified': r.get('qualified', False), 'motion_worst_ratio': r.get('worst_ratio'),
                      'motion_failed_requirements': r.get('motion_vs_B', {}).get('failed_requirements', []),
                      'original_axes': r.get('axes'), 'tracking': r.get('tracking'), 'error': r.get('error'),
                      'phase_cost': r.get('phase_cost'),
                      'native_metrics': native,
                      'jerk_RMS_deg_s3': None if m is None else m.get('motion', {}).get('raw', {}).get('full', {}).get('jerk_deg_s3', {}).get('rms')}
            row = {'schema': 'v8.historical_recipe_row.v1', 'id': r['id'], 'group': g,
                   'status': 'HISTORICAL_EXPOSED_DEVELOPMENT', 'context': ctx, 'action': action,
                   'action_recipe_sha256': digest(action), 'continuation_policy': config['continuation_policy'],
                   'boundary': {'phase': config['fork_phase'], 'slot': config['fork_slot']},
                   'labels_evaluation_only': labels,
                   'eligible_for_success_ranking': bool(r.get('complete') and r.get('qualified')),
                   'causal_input_exclusions': ['id', 'group', 'case_path', 'case_sha256', 'native_integration_sha256', 'labels_evaluation_only', 'historical_best_action'],
                   'identity_evaluation_only': {'case_path': config.get('case_path'), 'case_sha256': config.get('case_sha256'), 'native_integration_sha256': integration, 'context_sha256': MANIFEST[str((OLD / 'history' / (g + '_PREFORK_CAUSAL_CONTEXT.json')).relative_to(ROOT))]['sha256'], 'parent_records': parent_records},
                   'historical_resource_evaluation_only': {'actual_new_native_steps': r.get('actual_new_native_steps'), 'wall_s': r.get('wall_s')},
                   'source_result': str(path.relative_to(ROOT))}
            rows.append(row)
            group_rows.append(row)
        b = next((r for r in group_rows if r['action'].get('family') == 'B'), None)
        assert b is not None and b['labels_evaluation_only']['complete'], (g, '缺完整 B')
        for r in group_rows:
            r['labels_evaluation_only']['delta_JF_vs_B_N_s'] = r['labels_evaluation_only']['JF_N_s'] - b['labels_evaluation_only']['JF_N_s'] if finite(r['labels_evaluation_only']['JF_N_s']) else None
            r['labels_evaluation_only']['delta_JM_vs_B_Nm_s'] = r['labels_evaluation_only']['JM_Nm_s'] - b['labels_evaluation_only']['JM_Nm_s'] if finite(r['labels_evaluation_only']['JM_Nm_s']) else None
        groups.append({'group': g, 'rows': len(group_rows), 'qualified': sum(r['eligible_for_success_ranking'] for r in group_rows), 'context_identity_sha256': ctx['subset_numeric_identity_sha256'], 'recipe_hashes': [r['action_recipe_sha256'] for r in group_rows], 'B_qualified': b['labels_evaluation_only']['original_qualified'], 'continuation_policy': config['continuation_policy']})
    # 实际积分身份保留，不能以单一 integration hash 假定父 controller 状态相同。
    pair_observations = {}
    for g in GROUPS:
        rr = [r for r in rows if r['group'] == g and r.get('schema')]
        for a, b in itertools.combinations(sorted(rr, key=lambda r: r['action_recipe_sha256']), 2):
            if not (a['eligible_for_success_ranking'] and b['eligible_for_success_ranking']):
                continue
            key = a['action_recipe_sha256'] + ':' + b['action_recipe_sha256']
            la, lb = a['labels_evaluation_only'], b['labels_evaluation_only']
            delta = la['JF_N_s'] - lb['JF_N_s']
            pair_observations.setdefault(key, []).append({'group': g, 'A': a['id'], 'B': b['id'], 'A_action': a['action'], 'B_action': b['action'], 'delta_JF_N_s': delta, 'delta_JM_Nm_s': la['JM_Nm_s'] - lb['JM_Nm_s'], 'orientation_at_0p02_N_s': 1 if delta > .02 else -1 if delta < -.02 else 0, 'context_identity_sha256': a['context']['subset_numeric_identity_sha256']})
    pairs = [{'action_pair': k, 'observations': v, 'JF_order_flip': {-1, 1}.issubset({r['orientation_at_0p02_N_s'] for r in v})} for k, v in pair_observations.items()]
    data = {'schema': 'v8.historical_recipe_dataset.v1', 'groups': groups, 'rows': rows,
            'split_scope': '全部是已暴露历史开发；不得冒充 v8 冻结独立测试',
            'input_scope': 'commissioning25 + QA33；模型只得从 context 数值/质量与完整 action recipe 读取',
            'gamma': 1, 'JF_JM_scalarized': False, 'partial_success_ranking_forbidden': True,
            'continuation_policy_mixing_forbidden': True, 'new_physics': 0, 'new_fits': 0}
    write('data/HISTORICAL_RECIPE_DATASET_V1.json', data)
    write('analysis/HISTORICAL_RECIPE_RANK_AUDIT_V1.json', {'groups': groups, 'pairs': pairs, 'qualified_JF_flip_pairs': [p for p in pairs if p['JF_order_flip']], 'native_integrations_evaluation_only': sorted(set(identities)), 'causal_context_unique': len(set(r['context']['subset_numeric_identity_sha256'] for r in rows if r.get('schema'))), 'new_physics': 0, 'new_fits': 0, 'limitations': ['资格仅评价标签，不能在当前决策中 mask', '每 context 多动作不增加独立 context 数', '相同 recipe 不自动保证实际 applied action 相同', '父状态需 native/causal/controller prefix 联合核验，当前 context 指纹不是完整状态指纹', 'JF翻转仅为能力线索；JM、motion 与强传统必须同时单列验证']})
    elapsed = time.monotonic() - begin
    write('data/HISTORICAL_RECIPE_SOURCE_MANIFEST_V1.json', {'files': MANIFEST, 'file_count': len(MANIFEST), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'resources': {'wall_s': elapsed, 'cpu_user_s': resource.getrusage(resource.RUSAGE_SELF).ru_utime - usage.ru_utime, 'cpu_system_s': resource.getrusage(resource.RUSAGE_SELF).ru_stime - usage.ru_stime, 'peak_RSS_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'new_native_steps': 0, 'new_fits': 0}, 'within_60s': elapsed < 60, 'python_bytecode_disabled': bool(os.environ.get('PYTHONDONTWRITEBYTECODE'))})
    print(json.dumps({'rows': len(rows), 'groups': len(groups), 'qualified_JF_flip_pairs': len([p for p in pairs if p['JF_order_flip']]), 'wall_s': elapsed}, ensure_ascii=False))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
