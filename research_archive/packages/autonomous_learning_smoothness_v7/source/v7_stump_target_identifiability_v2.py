"""Registered retrospective target diagnostic, no fit or policy selection."""
from pathlib import Path
import hashlib
import importlib.util
import json
import time

P = Path(__file__).resolve().parents[1]
dest = P / 'analysis/STUMP_TARGET_IDENTIFIABILITY_DIAGNOSTIC_V2.json'
assert not dest.exists()
inputs = {}


def read(relative):
    path = P / relative
    inputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


model = read('models/CAUSAL_STUMPS_V1/MODEL.json')
driver_file = P / 'agent_reviews/conditional_rule_driver/v7_conditional_rule_driver_v2.py'
assert hashlib.sha256(driver_file.read_bytes()).hexdigest() == '788ee828f19b29f47cfe7599bf71044cce6a563392df916e6880377f8d17e2bb'
spec = importlib.util.spec_from_file_location('pure_static_driver_no_top_level_model', driver_file)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
rows = []
for group in ['EARLYN01', 'EARLYL01', 'EARLYH01', 'CFACTORH01', 'CFACTORL01', 'HOLDSS03']:
    context = read('history/' + group + '_PREFORK_CAUSAL_CONTEXT.json')
    qa = driver.validate_context(context, model['feature_names'])
    assert qa['status'] == 'VALID_FOR_TWO_STUMP_INPUTS_ONLY'
    b = read('attempts/' + group + '_B_RESULT.json')
    h = read('attempts/' + group + '_EARLY_H150_RESULT.json')
    assert b['complete'] and b['qualified']
    bm = read('analysis/native_metrics/' + b['id'] + '.json')
    hm = read('analysis/native_metrics/' + h['id'] + '.json') if h['complete'] else None
    components = {
        'complete': h['complete'], 'original_qualified': bool(h['qualified']),
        'JF_less_than_B': hm is not None and hm['JF'] < bm['JF'],
        'both_native_jerk_less_than_B': hm is not None and all(x < y for x, y in zip(hm['native_motion']['jerk_deg_s3']['rms'], bm['native_motion']['jerk_deg_s3']['rms'])),
        'native_force_norm_rate_less_than_B': hm is not None and hm['native_force']['norm_rate']['rms'] < bm['native_force']['norm_rate']['rms'],
    }
    preds = {name: driver.predict_one(m, qa['inputs'][name]) for name, m in model['models'].items()}
    rows.append({'group': group, 'scope': 'TRAINING' if group in model['training_groups'] else 'RETROSPECTIVE_CF_DEVELOPMENT' if group.startswith('CF') else 'POSTHOC_EXPOSED_SS_DIAGNOSTIC_NOT_PROSPECTIVE',
                 'purpose3_validation': qa, 'predictions_unchanged_model': preds,
                 'original_benefit_label': int(all(components.values())), 'benefit_components': components,
                 'qualification_only_explanatory_label': int(h['complete'] and h['qualified']),
                 'B_native_jerk_RMS': bm['native_motion']['jerk_deg_s3']['rms'],
                 'EARLY_H150_native_jerk_RMS': hm['native_motion']['jerk_deg_s3']['rms'] if hm else None,
                 'B_JF_JM': [bm['JF'], bm['JM']], 'EARLY_H150_JF_JM': [hm['JF'], hm['JM']] if hm else None,
                 'JM_not_in_label_and_not_hidden': True})
scores = {}
for scope in ['TRAINING', 'RETROSPECTIVE_CF_DEVELOPMENT', 'POSTHOC_EXPOSED_SS_DIAGNOSTIC_NOT_PROSPECTIVE']:
    part = [r for r in rows if r['scope'] == scope]
    scores[scope] = {'n': len(part), 'original_benefit': {}, 'qualification_only_explanation': {}}
    for name in model['models']:
        scores[scope]['original_benefit'][name] = sum(r['predictions_unchanged_model'][name] == r['original_benefit_label'] for r in part)
        scores[scope]['qualification_only_explanation'][name] = sum(r['predictions_unchanged_model'][name] == r['qualification_only_explanatory_label'] for r in part)
    for name, constant in [('always_B', 0), ('always_EARLY_H150', 1)]:
        scores[scope]['original_benefit'][name] = sum(r['original_benefit_label'] == constant for r in part)

assert scores['TRAINING']['original_benefit']['K_stump'] == 3
assert all(r['original_benefit_label'] == r['qualification_only_explanatory_label'] for r in rows if r['scope'] == 'TRAINING')
assert scores['RETROSPECTIVE_CF_DEVELOPMENT']['original_benefit']['always_B'] == 2
result = {'id': 'STUMP_TARGET_IDENTIFIABILITY_DIAGNOSTIC_V2', 'status': 'COMPLETE_NEGATIVE_BENEFIT_RESULT_RETAINED',
          'created_unix': time.time(), 'rows': rows, 'scores': scores,
          'confirmed': 'All three training labels confound qualification and full benefit. In CFL original qualification passes but hip jerk increases; benefit remains0. Frozen K rule classifies original qualification in both CF development cases, but not the registered benefit better than always_B.',
          'supported_not_causal_proof': 'Training inputs support a qualification correlation; these few observations cannot identify what internal physical mechanism the stump learned or prove full benefit on new states.',
          'original_gate': 'NOT_MET_UNCHANGED', 'CVNHS01_CVHNM01': 'NOT_RUN_UNCHANGED',
          'new_fits': 0, 'threshold_refits': 0, 'new_neural_model_calls': 0, 'new_physics': 0,
          'pure_stump_prediction_rechecks': 12, 'controller_deployment': False,
          'explanatory_target_never_replaces_original_success_label': True,
          'input_sha256': inputs, 'driver_sha256': hashlib.sha256(driver_file.read_bytes()).hexdigest(),
          'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
for rel, expected in inputs.items():
    assert hashlib.sha256((P / rel).read_bytes()).hexdigest() == expected
with dest.open('x') as f:
    f.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(scores, ensure_ascii=False))
