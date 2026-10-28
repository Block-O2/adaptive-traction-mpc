"""A5 纯 SOURCE_ONLY API：成本不变，仅比较历史操作资格支持；无当前结果mask。"""
import copy
import hashlib
import json
import math
from causal_api import to_context_full

METHODS = ['A3_RISK48', 'A5_RISK50', 'RISK_OFF', 'NEAREST48', 'NEAREST50', 'PHASE_ANY_FAIL50', 'ALWAYS_B']
OBJECTIVES = ['JF_QUALIFIED', 'JM_QUALIFIED', 'STRICT_JM']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def bump(ledger, key, number=1):
    ledger[key] = ledger.get(key, 0) + number


def transform(spec, context):
    return [0. if pos in spec.get('numeric_constant_positions', []) else (context['features'][i] - c) / s
            for pos, (i, c, s) in enumerate(zip(spec['indices'], spec['center'], spec['scale']))]


def design(z, action, count):
    return [float(i == action) for i in range(count)] + [v if i == action else 0. for i in range(count) for v in z]


def dot(a, b):
    assert len(a) == len(b)
    return sum(x * y for x, y in zip(a, b))


def sigmoid(value):
    if value >= 0:
        return 1. / (1. + math.exp(-value))
    v = math.exp(value)
    return v / (1. + v)


def _costs(bundle, context, ledger):
    if bundle.get('development_only') is True:
        assert bundle['archived_context39_sha256'] == digest(context['features'])
        bump(ledger, 'archived_cost_and_risk48_batch')
        return copy.deepcopy(bundle['archived_A3_ABS_WRENCH39_predictions'])
    assert bundle['development_only'] is False
    spec = bundle['frozen_A3_cost_model']; head = spec['cost_heads']['ABS']; z = transform(spec, context)
    out = []
    bump(ledger, 'frozen_A3_full_cost_batch')
    for index, item in enumerate(bundle['menu']):
        vector = design(z, index, len(bundle['menu']))
        estimates = []
        for weights in head['weights']:
            values = []
            for j in range(2):
                bump(ledger, 'frozen_cost_scalar_dot_entry')
                values.append(dot(vector, [row[j] for row in weights]) * head['target_scale'][j] + head['target_center'][j])
                bump(ledger, 'frozen_cost_scalar_dot_completed')
            estimates.append(values)
        mean = [sum(v[j] for v in estimates) / len(estimates) for j in range(2)]
        spread = [(sum((v[j] - mean[j]) ** 2 for v in estimates) / len(estimates)) ** .5 for j in range(2)]
        points = spec['support_train_z'][index]
        distance = min((sum((a - b) ** 2 for a, b in zip(p, z)) / len(z)) ** .5 for p in points) if points and z else (0. if points else None)
        supported = len(points) >= bundle['minimum_support_contexts'] and distance is not None and distance <= bundle['distance_limit']
        bump(ledger, 'matched_risk48_scalar_dot_entry')
        risk48 = sigmoid(dot(vector, spec['risk_weights']))
        bump(ledger, 'matched_risk48_scalar_dot_completed')
        out.append({'tag': item['tag'], 'recipe_sha256': item['recipe_sha256'],
            'predicted_JF_component': mean[0], 'predicted_JM_component': mean[1],
            'ridge_spread_JF': spread[0], 'ridge_spread_JM': spread[1],
            'qualification_failure_score': risk48, 'support_context_count': len(points),
            'nearest_train_RMS_distance': distance, 'supported': supported})
    baseline = next(r for r in out if r['tag'] == 'B')
    for row in out:
        row['predicted_delta_JF_vs_B'] = row['predicted_JF_component'] - baseline['predicted_JF_component']
        row['predicted_delta_JM_vs_B'] = row['predicted_JM_component'] - baseline['predicted_JM_component']
    return out


def _nearest(history, recipe, z, ledger):
    bump(ledger, 'nearest_action_query_entry')
    points = [r for r in history if r['recipe_sha256'] == recipe]
    if not points:
        bump(ledger, 'nearest_action_query_completed')
        return {'status': 'UNKNOWN_NO_PAST_ACTION_LABEL', 'admitted': False, 'distance': None}
    distances = []
    for row in points:
        bump(ledger, 'nearest_history_distance_entry')
        distance = sum((a - b) ** 2 for a, b in zip(row['z39'], z)) / len(z)
        bump(ledger, 'nearest_history_distance_completed')
        distances.append((distance, row['operational_qualified']))
    best = min(d for d, _ in distances)
    tied = [ok for d, ok in distances if d <= best + 1e-12]
    bump(ledger, 'nearest_action_query_completed')
    return {'status': 'PAST_NEAREST_TIES_FAIL_VETO', 'admitted': all(tied), 'distance': best ** .5}


def predict_all(bundle, raw, *, source_proof=None, ledger=None):
    """一个合法OUT0返回7方法×3目标；只传raw+实际七角色proof，不接caseID/当前标签。"""
    assert bundle['schema'] == 'v8.a5.operational_qualification_bundle.v1'
    assert bundle['risk_threshold'] == .5 and bundle['minimum_support_contexts'] == 2 and bundle['distance_limit'] == 3.
    if ledger is None:
        ledger = {}
    bump(ledger, 'batch_API_entry')
    context = to_context_full(raw, bundle['input_source_profiles'], source_proof)
    bump(ledger, 'context39_extraction_completed')
    assert context['feature_names'] == bundle['feature_names39']
    predictions = _costs(bundle, context, ledger)
    assert [p['recipe_sha256'] for p in predictions] == [m['recipe_sha256'] for m in bundle['menu']]
    spec = bundle['risk50_model']; z = transform(spec, context)
    for cohort in ('48', '50'):
        bump(ledger, 'nearest_control_batch_entry')
        for row in predictions:
            row['nearest' + cohort] = _nearest(spec['history' + cohort], row['recipe_sha256'], z, ledger)
        bump(ledger, 'nearest_control_batch_completed')
    bump(ledger, 'phase_if_control_batch_entry')
    for index, row in enumerate(predictions):
        vector = design(z, index, len(bundle['menu']))
        bump(ledger, 'risk50_scalar_dot_entry')
        row['operational_failure_probability50'] = sigmoid(dot(vector, spec['weights']))
        bump(ledger, 'risk50_scalar_dot_completed')
        if row['tag'] in ('EARLY_PHASE', 'LATE_PHASE'):
            seen = [r['operational_qualified'] for r in spec['history50'] if r['recipe_sha256'] == row['recipe_sha256']]
            row['phase_if50'] = {'status': 'TRAIN_PHASE_ANY_FAIL' if seen else 'UNKNOWN_NO_PAST_ACTION_LABEL', 'admitted': bool(seen) and all(seen)}
        else:
            row['phase_if50'] = {'status': 'NON_PHASE_NO_VETO', 'admitted': True}
    bump(ledger, 'phase_if_control_batch_completed')
    for row in predictions:
        row['predicted_operational_admission_by_method'] = {
            'A3_RISK48': row['qualification_failure_score'] < .5,
            'A5_RISK50': row['operational_failure_probability50'] < .5,
            'RISK_OFF': True, 'NEAREST48': row['nearest48']['admitted'],
            'NEAREST50': row['nearest50']['admitted'], 'PHASE_ANY_FAIL50': row['phase_if50']['admitted'],
            'ALWAYS_B': row['tag'] == 'B'}
    decisions = {}
    for method in METHODS:
        for objective in OBJECTIVES:
            bump(ledger, 'selector_decision_entry')
            if method == 'ALWAYS_B':
                chosen = next(r for r in predictions if r['tag'] == 'B'); fallback = False
            else:
                allowed = []
                for row in predictions:
                    admit = row['predicted_operational_admission_by_method'][method]
                    if row['supported'] and admit and (objective != 'STRICT_JM' or row['predicted_delta_JM_vs_B'] <= 1e-12):
                        allowed.append(row)
                key = 'predicted_JM_component' if objective == 'JM_QUALIFIED' else 'predicted_JF_component'
                chosen = min(allowed, key=lambda r: (r[key], r['tag'])) if allowed else None
                fallback = chosen is None
            item = next((m for m in bundle['menu'] if chosen and m['recipe_sha256'] == chosen['recipe_sha256']), None)
            decisions[method + '/' + objective] = {'choice_tag': None if chosen is None else chosen['tag'],
                'choice_recipe_sha256': None if item is None else item['recipe_sha256'],
                'choice_action': None if item is None else item['action'], 'fallback_B_after_predictive_abstain': fallback,
                'execution_choice_tag': 'B' if fallback else chosen['tag'],
                'actual_future_qualification': 'UNKNOWN_NOT_A_CURRENT_MASK'}
            bump(ledger, 'selector_decision_completed')
    bump(ledger, 'batch_API_completed')
    return {'schema': 'v8.a5.support_decisions.v1', 'decisions': decisions, 'predictions': predictions,
        'input_representation': 'WRENCH39', 'source_identity_checked': True, 'raw77_valid': False,
        'primary': 'A5_RISK50/JF_QUALIFIED', 'original_risk_threshold': .5,
        'cost_weights_and_normalization': 'FROZEN_A3_OLD48_UNCHANGED',
        'current_B_or_future_outcome_used': False, 'qualified_or_conformal_safety_claim': False}
