"""冻结简单强对照的纯推理；只接收因果payload和冻结历史摘要。"""
import numpy as np
from value_api import to_context25, transform


def predict_control(bundle, causal_context, control='IF_STUMP_TRAIN'):
    ctx = to_context25(causal_context)
    if control == 'BEST_FIXED_TRAIN':
        chosen = bundle['best_fixed']
        detail = {'kind': 'constant'}
    elif control == 'IF_STUMP_TRAIN':
        tree = bundle['if_stump']
        if tree['kind'] == 'constant':
            chosen = tree['recipe']
        else:
            chosen = tree['left_recipe'] if ctx['features'][tree['feature_index']] <= tree['threshold'] else tree['right_recipe']
        detail = tree
    elif control == 'NEAREST_CONTEXT':
        z = transform(bundle['normalizer'], ctx)
        options, detail = [], []
        for item in bundle['menu']:
            records = [r for r in bundle['past_completed_feedback'] if r['recipe_sha256'] == item['recipe_sha256']]
            if not records:
                continue
            nearest = min(records, key=lambda r: float(np.mean((np.asarray(r['normalized_context']) - z) ** 2)))
            distance = float(np.sqrt(np.mean((np.asarray(nearest['normalized_context']) - z) ** 2)))
            detail.append({'tag': item['tag'], 'nearest_frozen_training_context': nearest['training_context_id'], 'distance': distance, 'historical_qualification': nearest['original_qualified'], 'historical_delta_JF_N_s': nearest['delta_JF_N_s']})
            if nearest['original_qualified'] and nearest['complete']:
                options.append((nearest['delta_JF_N_s'], item['tag'], item['recipe_sha256']))
        chosen = min(options)[-1] if options else next(a['recipe_sha256'] for a in bundle['menu'] if a['tag'] == 'B')
    else:
        raise ValueError('未知冻结对照：' + control)
    item = next(a for a in bundle['menu'] if a['recipe_sha256'] == chosen)
    return {'schema': 'v8.frozen_simple_control_decision.v1', 'control': control,
            'choice_tag': item['tag'], 'choice_recipe_sha256': chosen, 'choice_action': item['action'],
            'detail': detail, 'future_qualification_mask_used': False, 'risk_is_safety_certificate': False,
            'original_full_gate_is_final': True}
