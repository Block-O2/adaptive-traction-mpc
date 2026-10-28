"""Freeze the last completed finite-window categorical generation; metadata only."""
from pathlib import Path
import collections, hashlib, json, time

P = Path(__file__).resolve().parents[1]
R = P / 'families/ppo_reward/onpolicy_runs/GENUINE_V1'

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_new(path, obj):
    with path.open('x') as stream:
        json.dump(obj, stream, indent=2, allow_nan=False, ensure_ascii=False)
        stream.write('\n')

current = read(R / 'CURRENT.json')
identity = read(R / 'RUN_IDENTITY.json')
assert current['generation_index'] == 3
assert time.time() < identity['local_stop_unix']
assert identity['local_stop_unix'] - time.time() < 3400
generation = P / current['generation_directory']
transaction = read(generation / 'TRANSACTION.json')
assert transaction['status'] == 'ALL_FOUR_GENUINE_UPDATES_ATOMICALLY_COMMITTED'
assert transaction['preflight_errors'] == {}
assert transaction['all_arms_committed_together'] is True
assert sha(generation / 'TRANSACTION.json') == current['transaction_sha256']
assert sha(P / transaction['durable_computation_output_path']) == transaction['durable_computation_output_sha256']
groups = ['V8OP02H', 'V8OP02L']
rows = []
for group in groups:
    end = read(P / 'owned' / (group + '_SUPERVISOR_END.json'))
    done = read(P / 'jobs' / group / 'WORKER_DONE.json')
    assert end['state'] == 'STOP' and end['worker_exit_code'] == 0 and not end['survivors']
    assert done['all_children_joined'] and all(x['unchanged'] and x['child_exitcode'] == 0 for x in done['parent_checks'])
    for path in sorted((P / 'attempts').glob(group + '_OP_*_RESULT.json')):
        result = read(path)
        proposal = read(R / 'sampling' / group / (result['id'].removeprefix(group + '_') + '_PROPOSAL.json'))
        assert result['complete']
        rows.append({'attempt_id': result['id'], 'arm': proposal['arm_id'],
                     'action_index': proposal['action_index'], 'qualified': result['qualified'],
                     'JF': result['JF'], 'JM': result['JM'],
                     'actual_new_native_steps': result['actual_new_native_steps'],
                     'result_path': str(path.relative_to(P)), 'result_sha256': sha(path)})
assert len(rows) == 16 and len({r['attempt_id'] for r in rows}) == 16
steps = {}
for arm, entry in transaction['results'].items():
    result = entry['result']
    steps[arm] = {key: result[key] for key in ['algorithm', 'records', 'steps', 'counters', 'status', 'reward_baseline']}
    assert result['status'] == 'COMPLETED_GENUINE_ON_POLICY_UPDATE'
    info = current['checkpoints'][arm]
    assert sha(P / info['path']) == info['sha256']
destination = P / 'freeze/GENUINE_ENDPOINT_POINTER_V1.json'
with destination.open('xb') as stream:
    stream.write((R / 'CURRENT.json').read_bytes())
review = {
    'status': 'SECOND_ALIGNED_BATCH_REVIEWED_ENDPOINT_FROZEN_NOT_BEST',
    'created_unix': time.time(), 'source_sha256': sha(Path(__file__)),
    'early_pointer': 'freeze/GENUINE_FIRST_COMPLETED_POINTER_V1.json',
    'early_pointer_sha256': sha(P / 'freeze/GENUINE_FIRST_COMPLETED_POINTER_V1.json'),
    'endpoint_pointer': str(destination.relative_to(P)), 'endpoint_pointer_sha256': sha(destination),
    'generation_index': current['generation_index'], 'transaction_sha256': current['transaction_sha256'],
    'durable_computation_sha256': transaction['durable_computation_output_sha256'],
    'batch2_rows': rows, 'batch2_qualified': sum(r['qualified'] for r in rows),
    'batch2_action_counts': dict(collections.Counter(r['action_index'] for r in rows)),
    'actual_update_steps': steps,
    'original_local_stop_unix': identity['local_stop_unix'],
    'new_balanced_batch_minimum_reserve_s': 3400,
    'further_batch': 'NOT_DISPATCHED_INSUFFICIENT_FROZEN_START_RESERVE',
    'scope': '32 fresh policy trials in two aligned updates; first batch 8 complete light motion failures retained. No sealed validation opened. RF_RAW has one additional cancelled initial draw, never rewound.',
    'new_model_forward': 0, 'new_fit': 0, 'new_physics': 0,
}
write_new(P / 'audit/GENUINE_BATCH2_MAIN_REVIEW_ENDPOINT_V1.json', review)
state = read(P / 'WORK_STATE.json')
state.update(updated_unix=time.time(), current_physics='V8AXISG01 continuous-axis Gate1; zero learner initialization',
             last_complete_generation='GENERATION_0003 last completed aligned update in unchanged finite window',
             onpolicy_completed_real_gradient_updates=16,
             categorical_fresh_policy_trials=32,
             sealed_validation_opened=False)
state['pending'] = [
    'Review actual continuous axis Gate1 before any Beta initialization',
    'Dispatch already approved continuous ILC/BO V3 serially after Gate1 closure',
    'A4 component-margin source review and bounded fit; E common-OUT0 data builder and fit source review',
    'NeuralQ representation source proposal; SAC underfit mechanism analysis',
    'Freeze all actual models and equal-permission strong controls before two sealed conditions',
    'Original deadline and 30min closeout reserve remain unchanged',
]
state['completed'].extend([
    'Second genuine aligned batch 16/16 complete qualified, 15 B and one light LATE_PHASE; 8 further real SGD updates',
    'D SAC64 actual offpolicy replay and 48 initialization/1650 SGD bounded V6 fit; frozen six full models',
    'Genuine endpoint generation3 and first-completed generation2 pointers frozen independently',
])
(P / 'WORK_STATE.json').write_text(json.dumps(state, indent=2, allow_nan=False, ensure_ascii=False) + '\n')
print('ENDPOINT_FROZEN', review['endpoint_pointer_sha256'], 'batch2 qualified', review['batch2_qualified'], 'actions', review['batch2_action_counts'])
