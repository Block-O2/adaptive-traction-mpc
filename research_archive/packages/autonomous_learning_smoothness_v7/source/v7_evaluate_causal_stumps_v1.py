"""Final identity/time adjudication and two-case prediction diagnostic, no fit."""
from pathlib import Path
import hashlib
import json
import sys
import time

P = Path(__file__).resolve().parents[1]
groups = ['CFACTORH01', 'CFACTORL01']
dest = P / sys.argv[1]
assert not dest.exists(), 'NEW_OUTPUT_ONLY'
events = [json.loads(line) for line in (P / 'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
ledger = (P / 'runtime/ATTEMPTS.jsonl').read_bytes()


def read(f):
    return json.loads(f.read_text())


def sha(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def native(ident):
    return read(P / 'analysis/native_metrics' / (ident + '.json'))


model_file = P / 'models/CAUSAL_STUMPS_V1/MODEL.json'
model = read(model_file)
rows = []
for group in groups:
    assert read(P / 'owned' / (group + '_SUPERVISOR_END.json'))['state'] == 'STOP'
    base = P / 'predictions/CAUSAL_STUMPS_V1' / group
    receipt_file = P / 'audit' / (group + '_STUMP_MAIN_ADMISSIBILITY.json')
    errors = []
    admissible = False
    pred = None
    try:
        rec = read(receipt_file)
        assert rec['status'] == 'PREOUTCOME_RECEIPT_PENDING_FINAL_LEDGER_JOIN', 'NO_PREOUTCOME_MAIN_RECEIPT'
        assert rec['prediction_admissible'] is False
        assert not (base / 'WATCH_INVALIDATED.json').exists(), 'WATCH_INVALIDATED'
        end_file = base / 'WATCH_END.json'
        pred_file = base / 'PREDICTION.json'
        end = read(end_file)
        pred = read(pred_file)
        assert end['status'] == 'PREDICTION_SEALED_PENDING_MAIN_COMMIT_AUDIT' and end['local_deadline_checks_passed']
        assert end['prediction_admissible'] is False
        first_end = min(e['unix'] for e in events if e['event'] == 'END' and e['id'].startswith(group + '_') and e['id'] != group + '_parent')
        hard = rec['hard_wall']
        upper = min(first_end, hard)
        assert rec['captured_unix'] <= rec['ended_unix'] < upper
        assert all(f.stat().st_mtime < upper and f.stat().st_ctime < upper for f in [receipt_file, end_file, pred_file]), 'COMMIT_LATE_OR_METADATA_CHANGED'
        for rel, expected in rec['input_sha256'].items():
            assert sha(P / rel) == expected, 'INPUT_CHANGED:' + rel
        n = rec['ledger_prefix_length']
        assert hashlib.sha256(ledger[:n]).hexdigest() == rec['ledger_prefix_sha256'], 'LEDGER_PREFIX_CHANGED'
        assert sha(model_file) == pred['model_sha256'] == end['model_sha256']
        context = read(P / 'history' / (group + '_PREFORK_CAUSAL_CONTEXT.json'))
        features = dict(zip(context['feature_names'], context['features']))
        inputs = {'K_stump': (features['estimated_beta_k1_passive_stiffness'] + features['estimated_beta_k2_passive_stiffness']) / 2,
                  'geometry_stump': features['estimated_geometry_thigh_length']}
        assert inputs == pred['validation']['inputs']
        for name in ['K_stump', 'geometry_stump']:
            m = model['models'][name]
            y = int(inputs[name] > m['threshold']) if m['polarity'] == 'gt_positive' else int(inputs[name] <= m['threshold'])
            assert y == pred['predictions'][name]['predicted_qualified_benefit_label']
            assert pred['predictions'][name]['suggested_action'] == ('EARLY_H150' if y else 'B')
        assert context['model_vector_valid'] is False, 'FULL77D_MUST_REMAIN_INVALID'
        admissible = True
    except (AssertionError, KeyError, ValueError, FileNotFoundError) as error:
        errors.append(type(error).__name__ + ':' + str(error))
    bfile = P / 'attempts' / (group + '_B_RESULT.json')
    hfile = P / 'attempts' / (group + '_EARLY_H150_RESULT.json')
    label = None
    actual = {'label_observed': False, 'unobserved_is_not_negative': True}
    if bfile.exists() and hfile.exists():
        b, h = read(bfile), read(hfile)
        assert b['complete'] and b['qualified'], 'REGISTERED_B_QUALIFICATION_REQUIRED'
        bm = native(b['id'])
        if h['complete']:
            hm = native(h['id'])
            components = {'complete': True, 'original_qualified': h['qualified'], 'JF_less_than_B': hm['JF'] < bm['JF'],
                          'both_native_jerk_less_than_B': all(a < z for a, z in zip(hm['native_motion']['jerk_deg_s3']['rms'], bm['native_motion']['jerk_deg_s3']['rms'])),
                          'native_force_norm_rate_less_than_B': hm['native_force']['norm_rate']['rms'] < bm['native_force']['norm_rate']['rms']}
            label = int(all(components.values()))
            actual.update(label_observed=True, label=label, components=components, B_JF=bm['JF'], B_JM=bm['JM'], EARLY_H150_JF=hm['JF'], EARLY_H150_JM=hm['JM'], delta_JF=hm['JF']-bm['JF'], delta_JM=hm['JM']-bm['JM'], JM_not_scalarized=True)
        else:
            label = 0
            actual.update(label_observed=True, label=0, components={'complete': False, 'original_qualified': False}, partial_unranked=h.get('protected_task_failure'), error=h.get('error'), JM_not_scalarized=True)
    predictions = pred['predictions'] if admissible else None
    correct = {name: predictions[name]['predicted_qualified_benefit_label'] == label for name in ['K_stump', 'geometry_stump']} if predictions is not None and label is not None else None
    rows.append({'group': group, 'prospective_prediction_admissible_after_final_join': admissible, 'admissibility_errors': errors, 'predictions': predictions, 'actual': actual, 'correct': correct, 'controller_deployment': False, 'actual_attempts_saved': 0})
summary = {}
for name in ['K_stump', 'geometry_stump']:
    valid = [r for r in rows if r['correct'] is not None]
    summary[name] = {'prospective_cases_observed': len(valid), 'correct': sum(r['correct'][name] for r in valid), 'training_Human_contexts': 3, 'statistical_or_clinical_generalization_proven': False}
for name, constant in [('always_B', 0), ('always_EARLY_H150', 1)]:
    valid = [r for r in rows if r['correct'] is not None]
    summary[name] = {'prospective_cases_observed': len(valid), 'correct': sum(r['actual']['label'] == constant for r in valid), 'classification_comparator_only_not_a_deployed_policy': True}
dest.parent.mkdir(parents=True, exist_ok=True)
with dest.open('x') as f:
    f.write(json.dumps({'status': 'COMPLETE_PREDICTION_ONLY_DIAGNOSTIC', 'created_unix': time.time(), 'source_sha256': sha(Path(__file__)), 'model_sha256': sha(model_file), 'rows': rows, 'summary': summary, 'new_fits': 0, 'new_env': 0, 'new_neural_model_calls': 0, 'new_physics': 0, 'pure_stump_prediction_rechecks': 2 * sum(r['prospective_prediction_admissible_after_final_join'] for r in rows), 'same_seven_action_menus_fully_charged': True, 'no_online_state_policy_deployed': True, 'no_safety_qualification_inherited': True}, ensure_ascii=False, indent=2) + '\n')
print('CAUSAL_STUMP_FINAL_DIAGNOSTIC', summary, flush=True)
