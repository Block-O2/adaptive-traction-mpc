"""无训练/物理的冻结推理和输入防火墙验证，构造简单对照冻结摘要。"""
from pathlib import Path
import copy
import hashlib
import json
import time
from controls_api import predict_control
from value_api import predict, to_context25, transform

P = Path(__file__).resolve().parents[1]
OLD = P.parents[2] / 'autonomous_learning_smoothness_v7'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(rel, x):
    path = P / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists()
    path.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    start = time.monotonic()
    value = json.loads((P / 'models/VALUE_FAMILY_V1_FROZEN.json').read_text())
    data = json.loads((P / 'data/HISTORICAL_RECIPE_DATASET_V2.json').read_text())
    methods = list(value['methods'])
    context_rows = {}
    for row in data['rows']:
        context_rows.setdefault(row['group'], row)
    hashes = {a['recipe_sha256'] for a in value['menu']}
    feedback = []
    for row in data['rows']:
        if row['action_recipe_sha256'] not in hashes:
            continue
        lab = row['labels_evaluation_only']
        feedback.append({'recipe_sha256': row['action_recipe_sha256'], 'normalized_context': transform(value['methods']['DELTA_25'], to_context25(row['context'])).tolist(),
                         'training_context_id': row['group'], 'complete': lab['complete'],
                         'original_qualified': lab['original_qualified'], 'delta_JF_N_s': lab['delta_JF_vs_B_N_s'], 'delta_JM_Nm_s': lab['delta_JM_vs_B_Nm_s']})
    controls = {'schema': 'v8.simple_controls_frozen.v1', 'frozen_unix': time.time(), 'value_bundle_sha256': sha(P / 'models/VALUE_FAMILY_V1_FROZEN.json'),
                'data_sha256': value['data_sha256'], 'menu': value['menu'], 'best_fixed': value['strong_controls']['best_fixed'], 'if_stump': value['strong_controls']['if_stump'],
                'normalizer': {k: value['methods']['DELTA_25'][k] for k in ['indices', 'center', 'scale']}, 'past_completed_feedback': feedback,
                'source_sha256': {'controls_api.py': sha(P / 'source/controls_api.py'), 'value_api.py': sha(P / 'source/value_api.py')},
                'labels_scope': '仅已完成且已暴露的历史训练反馈，不含当前迁移结果', 'new_fits': 0, 'new_physics': 0}
    audit = []
    for group, row in context_rows.items():
        raw = json.loads((OLD / 'history' / (group + '_PREFORK_CAUSAL_CONTEXT.json')).read_text())
        for method in methods:
            for objective in ['JF_QUALIFIED', 'STRICT_JM']:
                a = predict(value, raw, method, objective)
                b = predict(value, row['context'], method, objective)
                assert a == b, (group, method, objective, '原始payload与已提取context不一致')
                perturbed = copy.deepcopy(raw)
                perturbed['case_key'] = 'UNTRUSTED_FUTURE_CASE'
                perturbed['future_costs_and_PASS'] = {'JF': -1e9, 'JM': -1e9, 'PASS': True, 'best_action': 'EARLY_PHASE'}
                body = {k: v for k, v in perturbed.items() if k != 'causal_payload_sha256'}
                perturbed['causal_payload_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                assert predict(value, perturbed, method, objective) == a, '不相关未来字段改变当前预测'
                audit.append({'context': group, 'method': method, 'objective': objective, 'raw_vs_subset_exact_equal': True, 'future_field_perturbation_exact_equal': True, 'choice': a['choice_tag']})
        for control in ['BEST_FIXED_TRAIN', 'IF_STUMP_TRAIN', 'NEAREST_CONTEXT']:
            assert predict_control(controls, raw, control) == predict_control(controls, row['context'], control)
    rejected = False
    try:
        predict(value, data['rows'][0])
    except AssertionError:
        rejected = True
    assert rejected, '含当前结果标签的数据行必须拒绝'
    put('models/STRONG_CONTROLS_V1_FROZEN.json', controls)
    put('analysis/INFERENCE_FIREWALL_AUDIT_V1.json', {'checks': audit, 'value_methods': len(methods), 'contexts': len(context_rows), 'label_bearing_row_rejected': rejected,
                                                  'simple_controls_raw_subset_exact_equal': True, 'wall_s': time.monotonic() - start, 'new_fits': 0, 'new_physics': 0,
                                                  'limitation': '验证纯输入通路，不证明25D充分性、概率校准、完整运动资格、域外性能或实际attempt节省',
                                                  'process_metadata': '前台工具返回退出码，原fit未独立持久化PID/start_ticks；此限制保留，不补造',
                                                  'value_bundle_sha256': sha(P / 'models/VALUE_FAMILY_V1_FROZEN.json'), 'controls_bundle_sha256': sha(P / 'models/STRONG_CONTROLS_V1_FROZEN.json')})
    print(json.dumps({'contexts': len(context_rows), 'value_decision_checks': len(audit), 'control_decision_checks': len(context_rows) * 3, 'value_bundle_sha256': sha(P / 'models/VALUE_FAMILY_V1_FROZEN.json'), 'controls_bundle_sha256': sha(P / 'models/STRONG_CONTROLS_V1_FROZEN.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
