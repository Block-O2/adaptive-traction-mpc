"""root批准的小型合成数学检查；绝无真实replay/机器人环境。"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import os
import resource
import time

P = Path(__file__).resolve().parents[1]


def main():
    start = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    source = P / 'source/terminal_discrete_sac.py'
    module_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    approval = P / 'analysis/MATH_APPROVAL_V1.json'
    approval_sha = hashlib.sha256(approval.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location('SYNTHETIC_MATH_ONLY_terminal_sac', source)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    counts = {'synthetic_model_initializations': 0, 'synthetic_BC_lifts': 0, 'linear_forward_calls': 0,
              'softmax_calls': 0, 'predict_calls': 0, 'step_calls': 0, 'successful_synthetic_steps': 0,
              'rejected_synthetic_steps': 0, 'finite_difference_scalar_gradients': 0,
              'finite_difference_loss_evaluations': 0, 'finite_difference_scalar_parameter_perturbations': 0}
    old_linear, old_softmax = m.linear, m.softmax
    def linear(*args, **kwargs):
        counts['linear_forward_calls'] += 1
        return old_linear(*args, **kwargs)
    def softmax(*args, **kwargs):
        counts['softmax_calls'] += 1
        return old_softmax(*args, **kwargs)
    m.linear, m.softmax = linear, softmax
    recipes = [{'SYNTHETIC_ONLY_NOT_AN_EXECUTABLE_ROBOT_RECIPE': i,
                'action': {'family': 'B'} if i == 0 else {'family': 'SYNTHETIC_ONLY', 'index': i},
                'resolved_base_candidate': {'SYNTHETIC': i}} for i in range(5)]
    parent = {'feature_names': list(m.FEATURE_NAMES), 'normalization': {'mean': [0.] * 25, 'scale': [1.] * 25},
              'action_contracts': recipes[:3], 'action_sha256': [m.digest(a) for a in recipes[:3]],
              'weights': [[.1 * (i - 1)] + [.002 * (i + 1) * (j + 1) for j in range(25)] for i in range(3)]}
    common = m.lift_bc_three_to_five(parent, recipes, approved_contract_sha256=approval_sha)
    counts['synthetic_BC_lifts'] += 1
    assert common['weights'][:3] == parent['weights']
    assert common['weights'][3] == common['weights'][4] == [(a + b) / 2 for a, b in zip(parent['weights'][1], parent['weights'][2])]

    def initialize(mechanism):
        counts['synthetic_model_initializations'] += 1
        result = m.initialize(common, mechanism=mechanism, seed=17,
                              approved_contract_sha256=approval_sha, module_source_sha256=module_sha)
        result['configuration']['gradient_norm_limit'] = 1e6  # 合成有限差分需排除裁剪。
        return result
    models = {kind: initialize(kind) for kind in m.MECHANISMS}
    assert len({m.digest(a['actor']) for a in models.values()}) == 1
    assert len({m.digest([a['q1'], a['q2']]) for a in models.values()}) == 1
    fixture_rows = []
    for i in range(4):
        features = [.1 * (i // 2)] + [.01 * j for j in range(1, 25)]
        context = m.digest({'names': list(m.FEATURE_NAMES), 'values': features})
        action = i % 2
        fixture_rows.append({'schema': 'v8.sac_terminal_replay_record.v1', 'attempt_id': 'SYNTHETIC_ONLY_' + str(i),
                             'source_experiment': 'B_ONPOLICY_V1', 'source_data_semantics': 'FRESH_ON_POLICY_PHYSICAL_ROLLOUT',
                             'split': 'DEVELOPMENT_ONLY', 'feature_names': list(m.FEATURE_NAMES), 'features': features,
                             'causal_features_sha256': context, 'qa_validated': True, 'parent_fingerprint': 'a' * 64,
                             'action_index': action, 'full_recipe': recipes[action], 'full_recipe_sha256': m.digest(recipes[action]),
                             'behavior_policy_sha256': 'b' * 64, 'behavior_policy_version': 0, 'old_logprob': -math.log(5),
                             'done': True, 'next_state': None,
                             'baseline': {'complete': True, 'original_qualified': True, 'JF_N_s': 1000., 'JM_Nm_s': 80.,
                                          'result_source_sha256': 'c' * 64, 'full_recipe_sha256': m.digest(recipes[0]),
                                          'causal_features_sha256': context, 'parent_fingerprint': 'a' * 64},
                             'physical_receipt': {'true_hard_safety_violation': False, 'genuine_new_physical_attempt': True,
                                                  'historical_or_cached_outcome': False, 'engineering_complete': True,
                                                  'ownership_and_causality_audit_pass': True, 'actual_new_native_steps': 5,
                                                  'attempt_start_sha256': 'd' * 64, 'attempt_end_sha256': 'e' * 64,
                                                  'result_source_sha256': 'f' * 64, 'native_ownership_sha256': '1' * 64,
                                                  'applied_reference_receipt_stream_sha256': '2' * 64,
                                                  'complete': True, 'original_qualified': action == 0, 'JF_N_s': 900. + 50 * i, 'JM_Nm_s': 70. + i}})
    # 这些只有内存中的虚构字段，绝非owner真实回执；不写为可复用replay文件。
    def manifest(rows):
        return {'schema': 'v8.main_owner_terminal_sac_replay_manifest.v1', 'approved_contract_sha256': approval_sha,
                'producer': 'MAIN_AGENT_PHYSICS_OWNER', 'source_experiment': 'B_ONPOLICY_V1', 'split': 'DEVELOPMENT_ONLY',
                'raw_receipt_adapter_verified': True, 'recipe_sha256': [m.digest(r) for r in recipes],
                'records_sha256': {r['attempt_id']: m.digest(r) for r in rows}, 'excluded_attempts': [],
                'source_attempt_ids': [r['attempt_id'] for r in rows]}
    fixture_manifest = manifest(fixture_rows)
    examples = m.admit_replay(fixture_rows, fixture_manifest, expected_actor=common, approved_contract_sha256=approval_sha)
    expected_targets = [.1, -1., 0., -1.]
    assert [r['canonical_terminal_return'] for r in examples] == expected_targets

    def step(model, rows=fixture_rows):
        counts['step_calls'] += 1
        before = m.digest(model)
        try:
            result = m.step(model, rows, manifest(rows), approved_contract_sha256=approval_sha)
        except ValueError:
            counts['rejected_synthetic_steps'] += 1
            assert m.digest(model) == before, '拒绝输入不能修改fixture模型'
            raise
        counts['successful_synthetic_steps'] += 1
        assert result['terminal_targets'] == [r['canonical_terminal_return'] for r in m.admit_replay(rows, manifest(rows), expected_actor=common, approved_contract_sha256=approval_sha)]
        return result

    base = copy.deepcopy(models['VANILLA_FIXED_ENTROPY'])
    updated = copy.deepcopy(base)
    main_result = step(updated)
    assert main_result['terminal_targets'] == expected_targets
    assert all(v.get('gradient_scale', 1.) == 1. for v in main_result['gradient_metrics'].values())

    def loss(model, head):
        total = 0.
        for row in examples:
            x = m.design(model['actor'], row['features'])
            a = row['action_index']
            if head == 'actor':
                pi = m.softmax(m.linear(model['actor']['weights'], x))
                q1, q2 = m.linear(model['q1'], x), m.linear(model['q2'], x)
                total += sum(p * (math.exp(model['log_alpha']) * math.log(p) - min(q1[i], q2[i])) for i, p in enumerate(pi)) / len(examples)
            elif head == 'risk':
                z = m.linear(model[head], x)[a]
                total += (max(z, 0.) + math.log1p(math.exp(-abs(z))) - row['failure'] * z) / len(examples)
            else:
                target = row['canonical_terminal_return'] if head in ('q1', 'q2') else row[head] / model['component_output_units'][head]
                total += .5 * (m.linear(model[head], x)[a] - target) ** 2 / len(examples)
        if head != 'actor':
            total += .5 * model['configuration']['linear_weight_decay'] * sum(v * v for r in model[head] for v in r)
        return total

    gradient_checks = []
    epsilon = 1e-6
    for head in ('q1', 'q2', 'risk', 'JF', 'JM', 'actor'):
        before_weights = base['actor']['weights'] if head == 'actor' else base[head]
        after_weights = updated['actor']['weights'] if head == 'actor' else updated[head]
        lr = base['configuration']['actor_lr'] if head == 'actor' else base['configuration']['risk_lr'] if head == 'risk' else base['configuration']['cost_lr'] if head in ('JF', 'JM') else base['configuration']['critic_lr']
        maximum_error = 0.
        for i in range(5):
            for j in range(26):
                numeric_model = copy.deepcopy(base)
                weights = numeric_model['actor']['weights'] if head == 'actor' else numeric_model[head]
                old = weights[i][j]
                weights[i][j] = old + epsilon
                upper = loss(numeric_model, head)
                weights[i][j] = old - epsilon
                lower = loss(numeric_model, head)
                numerical = (upper - lower) / (2 * epsilon)
                source_gradient = (before_weights[i][j] - after_weights[i][j]) / lr
                maximum_error = max(maximum_error, abs(numerical - source_gradient))
                counts['finite_difference_scalar_gradients'] += 1
                counts['finite_difference_loss_evaluations'] += 2
                counts['finite_difference_scalar_parameter_perturbations'] += 2
        assert maximum_error < 2e-7, (head, maximum_error)
        gradient_checks.append({'head': head, 'scalar_gradients': 130, 'max_absolute_error': maximum_error})

    variant_results = {'VANILLA_FIXED_ENTROPY': main_result}
    for mechanism in ('ADAPTIVE_TEMPERATURE', 'CONSERVATIVE_SUPPORT'):
        variant_results[mechanism] = step(models[mechanism])
    assert variant_results['CONSERVATIVE_SUPPORT']['actor_states'] == 4
    for alpha in (.0001, .01, .1, 1., 10.):
        q = [.1, -.2, .3, .3, -1.]
        p = m.softmax([v / alpha for v in q])
        assert max(range(5), key=lambda i: (p[i], -i)) == max(range(5), key=lambda i: (q[i], -i))
    temp_results = []
    for deterministic in (False, True):
        model = initialize('ADAPTIVE_TEMPERATURE')
        for i, row in enumerate(model['actor']['weights']):
            row[:] = [30. if deterministic and i == 0 else -30. if deterministic else 0.] + [0.] * 25
        result = step(model)
        assert (result['alpha_after'] > result['alpha_before']) == deterministic
        temp_results.append({'near_deterministic_fixture': deterministic, 'mean_entropy': result['mean_entropy'], 'alpha_before': result['alpha_before'], 'alpha_after': result['alpha_after']})
    for gamma in (0., .99):
        model = copy.deepcopy(base)
        model['configuration']['gamma'] = gamma
        model['ignored_future_Q_metadata'] = [1e100] * 5
        assert step(model)['terminal_targets'] == expected_targets

    rejected = []
    mutations = {'missing_START': lambda r: r['physical_receipt'].pop('attempt_start_sha256'),
                 'nonterminal': lambda r: r.update(done=False), 'future_next_state': lambda r: r.update(next_state={'future_Q': 1e100}),
                 'engineering_censor': lambda r: r['physical_receipt'].update(engineering_complete=False),
                 'hard_violation': lambda r: r['physical_receipt'].update(true_hard_safety_violation=True, engineering_complete=False),
                 'boolean_cost': lambda r: r['physical_receipt'].update(JF_N_s=True),
                 'boolean_steps': lambda r: r['physical_receipt'].update(actual_new_native_steps=True),
                 'heldout_split': lambda r: r.update(split='HELDOUT'),
                 'recipe_body_drift': lambda r: r['full_recipe']['action'].update(family='WRONG')}
    for name, mutate in mutations.items():
        rows = copy.deepcopy(fixture_rows)
        mutate(rows[0])
        try:
            step(copy.deepcopy(base), rows)
        except ValueError as error:
            rejected.append({'test': name, 'reason': str(error)})
        else:
            raise AssertionError('必须拒绝：' + name)
    duplicated = copy.deepcopy(fixture_rows) + [copy.deepcopy(fixture_rows[0])]
    try:
        step(copy.deepcopy(base), duplicated)
    except ValueError as error:
        rejected.append({'test': 'duplicate_real_attempt_schema', 'reason': str(error)})
    else:
        raise AssertionError('重复attempt必须拒绝')
    rows = copy.deepcopy(fixture_rows)
    rows[0]['physical_receipt'].update(complete=False, original_qualified=False, protected_task_failure=True)
    model = copy.deepcopy(base)
    partial = step(model, rows)
    assert partial['terminal_targets'][0] == -1.
    assert partial['counters']['cost_gradient_examples'] == 6
    assert len(model['support_records']) == 4
    assert model['support_records'] == updated['support_records'], 'support不能依赖qualification标签'

    saved = m.snapshot(updated)
    restored = m.restore(json.loads(json.dumps(saved)), expected_source_sha256=module_sha,
                         expected_contract_sha256=approval_sha, expected_recipe_sha256=common['action_sha256'])
    for state in (updated, restored):
        counts['predict_calls'] += 1
    pred1 = m.predict(updated, list(m.FEATURE_NAMES), fixture_rows[0]['features'], qa_validated=True)
    pred2 = m.predict(restored, list(m.FEATURE_NAMES), fixture_rows[0]['features'], qa_validated=True)
    assert pred1 == pred2
    try:
        m.restore(saved, expected_source_sha256='0' * 64, expected_contract_sha256=approval_sha, expected_recipe_sha256=common['action_sha256'])
    except ValueError as error:
        rejected.append({'test': 'restore_source_changed', 'reason': str(error)})
    else:
        raise AssertionError('变更源必须拒绝restore')
    counts['predict_calls'] += 1
    empty_support = m.predict(models['CONSERVATIVE_SUPPORT'], list(m.FEATURE_NAMES), [100.] * 25, qa_validated=True)
    assert empty_support['action_index'] is None and empty_support['reason'].startswith('ABSTAIN')

    end_usage = resource.getrusage(resource.RUSAGE_SELF)
    audit = {'status': 'PASS_SYNTHETIC_MATH_ONLY', 'fixture_scope': '全部policy、recipe、回执字段及SHA均为内存合成；从未读真实replay或BC模型，不是实际MAIN_OWNER物理证据',
             'source_sha256': module_sha, 'math_driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'approval_sha256': approval_sha,
             'checks': {'terminal_y_equals_r': True, 'gamma_future_metadata_do_not_bootstrap': True, 'nonterminal_and_nextstate_rejected': True,
                        'shared_actor_and_twin_initialization': True, 'BC3_logits_preserved': True, 'direct_softmaxQ_argmax_invariance': True,
                        'temperature_direction': True, 'snapshot_prediction_exact': True, 'support_independent_of_qualification': True,
                        'no_support_abstains': True, 'rejected_step_no_parameter_commit': True},
             'gradient_checks': gradient_checks, 'temperature_checks': temp_results, 'rejections': rejected,
             'operation_counts_synthetic_only': counts,
             'successful_step_equivalent_parameter_head_updates': counts['successful_synthetic_steps'] * 6,
             'note_parameter_head_updates': '合成每成功step更新2Q+risk+JF+JM+actor；自适应alpha额外3步，有限差分参数扰动独立计数；fixture配置/熵方向初始化赋值不是真实训练',
             'resources': {'wall_s': time.monotonic() - start, 'cpu_user_s': end_usage.ru_utime - usage.ru_utime, 'cpu_system_s': end_usage.ru_stime - usage.ru_stime,
                           'peak_RSS_KiB': end_usage.ru_maxrss, 'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                           'threads': 1, 'timeout_s': 60},
             'real_model_initializations': 0, 'real_model_forward': 0, 'real_replay_fits': 0, 'new_physics': 0,
             'real_data_training_status': 'NOT_APPROVED_NOT_RUN', 'control_or_safety_qualification': 'NOT_ESTABLISHED'}
    output = P / 'analysis/SYNTHETIC_MATH_AUDIT_V1.json'
    assert not output.exists()
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': audit['status'], 'gradient_checks': gradient_checks, 'operations': counts, 'wall_s': audit['resources']['wall_s']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
