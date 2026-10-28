"""V7 纯终末 critic API；无初始化、训练、I/O或物理。当前 SOURCE_ONLY。"""
import copy
import hashlib
import json
import math

METHODS = ('EXACT_CRITIC_GAIN1_EMPIRICAL_ROWS', 'EXACT_CRITIC_GAIN20_EMPIRICAL_ROWS', 'EXACT_CRITIC_GAIN1_CASE_ACTION_BALANCED')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _vector(values, length):
    assert isinstance(values, (list, tuple)) and len(values) == length
    assert all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def validate(model):
    assert model['schema'] == 'v8.exact_terminal_critic_model.v7' and model['mechanism'] in METHODS
    assert len(model['feature_names']) == 25 and len(set(model['feature_names'])) == 25
    _vector(model['normalization']['mean'], 25); _vector(model['normalization']['scale'], 25)
    assert all(v > 0 for v in model['normalization']['scale'])
    assert len(model['weights']) == 5
    for row in model['weights']: _vector(row, 26)
    recipes = model['action_contracts']
    assert len(recipes) == 5 and recipes[0]['action'] == {'family': 'B'}
    assert [digest(r) for r in recipes] == model['full_recipe_sha256'] and len(set(model['full_recipe_sha256'])) == 5
    assert model['support_policy'] == 'UNRESTRICTED_SAME_AS_V6_VANILLA_NO_CURRENT_MASK'
    assert model['alpha'] == .01 and model['weight_decay'] == .001
    assert model['terminal_only'] is True and model['future_qualification_mask_used'] is False
    assert model['support_radius_RMS'] == 1. and model['support_count_unit'] == 'DISTINCT_TRAINING_CASE'
    for row in model['support_records']:
        _vector(row['normalized_features'], 25)
        assert type(row['action_index']) is int and row['action_index'] in range(5)
        assert isinstance(row['case_sha256'], str) and len(row['case_sha256']) == 64


def predict(model, feature_names, commissioned25, *, qa_validated):
    """只接受合法转换器输出；部署调用侧还须核实际 OUT0 source/checksum/age。"""
    validate(model)
    assert list(feature_names) == model['feature_names'] and qa_validated is True
    _vector(commissioned25, 25)
    z = [(v-m)/s for v, m, s in zip(commissioned25, model['normalization']['mean'], model['normalization']['scale'])]
    x = [1.] + z
    q = [sum(w*v for w, v in zip(row, x)) for row in model['weights']]
    assert all(math.isfinite(v) for v in q)
    allowed = list(range(5))  # 与 V6 vanilla 相同；不得读取当前结果作 mask。
    index = max(allowed, key=lambda i: (q[i], -i))
    exps = [math.exp((v-max(q))/.01) for v in q]; total = sum(exps)
    probabilities = [v/total for v in exps]
    soft_index = max(allowed, key=lambda i: (probabilities[i], -i))
    assert index == soft_index
    cases = [set() for _ in range(5)]
    for row in model['support_records']:
        distance = math.sqrt(sum((a-b)**2 for a, b in zip(z, row['normalized_features']))/25.)
        if distance <= 1.: cases[row['action_index']].add(row['case_sha256'])
    return {'schema': 'v8.exact_terminal_critic_prediction.v7', 'mechanism': model['mechanism'],
            'action_index': index, 'Q_terminal_return': q, 'direct_softmax_Q_probabilities': probabilities,
            'direct_Q_greedy_index': index, 'same_Q_softmax_index': soft_index,
            'full_recipe_sha256': model['full_recipe_sha256'][index],
            'proposal_action': copy.deepcopy(model['action_contracts'][index]['action']),
            'proposal_full_recipe': copy.deepcopy(model['action_contracts'][index]),
            'support_counts_report_only': [len(c) for c in cases], 'allowed_from_past_replay_only': allowed,
            'future_qualification_mask_used': False, 'original_qualification_granted': False,
            'twins_are_same_unique_convex_optimum_not_independent_ensemble': True,
            'actor_or_temperature_gradient_steps': 0, 'state_API_Q_dot_calls': 5,
            'reason': 'EXACT_TERMINAL_Q_GREEDY_ALL_FIVE_VANILLA_PERMISSION'}


def snapshot(model):
    validate(model)
    body = copy.deepcopy(model)
    return {'schema': 'v8.exact_terminal_critic_snapshot.v7', 'model': body, 'snapshot_sha256': digest(body)}


def restore(saved, *, expected_source_sha256, expected_contract_sha256, expected_recipe_sha256):
    assert saved['schema'] == 'v8.exact_terminal_critic_snapshot.v7' and digest(saved['model']) == saved['snapshot_sha256']
    model = saved['model']; validate(model)
    assert model['source_manifest_sha256'] == expected_source_sha256 and model['approved_contract_sha256'] == expected_contract_sha256
    assert model['full_recipe_sha256'] == expected_recipe_sha256
    return copy.deepcopy(model)
