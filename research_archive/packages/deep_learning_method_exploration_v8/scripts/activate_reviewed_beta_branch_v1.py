"""Root-only future activation after a successful exposed integration review.

Starts one new finite Beta branch inside the unchanged global activation. No
physical job is launched. Durable initialization owns its own unique intent.
"""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, time

P = Path(__file__).resolve().parents[1]
F = 'families/ppo_reward/continuous_scale_v1/'
RUN = F + 'real_runs/GENUINE_BETA_V1'
ACTIVATION_OUTPUT = F + 'ROOT_ACTIVATION_REAL_V1'

def load(relative):
    return json.loads((P / relative).read_text())

def sha(relative):
    return hashlib.sha256((P / relative).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def ref(relative):
    return dict(path=relative, sha256=sha(relative))

def new(relative, value):
    path = P / relative
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration-review', required=True)
    parser.add_argument('--integration-review-sha256', required=True)
    args = parser.parse_args()
    assert sha(args.integration_review) == args.integration_review_sha256
    integration = load(args.integration_review)
    assert integration['status'] == 'PASS_EXPOSED_LIVE_INTEGRATION_AND_ORIGINAL_RAW'
    assert integration['all_five_core_complete'] and integration['true_hard_safety_violation'] is False
    assert integration['all_expected_pre_B_selectors_bound_before_B']
    assert not (P / RUN).exists() and not (P / ACTIVATION_OUTPUT).exists()
    for path in (P / 'owned').glob('*_SUPERVISOR.json'):
        end_path = path.with_name(path.name.replace('_SUPERVISOR.json', '_SUPERVISOR_END.json'))
        assert end_path.exists(), 'PRIOR_PHYSICS_OWNER_NOT_CLOSED:' + path.name
        end = json.loads(end_path.read_text())
        assert end['state'] == 'STOP' and not end['survivors']
    assert (P / 'families/ppo_reward/onpolicy_runs/GENUINE_V1/FINITE_WINDOW_END_V1.json').exists()
    assert load('ACTIVATION.json')['hard_stop_unix'] == 1793114740.
    assert time.time() + 7200 < load('runtime/RUN_PLAN.json')['dispatch_cutoff_unix'] - 1800
    contract_path = 'freeze/BETA_MAIN_TRAINING_CONTRACT_V1.json'
    contract = load(contract_path)
    assert sha(contract_path) == '3e5a95e65a1af44d6920b52789fd7f428ce33f3217e294befe97cb85889311b8'
    assert contract['real_initialization_authorized'] and contract['real_sampling_authorized'] and contract['real_updates_authorized']
    source_manifest = load(F + 'DURABLE_TRANSACTION_SOURCE_MANIFEST_V2.json')
    sources = dict(source_manifest['full_model_axis_control_dependency_sha256'])
    for relative in [F + 'beta_root_prepare_candidate_v1.py', 'source/v8_worker_v2.py', 'source/v8_case_adapter_v2.py',
                     'source/v8_beta_onpolicy_sequence_v1.py', 'scripts/activate_reviewed_beta_branch_v1.py']:
        sources[relative] = sha(relative)
    for relative, expected in sources.items():
        assert sha(relative) == expected, relative
    route_path = 'freeze/ONPOLICY_V1_CASE_ROUTES.json'
    routes = load(route_path)['development_routes']
    approved = time.time(); initialized = time.time(); stop = initialized + 7200.
    parameters = dict(normalization_source=ref('families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json'),
                      normalization_keys=['policy', 'normalization'], feature_names_keys=['policy', 'feature_names'],
                      initialization_seed=2791, sampling_seed=2792,
                      optimizer=dict(learning_rate=.15, max_gradient_norm=1., ppo_clip_range=.2),
                      expected_context_counts={key:2 for key in routes}, local_stop_unix=stop,
                      beta_initial_shapes=[2., 2.], same_initial_weights_and_sampling_seed=True)
    request = dict(schema='v8.beta_root_activation_request.v1', status='APPROVED_BY_MAIN_AGENT',
                   approved_for_real_initialization=True, approved_for_real_sampling=True, approved_for_real_updates=True,
                   approved_unix=approved, activation_sha256=sha('ACTIVATION.json'),
                   source_files_sha256=sources, sequence_wrapper=dict(path='source/v8_beta_onpolicy_sequence_v1.py',
                       sha256=sha('source/v8_beta_onpolicy_sequence_v1.py'), algorithm='v8_beta_onpolicy_sequence_v1'),
                   approved_contract=ref(contract_path), gate1_review=ref('audit/CONTINUOUS_AXIS_GATE1_MAIN_REVIEW_V1.json'),
                   axis=ref(F + 'FROZEN_AXIS_GATE1_V1.json'), case_routes=ref(route_path),
                   base_job_template=ref('experiments/V8OP02H.json'), run_path=RUN,
                   candidate_job_groups=[f'V8BETA{batch:02d}{suffix}' for batch in range(1, 11) for suffix in ('H', 'L')],
                   initialized_window=dict(clock_initialized_after_main_approval=True, initialized_unix=initialized,
                       local_stop_unix=stop, original_global_deadline_unix=1793114740.),
                   initialization_parameters=parameters, durable_initialization_parameters_sha256=digest(parameters),
                   exposed_integration_review=ref(args.integration_review),
                   no_automatic_physics_dispatch=True, categorical_or_global_clock_reset=False)
    request_path = 'freeze/BETA_ROOT_ACTIVATION_REQUEST_REAL_V1.json'
    new(request_path, request)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    commands = [
        [sys.executable, '-B', str(P / F / 'beta_root_prepare_candidate_v1.py'), 'activate', '--package', str(P),
         '--request', request_path, '--request-sha', sha(request_path), '--destination', ACTIVATION_OUTPUT],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=P, text=True, capture_output=True, timeout=30)
        new('audit/BETA_ACTIVATION_METADATA_CLI_V1.json', dict(returncode=result.returncode,
            stdout=result.stdout, stderr=result.stderr, new_actor_calls=0, new_physics=0))
        assert result.returncode == 0, result.stderr
    plan_path = ACTIVATION_OUTPUT + '/RUN_PLAN.json'
    command = [sys.executable, '-B', str(P / F / 'beta_durable_transaction_candidate_v2.py'), 'init',
               '--package', str(P), '--run', RUN, '--input', plan_path, '--input-sha256', sha(plan_path)]
    result = subprocess.run(command, cwd=P, text=True, capture_output=True, timeout=60)
    new('audit/BETA_DURABLE_INITIALIZATION_CLI_V1.json', dict(returncode=result.returncode,
        stdout=result.stdout, stderr=result.stderr, original_local_stop_unix=stop, new_physics=0,
        failure_requires_original_durable_intent_review_no_reinitialization=True))
    assert result.returncode == 0, result.stderr
    current = load(RUN + '/CURRENT.json')
    assert current['generation_index'] == 0 and current['status'] == 'READY_ALL_FOUR_INITIALIZED'
    print('BETA_REAL_INITIALIZED_NO_PHYSICS', 'local_start', initialized, 'local_stop', stop,
          'plan_sha256', sha(plan_path), 'current_sha256', sha(RUN + '/CURRENT.json'))

if __name__ == '__main__':
    main()
