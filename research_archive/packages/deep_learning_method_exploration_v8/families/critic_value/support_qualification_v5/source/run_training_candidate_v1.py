"""A5 候选CLI；SOURCE_ONLY，必须另有主审精确一次fit批准和新有限时钟。"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import resource
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT.parents[2]
STOP = 1793114740.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())


def usage():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return {'unix': time.time(), 'CPU_user_s': r.ru_utime, 'CPU_system_s': r.ru_stime,
        'peak_RSS_KiB': r.ru_maxrss, 'PID': os.getpid(),
        'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
        'python': sys.executable, 'binary_path': str(Path(sys.executable).resolve()),
        'binary_sha256': sha(Path(sys.executable).resolve()), 'actual_affinity': sorted(os.sched_getaffinity(0))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval', type=Path, required=True)
    parser.add_argument('--approval-sha', required=True)
    args = parser.parse_args()
    initial = usage(); approval_path = args.approval.resolve()
    assert approval_path.is_relative_to(ROOT) and sha(approval_path) == args.approval_sha
    approval = load(approval_path)
    assert approval['status'] == 'APPROVED_BY_MAIN_AGENT_FOR_A5_ONE_OFFLINE_RISK_FIT'
    assert approval['training_authorized'] is True and approval['new_physics_or_deployment_authorized'] is False
    contract_path = ROOT / 'contracts/FIT_CONTRACT_PROPOSED_V1.json'
    manifest_path = ROOT / 'SOURCE_CANDIDATE_MANIFEST_V1.json'
    data_path = ROOT / 'data/OPERATIONAL_RISK50_DATASET_V1.json'
    assert approval['contract_sha256'] == sha(contract_path)
    assert approval['source_manifest_sha256'] == sha(manifest_path)
    assert approval['data_sha256'] == sha(data_path)
    contract = load(contract_path); manifest = load(manifest_path)
    assert contract['dataset_sha256'] == sha(data_path)
    assert approval['approved_unix'] <= initial['unix'] < approval['expires_unix'] <= min(initial['unix'] + 60., STOP)
    assert approval['expected_binary_sha256'] == initial['binary_sha256'] == contract['expected_python_binary_sha256']
    activation = load(PACKAGE / 'ACTIVATION.json')
    assert activation['activation_id'] == contract['activation_id'] and activation['hard_stop_unix'] == STOP
    assert sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    assert len(initial['actual_affinity']) == 1
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        assert os.environ.get(key) == '1'
    for rel, expected in manifest['source_files_sha256'].items():
        assert sha(ROOT / rel) == expected
    data = load(data_path)
    for item in data['source_files'].values():
        assert sha(PACKAGE / item['path']) == item['sha256']
    out = ROOT / contract['output_directory']
    assert out.parent == ROOT and not out.exists(), 'A5_NO_RETRY_OR_CLOCK_RESET'
    out.mkdir()
    save(out / 'START.json', {'process': initial, 'approval_sha256': args.approval_sha,
        'expires_unix': approval['expires_unix'], 'new_physics': 0})
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    def timeout(signum, frame):
        raise TimeoutError('A5_FIXED_LOCAL_OR_GLOBAL_PAID_STOP')
    signal.signal(signal.SIGTERM, timeout); signal.signal(signal.SIGALRM, timeout); signal.signal(signal.SIGXCPU, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, approval['expires_unix'] - time.time()))
    fit_ledger = []; API_ledger = {}; records = []; full_records = []; saved_full_bundle = None; phase = 'IMPORTS'
    try:
        import numpy as np
        import scipy
        from causal_api import FEATURE_NAMES, to_context_full
        from fit_risk_candidate_v1 import normalization, fit_one, check
        from predict_api_v1 import predict_all, digest
        assert np.__version__ == contract['expected_numpy_version'] and scipy.__version__ == contract['expected_scipy_version']
        assert sha(Path(np.__file__)) == contract['expected_numpy_module_sha256']
        assert sha(Path(scipy.__file__)) == contract['expected_scipy_module_sha256']
        save(out / 'ACTUAL_DEPENDENCY_IDENTITY_BEFORE_FIT.json', {'process': usage(),
            'numpy': {'version': np.__version__, 'file': np.__file__, 'module_sha256': sha(Path(np.__file__))},
            'scipy': {'version': scipy.__version__, 'file': scipy.__file__, 'module_sha256': sha(Path(scipy.__file__))}})
        old_data = load(PACKAGE / data['source_files']['A3_data']['path'])
        old_bundle = load(PACKAGE / data['source_files']['A3_bundle']['path'])
        old_loco = load(PACKAGE / data['source_files']['A3_LOCO']['path'])
        by_id = {r['id_evaluation_only']: r for r in data['risk_rows']}
        # 原48行保留A3真实row顺序；新增2行只追加，heavy-held严格同训练顺序。
        ordered = [by_id[r['id']] for r in old_data['rows']] + sorted([r for r in data['risk_rows'] if r['origin_evaluation_only'] != 'OLD48_FULL_TASK'], key=lambda r: r['id_evaluation_only'])
        assert len(ordered) == 50 and len(by_id) == 50
        context_by_id = {r['id_evaluation_only']: to_context_full(r['context'], data['input_source_profiles']) for r in ordered}
        assert all(c['feature_names'] == FEATURE_NAMES for c in context_by_id.values())
        initial_extractions = len(ordered)
        cases = sorted({r['case_sha256_split_evaluation_only'] for r in ordered}); assert len(cases) == 10
        old_case_by_id = {r['id']: data['group_to_case_sha256_split_only'][r['group']] for r in old_data['rows']}
        cost_truth = {(old_case_by_id[r['id']], r['action_recipe_sha256']): r['labels_evaluation_only'] for r in old_data['rows']}
        risk_truth = {(r['case_sha256_split_evaluation_only'], r['recipe_sha256']): r for r in ordered}
        assert len(cost_truth) == 48 and len(risk_truth) == 50
        full_spec = old_bundle['cohorts']['MERGED']['models']['WRENCH39']
        inherited_cost_model_hash = digest(full_spec)
        def evaluate(answer, case, scope):
            result = {'scope_evaluation_only': scope, 'case_sha256_evaluation_only': case,
                'prediction': answer, 'selection_evaluation': {}}
            for method, decision in answer['decisions'].items():
                chosen = next(m for m in data['menu'] if m['tag'] == decision['execution_choice_tag'])
                known = risk_truth.get((case, chosen['recipe_sha256'])); cost = cost_truth.get((case, chosen['recipe_sha256']))
                result['selection_evaluation'][method] = {'choice_tag': chosen['tag'],
                    'B_fallback': decision['fallback_B_after_predictive_abstain'],
                    'operational_qualification': None if known is None else known['operational_qualified_target_only'],
                    'complete': None if known is None else known['complete_target_metadata_only'],
                    'full_cost_available': cost is not None, 'JF_N_s': None if cost is None else cost['JF_N_s'],
                    'JM_Nm_s': None if cost is None else cost['JM_Nm_s'],
                    'delta_JF_vs_B_N_s': None if cost is None else cost['delta_JF_vs_B_N_s'],
                    'delta_JM_vs_B_Nm_s': None if cost is None else cost['delta_JM_vs_B_Nm_s'],
                    'UNKNOWN_is_not_zero_cost': True}
            return result
        for held in cases + [None]:
            check(approval['expires_unix']); scope = 'ALL_DEVELOPMENT' if held is None else held
            phase = 'FIT_' + scope
            train = [r for r in ordered if r['case_sha256_split_evaluation_only'] != held]
            old_train = [r for r in train if r['origin_evaluation_only'] == 'OLD48_FULL_TASK']
            assert held is None or all(r['case_sha256_split_evaluation_only'] != held for r in train)
            norm = normalization(old_train, context_by_id, full_spec if held is None else None)
            risk50 = fit_one(train, data['menu'], norm, context_by_id, fit_ledger, approval['expires_unix'], scope)
            core = {'schema': 'v8.a5.operational_qualification_bundle.v1', 'menu': data['menu'],
                'feature_names39': FEATURE_NAMES, 'input_source_profiles': data['input_source_profiles'],
                'input_source_profile_paths': data['input_source_profile_paths'], 'risk50_model': risk50,
                'minimum_support_contexts': 2, 'distance_limit': 3., 'risk_threshold': .5,
                'primary': 'A5_RISK50/JF_QUALIFIED', 'data_sha256': sha(data_path),
                'contract_sha256': sha(contract_path), 'source_manifest_sha256': sha(manifest_path),
                'inherited_A3_full_cost_model_sha256': inherited_cost_model_hash,
                'all_training_and_evaluation_cases_exposed': True, 'new_physics': 0}
            evaluate_cases = cases if held is None else [held]
            if held is None:
                core.update(development_only=False, frozen_A3_cost_model=copy.deepcopy(full_spec))
                assert digest(core['frozen_A3_cost_model']) == inherited_cost_model_hash
                saved_full_bundle = core
            for case in evaluate_cases:
                phase = 'API_' + scope
                representative = next(r for r in ordered if r['case_sha256_split_evaluation_only'] == case and r['origin_evaluation_only'] == 'OLD48_FULL_TASK')
                if held is not None:
                    parent = representative['old_parent_split_evaluation_only']
                    archived = next(r for r in old_loco['rows'] if r['heldout_parent_group'] == parent and r['method'] == 'ABS_WRENCH39/RISK_ON' and r['objective'] == 'JF_QUALIFIED')
                    core.update(development_only=True, archived_context39_sha256=digest(context_by_id[representative['id_evaluation_only']]['features']),
                        archived_A3_ABS_WRENCH39_predictions=copy.deepcopy(archived['prediction']['predictions']))
                answer = predict_all(core, representative['context'], ledger=API_ledger)
                value = evaluate(answer, case, scope)
                if held is None:
                    full_records.append(value)
                else:
                    records.append(value)
                    # 同heavy case全部hold后，新两标签不可影响此负对照。
                    if representative['group_evaluation_only'] == 'EARLYH01':
                        err = max(abs(p['operational_failure_probability50'] - p['qualification_failure_score']) for p in answer['predictions'])
                        assert err <= 1e-9, ('HEAVY_HELD_MATCHED_RISK48_PARITY', err)
                        value['heavy_held_new_labels_absent_risk_parity_max_error'] = err
        assert len(fit_ledger) == 11 and sum(e['training_design_rows'] for e in fit_ledger) == 500
        assert all(e['completed'] for e in fit_ledger)
        expected = contract['expected_API_accounting']
        assert API_ledger == expected, ('A5_EXACT_API_COUNTS', API_ledger, expected)
        assert len(records) == len(full_records) == 10
        phase = 'DURABLE_SUCCESS_SAVE'
        save(out / 'A5_FROZEN_BUNDLE_V1.json', saved_full_bundle)
        save(out / 'DEVELOPMENT_LOCO_AND_FULL_V1.json', {'LOCO': records, 'FULL': full_records,
            'all_development_only': True, 'heavy_case_new_labels_held_together': True,
            'partial_full_cost_and_45_margins': 'MISSING_NOT_IMPUTED', 'FULL_seen_cell_repair_is_not_generalization': True})
        save(out / 'COMPLETE.json', {'status': 'COMPLETED_A5_OFFLINE_RISK_ONLY_NOT_DEPLOYMENT',
            'START': initial, 'END': usage(), 'fit_ledger': fit_ledger, 'API_ledger': API_ledger,
            'initial_data_context39_extractions': initial_extractions,
            'frozen_cost_model_sha256': inherited_cost_model_hash, 'cost_or_margin_fit': 0,
            'bundle_sha256': sha(out / 'A5_FROZEN_BUNDLE_V1.json'), 'new_physics': 0})
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        save(out / 'FAILED_PAID_PREFIX_V1.json', {'status': 'FAILED_NO_RETRY', 'START': initial, 'END': usage(),
            'phase': phase, 'error_type': type(exc).__name__, 'error': str(exc), 'traceback': traceback.format_exc(),
            'fit_ledger': fit_ledger, 'API_ledger': API_ledger, 'LOCO_completed': len(records), 'FULL_completed': len(full_records),
            'work_after_last_complete_suboperation': 'UNKNOWN_BOUNDED_NOT_ZERO', 'new_physics': 0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)


if __name__ == '__main__':
    main()
