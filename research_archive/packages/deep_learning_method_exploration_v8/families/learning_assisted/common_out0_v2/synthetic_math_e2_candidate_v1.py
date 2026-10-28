"""SOURCE_ONLY; requires separate exact one-shot SYNTHETIC_ONLY approval.

No E2 NPZ, raw, actor, worker, physics or real-data training is read/called.
The frozen V1 numerical functions are invoked only by an approved main().
"""
from pathlib import Path
import argparse
from collections import Counter
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
SOURCE = REL + 'SYNTHETIC_MATH_E2_SOURCE_MANIFEST_V1.json'
CONTRACT = REL + 'SYNTHETIC_MATH_E2_CONTRACT_V1.json'
OUT = REL + 'synthetic/e2_math_v1'
MODEL = 'e2_models_candidate_v1.py'
MODEL_SHA = 'edaf6fab6d48bfdf44bb5e4bcc09c73b7532079cabc6a4fc6b303a4839275e32'
STOP = 1793114740.0
ACTIVATION = 'deep_learning_method_exploration_v8_20261027T032540Z'
EXPECTED = dict(
    synthetic_fixed_parameter_sets=2, finite_difference_cases=3,
    finite_difference_coordinates=192, finite_difference_loss_evaluations=384,
    analytical_gradient_cases=3, equal_branch_cancellation_cases=1,
    physical_decode_predict_API_calls=3,
    neural_initialization_attempts=3, neural_initializations=3,
    gradient_update_attempts=600, parameter_gradient_updates=600,
    network_training_forward_API_calls=800,
    network_training_forward_query_vectors=102400,
    network_backward_API_calls=806, network_backward_query_vectors=102436,
    shared_B_training_forward_API_calls=200, shared_B_backward_API_calls=202,
    shared_B_inference_forward_API_calls=131,
    prediction_API_calls=522, prediction_query_vectors=3132,
    adam_first_two_step_checks=6, scalar_adam_coordinate_updates=24,
    real_data_reads=0, real_model_fits=0, physics=0)


def need(test, reason):
    if not test:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if hasattr(value, 'tolist'):
        return clean(value.tolist())
    return value


def new(path, value):
    with Path(path).open('x') as stream:
        json.dump(clean(value), stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def append(path, value):
    with Path(path).open('a') as stream:
        stream.write(json.dumps(clean(value), sort_keys=True, allow_nan=False) + '\n')
        stream.flush();os.fsync(stream.fileno())


def coordinates(d):
    """64 preregistered coordinates: all16 hidden and all16 output W/b."""
    return ([('W1', (j % d, j)) for j in range(16)] +
            [('b1', (j,)) for j in range(16)] +
            [('W2', (j, j)) for j in range(16)] +
            [('b2', (j,)) for j in range(16)])


def scalar_coordinates():
    return [('W1', (0, 0)), ('b1', (0,)), ('W2', (0, 0)), ('b2', (0,))]


def close(a, b, reason, *, atol=5e-14, rtol=5e-12):
    need(math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol),
         reason + ':' + repr((float(a), float(b))))


class SyntheticWork:
    """Synthetic-only counters. No import or inheritance from the real runner."""
    def __init__(self, out, deadline):
        self.out = out;self.deadline = deadline
        self.c = {k: 0 for k in EXPECTED}
        self.current_neural_state = None
        self.phase = 'SYNTHETIC_MATH';self.step = 0
        self.captured_gradients = [];self.scalar = {};self.adam_checks = []
        self.prediction_kinds = Counter()

    def guard(self):
        need(time.monotonic() < self.deadline and time.time() < STOP,
             'SYNTHETIC_UNCHANGED_LOCAL_GLOBAL_DEADLINE')

    def prediction(self, kind, count):
        self.guard();self.c['prediction_API_calls'] += 1
        self.c['prediction_query_vectors'] += count
        self.prediction_kinds[kind] += 1
        need(self.c['prediction_API_calls'] <= 522 and
             self.c['prediction_query_vectors'] <= 3132,
             'SYNTHETIC_PREDICTION_CAP')

    def event(self, kind, **payload):
        self.guard()
        if kind == 'NEURAL_INITIALIZE':
            need(self.phase == 'SYNTHETIC_ADAM', 'NO_REAL_INITIALIZATION')
            state = self.current_neural_state
            self.scalar = {(key, ix): dict(p=float(state['parameters'][key][ix]),
                                          m=0., v=0.)
                           for key, ix in scalar_coordinates()}
        if kind == 'GRADIENT_STEP_START':
            self.step = payload['step'];self.captured_gradients = []
        if kind == 'GRADIENT_STEP_RETURN' and self.step <= 2:
            self._check_scalar_adam(payload)
        append(self.out / 'SYNTHETIC_WORK_EVENTS.jsonl', dict(
            event=kind, identity='SYNTHETIC_ONLY_NOT_E2_DATA',
            unix=time.time(), counters=self.c.copy(), **payload))

    def capture_backward(self, gradient, branch_B, np):
        if self.phase == 'SYNTHETIC_ADAM' and self.step <= 2:
            self.captured_gradients.append((branch_B,
                {key: np.array(value, copy=True) for key, value in gradient.items()}))

    def _check_scalar_adam(self, payload):
        state = self.current_neural_state
        paired = state['kind'] == 'MLP_PAIRED'
        need([b for b, _ in self.captured_gradients] ==
             ([False, True] if paired else [False]), 'SYNTHETIC_BRANCH_ORDER')
        gradient = {key: sum((value[key] for _, value in self.captured_gradients))
                    for key in state['parameters']}
        # Independent Python scalar summation/sqrt and scalar Adam recurrence.
        norm = math.sqrt(math.fsum(float(g) ** 2
            for value in gradient.values() for g in value.flat))
        clip = min(1., 5. / max(norm, 1e-300))
        close(norm, payload['raw_gradient_norm'], 'SYNTHETIC_RAW_GRADIENT_NORM')
        close(clip, payload['gradient_clip'], 'SYNTHETIC_CLIP')
        for key, ix in scalar_coordinates():
            previous = self.scalar[(key, ix)];g = float(gradient[key][ix]) * clip
            m = .9 * previous['m'] + .1 * g
            v = .999 * previous['v'] + .001 * g * g
            parameter = previous['p'] - .003 * (m / (1. - .9 ** self.step)) / (
                math.sqrt(v / (1. - .999 ** self.step)) + 1e-8)
            close(m, state['adam_first'][key][ix], 'SYNTHETIC_SCALAR_ADAM_M')
            close(v, state['adam_second'][key][ix], 'SYNTHETIC_SCALAR_ADAM_V')
            close(parameter, state['parameters'][key][ix], 'SYNTHETIC_SCALAR_ADAM_PARAMETER')
            self.scalar[(key, ix)] = dict(p=parameter, m=m, v=v)
            self.c['scalar_adam_coordinate_updates'] += 1
        self.c['adam_first_two_step_checks'] += 1
        self.adam_checks.append(dict(kind=state['kind'], step=self.step,
            coordinate_count=4, independent_scalar_math=True,
            raw_gradient_norm=norm, gradient_clip=clip))


def fixed_parameters(d, work, np):
    work.c['synthetic_fixed_parameter_sets'] += 1
    return dict(W1=.08 * np.sin(np.arange(d * 16).reshape(d, 16) + .5),
                b1=.03 * np.cos(np.arange(16) + .25),
                W2=.07 * np.cos(np.arange(256).reshape(16, 16) + .75),
                b2=.02 * np.sin(np.arange(16) + .4))


def physical_loss(inputs, B_inputs, parameters, initial, target,
                  center, scale, u, paired, work, models, np):
    a, _ = models.forward(inputs, parameters, work, np, training=False)
    if paired:
        b, _ = models.forward(B_inputs, parameters, work, np,
                              training=False, branch_B=True)
        prediction = (a - b) * scale * u
    else:
        prediction = initial + (a * scale + center) * u
    work.c['finite_difference_loss_evaluations'] += 1
    return float(np.mean((prediction - target) ** 2))


def finite_difference_case(label, inputs, B_inputs, parameters, initial, target,
                           center, scale, u, paired, work, models, np):
    work.c['finite_difference_cases'] += 1
    a, cache = models.forward(inputs, parameters, work, np, training=False)
    if paired:
        b, Bcache = models.forward(B_inputs, parameters, work, np,
                                   training=False, branch_B=True)
        physical = (a - b) * scale * u
    else:
        b = None;physical = initial + (a * scale + center) * u
    derivative = (2. * (physical - target) / physical.size) * scale * u
    gradient = models.backward(cache, derivative, parameters, work, np)
    if paired:
        other = models.backward(Bcache, -derivative, parameters, work, np,
                                branch_B=True)
        gradient = {key: gradient[key] + other[key] for key in gradient}
    work.c['analytical_gradient_cases'] += 1
    residuals = [];epsilon = 1e-6
    for key, ix in coordinates(inputs.shape[1]):
        work.guard();original = float(parameters[key][ix])
        try:
            parameters[key][ix] = original + epsilon
            plus = physical_loss(inputs, B_inputs, parameters, initial, target,
                                 center, scale, u, paired, work, models, np)
            parameters[key][ix] = original - epsilon
            minus = physical_loss(inputs, B_inputs, parameters, initial, target,
                                  center, scale, u, paired, work, models, np)
        finally:
            parameters[key][ix] = original
        finite = (plus - minus) / (2. * epsilon)
        analytical = float(gradient[key][ix])
        tolerance = 2e-7 + 2e-5 * max(abs(finite), abs(analytical))
        need(abs(finite - analytical) <= tolerance, 'SYNTHETIC_FD:' + label + ':' + key + str(ix))
        residuals.append(dict(key=key, coordinate=list(ix), analytical=analytical,
                              finite_difference=finite, absolute_error=abs(finite - analytical),
                              tolerance=tolerance))
        work.c['finite_difference_coordinates'] += 1
    return dict(case=label, coordinates=residuals, paired_shared_parameters=paired,
                output_head_W_and_b_coverage=list(range(16))), physical


def perform(models, work, np):
    # All arrays are closed-form synthetic values; no file-derived feature/label.
    z = .3 * np.sin(np.arange(6 * 39).reshape(6, 39) * .17 + .1)
    actions = np.array([0, 1, 2, 3, 4, 0], int)
    times = np.array([0., .5, 1., 2., 4., 8.]);u = times[:, None] / 20.
    initial = .1 * np.cos(np.arange(6 * 16).reshape(6, 16) * .13)
    center = np.linspace(-.3, .4, 16);scale = .4 + .11 * np.arange(16)
    target = initial + .2 * np.sin(np.arange(6 * 16).reshape(6, 16) * .23)
    paired_target = .15 * np.cos(np.arange(6 * 16).reshape(6, 16) * .19)
    x6 = models.nn_inputs(z, actions, times, True, np)
    x45 = models.nn_inputs(z, actions, times, False, np)
    b45 = models.nn_inputs(z, np.zeros(6, int), times, False, np)
    need(x6.shape == (6, 6) and x45.shape == (6, 45), 'SYNTHETIC_INPUT_SHAPES')
    p6 = fixed_parameters(6, work, np);p45 = fixed_parameters(45, work, np)
    reports = [];expected_decodes = []
    cases = [('ABSOLUTE_6D', x6, None, p6, target, False),
             ('ABSOLUTE_45D', x45, None, p45, target, False),
             ('SHARED_A_MINUS_B_45D', x45, b45, p45, paired_target, True)]
    for label, inputs, B_inputs, parameters, y, paired in cases:
        report, prediction = finite_difference_case(label, inputs, B_inputs,
            parameters, initial, y, center, scale, u, paired, work, models, np)
        reports.append(report);expected_decodes.append(prediction)

    # Nonzero upstream derivative makes cancellation test meaningful even when
    # the equal-branch output is exactly zero. No zero-loss shortcut is used.
    same_a, same_cache = models.forward(b45, p45, work, np, training=False)
    same_b, same_Bcache = models.forward(b45, p45, work, np,
                                       training=False, branch_B=True)
    upstream = .02 + .01 * np.sin(np.arange(96).reshape(6, 16))
    ga = models.backward(same_cache, upstream, p45, work, np)
    gb = models.backward(same_Bcache, -upstream, p45, work, np, branch_B=True)
    need(np.array_equal(same_a - same_b, np.zeros_like(same_a)), 'SYNTHETIC_EQUAL_BRANCH_OUTPUT')
    need(all(np.array_equal(ga[key] + gb[key], np.zeros_like(ga[key])) for key in ga),
         'SYNTHETIC_EQUAL_BRANCH_GRADIENT_CANCELLATION')
    work.c['equal_branch_cancellation_cases'] += 1

    for index, kind in enumerate(('MLP_ACTION_ONLY', 'MLP_CONTEXT_ACTION', 'MLP_PAIRED')):
        paired = kind == 'MLP_PAIRED';parameters = p6 if index == 0 else p45
        model = dict(kind=kind, paired=paired, action_only=index == 0,
            parameters={key: value.tolist() for key, value in parameters.items()},
            target_center=(np.zeros(16) if paired else center).tolist(),
            target_scale=scale.tolist())
        decoded = models.predict_mlp(z, actions, times, initial, model, work, np)
        need(np.allclose(decoded, expected_decodes[index], rtol=1e-14, atol=1e-14),
             'SYNTHETIC_PHYSICAL_16HEAD_DECODE:' + kind)
        need(np.array_equal(decoded[0], np.zeros(16) if paired else initial[0]),
             'SYNTHETIC_T0_ANCHOR:' + kind)
        if paired:
            need(np.array_equal(decoded[actions == 0], np.zeros_like(decoded[actions == 0])),
                 'SYNTHETIC_B_DELTA_ANCHOR')
            # Cost heads remain independent signed deltas, never wrench norms.
            need(np.allclose(decoded[:, 14:], expected_decodes[index][:, 14:], rtol=1e-14, atol=1e-14),
                 'SYNTHETIC_INDEPENDENT_DELTA_JF_JM_HEADS')
        work.c['physical_decode_predict_API_calls'] += 1

    # Three *actual frozen fit_mlp* invocations, each the fixed200 updates.
    # A value-preserving trace wrapper calls original backward exactly once;
    # it copies gradients only for the first two steps and returns unchanged.
    train_z = .25 * np.sin(np.arange(10 * 39).reshape(10, 39) * .11)
    train_a = np.tile(np.arange(5), 2);train_t = np.linspace(.5, 4., 10)
    train_u = train_t[:, None] / 20.;train_initial = .05 * np.cos(np.arange(160).reshape(10, 16) * .07)
    head = np.linspace(.2, 1.1, 16)[None, :]
    action_delta = train_a[:, None] * head * .12
    base_rate = .15 * np.sin(train_z.sum(axis=1, keepdims=True)) + head * .07
    absolute_target = train_initial + train_u * (base_rate + action_delta)
    delta_target = train_u * action_delta
    original_backward = models.backward
    def traced_backward(cache, grad_output, parameters, local_work, local_np, *, branch_B=False):
        need(local_work is work and local_np is np, 'SYNTHETIC_TRACE_OWNER')
        gradient = original_backward(cache, grad_output, parameters, local_work,
                                     local_np, branch_B=branch_B)
        work.capture_backward(gradient, branch_B, np)
        return gradient
    models.backward = traced_backward;fit_receipts = []
    try:
        work.phase = 'SYNTHETIC_ADAM'
        for kind in ('MLP_ACTION_ONLY', 'MLP_CONTEXT_ACTION', 'MLP_PAIRED'):
            model = models.fit_mlp(train_z, train_a, train_t,
                delta_target if kind == 'MLP_PAIRED' else absolute_target,
                train_initial, kind=kind, work=work,
                label='SYNTHETIC_ONLY/' + kind, np=np)
            need(model['optimizer']['step'] == 200 and work.current_neural_state is None,
                 'SYNTHETIC_FIXED200_COMPLETION')
            fit_receipts.append(dict(kind=kind, steps=200,
                initial_weights_sha256=model['initial_weights_sha256'],
                synthetic_model_sha256=models.digest(model),
                deployment_eligible=False, real_data_training=False))
    finally:
        models.backward = original_backward
    need(work.c == EXPECTED, 'SYNTHETIC_EXACT_COUNT_MISMATCH:' + repr(work.c))
    return dict(finite_difference=reports, scalar_adam_checks=work.adam_checks,
                synthetic_fit_receipts=fit_receipts,
                equal_branch_output_and_gradient_exact_zero=True,
                t0_and_paired_B_exact_zero_anchors=True,
                cost_heads_independent_not_norm_delta_wrench=True,
                real_dataset_opened=False, deployment_eligible=False)


def main():
    started = time.monotonic();cpu_started = time.process_time();out = None;work = None
    deadline = started + 30.
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    parser.add_argument('--approval', required=True)
    parser.add_argument('--approval-sha256', required=True)
    args = parser.parse_args();root = Path(args.package).resolve()
    need(root == ROOT and Path(__file__).resolve() == root / REL / Path(__file__).name,
         'SYNTHETIC_EXACT_PACKAGE_SOURCE_PATH')
    need(sha(args.approval) == args.approval_sha256, 'SYNTHETIC_EXACT_APPROVAL_SHA')
    approval = load(args.approval);manifest = load(root / SOURCE);contract = load(root / CONTRACT)
    need(approval.get('status') == 'ROOT_APPROVED_ONE_SHOT_SYNTHETIC_E2_MATH_V1',
         'SEPARATE_MAIN_SYNTHETIC_APPROVAL_REQUIRED')
    need(approval.get('source_manifest_sha256') == sha(root / SOURCE) and
         approval.get('contract_sha256') == sha(root / CONTRACT) and
         approval.get('output') == OUT and approval.get('synthetic_only') is True and
         approval.get('real_data_training') is False and approval.get('physics') == 0,
         'SYNTHETIC_APPROVAL_SCOPE')
    need(approval.get('budget') == dict(wall_seconds=30, cpu_threads=1,
         address_space_bytes=1073741824, real_model_fits=0, physics=0), 'SYNTHETIC_EXACT_BUDGET')
    need(manifest.get('status') == 'SOURCE_ONLY_NOT_APPROVED_NOT_RUN' and
         contract.get('expected_counters') == EXPECTED, 'SYNTHETIC_FROZEN_CONTRACT')
    for relative, expected in manifest['files_sha256'].items():
        need(sha(root / relative) == expected, 'SYNTHETIC_SOURCE_CHANGED:' + relative)
    need(sha(HERE / MODEL) == MODEL_SHA, 'SYNTHETIC_FROZEN_V1_MODEL_SOURCE')
    activation = load(root / 'ACTIVATION.json')
    need(activation.get('activation_id') == ACTIVATION and
         activation.get('hard_stop_unix') == STOP and activation.get('clock_must_not_reset') is True,
         'SYNTHETIC_UNCHANGED_ACTIVATION')
    need(time.time() < STOP and time.monotonic() < deadline, 'SYNTHETIC_ORIGINAL_CLOCK')
    need(sys.dont_write_bytecode and
         Path(sys.executable).resolve() == Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python').resolve(),
         'SYNTHETIC_CORRECT_VENV_MINUS_B')
    need(all(os.environ.get(key) == '1' for key in
             ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')) and
         os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'SYNTHETIC_THREADS_BYTECODE_ENV')
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('SYNTHETIC_30S_NO_RESET')))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(TimeoutError('SYNTHETIC_EXTERNAL_TIMEOUT_PRESERVED')))
    signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('SYNTHETIC_CANCEL_PRESERVED')))
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
    out = root / OUT;out.mkdir(parents=True, exist_ok=False)
    work = SyntheticWork(out, deadline)
    new(out / 'START.json', dict(identity='SYNTHETIC_ONLY_NOT_E2_DATA',
        approval_sha256=args.approval_sha256, source_manifest_sha256=sha(root / SOURCE),
        contract_sha256=sha(root / CONTRACT), local_start_monotonic=started,
        unchanged_local_deadline=deadline, original_global_stop=STOP,
        no_real_dataset_reads=True, no_physics=True))
    try:
        import numpy as np
        spec = importlib.util.spec_from_file_location('v8_e2_synthetic_frozen_models_v1', HERE / MODEL)
        models = importlib.util.module_from_spec(spec);sys.modules[spec.name] = models
        spec.loader.exec_module(models)
        result = perform(models, work, np)
        need(sha(HERE / MODEL) == MODEL_SHA, 'SYNTHETIC_MODEL_SOURCE_POSTCHECK')
        work.guard()
        result.update(schema='v8.E2.synthetic_math_result.v1',
            status='PASS_SYNTHETIC_ONLY_NOT_REAL_FIT_NOT_DEPLOYMENT',
            counters=work.c, prediction_kinds=dict(work.prediction_kinds),
            wall_seconds=time.monotonic() - started, cpu_seconds=time.process_time() - cpu_started,
            max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        new(out / 'RESULT.json', result)
        signal.setitimer(signal.ITIMER_REAL, 0.)
        print(json.dumps(dict(status=result['status'], result_sha256=sha(out / 'RESULT.json'),
                              counters=work.c), sort_keys=True))
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        new(out / 'FAILED_PRESERVED.json', dict(status='FAILED_NO_RETRY_SYNTHETIC_ONLY',
            error=str(exc), traceback=traceback.format_exc(), counters=work.c,
            unfinished_state=work.current_neural_state,
            unfinished_state_semantics='MID_KEY_NONTRANSACTIONAL_NOT_RESUMABLE_NOT_DEPLOYABLE',
            wall_seconds=time.monotonic() - started, cpu_seconds=time.process_time() - cpu_started,
            max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        raise


if __name__ == '__main__':
    main()
