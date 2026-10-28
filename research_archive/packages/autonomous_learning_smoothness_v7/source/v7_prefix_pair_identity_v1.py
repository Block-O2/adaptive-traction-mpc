"""Finite post-execution identity filter for the two precommitted prefix states."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
OUT = P / 'analysis/FROZEN_PREFIX_PAIR_IDENTITY_V1.json'
assert not OUT.exists(), 'REFUSE_OVERWRITE'
inputs = {}


def read(relative):
    path = P / relative
    raw = path.read_bytes()
    inputs[relative] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


protocol = read('freeze/PREFIX_VALIDATION_EXECUTION_V2.json')
ledger = [json.loads(line) for line in (P / 'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
rows = []
for group in ['PFXV01', 'PFXV02']:
    post = read('analysis/' + group + '_POSTRUN_IDENTITY_V1.json')
    capture = read('history/' + group + '_PREFORK_CAUSAL_CONTEXT.json')
    result = read('attempts/' + group + '_B_RESULT.json')
    config = read('experiments/' + group + '.json')
    freeze = read('freeze/' + group + '.json')
    starts = [r for r in ledger if r['event'] == 'START' and r['group'] == group]
    assert starts and protocol['frozen_unix'] < min(r['unix'] for r in starts)
    assert inputs['experiments/' + group + '.json'] == freeze['config_sha256']
    assert config['actions'] == protocol['actions']
    assert capture['model_vector_valid'] and not capture['causality_errors']
    assert result['complete'] and result['qualified']
    rows.append({'group': group, 'post': post, 'capture': capture})
a, b = [r['post']['candidate'] for r in rows]
different = {'native_integration': a['native_integration'] != b['native_integration'],
             'causal_current4': a['causal_current_deployable_array'] != b['causal_current_deployable_array'],
             'pure_physical_prefork_trace': a['own_prefork_projection']['actual_human_trace_sha256'] != b['own_prefork_projection']['actual_human_trace_sha256'],
             'pure_physical_values_without_time': a['own_prefork_projection']['actual_human_values_sha256'] != b['own_prefork_projection']['actual_human_values_sha256']}
names = rows[0]['capture']['feature_names']
assert names == rows[1]['capture']['feature_names']
changed_features = [name for name, x, y in zip(names, rows[0]['capture']['features'], rows[1]['capture']['features']) if x != y]
known_filter = all(r['post']['native_differs_from_every_inventory_row'] and r['post']['common_causal4_differs_from_every_inventory_row'] and not r['post']['prefork_trace_aliases'] for r in rows)
passed = all(different.values()) and known_filter
payload = {'status': 'PASS_FINITE_IDENTITY_FILTER' if passed else 'FAIL_OR_ALIAS_RETAINED',
           'created_unix': time.time(), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'input_sha256': inputs, 'pair_differs': different, 'changed_causal77_feature_names': changed_features,
           'known_inventory_filter': known_filter, 'frozen_before_first_START': True,
           'both_originalB_qualified': True, 'causal77_valid': True,
           'prefix_historical_coverage_complete': all(r['post']['prefix_comparison_complete_per_known_history'] for r in rows),
           'statistical_independence_established': False, 'patient_generalization_established': False,
           'limits': ['Two same-Human deterministic legal prefix states; small finite simulation coverage',
                      '772 known snapshot rows/45 native identities, one missing historical trace retained',
                      'Other histories without compatible snapshots are not exhaustively excluded',
                      'The comparison does not select candidates, fit models or replace failed/aliased states'],
           'new_physics': 0, 'model_calls': 0, 'training': 0}
temp = OUT.with_suffix('.tmp')
temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
temp.replace(OUT)
print('PREFIX_PAIR_FILTER', payload['status'], different, flush=True)
