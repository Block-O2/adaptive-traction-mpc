"""Prepare one reviewed engineering gate; never launch physics or a learner."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]


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
    group = 'V8AXISG01'
    activation = load('ACTIVATION.json')
    assert time.time() < activation['hard_stop_unix'] - 3600
    axis_rel = 'families/ppo_reward/continuous_scale_v1/FROZEN_AXIS_GATE1_V1.json'
    axis = load(axis_rel)
    assert sha(P / axis_rel) == '66cee45dc9b3c3fb66fddb277e054bb9f2b80e91b35cd17ba9391542f26b664c'
    wrapper = 'source/v8_continuous_axis_gate_v2.py'
    wrapper_text = '''"""Reviewed exposed-condition continuous-axis engineering gate."""
from pathlib import Path
import os, sys
sys.path.insert(0, str(Path(os.environ['ACL2_PACKAGE']) / 'families/ppo_reward/continuous_scale_v1'))
from gate1_sequence_candidate_v2 import sequence
'''
    ast.parse(wrapper_text)
    with (P / wrapper).open('x') as stream:
        stream.write(wrapper_text)
    dependencies = dict(axis['source_files_sha256'])
    for relative in [axis_rel, wrapper,
                     'families/ppo_reward/continuous_scale_v1/gate1_sequence_candidate_v2.py',
                     'families/ppo_reward/continuous_scale_v1/GATE1_OWNER_WRITE_AUTHORITY_V2.md',
                     'families/ppo_reward/continuous_scale_v1/GATE1_SOURCE_CONTRACT_V1.md',
                     'families/ppo_reward/continuous_scale_v1/axis_mapping.py',
                     'source/v8_worker_v1.py', 'source/v8_case_adapter_v1.py',
                     'source/acl2_shared.py', 'runtime/code/analyze_matched.py',
                     'runtime/code/stream_runtime_evidence.py', 'runtime/ACTION_SET.json',
                     'runtime/RUN_PLAN.json', 'runtime/MOTION_ACCEPTANCE_PROTOCOL.json',
                     'runtime/EXECUTION_CODE_MANIFEST.json',
                     str(Path(__file__).relative_to(P))]:
        actual = sha(P / relative)
        if relative in dependencies:
            assert actual == dependencies[relative], relative
        dependencies[relative] = actual
    for relative, expected in dependencies.items():
        assert sha(P / relative) == expected, relative
    approval_rel = 'freeze/CONTINUOUS_AXIS_GATE1_MAIN_APPROVAL_V2.json'
    write(approval_rel, {
        'status': 'APPROVED_BY_MAIN_AGENT', 'created_unix': time.time(),
        'activation_id': activation['activation_id'],
        'hard_stop_unix': activation['hard_stop_unix'], 'group': group,
        'scope': 'Known-heavy exposed engineering: B, original H150, lambda1 exact raw repeat, lambda0, lambda.5.',
        'required_order': ['B', 'H150', 'AXIS_L1', 'AXIS_L0', 'AXIS_L05'],
        'gate': 'B/H150 original complete qualification; lambda1 original compare_raw PASS before later points.',
        'job_wall_cap_s': 1800, 'each_physical_timeout_s': 600,
        'physics_serial': True, 'new_learner_initializations': 0,
        'new_model_forward_or_updates': 0,
        'no_independent_generalization_claim': True,
        'lambda0_is_B': False, 'all_original_task_guard_scorer_unchanged': True,
        'future_beta_training_authorized': False,
        'dependencies': dependencies,
        'main_review': 'Actual V2 generator parent-write guards reviewed. Child GeneratorExit cannot write shared state. Every original outcome and fallback remains separate from requested lambda.',
    })
    dependencies[approval_rel] = sha(P / approval_rel)
    config = copy.deepcopy(load('experiments/V8ENGH01.json'))
    config.update(group=group, worker='v8_worker_v1.py',
                  algorithm='v8_continuous_axis_gate_v2', actions=[],
                  scientific_branch='CONTINUOUS_AXIS_MAPPING_ENGINEERING',
                  job_wall_cap_s=1800, historical_repeats={},
                  frozen_artifacts=dependencies)
    config.pop('reference_v7', None)
    config['condition']['name'] = group
    config['continuous_axis_gate1'] = {
        'schema': 'v8.continuous_axis_gate1_job.v1',
        'exposed_engineering_condition': 'knownheavy',
        'independent_generalization_test': False,
        'axis_path': axis_rel, 'axis_file_sha256': sha(P / axis_rel),
        'axis_object_sha256': 'ad1e44aca095b872ba673d077124841058f4ae55c9002b016f19253d22131faf',
        'approved_contract_path': approval_rel,
        'approved_contract_sha256': sha(P / approval_rel),
        'output_directory': 'families/ppo_reward/continuous_scale_v1/gate1_runs/' + group,
    }
    write('experiments/' + group + '.json', config)
    print(json.dumps({'status': 'PREPARED_NO_PHYSICS', 'group': group,
                      'config_sha256': sha(P / ('experiments/' + group + '.json'))}))


if __name__ == '__main__':
    main()
