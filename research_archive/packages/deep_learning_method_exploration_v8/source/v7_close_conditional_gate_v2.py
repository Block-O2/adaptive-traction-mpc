"""Close the registered CF retrospective development gate; never deploy/refit."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((P / path).read_text())


def sha(path):
    return hashlib.sha256((P / path).read_bytes()).hexdigest()


def put_new(path, data):
    with (P / path).open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


groups = ['CFACTORH01', 'CFACTORL01']
joined_path = 'analysis/CAUSAL_STUMPS_FINAL_IDENTITY_DIAGNOSTIC_V2.json'
joined = read(joined_path)
model_path = 'models/CAUSAL_STUMPS_V1/MODEL.json'
model = read(model_path)
gate = read('agent_reviews/conditional_rule_driver/DEVELOPMENT_GATE_V2_SKELETON.json')
labels = {r['group']: r['actual']['label'] for r in joined['rows']}
assert set(labels) == set(groups)
inputs, predictions, evidence = {}, {n: {} for n in model['models']}, {}
for group in groups:
    end = read('owned/' + group + '_SUPERVISOR_END.json')
    assert end['state'] == 'STOP' and not end['survivors']
    context_path = 'history/' + group + '_PREFORK_CAUSAL_CONTEXT.json'
    context = read(context_path)
    f = dict(zip(context['feature_names'], context['features']))
    inputs[group] = {
        'K_stump': (f['estimated_beta_k1_passive_stiffness'] + f['estimated_beta_k2_passive_stiffness']) / 2,
        'geometry_stump': f['estimated_geometry_thigh_length'],
    }
    for name, m in model['models'].items():
        assert m['polarity'] in ['gt_positive', 'le_positive']
        predictions[name][group] = int(inputs[group][name] > m['threshold']) if m['polarity'] == 'gt_positive' else int(inputs[group][name] <= m['threshold'])
    config_path = 'experiments/' + group + '.json'
    c = read(config_path)
    assert sha(c['case_path']) == c['case_sha256']
    gate['development_case_sha256'][group] = c['case_sha256']
    evidence[context_path] = sha(context_path)
    evidence[config_path] = sha(config_path)
    for tag in ['B', 'EARLY_H150']:
        for prefix, suffix in [('attempts/', '_RESULT.json'), ('analysis/native_metrics/', '.json')]:
            path = prefix + group + '_' + tag + suffix
            evidence[path] = sha(path)

counts = {n: sum(predictions[n][g] == labels[g] for g in groups) for n in predictions}
constants = {'always_B': sum(labels[g] == 0 for g in groups), 'always_EARLY_H150': sum(labels[g] == 1 for g in groups)}
chosen = 'K_stump' if counts['K_stump'] >= counts['geometry_stump'] else 'geometry_stump'
both_B = all(read('attempts/' + g + '_B_RESULT.json')['qualified'] for g in groups)
observed = all(r['actual']['label_observed'] for r in joined['rows'])
balanced = sorted(labels.values()) == [0, 1]
passed = both_B and observed and balanced and counts[chosen] == 2 and max(constants.values()) == 1
gate.update(status='DEVELOPMENT_GATE_V2_PASS' if passed else 'NOT_MET', labels=labels,
            both_B_qualified=both_B, both_actual_labels_observed=observed,
            frozen_predictions=predictions, correct_counts=counts,
            constant_correct_count=max(constants.values()), selected_name=chosen if passed else None)
gate.update(created_unix=time.time(), inputs=inputs, constant_counts=constants,
            balanced_labels=balanced, threshold_refits=0, new_model_fits=0,
            actual_labels_and_components={r['group']: r['actual'] for r in joined['rows']},
            original_prospective_status={r['group']: r['prospective_prediction_admissible_after_final_join'] for r in joined['rows']},
            evidence_sha256={**evidence, joined_path: sha(joined_path), model_path: sha(model_path),
                             'source/v7_close_conditional_gate_v2.py': sha('source/v7_close_conditional_gate_v2.py')},
            future_physics='CONDITIONAL_NOT_LAUNCHED' if passed else 'NOT_RUN_GATE_NOT_MET',
            future_groups=['CVNHS01', 'CVHNM01'], future_case_or_label_substitution=False,
            actor_descriptor_created=False, validation_cases_installed=False,
            failure_reason=None if passed else 'Both frozen benefit labels are 0; neither stump exceeds always_B, despite CFL original qualification. Hip jerk remains part of unchanged benefit label.',
            scope='Retrospective CF development only; CFL prospective NOT_TESTED and original V1 NOT_RUN remain unchanged.')
put_new('freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json', gate)
event = {'event': 'CLOSE_DEVELOPMENT_GATE', 'unix': time.time(), 'id': gate['protocol_id'],
         'status': gate['status'], 'gate_path': 'freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json',
         'gate_sha256': sha('freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json'),
         'labels': labels, 'counts': counts, 'constant_counts': constants,
         'future_physics': gate['future_physics'], 'new_fits': 0, 'threshold_refits': 0,
         'preserved_prospective_NOT_TESTED': 'CFACTORL01', 'source_sha256': sha('source/v7_close_conditional_gate_v2.py')}
with (P / 'RESEARCH_DECISIONS.jsonl').open('a') as f:
    f.write(json.dumps(event, ensure_ascii=False) + '\n')
print(json.dumps(event, ensure_ascii=False))
