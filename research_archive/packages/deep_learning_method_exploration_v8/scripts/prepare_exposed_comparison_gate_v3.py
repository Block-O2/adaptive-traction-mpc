"""Freeze a known-heavy integration gate. No model imports or physical launch."""
from pathlib import Path
import ast, copy, hashlib, json, time

P = Path(__file__).resolve().parents[1]
GROUP = 'V8COMPENG03'

def load(relative):
    return json.loads((P / relative).read_text())

def sha(relative):
    return hashlib.sha256((P / relative).read_bytes()).hexdigest()

def put(relative, value):
    with (P / relative).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False, ensure_ascii=False)
        stream.write('\n')

deps = {}
def pin(relative, expected=None):
    value = sha(relative)
    if expected is not None:
        assert value == expected, relative
    assert relative not in deps or deps[relative] == value
    deps[relative] = value

def refs(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            pin(value['path'], value['sha256'])
        for item in value.values():
            refs(item)
    elif isinstance(value, list):
        for item in value:
            refs(item)

assert time.time() < load('runtime/RUN_PLAN.json')['dispatch_cutoff_unix'] - 1800
assert sha('source/v8_comparative_validation_candidate_v3.py') == '874fd52f71852480a23fef3aae6b91e494f1e9f6ed7974a6537e38d9b360c2a9'
config = copy.deepcopy(load('experiments/V8AXISG01.json'))
for key in ['continuous_axis_gate1', 'value_bundle', 'simple_control_bundle', 'policy_checkpoints',
            'history_snapshot', 'holdout_protocol', 'holdout_protocol_sha256']:
    config.pop(key, None)
config.update(group=GROUP, mode='engineering', worker='v8_worker_v2.py', algorithm='v8_comparative_validation_v3',
              historical_repeats={}, job_wall_cap_s=1800)
config['condition'].update(name=GROUP, seed=2690,
                          scope='Exposed known-heavy integration gate. Not sealed validation or independent generalization.')
menu = load('freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json')['action_contracts']
tags = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
config['actions'] = [dict(tag=tag, action=copy.deepcopy(recipe['action']), category='EXPOSED_FROZEN_COMPARISON_ENGINEERING')
                     for tag, recipe in zip(tags, menu)]
spec = dict(status='APPROVED_BY_MAIN_AGENT', no_training=True, no_outcome_reselection=True,
            A_parallel_adapter='families/critic_value/coverage_state_v3/source/live_selector_adapter_candidate_v1.py',
            menu_path='freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json',
            A1_controls='families/critic_value/models/STRONG_CONTROLS_V1_FROZEN.json',
            BC_aggregation_API='families/il_dagger_sac/context_aggregation_v1/context_aggregation_api_v1.py',
            categorical_checkpoints=[], BC_aggregation_bundles=[],
            history_snapshot='families/history_conditioned/c3b_offline_v1/FROZEN_FULL_SNAPSHOT.json',
            parallel_selector_adapters=[])
for gen, label in [(0, 'PARENT'), (2, 'EARLY_FIRST_COMPLETED'), (3, 'ENDPOINT_LAST_COMPLETED')]:
    for arm in ['RF_RAW', 'PPO_RAW', 'RF_SCALED', 'PPO_SCALED']:
        path = f'families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_{gen:04d}/{arm}.json'
        policy = load(path)['policy']
        assert policy['action_contracts'] == menu, 'OLD_THREE_RECIPE_POLICY_FORBIDDEN'
        spec['categorical_checkpoints'].append(dict(label=f'GENUINE_{label}_{arm}', path=path))
bc_dir = 'families/il_dagger_sac/context_aggregation_v1/approved_fit_v1/'
bc = load(bc_dir + 'DEPLOYMENT_FREEZE.json')
bc_linear = 0
for name in sorted(bc['bundle_object_sha256']):
    relative = bc_dir + 'models/' + name + '.json'
    doc = load(relative)
    assert doc['bundle_object_sha256'] == bc['bundle_object_sha256'][name]
    spec['BC_aggregation_bundles'].append(dict(label='BCAGG_' + name, path=relative))
    bc_linear += int(doc['bundle']['model'].get('kind') == 'BC_LINEAR')
for label, path in [
    ('A4', 'families/critic_value/coverage_margin_v4/source/live_selector_adapter_candidate_v1.py'),
    ('SAC_V6', 'families/il_dagger_sac/discrete_sac_v1/source/frozen_live_api_candidate_v6.py'),
    ('SAC_V7', 'families/il_dagger_sac/discrete_sac_v1/solver_floor_v7/source/live_selector_adapter_candidate_v7.py'),
]:
    spec['parallel_selector_adapters'].append(dict(label=label, path=path))
manifest_paths = [
    'families/critic_value/coverage_state_v3/LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json',
    'families/critic_value/coverage_margin_v4/LIVE_ADAPTER_MANIFEST_V1.json',
    'families/il_dagger_sac/discrete_sac_v1/FROZEN_LIVE_API_MANIFEST_V6.json',
    'families/il_dagger_sac/discrete_sac_v1/solver_floor_v7/LIVE_ADAPTER_MANIFEST_V7.json',
]
for relative in manifest_paths:
    pin(relative)
    refs(load(relative))
for relative in ['ACTIVATION.json', 'runtime/RUN_PLAN.json', 'source/v8_worker_v1.py', 'source/v8_worker_v2.py',
                 'source/v8_case_adapter_v2.py', 'source/v8_comparative_validation_v3.py',
                 'source/v8_comparative_validation_candidate_v3.py', 'source/acl2_shared.py',
                 'families/critic_value/source/controls_api.py', 'families/ppo_reward/categorical_policy.py',
                 'families/history_conditioned/completed_history_reader.py', 'families/history_conditioned/c3b_inference.py',
                 'families/history_conditioned/trial_interface.py',
                 'freeze/GENUINE_FIRST_COMPLETED_POINTER_V1.json', 'freeze/GENUINE_ENDPOINT_POINTER_V1.json',
                 'scripts/prepare_exposed_comparison_gate_v3.py', config['case_path'], bc_dir + 'DEPLOYMENT_FREEZE.json']:
    pin(relative)
for key in ['A_parallel_adapter', 'A1_controls', 'menu_path', 'BC_aggregation_API', 'history_snapshot']:
    pin(spec[key])
for item in spec['categorical_checkpoints'] + spec['BC_aggregation_bundles'] + spec['parallel_selector_adapters']:
    pin(item['path'])
for rel in deps:
    if rel.endswith('.py'):
        ast.parse((P / rel).read_text(), filename=rel)
snapshot = load(spec['history_snapshot'])
hashes = [hashlib.sha256(json.dumps(r, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() for r in menu]
assert snapshot['recipe_hashes'] == hashes[:3], 'C3B_THREE_PERMISSION_IDENTITY'
contract = dict(schema='v8.exposed_frozen_comparison_gate.v1', status='APPROVED_BY_MAIN_AGENT',
                created_unix=time.time(), activation=load('ACTIVATION.json')['activation_id'], group=GROUP,
                scope='Known-heavy exposed source/API/physical linkage engineering; not independent validation',
                worker='source/v8_worker_v2.py', exact_menu_hashes=hashes,
                frozen_dependencies=copy.deepcopy(deps),
                before_B_selectors=55, top_API_entry_expected_before_B=28, nested_model_control_API_expected_before_B=52,
                model_restore_expected=6, BC_linear_bundles=bc_linear,
                C_after_B_cold_replay_methods=5, C_recipe_permissions=3, other_main_recipe_permissions=5,
                physics='5 core full continuations + optional independent HISTORY_B repeat + original parent; each paid once',
                closure_requirements=['Supervisor STOP/exit0/no survivors; all START unique END joined and parent unchanged',
                                      'Every five core result complete; B qualified; original receipt and raw/scorer replay PASS',
                                      'All55 preB choices recorded before B START; all expected inference RETURNs present',
                                      'Original C3B three-recipe permissions kept separate, after complete B only',
                                      'All model and source bytes unchanged; no fit, RNG sampling or outcome reselection',
                                      'Worker PHYSICS_DONE alone is insufficient because EARLY_STOP can still write it',
                                      'Failed nested API counts unknown unless original entry evidence exists; never infer zero'],
                training=0, sealed_conditions_opened=False, original_hard_stop_unix=1793114740.)
put('freeze/EXPOSED_COMPARISON_GATE_MAIN_APPROVAL_V3.json', contract)
pin('freeze/EXPOSED_COMPARISON_GATE_MAIN_APPROVAL_V3.json')
config['comparative_validation'] = spec
config['frozen_artifacts'] = deps
put('experiments/' + GROUP + '.json', config)
print('EXPOSED_COMPARISON_PREPARED_NO_MODEL_OR_PHYSICS', sha('experiments/' + GROUP + '.json'), 'dependencies', len(deps))
