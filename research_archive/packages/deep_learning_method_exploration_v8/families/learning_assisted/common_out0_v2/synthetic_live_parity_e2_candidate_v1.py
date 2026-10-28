"""SOURCE_ONLY synthetic E2 live-helper parity; separate approval required.

No real bundle/weight/data/raw/A3 API is read or called. All coefficients are
fixed closed-form synthetic tensors. No numerical work occurs on import.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import resource
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = 'families/learning_assisted/common_out0_v2/'
CONTRACT = REL + 'SYNTHETIC_LIVE_E2_PARITY_CONTRACT_V1.json'
MANIFEST = REL + 'SYNTHETIC_LIVE_E2_PARITY_SOURCE_MANIFEST_V1.json'
OUT = REL + 'synthetic/live_e2_parity_v1'
STOP = 1793114740.0
EXPECTED = dict(prediction_API_calls=25, prediction_query_vectors=85,
                shared_B_inference_forward_API_calls=4,
                backward_API_calls=0, stochastic_initializations=0,
                gradient_updates=0, fit=0, actual_A3_predict_calls=0,
                real_weight_reads=0, real_dataset_reads=0, physics=0)


def need(test, reason):
    if not test:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def authority(root, approval_path, approval_sha256):
    need(root == ROOT, 'SYNTHETIC_PARITY_UNIQUE_PACKAGE')
    path = Path(approval_path).resolve()
    need(path.is_relative_to(root) and sha(path) == approval_sha256,
         'SYNTHETIC_PARITY_EXACT_MAIN_APPROVAL')
    approval = load(path);contract = load(root / CONTRACT)
    need(approval.get('schema') == 'v8.E2.synthetic_live_parity_approval.v1' and
         approval.get('status') == 'ROOT_APPROVED_SYNTHETIC_LIVE_E2_PARITY_ONCE_V1' and
         approval.get('contract_sha256') == sha(root / CONTRACT) and
         approval.get('source_manifest_sha256') == sha(root / MANIFEST) and
         approval.get('output') == OUT and approval.get('synthetic_only') is True and
         approval.get('real_weight_read_authorization') is False and
         approval.get('A3_call_authorization') is False and
         approval.get('fit_authorization') is False and
         approval.get('physics_authorization') is False and
         approval.get('budget') == contract['budget'],
         'SYNTHETIC_PARITY_SEPARATE_EXACT_AUTHORITY_REQUIRED')
    need(contract['expected_success_counters'] == EXPECTED,
         'SYNTHETIC_PARITY_EXACT_PREREGISTERED_COUNTS')
    manifest = load(root / MANIFEST)
    allowed = {REL + name for name in (
        'synthetic_live_parity_e2_candidate_v1.py',
        'launch_synthetic_live_parity_e2_once_v1.py',
        'frozen_live_e2_candidate_v1.py', 'e2_models_candidate_v1.py',
        'SYNTHETIC_LIVE_E2_PARITY_CONTRACT_V1.json')}
    allowed.add('ACTIVATION.json')
    need(set(manifest['files_sha256']) == allowed,
         'SYNTHETIC_PARITY_NO_REAL_WEIGHTS_IN_SOURCE_ALLOWLIST')
    for relative, expected in manifest['files_sha256'].items():
        source = (root / relative).resolve()
        need(source.is_relative_to(root) and sha(source) == expected,
             'SYNTHETIC_PARITY_SOURCE_CHANGED:' + relative)
    activation = load(root / 'ACTIVATION.json')
    need(activation['activation_id'] == 'deep_learning_method_exploration_v8_20261027T032540Z'
         and activation['hard_stop_unix'] == STOP and activation['clock_must_not_reset'] is True,
         'SYNTHETIC_PARITY_ORIGINAL_CLOCK')
    return approval, contract, manifest


class SyntheticWork:
    def __init__(self, deadline):
        self.deadline = deadline;self.phase = 'CANDIDATE'
        self.c = {key: 0 for key in EXPECTED};self.kinds = {};self.phases = {}

    def guard(self):
        need(time.monotonic() < self.deadline and time.time() < STOP,
             'SYNTHETIC_PARITY_DECREASING_OWNER_LOCAL_GLOBAL_DEADLINE')

    def prediction(self, kind, count):
        self.guard();need(kind in ('RIDGE_KNOT_MATRIX', 'KNOTWISE_INTERPOLATION',
                                  'NEURAL_FORWARD_A', 'NEURAL_FORWARD_B'),
                           'SYNTHETIC_PARITY_UNREGISTERED_BACKEND')
        self.c['prediction_API_calls'] += 1;self.c['prediction_query_vectors'] += count
        need(self.c['prediction_API_calls'] <= 25 and
             self.c['prediction_query_vectors'] <= 85, 'SYNTHETIC_PARITY_API_CAP')
        for mapping, key in ((self.kinds, kind), (self.phases, self.phase)):
            item = mapping.setdefault(key, dict(API_calls=0, query_vectors=0))
            item['API_calls'] += 1;item['query_vectors'] += count


def source_module(path, name):
    need(name not in sys.modules, 'SYNTHETIC_PARITY_FRESH_PRIVATE_NAMESPACE')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec);sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None);raise
    return module


def synthetic_bundle(np):
    """16 fixed ridge tensors + 2 fixed MLP tensors; no RNG/init/fit calls."""
    all_models = {}
    domains = {'D4': [.5, 1., 1.5, 2., 2.5, 3., 3.5, 4.],
               'DFull': [.5, 1., 2., 4., 8., 12., 16., 19.03]}
    for domain_index, (domain, knots) in enumerate(domains.items()):
        norm = dict(center=(np.linspace(-.2, .2, 39) + .08 * domain_index).tolist(),
                    scale=(.5 + .01 * np.arange(39)).tolist())
        nodes = []
        for node_index, knot in enumerate(knots):
            nodes.append(dict(weights=(.02 * np.sin(
                np.arange(3200).reshape(200, 16) * .013 + knot + domain_index)).tolist(),
                target_center=(.03 * np.cos(np.arange(16) + node_index)).tolist(),
                target_scale=(.5 + .03 * np.arange(16)).tolist()))
        all_models[domain + '/RIDGE_CONTEXT_ACTION'] = dict(
            kind='RIDGE_CONTEXT_ACTION', paired=False, normalizer=norm,
            knot_times_s=knots, node_models=nodes)
        parameters = dict(
            W1=(.07 * np.sin(np.arange(720).reshape(45, 16) * .019 + domain_index)).tolist(),
            b1=(.02 * np.cos(np.arange(16) + domain_index)).tolist(),
            W2=(.06 * np.cos(np.arange(256).reshape(16, 16) * .023 + domain_index)).tolist(),
            b2=(.03 * np.sin(np.arange(16) + .4)).tolist())
        all_models[domain + '/MLP_PAIRED'] = dict(
            kind='MLP_PAIRED', paired=True, normalizer=norm,
            model=dict(kind='MLP_PAIRED', paired=True, action_only=False,
                       parameters=parameters, target_center=[0.] * 16,
                       target_scale=(.4 + .11 * np.arange(16)).tolist()))
    return dict(all_development_models=all_models,
                identity='SYNTHETIC_ONLY_NOT_FROZEN_E2_WEIGHTS')


def references(bundle, context, models, work, np):
    work.phase = 'REFERENCE';answers = {}
    x = np.asarray(context['features'], float);actions = np.arange(5, dtype=int)
    times = np.full(5, 19.03)
    initial = np.repeat(np.r_[x[25:39], 0., 0.][None, :], 5, axis=0)
    for domain in ('D4', 'DFull'):
        entry = bundle['all_development_models'][domain + '/RIDGE_CONTEXT_ACTION']
        norm = entry['normalizer']
        z = np.repeat(((x - np.asarray(norm['center'])) / np.asarray(norm['scale']))[None, :], 5, axis=0)
        design = models.ridge_design(z, actions, 'RIDGE_CONTEXT_ACTION', np)
        low = models.predict_knots(design, entry['node_models'][-2], work, np)
        high = models.predict_knots(design, entry['node_models'][-1], work, np)
        knots = np.asarray(entry['knot_times_s'][-2:], float)
        rows = [models.interpolate_knots(np.array([19.03]), knots,
                    np.stack([low[index], high[index]]), work, np)[0] for index in range(5)]
        answers[domain + '_RIDGE_CONTEXT_ACTION'] = np.asarray(rows)
        model = bundle['all_development_models'][domain + '/MLP_PAIRED']['model']
        answers[domain + '_MLP_PAIRED'] = models.predict_mlp(z, actions, times, initial, model, work, np)
    return answers


def selection_checks(api):
    tags = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
    menu = []
    for tag in tags:
        action = dict(synthetic_only_recipe=tag)
        menu.append(dict(tag=tag, action=action,
                         recipe_sha256=digest(dict(identity='SYNTHETIC_ONLY', action=action))))
    labels = ['D4_RIDGE_CONTEXT_ACTION', 'D4_MLP_PAIRED',
              'DFull_RIDGE_CONTEXT_ACTION', 'DFull_MLP_PAIRED']
    below = math.nextafter(.5, -math.inf);above = math.nextafter(.5, math.inf)
    cases = [
        ('EXACT_RISK_HALF_REJECT_B_HIGH_FALLBACK', [0., -1., -2., -3., -4.],
         [.9, .9, .5, .9, .9], 4, 0, 0),
        ('NEXTAFTER_BELOW_HALF_ACCEPT', [0., -1., -2., -3., -4.],
         [.9, .9, below, .9, .9], 4, 2, 2),
        ('NEXTAFTER_ABOVE_HALF_REJECT', [0., -1., -2., -3., -4.],
         [.9, .9, above, .9, .9], 4, 0, 0),
        ('EXACT_COST_TIE_INDEX_ZERO', [0.] * 5, [.9, .1, .1, .1, .1], 0, 0, 2),
        ('TINY_COST_GAP_NOT_FLOORED', [0., -1e-12, 1., 2., 3.],
         [.9, .1, .1, .1, .1], 1, 1, 2),
    ]
    records = []
    for name, values, risks, expected_raw, expected_gate, expected_fixed in cases:
        forecasts = {}
        for label in labels:
            vectors = [[0.] * 16 for _ in range(5)]
            for index in range(5):
                vectors[index][14] = values[index]
                vectors[index][15] = (index - 2) * 1e9  # Cannot enter JF objective.
            forecasts[label] = dict(values16=vectors, cost_semantics='SYNTHETIC_JF_AND_INDEPENDENT_JM')
        decisions = api.selector_decisions(forecasts, risks, menu)
        for label in labels:
            need(decisions[label + '_RAW']['choice_index'] == expected_raw,
                 'SYNTHETIC_PARITY_RAW_RULE:' + name)
            need(decisions[label + '_A3_RISK_LT_HALF']['choice_index'] == expected_gate,
                 'SYNTHETIC_PARITY_RISK_RULE:' + name)
        need(decisions['FIXED_EARLY_H150_A3_RISK_ELSE_B']['choice_index'] == expected_fixed,
             'SYNTHETIC_PARITY_FIXED_RULE:' + name)
        records.append(dict(case=name, valuesJF=values, synthetic_risks=risks,
            expected_raw_index=expected_raw, expected_gated_index=expected_gate,
            expected_fixed_index=expected_fixed, nine_selectors_checked=True))
    return records


def perform(api, models, work, np):
    bundle = synthetic_bundle(np)
    context = dict(features=(.15 * np.sin(np.arange(39) * .17 + .3)).tolist())
    before = digest(dict(bundle=bundle, context=context))
    candidate = api.cost_predictions(bundle, context, models, work, np)
    reference = references(bundle, context, models, work, np)
    comparisons = []
    for label, forecast in candidate.items():
        actual = np.asarray(forecast['values16']);expected = reference[label]
        need(actual.shape == expected.shape == (5, 16), 'SYNTHETIC_PARITY_ALL16_SHAPE')
        need(np.allclose(actual, expected, atol=1e-12, rtol=1e-12),
             'SYNTHETIC_PARITY_ALL16_VALUES:' + label)
        need(forecast['OOD_time'] == label.startswith('D4_') and
             forecast['query_time_s'] == 19.03 and forecast['future_true_B_used'] is False,
             'SYNTHETIC_PARITY_EXPLICIT_TIME_DOMAIN:' + label)
        if label.endswith('MLP_PAIRED'):
            need(np.array_equal(actual[0], np.zeros(16)) and
                 forecast['absolute_wrench_integral'] == 'NOT_APPLICABLE_NO_ABSOLUTE_B_RECONSTRUCTION',
                 'SYNTHETIC_PARITY_PAIRED_ANCHOR_INTEGRAL_NA')
        comparisons.append(dict(method=label, recipe_rows=5, heads=16,
            maximum_absolute_error=float(np.max(np.abs(actual - expected))),
            bit_exact=bool(np.array_equal(actual, expected)),
            per_head_maximum_absolute_error=np.max(np.abs(actual - expected), axis=0).tolist(),
            OOD_time=forecast['OOD_time']))
    checks = selection_checks(api)
    need(before == digest(dict(bundle=bundle, context=context)), 'SYNTHETIC_PARITY_INPUT_MUTATION')
    need(work.c == EXPECTED, 'SYNTHETIC_PARITY_EXACT_COUNTS:' + repr(work.c))
    need(work.phases == dict(CANDIDATE=dict(API_calls=7, query_vectors=35),
                            REFERENCE=dict(API_calls=18, query_vectors=50)),
         'SYNTHETIC_PARITY_CANDIDATE_REFERENCE_SEPARATE')
    return dict(parity=comparisons, scalar_comparisons=320,
                selection_cases=checks, selector_decisions_checked=45,
                fixed_tensor_constructions=dict(ridge_nodes=16, MLP_parameter_sets=2),
                synthetic_identity_sha256=before,
                real_weight_or_A3_or_raw_access=False,
                actual_OUT0_source_proof_exercised=False,
                deployment_eligible=False)


def main():
    start = time.monotonic();cpu = time.process_time();work = None;out = None
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True);parser.add_argument('--approval', required=True)
    parser.add_argument('--approval-sha256', required=True)
    parser.add_argument('--owner-deadline-monotonic', required=True, type=float)
    args = parser.parse_args();root = Path(args.package).resolve()
    need(math.isfinite(args.owner_deadline_monotonic), 'SYNTHETIC_PARITY_OWNER_DEADLINE')
    deadline = min(start + 30., args.owner_deadline_monotonic, start + STOP - time.time())
    approval, contract, manifest = authority(root, args.approval, args.approval_sha256)
    need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
         and all(os.environ.get(key) == '1' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')),
         'SYNTHETIC_PARITY_MINUS_B_THREADS')
    need(Path(sys.executable).resolve() == Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python').resolve(),
         'SYNTHETIC_PARITY_MAIN_VENV')
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    def stop_signal(signum, frame):
        raise TimeoutError('SYNTHETIC_PARITY_TIMEOUT_OR_CANCEL:' + str(signum))
    for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop_signal)
    need(time.monotonic() < deadline and time.time() < STOP, 'SYNTHETIC_PARITY_NO_CLOCK_RESET')
    signal.setitimer(signal.ITIMER_REAL, deadline - time.monotonic())
    out = root / OUT;out.mkdir(parents=True, exist_ok=False);work = SyntheticWork(deadline)
    new(out / 'START.json', dict(identity='SYNTHETIC_ONLY_NO_REAL_WEIGHTS',
        approval_sha256=args.approval_sha256, source_manifest_sha256=sha(root / MANIFEST),
        original_stop_unix=STOP, existing_owner_deadline=args.owner_deadline_monotonic,
        effective_deadline=deadline, single_CPU_affinity=sorted(os.sched_getaffinity(0)),
        source_module_imports_planned=2, real_model_bundle_reads=0))
    try:
        import numpy as np
        need(Path(np.__file__).resolve().is_relative_to(
            Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/lib')), 'SYNTHETIC_PARITY_MAIN_NUMPY')
        api = source_module(HERE / 'frozen_live_e2_candidate_v1.py', '_v8_E2_parity_synthetic_live_v1')
        models = source_module(HERE / 'e2_models_candidate_v1.py', '_v8_E2_parity_synthetic_math_v1')
        result = perform(api, models, work, np)
        for relative, expected in manifest['files_sha256'].items():
            work.guard();need(sha(root / relative) == expected, 'SYNTHETIC_PARITY_SOURCE_POSTCHECK')
        result.update(schema='v8.E2.synthetic_live_parity_result.v1',
            status='PASS_SYNTHETIC_PARITY_ONLY_NOT_ACTUAL_OUT0_APPROVAL',
            counters=work.c, backend_kinds=work.kinds, phase_counters=work.phases,
            wall_seconds=time.monotonic() - start, CPU_seconds=time.process_time() - cpu,
            RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            actual_candidate_and_math_source_module_imports=2)
        work.guard();new(out / 'RESULT.json', result)
        signal.setitimer(signal.ITIMER_REAL, 0.)
        print(json.dumps(dict(status=result['status'], result_sha256=sha(out / 'RESULT.json'),
                              counters=work.c), sort_keys=True))
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        new(out / 'FAILED_PRESERVED.json', dict(status='FAILED_NO_RETRY_SYNTHETIC_ONLY',
            error=str(error), traceback=traceback.format_exc(), counters=work.c,
            backend_kinds=work.kinds, phase_counters=work.phases,
            current_phase=work.phase, no_fit_or_resume_state=True,
            wall_seconds=time.monotonic() - start, CPU_seconds=time.process_time() - cpu,
            RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        raise


if __name__ == '__main__':
    main()
