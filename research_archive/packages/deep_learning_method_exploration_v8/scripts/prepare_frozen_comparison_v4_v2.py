"""Metadata-only builder for one exposed integration and two frozen validations.

No model module imports, forward, fit, RNG, or physical dispatch. The actual
closed Beta endpoint inventory must already exist and be explicitly supplied.
"""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
FAMILY = 'families/ppo_reward/continuous_scale_v1/'
GROUPS = ['V8FROZENENG01', 'V8VAL01', 'V8VAL02']
STOP = 1793114740.0


def load(relative):
    return json.loads((P / relative).read_text())


def sha(relative):
    return hashlib.sha256((P / relative).read_bytes()).hexdigest()


def new(relative, value):
    with (P / relative).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--beta-inventory', required=True)
    parser.add_argument('--beta-inventory-sha', required=True)
    args = parser.parse_args()
    assert time.time() < load('runtime/RUN_PLAN.json')['dispatch_cutoff_unix'] - 3600
    deps = {}

    def pin(relative, expected=None):
        path = (P / relative).resolve()
        assert path.is_relative_to(P) and path.is_file(), relative
        value = sha(relative)
        assert expected is None or value == expected, relative
        assert relative not in deps or deps[relative] == value
        deps[relative] = value

    def refs(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                pin(value['path'], value['sha256'])
            for key, item in value.items():
                if key in ('files_sha256', 'source_files_sha256', 'required_config_frozen_artifacts'):
                    for relative, expected in item.items():
                        pin(relative, expected)
                refs(item)
        elif isinstance(value, list):
            for item in value:
                refs(item)

    base = load('experiments/V8COMPENG03.json')
    for relative, expected in base['frozen_artifacts'].items():
        pin(relative, expected)
    inventory_ref = dict(path=args.beta_inventory, sha256=args.beta_inventory_sha)
    pin(**dict(relative=inventory_ref['path'], expected=inventory_ref['sha256']))
    inventory = load(args.beta_inventory)
    assert inventory['status'] == 'FROZEN_ACTUAL_PARENT_FIRST_LAST_NOT_BEST'
    refs(inventory)
    endpoint = load(inventory['root_endpoint_review']['path'])
    assert endpoint['status'] == 'CLOSED_ACTUAL_ENDPOINTS_PARENT_FIRST_LAST_REVIEWED'
    assert endpoint['all_training_physical_owners_closed'] and endpoint['true_hard_safety_violation'] is False
    assert endpoint['endpoint_selected_by_outcome_or_best_seed'] is False
    for relative, expected in endpoint['original_evidence_files_sha256'].items():
        pin(relative, expected)
    pin('source/v8_comparative_validation_v5.py', '14580328c2e5219fcc98f2e1e86c812eddce62a874103ec62063895735a141b1')
    pin(FAMILY + 'comparative_composer_v4_candidate_v3.py', 'c5601b1cf928760e6c1a24268578dfd5dbd73499ca5690f3408bd1cc499bd5a0')
    pin(FAMILY + 'beta_frozen_mean_extension_candidate_v1.py', '4dd92a133c1cc7eecd60b7c51aea66cc360e0692e103a68d65ed02df09f26876')
    pin(FAMILY + 'COMPARATIVE_ORIGINAL_55_CORE_LABELS_V1.json', '633b7f0d1081554085ed807e28d81248e50dbeed4813b30f20d933d34109372f')
    manifests = [
        FAMILY + 'COMPARATIVE_COMPOSER_V4_SOURCE_MANIFEST_V3.json',
        FAMILY + 'BETA_MEAN_EXTENSION_SOURCE_MANIFEST_V1.json',
        'families/il_dagger_sac/neural_q_v2/FROZEN_LIVE_SOURCE_MANIFEST_V3.json',
        'families/learning_assisted/common_out0_v2/FROZEN_LIVE_E2_SOURCE_MANIFEST_V1.json',
        'families/learning_assisted/common_out0_v2/LIVE_SELECTOR_E2_V3_WRAPPER_MANIFEST_V1.json',
        'families/critic_value/support_qualification_v5/LIVE_ADAPTER_MANIFEST_V1.json',
    ]
    for relative in manifests:
        pin(relative); refs(load(relative))
    for relative in [
        'families/il_dagger_sac/neural_q_v2/frozen_live_adapter_candidate_v3.py',
        'families/il_dagger_sac/neural_q_v2/FROZEN_LIVE_READONLY_CONTRACT_V3.json',
        'families/learning_assisted/common_out0_v2/live_selector_e2_v3_wrapper_candidate_v1.py',
        'families/learning_assisted/common_out0_v2/FROZEN_LIVE_E2_CONTRACT_V1.json',
        'families/critic_value/support_qualification_v5/source/live_selector_adapter_candidate_v1.py',
        'families/critic_value/support_qualification_v5/contracts/LIVE_ADAPTER_SOURCE_ONLY_CONTRACT_V1.json',
        'freeze/NEURALQ_FROZEN_OUT0_MAIN_AUTHORIZATION_V1.json',
        'freeze/A5_FROZEN_OUT0_MAIN_SOURCE_APPROVAL_V1.json',
        'scripts/prepare_frozen_comparison_v4_v2.py',
    ]:
        pin(relative)
    for group in GROUPS:
        pin('freeze/E2_FROZEN_OUT0_' + group + '_MAIN_AUTHORIZATION_V1.json')
    routes = load('freeze/ONPOLICY_V1_CASE_ROUTES.json')
    validation_shas = {row['payload_sha256'] for row in routes['sealed_validation']}
    for raw in (P / 'runtime/ATTEMPTS.jsonl').read_text().splitlines():
        event = json.loads(raw)
        if event.get('event') == 'START' and event.get('group'):
            cfg = load('experiments/' + event['group'] + '.json')
            assert cfg.get('case_sha256') not in validation_shas, 'ORIGINAL_NEW_PARAMETER_PHYSICS_ALREADY_OPENED'
    pin('freeze/ONPOLICY_V1_CASE_ROUTES.json')
    for route in routes['sealed_validation']:
        pin(route['payload_relative_path'], route['payload_sha256'])
        pin('runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/' + route['case_key'] + '.json', route['payload_sha256'])
    # Read-only deployment has a separate deadline; no old training clock is extended.
    beta_auth = dict(schema='v8.beta_frozen_mean_deployment_authorization.v1',
        status='APPROVED_BY_MAIN_READ_ONLY_FROZEN_DEPLOYMENT', inventory=inventory_ref,
        activation_sha256=sha('ACTIVATION.json'), mean_policy_forward_only=True,
        new_training_or_restore_authorized=False, authorized_job_groups=GROUPS,
        approved_unix=time.time(), deployment_deadline_unix=load('runtime/RUN_PLAN.json')['physics_hard_stop_unix'],
        source_files_sha256={relative: value for relative, value in deps.items()
                             if relative.endswith('.py') or relative.endswith('LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json')
                             or relative.endswith('A3_FROZEN_BUNDLE_V1.json')})
    auth_rel = 'freeze/BETA_FROZEN_MEAN_OUT0_AUTHORIZATION_V1.json'
    new(auth_rel, beta_auth); pin(auth_rel)
    approval_rel = 'freeze/FROZEN_COMPARISON_V4_MAIN_APPROVAL_V1.json'
    approval = dict(schema='v8.frozen_comparison_v4_main_approval.v1', status='APPROVED_BY_MAIN_AGENT',
        frozen_unix=time.time(), original_global_stop_unix=STOP, groups=GROUPS,
        core_pre_B_decisions=153, fixed_original_core_subset=55, new_NeuralQ_decisions=68,
        new_E2_decisions=9, new_A5_decisions=21, C_after_B_decisions=5,
        Beta_mean_forwards=12, fixed_axis_maps=5, training=0,
        same_recipe_sharing_is_not_independent_replication_or_efficiency=True,
        phase_partial_preserved_and_not_ranked=True,
        true_or_unknown_hard_safety_stops_all=True,
        continuous_requires_new_paid_H150_lambda1_exact_repeat=True,
        original_val_parameter_payloads_structurally_read=True,
        original_val_physics_or_outcomes_generated=False,
        dependencies_before_this_approval=copy.deepcopy(deps))
    new(approval_rel, approval); pin(approval_rel)
    for index, group in enumerate(GROUPS):
        config = copy.deepcopy(base)
        config.update(group=group, algorithm='v8_comparative_validation_v5', job_wall_cap_s=3600,
            mode='engineering' if index == 0 else 'validation', historical_repeats={})
        config['condition'].update(name=group)
        if index:
            route = routes['sealed_validation'][index - 1]
            config['condition'].update(seed=route['seed'], split='FROZEN_NEW_PARAMETER_VALIDATION',
                role='All model choices and recipes frozen before original new-parameter outcomes; exact original task.',
                scope='New parameter-condition test; not file-byte blind, not hardware or clinical qualification.')
            config['case_path'] = 'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/' + route['case_key'] + '.json'
            config['case_sha256'] = route['payload_sha256']
        config['comparative_validation']['parallel_selector_adapters'] += [
            dict(label='NEURAL_Q_V3', path='families/il_dagger_sac/neural_q_v2/frozen_live_adapter_candidate_v3.py'),
            dict(label='E2_V1', path='families/learning_assisted/common_out0_v2/live_selector_e2_v3_wrapper_candidate_v1.py'),
            dict(label='A5_V1', path='families/critic_value/support_qualification_v5/source/live_selector_adapter_candidate_v1.py')]
        config['comparative_validation']['neuralq_readonly_authorization'] = dict(
            path='freeze/NEURALQ_FROZEN_OUT0_MAIN_AUTHORIZATION_V1.json',
            sha256=sha('freeze/NEURALQ_FROZEN_OUT0_MAIN_AUTHORIZATION_V1.json'))
        e2 = 'freeze/E2_FROZEN_OUT0_' + group + '_MAIN_AUTHORIZATION_V1.json'
        config['comparative_validation']['e2_readonly_authorization'] = dict(path=e2, sha256=sha(e2))
        config['comparative_composer_v4'] = dict(schema='v8.comparative_composer_v4_job.v2',
            status='APPROVED_BY_MAIN_AGENT', no_training=True, no_outcome_reselection=True,
            root_postclosure_raw_and_scorer_review_required=True, expected_core_pre_B_decision_count=153,
            preserved_v3=dict(path='source/v8_comparative_validation_candidate_v3.py', sha256=sha('source/v8_comparative_validation_candidate_v3.py')),
            beta_mean_extension=dict(path=FAMILY + 'beta_frozen_mean_extension_candidate_v1.py', sha256=sha(FAMILY + 'beta_frozen_mean_extension_candidate_v1.py')))
        config['beta_mean_extension'] = dict(schema='v8.beta_frozen_mean_extension_job.v1', inventory=inventory_ref,
            deployment_authorization=dict(path=auth_rel, sha256=sha(auth_rel)))
        config['frozen_artifacts'] = copy.deepcopy(deps)
        new('experiments/' + group + '.json', config)
        print(group, sha('experiments/' + group + '.json'), 'dependencies', len(deps))
    for relative in deps:
        if relative.endswith('.py'):
            ast.parse((P / relative).read_text(), filename=relative)


if __name__ == '__main__':
    main()
