"""STUB_ONLY: approved metadata/file-control fixture; never imports real models.

Executes only AST-extracted function definitions against temporary fake files.
All PASS/status/receipt-looking fields below are synthetic schema fixtures.
"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os
import tempfile
import time
import traceback
import types

PACKAGE = Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
OUT = PACKAGE / 'families/il_dagger_sac/discrete_sac_v1/analysis/TRANSACTION_STUB_AUDIT_V2.json'
ARMS = ['RF_RAW', 'PPO_RAW', 'RF_SCALED', 'PPO_SCALED']
EXECUTED_SOURCE_HASHES = {}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def stub_policy_sha(policy):
    return digest({'STUB_ONLY': True, 'token': policy['stub_token'], 'version': policy['version']})


def extract(relative, env):
    source = (PACKAGE / relative).read_bytes()
    tree = ast.parse(source, filename=relative)
    definitions = ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))], type_ignores=[])
    exec(compile(definitions, relative, 'exec'), env)
    result = hashlib.sha256(source).hexdigest()
    assert relative not in EXECUTED_SOURCE_HASHES or EXECUTED_SOURCE_HASHES[relative] == result, 'SOURCE_CHANGED_DURING_FIXTURE'
    EXECUTED_SOURCE_HASHES[relative] = result
    return result


def stub_verify(package, configs, models, *, prior_snapshots, allow_missing_receipts=False):
    """Strict current signature, explicitly no original-physics proof."""
    assert set(prior_snapshots) == set(ARMS)
    assert all(prior_snapshots[a]['policy']['version'] == 0 for a in ARMS)
    return [{'fixture_semantics': 'STUB_ONLY_SOURCE_JOIN_STUB', 'required_prior_snapshots_received': True}]


class FakeArm:
    def __init__(self, snapshot, control):
        self.data = copy.deepcopy(snapshot)
        self.control = control
        for key, value in self.data.items():
            setattr(self, key, value)
        self.seen_attempt_ids = set(self.seen_attempt_ids)

    def snapshot(self):
        result = copy.deepcopy(self.data)
        for key in ['policy', 'pending', 'seen_attempt_ids', 'finished_batches', 'batch_id']:
            result[key] = copy.deepcopy(getattr(self, key))
        result['seen_attempt_ids'] = sorted(self.seen_attempt_ids)
        return result

    def preflight_batch_metadata(self):
        self.control['events'].append('preflight:' + self.arm_id)
        return {'admissible': self.arm_id != self.control.get('censor_arm'), 'model_forward': 0, 'parameter_updates': 0}

    def finish_batch(self):
        assert {x.removeprefix('preflight:') for x in self.control['events'] if x.startswith('preflight:')} == set(ARMS)
        self.control['events'].append('fake_finish:' + self.arm_id)
        self.control['fake_finish_calls'] += 1
        if self.arm_id == self.control.get('fail_arm'):
            raise RuntimeError('STUB_ONLY_THIRD_ARM_EXCEPTION')
        self.policy['version'] += 1
        self.policy['counters']['parameter_updates'] += 1  # Fake dictionary only.
        result = {'result': {'status': 'COMPLETED_GENUINE_ON_POLICY_UPDATE', 'fixture_semantics': 'STUB_ONLY'}}
        self.finished_batches.append(copy.deepcopy(result))
        self.pending = []
        self.batch_id += 1
        return result

    def cancel_pending_batch(self, *, group_transaction_id, reason):
        if any(p.get('physical_result', {}).get('true_hard_safety_violation') is True for p in self.pending):
            raise ValueError('STUB_ONLY_HARD_SAFETY')
        self.control['events'].append('fake_cancel:' + self.arm_id)
        result = {'result': {'status': 'STUB_ONLY_CANCELLED', 'group_transaction_id': group_transaction_id, 'reason': reason}, 'preserved': copy.deepcopy(self.pending)}
        self.pending = []
        self.batch_id += 1
        self.finished_batches.append(copy.deepcopy(result))
        return result


def setup(base):
    p = base / 'STUB_ONLY_WORKSPACE'
    f = p / 'families/ppo_reward'
    run = f / 'STUB_ONLY_RUN'
    control = {'events': [], 'fake_finish_calls': 0}
    env = {'Path': Path, 'argparse': None, 'copy': copy, 'hashlib': hashlib, 'json': json, 'os': os,
           'sys': None, 'time': time, 'traceback': traceback, 'P': p, 'F': f, 'ARMS': ARMS,
           'digest': digest, 'policy_sha256': stub_policy_sha,
           'verify_original_proposals_and_receipts': stub_verify}
    source_sha = extract('scripts/onpolicy_four_arm_transaction_v1.py', env)
    env['restore'] = lambda snapshot, *args: FakeArm(snapshot, control)
    tx = types.SimpleNamespace(**env)
    put = env['write_new']
    put(p / 'ACTIVATION.json', {'activation_id': 'STUB_ONLY', 'hard_stop_unix': time.time() + 3600})
    put(p / 'freeze/STUB_ONLY_CONTRACT.json', {'fixture_semantics': 'STUB_ONLY', 'status': 'APPROVED_BY_MAIN_AGENT', 'activation': 'STUB_ONLY', 'global_deadline_unix': time.time() + 3600, 'frozen_dependencies': {}, 'menu_path': 'freeze/STUB_ONLY_MENU.json'})
    put(p / 'freeze/STUB_ONLY_MENU.json', {'fixture_semantics': 'STUB_ONLY', 'full_recipe_sha256': ['STUB_ONLY_' + str(i) for i in range(5)]})
    f.mkdir(parents=True, exist_ok=True)
    (f / 'categorical_policy.py').write_text('# STUB_ONLY; no model code\n')
    contract_sha = env['sha'](p / 'freeze/STUB_ONLY_CONTRACT.json')
    stop = time.time() + 1800
    put(run / 'RUN_IDENTITY.json', {'fixture_semantics': 'STUB_ONLY', 'approved_contract_path': 'freeze/STUB_ONLY_CONTRACT.json', 'approved_contract_sha256': contract_sha, 'local_stop_unix': stop})
    old = {}
    for arm in ARMS:
        old[arm] = {'fixture_semantics': 'STUB_ONLY', 'arm_id': arm, 'algorithm': 'PPO' if arm.startswith('PPO') else 'REINFORCE', 'gain': 20 if arm.endswith('SCALED') else 1, 'expected_context_counts': {'C1': 2, 'C2': 2}, 'contract_sha256': contract_sha, 'frozen_menu_sha256': ['STUB_ONLY_' + str(i) for i in range(5)], 'categorical_dependency': {'source_sha256': env['sha'](f / 'categorical_policy.py')}, 'policy': {'stub_token': arm, 'version': 0, 'counters': {'forward': 0, 'backward_equivalent': 0, 'parameter_updates': 0}}, 'pending': [], 'seen_attempt_ids': [], 'finished_batches': [], 'batch_id': 0, 'batch_policy_sha256': '', 'local_stop_unix': stop, 'rng': ['STUB_ONLY_ORIGINAL_RNG']}
        old[arm]['batch_policy_sha256'] = stub_policy_sha(old[arm]['policy'])
    current = env['publish_generation'](run, 0, old, {'status': 'STUB_ONLY_INITIAL', 'all_arms_committed_together': True})
    configs = []
    pending_bundles = []
    previous = copy.deepcopy(old)
    events = []
    for index, group in enumerate(['STUBG1', 'STUBG2'], 1):
        context = 'C' + str(index)
        if index == 1:
            inputs = [{'arm_id': arm, 'snapshot_path': current['checkpoints'][arm]['path'], 'snapshot_sha256': current['checkpoints'][arm]['sha256']} for arm in ARMS]
        else:
            inputs = []
            for arm in ARMS:
                path = run / 'pending_inputs/STUBG2' / (arm + '.json')
                put(path, previous[arm])
                inputs.append({'arm_id': arm, 'snapshot_path': str(path.relative_to(p)), 'snapshot_sha256': env['sha'](path)})
        output = run / 'sampling' / group
        config = {'fixture_semantics': 'STUB_ONLY', 'group': group, 'onpolicy_sampling': {'output_directory': str(output.relative_to(p)), 'arm_inputs': inputs, 'development_context_id': context}}
        put(p / 'experiments' / (group + '.json'), config)
        config_sha = env['sha'](p / 'experiments' / (group + '.json'))
        for arm in ARMS:
            for i in range(2):
                ident = group + '_OP_' + arm + '_' + str(i + 1).zfill(2)
                previous[arm]['pending'].append({'fixture_semantics': 'STUB_ONLY', 'attempt_id': ident, 'context_group_evaluation_only': context, 'physical_result': {'fixture_semantics': 'STUB_ONLY', 'attempt_id': ident, 'true_hard_safety_violation': False}})
                previous[arm]['seen_attempt_ids'].append(ident)
            previous[arm]['rng'] = ['STUB_ONLY_ADVANCED_' + str(index)]
        bundle = {'fixture_semantics': 'STUB_ONLY', 'job_group_evaluation_only': group, 'stage': 'ALL_CURRENT_CONTEXT_SAMPLES_COLLECTED_NO_UPDATE', 'parameter_updates_in_this_job': 0, 'development_context_id_evaluation_only': context, 'snapshots': copy.deepcopy(previous)}
        put(output / 'PENDING_CHECKPOINTS.json', bundle)
        pending_bundles.append(bundle)
        configs.append(config)
        idents = [group + '_COLD_PARENT', group + '_B'] + [group + '_OP_' + arm + '_' + str(i + 1).zfill(2) for arm in ARMS for i in range(2)]
        for ident in idents:
            events.extend([{'fixture_semantics': 'STUB_ONLY', 'event': 'START', 'id': ident, 'group': group, 'config_sha256': config_sha}, {'fixture_semantics': 'STUB_ONLY', 'event': 'END', 'id': ident, 'group': group, 'joined': True, 'returncode': 0}])
        put(p / 'jobs' / group / 'WORKER_DONE.json', {'fixture_semantics': 'STUB_ONLY', 'status': 'PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'})
        put(p / 'owned' / (group + '_SUPERVISOR_END.json'), {'fixture_semantics': 'STUB_ONLY', 'state': 'STOP', 'worker_exit_code': 0, 'survivors': []})
        put(p / 'owned' / (group + '_EXIT.json'), {'fixture_semantics': 'STUB_ONLY'})
        put(p / 'audit' / (group + '_PARENT_RAW_GATE.json'), {'fixture_semantics': 'STUB_ONLY', 'status': 'PASS'})
    (p / 'runtime').mkdir()
    (p / 'runtime/ATTEMPTS.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in events))
    final_pending = run / 'sampling/STUBG2/PENDING_CHECKPOINTS.json'
    envelope = run / 'STUB_ONLY_ENVELOPE.json'
    put(envelope, {'fixture_semantics': 'STUB_ONLY', 'schema': 'v8.root_bound_two_job_pending.v1', 'root_expected_sampling_groups': ['STUBG1', 'STUBG2'], 'original_final_pending_path': str(final_pending.relative_to(p)), 'original_final_pending_sha256': env['sha'](final_pending)})
    return env, tx, control, run, envelope, old, source_sha


def checks():
    results = []
    source_shas = set()
    with tempfile.TemporaryDirectory(prefix='v8-STUB_ONLY-tx-') as temporary:
        root = Path(temporary)
        for name in ['success', 'third_arm_failure', 'pointer_failure_recovery', 'whole_group_censor', 'partial_cancel', 'partial_hard_stop']:
            env, tx, control, run, envelope, old, source_sha = setup(root / name)
            source_shas.add(source_sha)
            before = (run / 'CURRENT.json').read_bytes()
            if name == 'success':
                result = env['commit_run'](run, envelope)
                assert result['generation_index'] == 1 and control['fake_finish_calls'] == 4
                assert [x for x in control['events'] if x.startswith('preflight:')] == ['preflight:' + a for a in ARMS]
                assert all(env['load'](env['P'] / result['checkpoints'][arm]['path'])['policy']['version'] == 1 for arm in ARMS)
                assert all(s['policy']['version'] == 0 for s in old.values())
            elif name == 'third_arm_failure':
                control['fail_arm'] = ARMS[2]
                try:
                    env['commit_run'](run, envelope)
                    raise AssertionError('STUB_ONLY_EXPECTED_EXCEPTION')
                except RuntimeError as error:
                    assert str(error) == 'STUB_ONLY_THIRD_ARM_EXCEPTION'
                assert (run / 'CURRENT.json').read_bytes() == before and control['fake_finish_calls'] == 3
                assert list(run.glob('*_ABORTED_COMPUTATION.json'))
            elif name == 'pointer_failure_recovery':
                original_pointer = env['atomic_pointer']
                env['atomic_pointer'] = lambda *args, **kwargs: (_ for _ in ()).throw(OSError('STUB_ONLY_POINTER_FAILURE'))
                try:
                    env['commit_run'](run, envelope)
                    raise AssertionError('STUB_ONLY_EXPECTED_POINTER_FAILURE')
                except OSError:
                    pass
                assert (run / 'CURRENT.json').read_bytes() == before and (run / 'GENERATION_0001').is_dir()
                assert control['fake_finish_calls'] == 4
                try:
                    env['commit_run'](run, envelope)
                    raise AssertionError('STUB_ONLY_EXPECTED_NO_REFIT_GATE')
                except AssertionError as error:
                    assert 'ORPHAN_GENERATION' in str(error)
                assert control['fake_finish_calls'] == 4
                env['atomic_pointer'] = original_pointer
                result = env['recover_publication'](run)
                assert result['generation_index'] == 1 and control['fake_finish_calls'] == 4
            elif name == 'whole_group_censor':
                control['censor_arm'] = ARMS[2]
                result = env['commit_run'](run, envelope)
                assert result['status'] == 'ALL_FOUR_CANCELLED_NO_UPDATE' and control['fake_finish_calls'] == 0
                assert [x for x in control['events'] if x.startswith('fake_cancel:')] == ['fake_cancel:' + a for a in ARMS]
            else:
                p = env['P']
                first = run / 'sampling/STUBG1/PENDING_CHECKPOINTS.json'
                bundle = env['load'](first)
                # One synthetic consumed proposal; later arms never dispatched.
                for arm in ARMS:
                    bundle['snapshots'][arm]['pending'] = bundle['snapshots'][arm]['pending'][:1] if arm == ARMS[0] else []
                    bundle['snapshots'][arm]['seen_attempt_ids'] = [x['attempt_id'] for x in bundle['snapshots'][arm]['pending']]
                if name == 'partial_hard_stop':
                    bundle['snapshots'][ARMS[0]]['pending'][0]['physical_result']['true_hard_safety_violation'] = True
                bundle['stage'] = 'STOPPED_WITH_PRESERVED_PENDING'
                first.write_text(json.dumps(bundle))
                partial = run / 'STUB_ONLY_PARTIAL_ENVELOPE.json'
                env['write_new'](partial, {'fixture_semantics': 'STUB_ONLY', 'schema': 'v8.root_bound_partial_pending_cancel.v1', 'original_final_pending_path': str(first.relative_to(p)), 'original_final_pending_sha256': env['sha'](first), 'all_sampling_groups_in_current_batch': ['STUBG1'], 'all_actual_failure_artifacts_reviewed_for_hard_safety': True, 'confirmed_hard_safety_attempts': []})
                cancel_env = {'Path': Path, 'argparse': None, 'fcntl': None, 'json': json, 'time': time, 'P': p, 'tx': tx, 'verify_original_proposals_and_receipts': env['verify_original_proposals_and_receipts']}
                reconcile_sha = extract('scripts/onpolicy_reconcile_cancel_v1.py', cancel_env)
                if name == 'partial_cancel':
                    result = cancel_env['cancel'](run, partial, 'STUB_ONLY_ENGINEERING_FAILURE')
                    assert result['generation_index'] == 1 and control['fake_finish_calls'] == 0
                    snap = env['load'](p / result['checkpoints'][ARMS[0]]['path'])
                    assert snap['rng'] == bundle['snapshots'][ARMS[0]]['rng'] and snap['seen_attempt_ids'] == bundle['snapshots'][ARMS[0]]['seen_attempt_ids']
                else:
                    try:
                        cancel_env['cancel'](run, partial, 'STUB_ONLY_ENGINEERING_FAILURE')
                        raise AssertionError('STUB_ONLY_EXPECTED_HARD_STOP')
                    except ValueError as error:
                        assert 'HARD_SAFETY_STOP' in str(error)
                    assert (run / 'CURRENT.json').read_bytes() == before and control['fake_finish_calls'] == 0
                    assert not any(x.startswith('fake_cancel:') for x in control['events'])
            results.append({'name': name, 'status': 'PASS_STUB_ONLY', 'fake_finish_calls': control['fake_finish_calls'], 'events': control['events']})
    assert len(source_shas) == 1, 'SOURCE_CHANGED_DURING_FIXTURE'
    return results, source_shas.pop()


if __name__ == '__main__':
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    started = time.monotonic()
    results, source_sha = checks()
    output = {'schema': 'v8.transaction_control_flow_stub_audit.v2', 'semantics': 'STUB_ONLY', 'status': 'PASS_STUB_ONLY_CONTROL_FLOW', 'source_sha256': source_sha, 'executed_function_source_hashes': EXECUTED_SOURCE_HASHES, 'tests': results, 'wall_s': time.monotonic() - started, 'real_model_initializations': 0, 'real_model_forwards': 0, 'real_gradients_or_parameter_updates': 0, 'physics': 0, 'actual_receipt_adapter_calls': 0, 'genuine_physical_evidence_tested': False, 'evidence_join_for_main_control_flow': 'EXPLICIT_STUB_NOT_END_TO_END_TEST_STRICT_PRIOR_SNAPSHOTS_SIGNATURE', 'real_source_imports': 0, 'temporary_files_removed': True}
    with OUT.open('x') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': output['status'], 'tests': len(results), 'wall_s': output['wall_s'], 'audit': str(OUT)}))
