"""SOURCE_ONLY A5 actual pre-B adapter；不派发、不写文件、不修改父signal/RLIMIT/时钟。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import time

ROOT_REL = 'families/critic_value/support_qualification_v5'
STOP = 1793114740.
METHODS = ['A3_RISK48', 'A5_RISK50', 'RISK_OFF', 'NEAREST48', 'NEAREST50', 'PHASE_ANY_FAIL50', 'ALWAYS_B']
OBJECTIVES = ['JF_QUALIFIED', 'JM_QUALIFIED', 'STRICT_JM']
PREFIXES = {'A3_RISK48': 'A5_MATCHED_RISK48', 'A5_RISK50': 'A5_PRIMARY', 'RISK_OFF': 'A5_RISK_OFF',
            'NEAREST48': 'A5_NEAREST48', 'NEAREST50': 'A5_NEAREST50',
            'PHASE_ANY_FAIL50': 'A5_PHASE_ANY_FAIL50', 'ALWAYS_B': 'A5_ALWAYS_B'}
SELECTORS = [PREFIXES[m] + '_' + o for m in METHODS for o in OBJECTIVES]
PRIMARY = 'A5_PRIMARY_JF_QUALIFIED'
_ATTEMPTED = set()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text())


def bounded(P, relative):
    p = (P / relative).resolve()
    assert p.is_relative_to(P), 'A5_PATH_ESCAPES_PACKAGE'
    return p


def predict_before_B(package, config, study):
    """仅三位置参数；失败paid prefix放异常文本，供generic owner原样存证。"""
    P = Path(package).resolve(); owner_pid = os.getpid(); began = time.time()
    counters = {'wrapper_entry': 1, 'proof_entry': 0, 'proof_completed': 0,
        'private_API_module_loader_entry': 0, 'private_API_module_loader_completed': 0,
        'A5_predict_all_entry': 0, 'A5_predict_all_completed': 0,
        'normalized_selector_completed': 0, 'wrapper_completed': 0}
    paid = {}; phase = 'ORIGINAL_OWNER_AND_DEADLINE'; clock = None
    try:
        group = config['group']
        ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
        key = (owner_pid, ticks, group)
        assert key not in _ATTEMPTED, 'A5_ONE_PRE_B_ATTEMPT_NO_LOCAL_CLOCK_RESET'
        _ATTEMPTED.add(key)
        assert config['comparative_validation']['status'] == 'APPROVED_BY_MAIN_AGENT'
        assert config['comparative_validation']['no_training'] is True
        assert config['comparative_validation']['no_outcome_reselection'] is True
        config_path = bounded(P, 'experiments/' + group + '.json')
        assert load(config_path) == config
        supervisor_path = bounded(P, 'owned/' + group + '_SUPERVISOR.json')
        supervisor = load(supervisor_path)
        assert supervisor['state'] == 'RUNNING'
        assert supervisor['worker']['pid'] == owner_pid and supervisor['worker']['start_ticks'] == ticks
        assert supervisor['config_sha256'] == sha(config_path)
        assert supervisor['activation'] == 'deep_learning_method_exploration_v8_20261027T032540Z'
        cutoff = supervisor['cutoff_unix']
        assert isinstance(cutoff, (int, float)) and not isinstance(cutoff, bool) and began < min(cutoff, STOP)
        clock = {'entered_unix': began, 'local_stop_unix': min(began + 10., cutoff, STOP),
            'original_job_cutoff_unix': cutoff, 'original_global_stop_unix': STOP,
            'supervisor_sha256': sha(supervisor_path), 'original_worker_PID': owner_pid,
            'original_worker_start_ticks': ticks, 'config_sha256': sha(config_path),
            'signal_RLIMIT_or_parent_clock_changed': False}
        def check():
            assert os.getpid() == owner_pid, 'A5_FORK_CHILD_NOT_OWNER'
            if time.time() >= clock['local_stop_unix']:
                raise TimeoutError('A5_FIXED_READONLY_LOCAL_JOB_OR_GLOBAL_STOP')
        check()
        phase = 'FROZEN_SOURCE_AND_FULL_BUNDLE'
        manifest_path = bounded(P, ROOT_REL + '/LIVE_ADAPTER_MANIFEST_V1.json')
        manifest = load(manifest_path)
        assert sha(__file__) == manifest['adapter_sha256']
        assert manifest['selectors'] == SELECTORS and manifest['primary'] == PRIMARY
        assert config['frozen_artifacts'].get(str(manifest_path.relative_to(P))) == sha(manifest_path)
        for relative, expected in manifest['required_config_frozen_artifacts'].items():
            assert config['frozen_artifacts'].get(relative) == sha(bounded(P, relative)) == expected
        def document(item):
            path = bounded(P, item['path']); assert sha(path) == item['sha256']; return load(path)
        identity = document(manifest['bundle_identity'])
        bundle = document(manifest['bundle']); proof_bundle = document(manifest['proof_bundle'])
        assert identity['bundle'] == manifest['bundle']
        assert identity['bundle']['object_sha256'] == manifest['bundle_object_sha256']
        assert bundle['schema'] == 'v8.a5.operational_qualification_bundle.v1' and bundle['development_only'] is False
        assert bundle['menu'] == proof_bundle['menu']
        assert bundle['input_source_profiles'] == proof_bundle['input_source_profiles']
        assert bundle['input_source_profile_paths'] == proof_bundle['input_source_profile_paths']
        assert len(bundle['risk50_model']['history48']) == 48 and len(bundle['risk50_model']['history50']) == 50
        assert identity['fit_completed_unix'] < began and identity['freeze_record_created_unix'] < began
        check()
        proof_path = bounded(P, manifest['proof_adapter']['path'])
        assert sha(proof_path) == manifest['proof_adapter']['sha256']
        spec = importlib.util.spec_from_file_location('_a5_frozen_actual_source_gate_v1', proof_path)
        proof_adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(proof_adapter)
        assert Path(proof_adapter.__file__).resolve() == proof_path
        assert proof_adapter.digest(bundle) == manifest['bundle_object_sha256']
        proof_adapter._menu_matches(P, config, bundle['menu'])
        phase = 'ACTUAL_SEVEN_ROLE_PROOF'
        counters['proof_entry'] += 1
        raw, proof, proof_audit = proof_adapter._actual_live_proof(P, config, study, bundle)
        counters['proof_completed'] += 1
        check()
        phase = 'PRIVATE_API_MODULES'
        counters['private_API_module_loader_entry'] += 1
        modules = proof_adapter._private_modules(P, manifest['api_files'], 'A5_OPERATIONAL_RISK_V1')
        counters['private_API_module_loader_completed'] += 1
        api = modules['predict_api_v1']
        assert api.METHODS == METHODS and api.OBJECTIVES == OBJECTIVES
        check()
        phase = 'ONE_SHARED_A5_PREDICT_ALL'
        counters['A5_predict_all_entry'] += 1
        answer = api.predict_all(bundle, raw, source_proof=proof, ledger=paid)
        counters['A5_predict_all_completed'] += 1
        check()
        assert paid == manifest['expected_API_accounting'], ('A5_EXACT_LIVE_COUNTS', paid)
        assert list(answer['decisions']) == [m + '/' + o for m in METHODS for o in OBJECTIVES]
        phase = 'NORMALIZE_21_SHARED_SELECTORS'
        decisions = {}
        for method in METHODS:
            for objective in OBJECTIVES:
                decision = answer['decisions'][method + '/' + objective]
                normalized = proof_adapter._with_fallback(decision, bundle['menu'])
                assert normalized['choice_tag'] == decision['execution_choice_tag']
                assert normalized['fallback_B_after_predictive_abstain'] == decision['fallback_B_after_predictive_abstain']
                decisions[PREFIXES[method] + '_' + objective] = normalized
                counters['normalized_selector_completed'] += 1
        assert list(decisions) == SELECTORS and len(decisions) == 21
        assert not study.metrics and study.child is None and study.fork_done is True
        check(); counters['wrapper_completed'] += 1
        return {'schema': 'v8.a5.frozen_actual_pre_B_decisions.v1', 'primary': PRIMARY, 'decisions': decisions,
            'raw_shared_prediction': answer, 'actual_source_proof': proof, 'proof_audit': proof_audit,
            'all_choices_before_any_B_result': True, 'wrapper_accounting': counters, 'API_accounting': paid,
            'API_calls': {'A5_predict_all': 1}, 'new_fit_or_physics': 0, 'fixed_readonly_clock': clock,
            'wholecase_LOCO_gain_claim': False, 'FULL_seen_cell_repair_is_not_generalization': True,
            'same_recipe_sharing_not_independent_rollouts_or_savings': True,
            'bundle_sha256': manifest['bundle']['sha256'], 'adapter_sha256': manifest['adapter_sha256'],
            'adapter_manifest_sha256': sha(manifest_path), 'logical_deepcopy_calls': {'raw_proof': 1, 'menu_candidates': 10, 'selected_actions': 21},
            'numeric_model_restores_or_array_constructions': 0, 'two_bundle_JSON_loads_not_model_forward': 2}
    except BaseException as error:
        # generic V3只保存str(error)：逐层entry/completed和未知区间必须进入文本。
        text = {'schema': 'v8.a5.failed_readonly_paid_prefix.v1', 'error_type': type(error).__name__,
            'error': str(error), 'phase': phase, 'owner_PID': owner_pid, 'failure_PID': os.getpid(),
            'entered_unix': began, 'failed_unix': time.time(), 'fixed_readonly_clock': clock,
            'wrapper_accounting': counters, 'API_paid_prefix': paid,
            'incomplete_suboperation_work': 'UNKNOWN_BOUNDED_NOT_ZERO_UNLESS_ENTRY_WAS_NOT_REACHED',
            'partial_deepcopies_or_JSON_load_work': 'UNKNOWN_IF_WRAPPER_NOT_COMPLETED',
            'automatic_retry': False, 'new_fit_or_physics': 0}
        raise RuntimeError(json.dumps(text, ensure_ascii=False, sort_keys=True, allow_nan=False)) from error
