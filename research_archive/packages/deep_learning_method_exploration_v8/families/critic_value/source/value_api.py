"""纯因果 episode 价值预测 API；无文件读写、无仿真、无结果标签输入。"""
import hashlib
import json
import math
import numpy as np
from scipy.special import expit

BETA = ['a_inertia_combination', 'b_distal_inertia_combination', 'd_mass_length_com_combination', 'g1_proximal_gravity_combination', 'g2_distal_gravity_combination', 'k1_passive_stiffness', 'k2_passive_stiffness', 'rho1_stiffness_rest_combination', 'rho2_stiffness_rest_combination', 'bv1_viscous_damping', 'bv2_viscous_damping']
FEATURE_NAMES = ['estimated_beta_' + n for n in BETA] + ['estimated_geometry_' + n for n in ['hip_plane_x', 'hip_plane_z', 'thigh_length', 'knee_to_cuff_distance']] + ['residual_weight_' + j + '_' + n for j in ['hip', 'knee'] for n in ['constant', 'q_hip_normalized', 'q_knee_normalized', 'dq_hip_bounded', 'dq_knee_bounded']]


def to_context25(payload):
    """复制 OUT0 已有25数和质量；禁止补齐77D或读case/未来结果。"""
    assert isinstance(payload, dict) and 'labels_evaluation_only' not in payload, '只接受因果payload，不接受含标签数据行'
    if payload.get('schema') == 'ihear.causal_human_context.v1.77d':
        assert payload.get('hidden_or_future_inputs_used') is False
        assert payload.get('model_prediction_or_observe_calls') == 0
        assert payload.get('model_vector_valid') is False, '不能把原77D改名有效'
        assert payload.get('phase') == 'OUTBOUND' and abs(payload.get('task_s', 1)) < 1e-9
        assert payload.get('capture_position') == 'parent request boundary BEFORE fork loop/candidate selection/control mutation'
        body = {k: v for k, v in payload.items() if k != 'causal_payload_sha256'}
        checksum = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        assert checksum == payload.get('causal_payload_sha256')
        values = dict(zip(payload['feature_names'], payload['features']))
        assert values.get('decision_slot') == 0
    else:
        assert payload.get('schema') == 'v8.recipe_context.commissioning25.v1'
        assert payload.get('legacy77d_valid') is False
        assert payload.get('checks') and all(payload['checks'].values())
        assert payload['feature_names'] == FEATURE_NAMES
        values = dict(zip(payload['feature_names'], payload['features']))
    x = [values[n] for n in FEATURE_NAMES]
    assert all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in x)
    quality = payload['quality']
    assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in quality.values())
    return {'schema': 'v8.recipe_context.commissioning25.v1', 'feature_names': FEATURE_NAMES,
            'features': list(x), 'quality': dict(quality), 'legacy77d_valid': False,
            'checks': {'scoped_copy': True}, 'fit_absolute_timestamp': None}


def design(z, action_index, actions):
    one = np.zeros(actions)
    one[action_index] = 1.
    return np.r_[one, np.outer(one, z).ravel()]


def transform(spec, context):
    x = np.asarray(context['features'], float)[spec['indices']]
    return (x - np.asarray(spec['center'])) / np.asarray(spec['scale'])


def predict(bundle, causal_context, method=None, objective='JF_QUALIFIED', recipe_hashes=None):
    """返回分量、risk、support及实际recipe；不读取当前结果或case标签。"""
    ctx = to_context25(causal_context)
    method = method or bundle['primary_method']
    spec = bundle['methods'][method]
    z = transform(spec, ctx)
    menu = bundle['menu']
    rows = []
    for i, item in enumerate(menu):
        if recipe_hashes is not None and item['recipe_sha256'] not in recipe_hashes:
            continue
        d = design(z, i, len(menu))
        predictions = np.asarray([d @ np.asarray(w) for w in spec['cost_weights']])
        mean = predictions.mean(0) * np.asarray(spec['target_scale']) + np.asarray(spec['target_center'])
        std = predictions.std(0) * np.asarray(spec['target_scale'])
        risk = float(expit(d @ np.asarray(spec['risk_weights'])))
        train_z = np.asarray(spec['support_train_z'][i], float)
        distance = float(np.min(np.sqrt(np.mean((train_z - z) ** 2, axis=1)))) if train_z.size and len(z) else (0. if len(spec['support_train_z'][i]) else None)
        support = len(spec['support_train_z'][i]) >= 2 and distance is not None and distance <= bundle['distance_limit']
        rank_utility = float(d @ np.asarray(spec['rank_weights_JF']))
        rank_utility_JM = float(d @ np.asarray(spec['rank_weights_JM']))
        if item['tag'] == 'B' and spec['target_kind'] == 'DELTA_B':
            mean[:] = 0.  # 同一B相对自身的代数恒等式，非未来测量。
            std[:] = 0.
        if spec['target_kind'] == 'DELTA_STRONG' and item['tag'] == 'LATE_H150':
            mean[:] = 0.
            std[:] = 0.
        score = -rank_utility if spec['target_kind'] == 'PAIR' else float(mean[0])
        rows.append({'tag': item['tag'], 'recipe_sha256': item['recipe_sha256'], 'predicted_JF_component': float(mean[0]),
                     'predicted_JM_component': float(mean[1]), 'component_semantics': spec['target_kind'],
                     'ensemble_std_JF_JM': std.tolist(), 'qualification_failure_score': risk,
                     'rank_utility_JF': rank_utility, 'rank_utility_JM': rank_utility_JM,
                     'nearest_training_distance': distance, 'supported': support, 'score': score})
    if not rows:
        return {'choice_tag': None, 'reason': 'ABSTAIN_EMPTY_MENU', 'predictions': []}
    b = next((r for r in rows if r['tag'] == 'B'), None)
    for r in rows:
        if spec['target_kind'] == 'ABS' and b:
            r['predicted_delta_JM_vs_B'] = r['predicted_JM_component'] - b['predicted_JM_component']
        elif spec['target_kind'] == 'DELTA_B':
            r['predicted_delta_JM_vs_B'] = r['predicted_JM_component']
        else:
            r['predicted_delta_JM_vs_B'] = r['predicted_JM_component'] - b['predicted_JM_component'] if b else None
    allowed = [r for r in rows if r['supported'] and r['qualification_failure_score'] < .5]
    if objective == 'STRICT_JM':
        allowed = [r for r in allowed if r['predicted_delta_JM_vs_B'] is not None and r['predicted_delta_JM_vs_B'] <= 1e-12]
    else:
        assert objective == 'JF_QUALIFIED'
    chosen = min(allowed, key=lambda r: (r['score'], r['tag'])) if allowed else None
    return {'schema': 'v8.value_family_decision.v1', 'method': method, 'objective': objective,
            'choice_tag': None if chosen is None else chosen['tag'],
            'choice_recipe_sha256': None if chosen is None else chosen['recipe_sha256'],
            'choice_action': None if chosen is None else next(a['action'] for a in menu if a['tag'] == chosen['tag']),
            'reason': 'PREDICTED_RISK_SUPPORT_THEN_COMPONENT' if chosen else 'ABSTAIN_NO_SUPPORTED_PREDICTED_QUALIFIED_ACTION',
            'predictions': rows, 'future_qualification_mask_used': False,
            'original_full_gate_is_final': True, 'risk_is_calibrated_or_safety_certificate': False,
            'quality_warnings': [n for n, v in ctx['quality'].items() if (n.startswith('last_attempt_conditional_frozen_') or n in ['last_attempt_bound_hit', 'last_attempt_rate_limit_hit']) and v == 1]}
