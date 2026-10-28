"""SOURCE_ONLY actual frozen E2 bundle canary; separate approval required.

One fixed old development INDEX39; no NPZ, new validation, live proof, wrapper, A3 call, fit or physics.
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
CONTRACT = REL + 'ACTUAL_BUNDLE_E2_CANARY_CONTRACT_V1.json'
MANIFEST = REL + 'ACTUAL_BUNDLE_E2_CANARY_SOURCE_MANIFEST_V1.json'
OUT = REL + 'canaries/actual_bundle_e2_v1'
STOP = 1793114740.0
EXPECTED = dict(prediction_API_calls=25, prediction_query_vectors=85,
                shared_B_inference_forward_API_calls=4,
                backward_API_calls=0, stochastic_initializations=0,
                gradient_updates=0, fit=0, actual_A3_predict_calls=0,
                real_bundle_JSON_loads=1, old_development_INDEX_JSON_loads=1, physics=0)


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
    need(root == ROOT, 'ACTUAL_BUNDLE_CANARY_UNIQUE_PACKAGE')
    path = Path(approval_path).resolve()
    need(path.is_relative_to(root) and sha(path) == approval_sha256,
         'ACTUAL_BUNDLE_CANARY_EXACT_MAIN_APPROVAL')
    approval = load(path);contract = load(root / CONTRACT)
    need(approval.get('schema') == 'v8.E2.actual_bundle_canary_approval.v1' and
         approval.get('status') == 'ROOT_APPROVED_ACTUAL_BUNDLE_E2_CANARY_ONCE_V1' and
         approval.get('contract_sha256') == sha(root / CONTRACT) and
         approval.get('source_manifest_sha256') == sha(root / MANIFEST) and
         approval.get('output') == OUT and approval.get('actual_bundle_only') is True and
         approval.get('real_weight_read_authorization') is True and
         approval.get('old_development_INDEX_read_authorization') is True and
         approval.get('actual_OUT0_wrapper_call_authorization') is False and
         approval.get('A3_call_authorization') is False and
         approval.get('fit_authorization') is False and
         approval.get('physics_authorization') is False and
         approval.get('budget') == contract['budget'],
         'ACTUAL_BUNDLE_CANARY_SEPARATE_EXACT_AUTHORITY_REQUIRED')
    need(contract['expected_success_counters'] == EXPECTED,
         'ACTUAL_BUNDLE_CANARY_EXACT_PREREGISTERED_COUNTS')
    manifest = load(root / MANIFEST)
    allowed = {REL + name for name in (
        'actual_bundle_canary_e2_candidate_v1.py',
        'launch_actual_bundle_canary_e2_once_v1.py',
        'frozen_live_e2_candidate_v2.py', 'e2_models_candidate_v1.py',
        'ACTUAL_BUNDLE_E2_CANARY_CONTRACT_V1.json')}
    allowed.update({'ACTIVATION.json', REL+'fits/e2_v1/FROZEN_E2_BUNDLE.json',
                    REL+'data/fulltask_e2_v1/INDEX.json', REL+'FROZEN_LIVE_E2_CONTRACT_V2.json',
                    REL+'FROZEN_LIVE_E2_SOURCE_MANIFEST_V2.json'})
    need(set(manifest['files_sha256']) == allowed,
         'ACTUAL_BUNDLE_CANARY_EXACT_REAL_WEIGHT_AND_OLD_INDEX_ALLOWLIST')
    for relative, expected in manifest['files_sha256'].items():
        source = (root / relative).resolve()
        need(source.is_relative_to(root) and sha(source) == expected,
             'ACTUAL_BUNDLE_CANARY_SOURCE_CHANGED:' + relative)
    activation = load(root / 'ACTIVATION.json')
    need(activation['activation_id'] == 'deep_learning_method_exploration_v8_20261027T032540Z'
         and activation['hard_stop_unix'] == STOP and activation['clock_must_not_reset'] is True,
         'ACTUAL_BUNDLE_CANARY_ORIGINAL_CLOCK')
    return approval, contract, manifest


class CanaryWork:
    def __init__(self, deadline):
        self.deadline = deadline;self.phase = 'CANDIDATE'
        self.c = {key: 0 for key in EXPECTED};self.kinds = {};self.phases = {}

    def guard(self):
        need(time.monotonic() < self.deadline and time.time() < STOP,
             'ACTUAL_BUNDLE_CANARY_DECREASING_OWNER_LOCAL_GLOBAL_DEADLINE')

    def prediction(self, kind, count):
        self.guard();need(kind in ('RIDGE_KNOT_MATRIX', 'KNOTWISE_INTERPOLATION',
                                  'NEURAL_FORWARD_A', 'NEURAL_FORWARD_B'),
                           'ACTUAL_BUNDLE_CANARY_UNREGISTERED_BACKEND')
        self.c['prediction_API_calls'] += 1;self.c['prediction_query_vectors'] += count
        need(self.c['prediction_API_calls'] <= 25 and
             self.c['prediction_query_vectors'] <= 85, 'ACTUAL_BUNDLE_CANARY_API_CAP')
        for mapping, key in ((self.kinds, kind), (self.phases, self.phase)):
            item = mapping.setdefault(key, dict(API_calls=0, query_vectors=0))
            item['API_calls'] += 1;item['query_vectors'] += count


def source_module(path, name):
    need(name not in sys.modules, 'ACTUAL_BUNDLE_CANARY_FRESH_PRIVATE_NAMESPACE')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec);sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None);raise
    return module




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






def perform(api, models, work, np):
    work.guard();work.c['real_bundle_JSON_loads'] = 1
    bundle = load(HERE / 'fits/e2_v1/FROZEN_E2_BUNDLE.json')
    work.guard();work.c['old_development_INDEX_JSON_loads'] = 1
    index = load(HERE / 'data/fulltask_e2_v1/INDEX.json')
    row = index['rows'][0]
    need(row['id'] == 'CFACTORH01_B' and row['input']['recipe_index'] == 0,
         'ACTUAL_CANARY_PREREGISTERED_FIRST_OLD_DEVELOPMENT_ROW')
    context = dict(feature_names=row['input']['feature_names'], features=row['input']['features'])
    need(context['feature_names'] == bundle['feature_names'] == index['feature_names'] and
         len(context['features']) == 39 and bundle['menu'] == index['menu'],
         'ACTUAL_CANARY_FROZEN39_AND_FULLMENU')
    schema = {}
    for domain in ('D4', 'DFull'):
        entry = bundle['all_development_models'][domain + '/MLP_PAIRED']
        model = entry['model']
        need(set(entry) == {'model', 'normalizer'} and model['kind'] == 'MLP_PAIRED'
             and model['paired'] is True and model['action_only'] is False,
             'ACTUAL_CANARY_REAL_MLP_NESTED_SCHEMA_NOT_SYNTHETIC_REWRITE')
        schema[domain] = dict(outer_keys=sorted(entry), inner_keys=sorted(model),
                             inner_kind=model['kind'], paired=model['paired'], action_only=model['action_only'])
    before = digest(dict(bundle=bundle, context=context))
    candidate = api.cost_predictions(bundle, context, models, work, np)
    reference = references(bundle, context, models, work, np)
    comparisons = []
    for label, forecast in candidate.items():
        actual = np.asarray(forecast['values16']);expected = reference[label]
        need(actual.shape == expected.shape == (5, 16) and np.allclose(actual, expected, atol=1e-12, rtol=1e-12),
             'ACTUAL_CANARY_ALL16_PARITY:' + label)
        if label.endswith('MLP_PAIRED'):
            need(np.array_equal(actual[0], np.zeros(16)) and
                 forecast['absolute_wrench_integral'] == 'NOT_APPLICABLE_NO_ABSOLUTE_B_RECONSTRUCTION',
                 'ACTUAL_CANARY_PAIRED_B_ANCHOR_NO_FUTURE_B')
        need(forecast['OOD_time'] == label.startswith('D4_') and forecast['query_time_s'] == 19.03
             and forecast['future_true_B_used'] is False, 'ACTUAL_CANARY_TIME_IDENTITY')
        comparisons.append(dict(method=label, maximum_absolute_error=float(np.max(np.abs(actual-expected))),
            per_head_maximum_absolute_error=np.max(np.abs(actual-expected),axis=0).tolist(),
            bit_exact=bool(np.array_equal(actual,expected)), scalar_comparisons=80))
    # Fixed public scores exercise selection plumbing only: never call A3 or claim its risk proof.
    risks = [.9, .49, .5, math.nextafter(.5, math.inf), math.nextafter(.5, -math.inf)]
    decisions = api.selector_decisions(candidate, risks, bundle['menu'])
    reference_indices = {}
    allowed = [0] + [i for i in range(1,5) if risks[i] < .5]
    for label, values16 in reference.items():
        values = [float(row[14]) for row in values16]
        reference_indices[label + '_RAW'] = min(range(5),key=lambda i:(values[i],i))
        reference_indices[label + '_A3_RISK_LT_HALF'] = min(allowed,key=lambda i:(values[i],i))
    reference_indices['FIXED_EARLY_H150_A3_RISK_ELSE_B'] = 2 if risks[2] < .5 else 0
    need(set(decisions) == set(reference_indices) and len(decisions) == 9, 'ACTUAL_CANARY_NINE_SELECTORS')
    for label, chosen in decisions.items():
        i = reference_indices[label];item = bundle['menu'][i]
        need(chosen['choice_index'] == i and chosen['choice_tag'] == item['tag'] and
             chosen['choice_recipe_sha256'] == item['recipe_sha256'] and chosen['choice_action'] == item['action'],
             'ACTUAL_CANARY_EXACT_CHOICE_NO_TOLERANCE_FLOOR:' + label)
    need(before == digest(dict(bundle=bundle,context=context)), 'ACTUAL_CANARY_INPUT_WEIGHTS_UNCHANGED')
    need(work.c == EXPECTED, 'ACTUAL_CANARY_EXACT_COUNTS:' + repr(work.c))
    need(work.phases == dict(CANDIDATE=dict(API_calls=7,query_vectors=35),REFERENCE=dict(API_calls=18,query_vectors=50)),
         'ACTUAL_CANARY_PHASE_ACCOUNTING')
    return dict(parity=comparisons, scalar_comparisons=320, selector_decisions_checked=9,
        candidate_forecasts=candidate, reference_values16={key:value.tolist() for key,value in reference.items()},
        decisions=decisions, reference_choice_indices=reference_indices,
        controlled_risk_vector_not_A3_prediction=risks, actual_A3_predict_calls=0,
        actual_model_schema=schema, actual_old_context_row=row['id'],
        actual_old_context39_sha256=digest(context), all_inputs_and_weights_unchanged=True,
        numerical_tolerance_diagnostic_only_no_choice_floor=True,
        actual_OUT0_source_proof_exercised=False, actual_OUT0_wrapper_called=False,
        deployment_eligible=False, real_physical_qualification_granted=False)


def main():
    start = time.monotonic();cpu = time.process_time();work = None;out = None
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True);parser.add_argument('--approval', required=True)
    parser.add_argument('--approval-sha256', required=True)
    parser.add_argument('--owner-deadline-monotonic', required=True, type=float)
    args = parser.parse_args();root = Path(args.package).resolve()
    need(math.isfinite(args.owner_deadline_monotonic), 'ACTUAL_BUNDLE_CANARY_OWNER_DEADLINE')
    deadline = min(start + 30., args.owner_deadline_monotonic, start + STOP - time.time())
    approval, contract, manifest = authority(root, args.approval, args.approval_sha256)
    need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
         and all(os.environ.get(key) == '1' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')),
         'ACTUAL_BUNDLE_CANARY_MINUS_B_THREADS')
    need(Path(sys.executable).resolve() == Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python').resolve(),
         'ACTUAL_BUNDLE_CANARY_MAIN_VENV')
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    def stop_signal(signum, frame):
        raise TimeoutError('ACTUAL_BUNDLE_CANARY_TIMEOUT_OR_CANCEL:' + str(signum))
    for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop_signal)
    need(time.monotonic() < deadline and time.time() < STOP, 'ACTUAL_BUNDLE_CANARY_NO_CLOCK_RESET')
    signal.setitimer(signal.ITIMER_REAL, deadline - time.monotonic())
    out = root / OUT;out.mkdir(parents=True, exist_ok=False);work = CanaryWork(deadline)
    new(out / 'START.json', dict(identity='ACTUAL_FROZEN_BUNDLE_OLD_DEVELOPMENT_CONTEXT_NOT_LIVE_PROOF',
        approval_sha256=args.approval_sha256, source_manifest_sha256=sha(root / MANIFEST),
        original_stop_unix=STOP, existing_owner_deadline=args.owner_deadline_monotonic,
        effective_deadline=deadline, single_CPU_affinity=sorted(os.sched_getaffinity(0)),
        source_module_imports_planned=2, model_bundle_JSON_reads_planned=1, old_INDEX_JSON_reads_planned=1))
    try:
        import numpy as np
        need(Path(np.__file__).resolve().is_relative_to(
            Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/lib')), 'ACTUAL_BUNDLE_CANARY_MAIN_NUMPY')
        api = source_module(HERE / 'frozen_live_e2_candidate_v2.py', '_v8_E2_actual_bundle_live_v1')
        models = source_module(HERE / 'e2_models_candidate_v1.py', '_v8_E2_actual_bundle_math_v1')
        result = perform(api, models, work, np)
        for relative, expected in manifest['files_sha256'].items():
            work.guard();need(sha(root / relative) == expected, 'ACTUAL_BUNDLE_CANARY_SOURCE_POSTCHECK')
        result.update(schema='v8.E2.actual_bundle_canary_result.v1',
            status='PASS_ACTUAL_BUNDLE_CANARY_NOT_LIVE_OUT0_APPROVAL',
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
        new(out / 'FAILED_PRESERVED.json', dict(status='FAILED_NO_RETRY_ACTUAL_BUNDLE_CANARY',
            error=str(error), traceback=traceback.format_exc(), counters=work.c,
            backend_kinds=work.kinds, phase_counters=work.phases,
            current_phase=work.phase, no_fit_or_resume_state=True,
            wall_seconds=time.monotonic() - start, CPU_seconds=time.process_time() - cpu,
            RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        raise


if __name__ == '__main__':
    main()
