"""SOURCE_ONLY frozen E2/A3 pre-B inference adapter; no call authorization.

Main must separately approve exact sources/bundles and actual OUT0 invocation.
No data NPZ, future-B state, fit, physics, file writes or dispatch exists here.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = 'families/learning_assisted/common_out0_v2/'
MANIFEST = REL + 'FROZEN_LIVE_E2_SOURCE_MANIFEST_V2.json'
CONTRACT = REL + 'FROZEN_LIVE_E2_CONTRACT_V2.json'
STOP = 1793114740.0
ACTIVATION = 'deep_learning_method_exploration_v8_20261027T032540Z'
TAGS = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
EXPECTED = dict(prediction_API_calls=7, prediction_query_vectors=35,
                shared_B_inference_forward_API_calls=2,
                A3_predict_API_attempts=1, A3_predict_API_returns=1,
                completed_A3_risk_logits=5, completed_A3_cost_dot_outputs=30)


def need(test, reason):
    if not test:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def bounded(root, relative):
    path = (root / relative).resolve()
    need(path.is_relative_to(root), 'E2_LIVE_PATH_ESCAPES_PACKAGE')
    return path


class InferenceFailure(RuntimeError):
    """Caller must retain receipt; an incomplete API return grants no choice."""
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


class InferenceWork:
    def __init__(self, deadline):
        self.deadline = deadline
        self.c = {key: 0 for key in EXPECTED}
        self.kinds = {}

    def guard(self):
        need(time.monotonic() < self.deadline and time.time() < STOP,
             'E2_LIVE_ORIGINAL_OWNER_LOCAL_GLOBAL_DEADLINE')

    def prediction(self, kind, count):
        self.guard();self.c['prediction_API_calls'] += 1
        self.c['prediction_query_vectors'] += count
        need(self.c['prediction_API_calls'] <= 7 and
             self.c['prediction_query_vectors'] <= 35, 'E2_LIVE_EXACT_API_CAP')
        item = self.kinds.setdefault(kind, dict(API_calls=0, query_vectors=0))
        item['API_calls'] += 1;item['query_vectors'] += count


def exact_choice(values, risks=None):
    """B fallback; exact argmin(value,index), no tolerance-floor sorting."""
    need(len(values) == 5 and all(math.isfinite(float(v)) for v in values),
         'E2_LIVE_FINITE_FIVE_COSTS')
    if risks is None:
        allowed = list(range(5))
    else:
        need(len(risks) == 5 and all(math.isfinite(float(r)) and 0. <= r <= 1.
                                    for r in risks), 'E2_LIVE_FINITE_FIVE_RISKS')
        allowed = [0] + [index for index in range(1, 5) if risks[index] < .5]
    return min(allowed, key=lambda index: (float(values[index]), index))


def cost_predictions(bundle, context, models, work, np):
    """Pure frozen-cost helper: 3 ridge matrices + 4 shared-NN forwards."""
    x = np.asarray(context['features'], float)
    need(x.shape == (39,) and np.all(np.isfinite(x)), 'E2_LIVE_FINITE39')
    actions = np.arange(5, dtype=int);times = np.full(5, 19.03)
    initial = np.repeat(np.r_[x[25:39], 0., 0.][None, :], 5, axis=0)
    forecasts = {}
    for domain in ('D4', 'DFull'):
        entry = bundle['all_development_models'][domain + '/RIDGE_CONTEXT_ACTION']
        norm = entry['normalizer'];center = np.asarray(norm['center']);scale = np.asarray(norm['scale'])
        need(center.shape == scale.shape == (39,) and np.all(np.isfinite(center)) and
             np.all(np.isfinite(scale)) and np.all(scale > 0.), 'E2_LIVE_FROZEN_NORMALIZER')
        z = np.repeat(((x - center) / scale)[None, :], 5, axis=0)
        design = models.ridge_design(z, actions, 'RIDGE_CONTEXT_ACTION', np)
        need(entry['kind'] == 'RIDGE_CONTEXT_ACTION' and entry['paired'] is False,
             'E2_LIVE_REGISTERED_RIDGE_KIND')
        if domain == 'D4':
            need(entry['knot_times_s'] == [.5, 1., 1.5, 2., 2.5, 3., 3.5, 4.],
                 'E2_LIVE_EXACT_D4_KNOTS')
            low = models.predict_knots(design, entry['node_models'][-2], work, np)
            high = models.predict_knots(design, entry['node_models'][-1], work, np)
            fraction = (19.03 - 3.5) / (4. - 3.5)
            # Same order of operations as original interpolate_knots; this is
            # scalar algebra, not another backend interpolation API invocation.
            ridge = low * (1. - fraction) + high * fraction
        else:
            need(entry['knot_times_s'] == [.5, 1., 2., 4., 8., 12., 16., 19.03],
                 'E2_LIVE_EXACT_DFULL_KNOTS')
            ridge = models.predict_knots(design, entry['node_models'][-1], work, np)
        need(ridge.shape == (5, 16) and np.all(np.isfinite(ridge)), 'E2_LIVE_RIDGE16')
        forecasts[domain + '_RIDGE_CONTEXT_ACTION'] = dict(
            values16=ridge.tolist(), cost_semantics='ABSOLUTE_JF_JM_INDEPENDENT_HEADS',
            training_domain_s=[.5, 4.] if domain == 'D4' else [.5, 19.03],
            query_time_s=19.03, OOD_time=domain == 'D4', future_true_B_used=False)
        paired_entry = bundle['all_development_models'][domain + '/MLP_PAIRED']
        need(paired_entry['normalizer'] == norm, 'E2_LIVE_SAME_TRAIN_NORMALIZER')
        model = paired_entry['model']
        need(model['kind'] == 'MLP_PAIRED' and model['paired'] is True and
             model['action_only'] is False, 'E2_LIVE_FROZEN_PAIRED_KIND')
        paired = models.predict_mlp(z, actions, times, initial, model, work, np)
        need(paired.shape == (5, 16) and np.all(np.isfinite(paired)) and
             np.array_equal(paired[0], np.zeros(16)), 'E2_LIVE_PAIRED_B_ZERO')
        forecasts[domain + '_MLP_PAIRED'] = dict(
            values16=paired.tolist(), cost_semantics='DELTA14_INDEPENDENT_DELTA_JF_JM',
            training_domain_s=[.5, 4.] if domain == 'D4' else [.5, 19.03],
            query_time_s=19.03, OOD_time=domain == 'D4', future_true_B_used=False,
            absolute_wrench_integral='NOT_APPLICABLE_NO_ABSOLUTE_B_RECONSTRUCTION')
    return forecasts


def selector_decisions(forecasts, risks, menu):
    decisions = {}
    for label, forecast in forecasts.items():
        values = [row[14] for row in forecast['values16']]
        for suffix, gate in [('RAW', None), ('A3_RISK_LT_HALF', risks)]:
            index = exact_choice(values, gate);item = menu[index]
            decisions[label + '_' + suffix] = dict(choice_index=index,
                choice_tag=item['tag'], choice_recipe_sha256=item['recipe_sha256'],
                choice_action=copy.deepcopy(item['action']),
                objective='JF_COMPONENT_ONLY', cost_semantics=forecast['cost_semantics'],
                risk_gate='NONE' if gate is None else 'NON_B_STRICT_RISK_LT_0.5_B_FALLBACK',
                exact_argmin_value_then_recipe_index=True,
                original_qualification_granted=False)
    need(len(risks) == 5 and all(math.isfinite(float(r)) and 0. <= r <= 1. for r in risks),
         'E2_LIVE_FIXED_CONTROL_RISKS')
    index = 2 if risks[2] < .5 else 0;item = menu[index]
    decisions['FIXED_EARLY_H150_A3_RISK_ELSE_B'] = dict(choice_index=index,
        choice_tag=item['tag'], choice_recipe_sha256=item['recipe_sha256'],
        choice_action=copy.deepcopy(item['action']), risk_gate='EARLY_H150_STRICT_RISK_LT_0.5_ELSE_B',
        objective='FIXED_ACTION_NO_COST_MODEL', original_qualification_granted=False)
    need(len(decisions) == 9, 'E2_LIVE_EXACT_NINE_SELECTORS')
    return decisions


def predict_before_B(package, config, study, *, approval_path, approval_sha256,
                     owner_deadline_monotonic):
    """Pure result return; owner logs all calls and owns core5 physics separately."""
    started = time.monotonic();cpu_started = time.process_time()
    need(math.isfinite(owner_deadline_monotonic), 'E2_LIVE_EXISTING_OWNER_DEADLINE_REQUIRED')
    work = InferenceWork(min(owner_deadline_monotonic, started + 5.,
                             started + (STOP - time.time())))
    stage = 'AUTHORITY';proof_audit = None
    try:
        root = Path(package).resolve();need(root == ROOT, 'E2_LIVE_UNIQUE_PACKAGE')
        approval_file = Path(approval_path).resolve()
        need(approval_file.is_relative_to(root) and sha(approval_file) == approval_sha256,
             'E2_LIVE_EXACT_NEW_READONLY_APPROVAL')
        approval = load(approval_file)
        need(approval.get('schema') == 'v8.E2.frozen_live_inference_approval.v1' and
             approval.get('status') == 'ROOT_APPROVED_FROZEN_E2_ACTUAL_OUT0_ONCE_V1' and
             approval.get('source_manifest_sha256') == sha(root / MANIFEST) and
             approval.get('contract_sha256') == sha(root / CONTRACT) and
             approval.get('operation') == 'FOUR_COST_PREDICTIONS_ONE_A3_RISK_NINE_SELECTORS' and
             approval.get('group') == config['group'] and
             approval.get('physics_authorization') is False and
             approval.get('real_fit_authorization') is False,
             'E2_LIVE_SEPARATE_EXACT_MAIN_AUTHORITY_REQUIRED')
        contract = load(root / CONTRACT);manifest = load(root / MANIFEST)
        need(contract['expected_success_counters'] == EXPECTED and
             contract['max_local_inference_seconds'] == 5., 'E2_LIVE_FROZEN_CALL_CONTRACT')
        activation = load(root / 'ACTIVATION.json')
        need(activation['activation_id'] == ACTIVATION and activation['hard_stop_unix'] == STOP,
             'E2_LIVE_ORIGINAL_ACTIVATION_CLOCK')
        for relative, expected in manifest['files_sha256'].items():
            work.guard();need(sha(bounded(root, relative)) == expected, 'E2_LIVE_SOURCE_CHANGED:' + relative)
        need(study.child is None and study.fork_done is True and not study.metrics,
             'E2_LIVE_ALL_SELECTIONS_BEFORE_ANY_B')
        stage = 'PRIVATE_SOURCE_LOAD'
        item = contract['A3_adapter_source'];path = bounded(root, item['path'])
        name = '_v8_e2_frozen_live_proof_' + item['sha256'][:20]
        if name in sys.modules:
            adapter = sys.modules[name]
            need(Path(adapter.__file__).resolve() == path, 'E2_LIVE_PRIVATE_ADAPTER_PATH')
        else:
            spec = importlib.util.spec_from_file_location(name, path)
            adapter = importlib.util.module_from_spec(spec);sys.modules[name] = adapter
            try:spec.loader.exec_module(adapter)
            except BaseException:
                sys.modules.pop(name, None);raise
        bundles = {key: load(bounded(root, value['path'])) for key, value in contract['bundles'].items()}
        e2 = bundles['E2'];a3 = bundles['A3'];menu = e2['menu']
        need(menu == a3['menu'] and [item['tag'] for item in menu] == TAGS,
             'E2_LIVE_SAME_FULL_CORE5_MENU')
        need(e2['schema'] == 'v8.E.E2_frozen_conditional_trajectory_surrogates.v1' and
             e2['dataset_sha256'] == contract['training_dataset_identity'] and
             e2['public_time_scale_s'] == 20. and e2['CV_best_or_epoch_selection'] is False,
             'E2_LIVE_ACTUAL_ALL_DEVELOPMENT_BUNDLE_ONLY')
        need(a3['schema'] == 'v8.a3.scoped_state_bundle.v1', 'E2_LIVE_FROZEN_A3_BUNDLE')
        risk_spec = a3['cohorts']['MERGED']['models']['WRENCH39']
        need(len(risk_spec['cost_heads']['ABS']['weights']) == 3 and
             len(risk_spec['risk_weights']) == 200, 'E2_LIVE_DECLARED_A3_HEAD_WORK')
        adapter._menu_matches(root, config, menu)
        raw, proof, proof_audit = adapter._actual_live_proof(root, config, study, a3)
        a3apis = adapter._private_modules(root, contract['A3_api_files'], 'E2_existing_A3')
        e2apis = adapter._private_modules(root, contract['E2_api_files'], 'E2_cost_v1')
        context = a3apis['causal_api'].to_context_full(raw, a3['input_source_profiles'], proof)
        common = e2apis['common_out0_interface_v1']
        need(context['feature_names'] == e2['feature_names'] == common.FEATURE_NAMES,
             'E2_LIVE_ACTUAL_SELECTED39_NAMES')
        for item in menu:
            common.input_vector(context, item['recipe_sha256'], menu, query_time_s=19.03)
        stage = 'FROZEN_E2_COSTS';work.guard()
        import numpy as np
        need(Path(np.__file__).resolve().is_relative_to(
            Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/lib')), 'E2_LIVE_MAIN_NUMPY')
        forecasts = cost_predictions(e2, context, e2apis['e2_models_candidate_v1'], work, np)
        stage = 'FROZEN_A3_RISK';work.guard()
        work.c['A3_predict_API_attempts'] += 1
        risk_result = a3apis['predict_api'].predict(a3, raw, 'ABS_WRENCH39',
            'JF_QUALIFIED', 'OFF', 'MERGED', source_proof=proof)
        work.c['A3_predict_API_returns'] += 1
        predictions = risk_result['predictions']
        need([row['recipe_sha256'] for row in predictions] == [item['recipe_sha256'] for item in menu],
             'E2_LIVE_EXACT_A3_RISK_ORDER')
        risks = [row['qualification_failure_score'] for row in predictions]
        work.c['completed_A3_risk_logits'] = 5;work.c['completed_A3_cost_dot_outputs'] = 30
        decisions = selector_decisions(forecasts, risks, menu)
        work.guard();need(work.c == EXPECTED, 'E2_LIVE_EXACT_COMPLETE_COUNTERS')
        need(study.child is None and study.fork_done is True and not study.metrics,
             'E2_LIVE_B_MUST_NOT_COMPLETE_DURING_SELECTION')
        for relative, expected in manifest['files_sha256'].items():
            work.guard();need(sha(bounded(root, relative)) == expected, 'E2_LIVE_POST_SOURCE_CHANGED:' + relative)
        return dict(schema='v8.E2.frozen_live_nine_selectors.v1', status='COMPLETE_INFERENCE_ONLY',
            forecasts=forecasts, decisions=decisions, A3_risks=risks,
            A3_full_prediction_receipt=risk_result,
            A3_choice_and_support_not_used_as_gate=True,
            A3_risk_calibrated=False, counters=work.c, backend_kinds=work.kinds,
            actual_source_proof=proof, proof_audit=proof_audit,
            approval_sha256=approval_sha256, source_manifest_sha256=sha(root / MANIFEST),
            model_bundle_sha256=contract['bundles']['E2']['sha256'],
            risk_bundle_sha256=contract['bundles']['A3']['sha256'],
            all_predictions_before_any_B_result=True, future_B_trajectory_used=False,
            new_fit=0, physics=0, deployment_authorized=False,
            shared_core5_physics_is_not_savings_or_independent_replication=True,
            wall_seconds=time.monotonic() - started, CPU_seconds=time.process_time() - cpu_started,
            unchanged_owner_deadline_monotonic=owner_deadline_monotonic,
            effective_decreasing_deadline_monotonic=work.deadline)
    except BaseException as error:
        raise InferenceFailure(str(error), dict(status='FAILED_NO_CHOICE_NO_RETRY',
            stage=stage, counters=work.c.copy(), backend_kinds=work.kinds,
            A3_partial_dot_count='UNKNOWN_IF_ATTEMPT_WITHOUT_RETURN',
            proof_audit=proof_audit, fit=0, physics=0,
            wall_seconds=time.monotonic() - started,
            CPU_seconds=time.process_time() - cpu_started)) from error
