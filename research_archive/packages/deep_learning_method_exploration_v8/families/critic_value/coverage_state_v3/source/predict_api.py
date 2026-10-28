"""A3 纯推理候选；无文件/模型加载，无当前结果资格 mask。"""
import math
from causal_api import to_context_full


def transform(spec, context):
    return [0. if pos in spec.get('numeric_constant_positions',[]) else (context['features'][i]-c)/s for pos,(i,c,s) in enumerate(zip(spec['indices'],spec['center'],spec['scale']))]


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


def _method(method):
    kind, representation = method.rsplit('_',1)
    assert kind in ['ABS','DELTA'] and representation in ['25','KIN33','WRENCH39']
    return 'ABS' if kind=='ABS' else 'DELTA_B', representation


def predict(bundle, causal_context, method='ABS_WRENCH39', objective='JF_QUALIFIED', risk_mode='ON', cohort='MERGED', *, source_proof=None):
    context = to_context_full(causal_context,bundle['input_source_profiles'],source_proof)
    assert bundle['schema'] == 'v8.a3.scoped_state_bundle.v1'
    assert objective in ['JF_QUALIFIED', 'JM_QUALIFIED', 'STRICT_JM'] and risk_mode in ['ON', 'OFF']
    kind, dimensions = _method(method)
    spec = bundle['cohorts'][cohort]['models'][dimensions]
    head = spec['cost_heads'][kind]
    z = transform(spec, context)
    menu = bundle['menu']
    predictions = []
    for index, item in enumerate(menu):
        vector = design(z, index, len(menu))
        estimates = [[dot(vector, [row[j] for row in weights]) * head['target_scale'][j] + head['target_center'][j] for j in range(2)] for weights in head['weights']]
        mean = [sum(v[j] for v in estimates) / len(estimates) for j in range(2)]
        spread = [(sum((v[j] - mean[j]) ** 2 for v in estimates) / len(estimates)) ** .5 for j in range(2)]
        if kind == 'DELTA_B' and item['tag'] == 'B':
            mean, spread = [0., 0.], [0., 0.]  # 同B相对自身恒等式，不读未来B。
        points = spec['support_train_z'][index]
        distance = min((sum((a - b) ** 2 for a, b in zip(p, z)) / len(z)) ** .5 for p in points) if points and z else (0. if points else None)
        supported = len(points) >= bundle['minimum_support_contexts'] and distance is not None and distance <= bundle['distance_limit']
        predictions.append({'tag': item['tag'], 'recipe_sha256': item['recipe_sha256'],
            'predicted_JF_component': mean[0], 'predicted_JM_component': mean[1],
            'ridge_spread_JF': spread[0], 'ridge_spread_JM': spread[1],
            'qualification_failure_score': sigmoid(dot(vector, spec['risk_weights'])),
            'support_context_count': len(points), 'nearest_train_RMS_distance': distance, 'supported': supported})
    baseline = next(r for r in predictions if r['tag'] == 'B')
    for row in predictions:
        row['predicted_delta_JF_vs_B'] = row['predicted_JF_component'] - baseline['predicted_JF_component']
        row['predicted_delta_JM_vs_B'] = row['predicted_JM_component'] - baseline['predicted_JM_component']
    allowed = [r for r in predictions if r['supported'] and (risk_mode == 'OFF' or r['qualification_failure_score'] < bundle['risk_threshold'])]
    if objective == 'STRICT_JM':
        allowed = [r for r in allowed if r['predicted_delta_JM_vs_B'] <= 1e-12]
    key = 'predicted_JM_component' if objective == 'JM_QUALIFIED' else 'predicted_JF_component'
    chosen = min(allowed, key=lambda row: (row[key], row['tag'])) if allowed else None
    item = next(m for m in menu if m['recipe_sha256'] == chosen['recipe_sha256']) if chosen else None
    return {'schema': 'v8.a3.scoped_state_decision.v1', 'input_representation': dimensions, 'source_identity_checked': True, 'legacy77_valid': False, 'cohort': cohort, 'method': method, 'objective': objective, 'risk_mode': risk_mode,
        'choice_tag': chosen['tag'] if chosen else None, 'choice_recipe_sha256': chosen['recipe_sha256'] if chosen else None,
        'choice_action': item['action'] if item else None, 'predictions': predictions,
        'reason': 'PREDICTED_COMPONENT_RISK_AND_SUPPORT' if chosen else 'ABSTAIN_NO_SUPPORTED_PREDICTED_ADMISSIBLE_ACTION',
        'future_qualification_mask_used': False, 'original_gate_or_risk_calibration_claim': False,
        'ridge_spread_is_calibrated_uncertainty': False, 'current_B_result_used': False}


def predict_control(bundle, causal_context, control='IF_STUMP', objective='JF_QUALIFIED', cohort='MERGED', *, representation='WRENCH39', source_proof=None):
    context = to_context_full(causal_context,bundle['input_source_profiles'],source_proof)
    controls = bundle['cohorts'][cohort]['controls'][representation][objective]
    if control == 'CONSTANT_B':
        chosen = next(m['recipe_sha256'] for m in bundle['menu'] if m['tag'] == 'B')
        detail = {'kind': 'constant_B'}
    elif control == 'BEST_FIXED':
        chosen, detail = controls['best_fixed'], {'kind': 'best_fixed_train'}
    elif control == 'IF_STUMP':
        detail = controls['if_stump']
        chosen = detail['recipe'] if detail['kind'] == 'constant' else detail['left_recipe'] if context['features'][detail['feature_index']] <= detail['threshold'] else detail['right_recipe']
    else:
        assert control == 'NEAREST'
        spec = bundle['cohorts'][cohort]['models'][representation]
        z = transform(spec, context)
        choices, detail = [], []
        for item in bundle['menu']:
            records = [r for r in controls['past_feedback'] if r['recipe_sha256'] == item['recipe_sha256']]
            if not records:
                continue
            nearest = min(records, key=lambda r: sum((a - b) ** 2 for a, b in zip(r['normalized_context'], z)))
            detail.append({'tag': item['tag'], 'nearest_training_context': nearest['training_context'], 'historical_admissible': nearest['admissible']})
            if nearest['admissible']:
                choices.append((nearest['component_delta'], item['tag'], item['recipe_sha256']))
        chosen = min(choices)[-1] if choices else next(m['recipe_sha256'] for m in bundle['menu'] if m['tag'] == 'B')
    item = next(m for m in bundle['menu'] if m['recipe_sha256'] == chosen)
    return {'schema': 'v8.a3.simple_control_decision.v1', 'input_representation': representation, 'source_identity_checked': True, 'legacy77_valid': False, 'cohort': cohort, 'control': control, 'objective': objective,
        'choice_tag': item['tag'], 'choice_recipe_sha256': chosen, 'choice_action': item['action'], 'detail': detail,
        'future_qualification_mask_used': False, 'current_B_result_used': False}
