"""Freeze the reviewed continuous engineering job; no process or physics launch."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
F = 'families/history_conditioned/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def write(relative, value):
    path = P / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def main():
    activation = load('ACTIVATION.json')
    assert time.time() < activation['hard_stop_unix'] - 5400
    template = F + 'CONTINUOUS_ILC_V3_CONFIG_TEMPLATE_REVIEW_ONLY.json'
    assert sha(P / template) == '6648e15004e12817fb632c5189a8a5e69a675caf1745e3fe48c7070079cc2dea'
    config = load(template)
    gate = load(config['persistent_B_gate_path'])
    assert gate['status'] == 'PERSISTENT_B_ENGINEERING_GATE_PASS'
    assert sha(P / config['persistent_B_gate_path']) == config['persistent_B_gate_sha256']
    assert load('audit/PERSISTENT_B_MAIN_REVIEW_V2.json')['status'].startswith('PASS')
    for relative, expected in config['frozen_artifacts'].items():
        assert sha(P / relative) == expected, relative
    group = 'V8CONTILC01'
    wrapper = 'source/v8_continuous_ilc_worker_v3.py'
    text = (P / 'source/v8_persistent_b_worker_v1.py').read_text()
    text = text.replace('from persistent_worker_v1 import main', 'from continuous_ilc_worker_v3 import main')
    text = text.replace('Reviewed B-only persistent engineering entrypoint; no direct non-B permissions.',
                        'Reviewed real continuous ILC and conditional same-parent component-BO entrypoint.')
    with (P / wrapper).open('x') as stream:
        stream.write(text)
    config['frozen_artifacts'][wrapper] = sha(P / wrapper)
    for relative in [template, F + 'CONTINUOUS_ILC_V3_EXACT_DEPENDENCIES.json',
                     F + 'CONTINUOUS_ILC_V3_INTEGRATION_SOURCE_REVIEW.json',
                     F + 'CONTINUOUS_ILC_V3_JOB_REVIEW.md',
                     str(Path(__file__).relative_to(P)),
                     config['persistent_B_gate_path'], 'audit/PERSISTENT_B_MAIN_REVIEW_V2.json']:
        config['frozen_artifacts'][relative] = sha(P / relative)
    approval = 'freeze/CONTINUOUS_ILC_BO_MAIN_APPROVAL_V3.json'
    write(approval, {
        'status': 'APPROVED_BY_MAIN_AGENT', 'created_unix': time.time(),
        'activation_id': activation['activation_id'], 'hard_stop_unix': activation['hard_stop_unix'],
        'group': group, 'owner_version': 'CONTINUOUS_ILC_COMPONENT_BO_V3',
        'scope': 'One exposed known-heavy true continuous session; original T1 B, live T2 arms, actual T2 H150 own boundary and live T3 counterfactual arms.',
        'original_B_engineering_and_independent_raw_review_required': True,
        'history_disabled': 'Prior fixed heterogeneous nominal-early/light-late population, not same-full-recipe unconditional value and never current BO labels.',
        'ILC': 'Past actual reference-error projection, gains.25/.10; fixed signed.25, zero and prior-disabled controls; no force-gradient identification claim.',
        'BO_fit': {'authorized': True, 'dataset_class': 'REAL_CURRENT_T3',
                   'wall_and_process_CPU_s': 120, 'CPU_threads': 1,
                   'max_unique_training_actions': 8, 'max_scalar_heads': 64,
                   'max_small_matrix_solves': 54, 'optimizer_steps': 0,
                   'required': 'Exact current-parent evidence, actual H150 and signed modal activation, zero raw equivalence, original B/H/zero/signed qualification. Missing evidence abstains.'},
        'BO_candidate': {'authorized': True, 'maximum_new_same_parent_forks': 1,
                         'grid': [-.25, -.125, 0., .125, .25],
                         'required': 'Previously untried registered point only after frozen conservative independent component decision; every real original task/safety/motion/receipt gate remains.'},
        'job_wall_cap_s': 3600, 'nested_owner_absolute_budget_s': 3600,
        'each_task_wall_cap_s': 600, 'each_task_native_guard': 180000,
        'local_max_no_alias_task_count': 15, 'local_max_boundaries': 2,
        'local_structural_native_envelope': 2716000,
        'global_attempt_cap': None, 'all_physics_serial': True,
        'hard_false_and_unknown_stop_stage': True,
        'deadlines_inherited_and_not_reset': True,
        'independent_generalization': False,
        'model_spreads_are_calibrated_safety_probabilities': False,
        'frozen_dependencies': config['frozen_artifacts'],
    })
    config.update(group=group, worker='v8_continuous_ilc_worker_v3.py',
                  continuous_ilc_physics_authorized=True,
                  c2b_component_bo_v2_fit_authorized=True,
                  c2b_component_bo_v2_fit_approval_id=approval,
                  c2b_component_bo_v2_candidate_physics_authorized=True)
    config['condition']['name'] = group
    config.pop('review_only_not_dispatchable')
    config['frozen_artifacts'][approval] = sha(P / approval)
    write('experiments/' + group + '.json', config)
    print(json.dumps({'status': 'PREPARED_NO_PHYSICS', 'group': group,
                      'config_sha256': sha(P / ('experiments/' + group + '.json'))}))


if __name__ == '__main__':
    main()
