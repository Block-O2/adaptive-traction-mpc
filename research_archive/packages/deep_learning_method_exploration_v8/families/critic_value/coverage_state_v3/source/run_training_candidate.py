"""A3 训练入口候选；必须有另行主审批准文件，当前禁止执行。"""
from pathlib import Path
import argparse
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
HARD_DEADLINE = 1793114740.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def evaluate_choice(row, prediction, test_rows, method, cohort, heldout, objective):
    chosen_hash = prediction['choice_recipe_sha256']
    abstained = chosen_hash is None
    if abstained:
        chosen_hash = next(r['action_recipe_sha256'] for r in test_rows if r['action_tag_evaluation_only'] == 'B')
    actual = next((r for r in test_rows if r['action_recipe_sha256'] == chosen_hash), None)
    label = actual['labels_evaluation_only'] if actual else None
    return {'cohort': cohort, 'heldout_parent_group': heldout, 'development_context': row['group'], 'method': method,
        'objective': objective, 'choice_recipe_sha256': chosen_hash, 'choice_id': actual['id'] if actual else None,
        'B_fallback_after_predictive_abstain': abstained, 'actual_available': actual is not None,
        'original_qualified': label['original_qualified'] if label else None,
        'JF_N_s': label['JF_N_s'] if label else None, 'JM_Nm_s': label['JM_Nm_s'] if label else None,
        'delta_JF_vs_B_N_s': label['delta_JF_vs_B_N_s'] if label else None,
        'delta_JM_vs_B_Nm_s': label['delta_JM_vs_B_Nm_s'] if label else None,
        'motion_failed_requirements': label.get('motion_failed_requirements') if label else None,
        'prediction': prediction, 'evaluation_only_actual_not_used_for_selection': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval', type=Path, required=True)
    args = parser.parse_args()
    contract_path = ROOT / 'contracts/FIT_CONTRACT_V1.json'
    manifest_path = ROOT / 'SOURCE_CANDIDATE_MANIFEST_V1.json'
    data_path = ROOT / 'data/STATE_JOINED_DATASET_V1.json'
    contract, approval = load(contract_path), load(args.approval)
    assert approval['status'] == 'APPROVED_BY_MAIN_AGENT'
    assert approval['contract_sha256'] == sha(contract_path)
    assert approval['source_manifest_sha256'] == sha(manifest_path)
    assert approval['dataset_sha256'] == sha(data_path) == contract['data_sha256']
    activation = load(PACKAGE / 'ACTIVATION.json')
    assert contract['activation_id'] == activation['activation_id']
    assert contract['global_deadline_unix'] == activation['hard_stop_unix'] == HARD_DEADLINE
    assert time.time() < HARD_DEADLINE
    for name, expected in contract['source_files_sha256'].items():
        assert sha(ROOT / name) == expected, 'A3_APPROVED_SOURCE_CHANGED:' + name
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
        assert os.environ.get(name) == '1', 'SINGLE_CPU_THREAD_ENV_REQUIRED:' + name
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    run = ROOT / contract['output_directory']
    assert not run.exists(), 'A3_NO_REINITIALIZATION_OR_CLOCK_RESET'
    run.mkdir(parents=True)
    started_unix, started_mono = time.time(), time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF)
    deadline = min(started_unix + contract['local_wall_cap_s'] - contract['final_audit_reserve_s'], HARD_DEADLINE)
    pid_ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
    write(run / 'OWNER_START.json', {'pid': os.getpid(), 'start_ticks': pid_ticks, 'start_unix': started_unix,
        'local_stop_unix': deadline, 'global_stop_unix': HARD_DEADLINE, 'contract_sha256': sha(contract_path),
        'data_sha256': sha(data_path), 'approval_sha256': sha(args.approval), 'cpu_affinity': sorted(os.sched_getaffinity(0)), 'new_physics': 0})
    def terminate(_sig, _frame):
        raise TimeoutError('A3_EXTERNAL_TIMEOUT_PRESERVED_ACCOUNTING')
    signal.signal(signal.SIGTERM, terminate)
    ledger, cv, prediction_diagnostics, cache = [], [], [], {}
    status, error = 'STARTED', None
    infer_calls = 0
    try:
        resource.setrlimit(resource.RLIMIT_AS, (contract['maximum_address_space_bytes'], contract['maximum_address_space_bytes']))
        # 重型数学依赖只在全部批准门之后导入；import 不会触发拟合。
        import numpy as np
        import scipy
        from fit_candidate import model, controls, check, OBJECTIVES
        from predict_api import predict, predict_control
        data = load(data_path)
        rows, menu = data['rows'], data['menu']
        assert data['development_only'] and data['sealed_interpolation_validation_read'] is False
        assert len(rows) == 48 and len(data['groups']) == 10
        parents = sorted({r['split_parent_group_evaluation_only'] for r in rows})
        cohorts = {'MERGED': rows}
        profiles = data['input_source_profiles']
        dimensions = {'25':25,'KIN33':33,'WRENCH39':39}
        def fitted(records):
            key = tuple(sorted(r['id'] for r in records))
            if key not in cache:
                check(deadline)
                models = {name: model(records, menu, d, profiles, ledger, deadline) for name,d in dimensions.items()}
                cache[key] = {'models': models, 'controls': {name: controls(records, menu, models[name], profiles, deadline) for name in dimensions},
                    'training_row_ids_evaluation_only': list(key)}
            return cache[key]
        def bundle(cohort, value):
            return {'schema': 'v8.a3.scoped_state_bundle.v1', 'menu': menu, 'cohorts': {cohort: value}, 'input_source_profiles': profiles,
                    'distance_limit': 3., 'minimum_support_contexts': 2, 'risk_threshold': .5}
        methods = ['ABS_25','DELTA_25','ABS_KIN33','DELTA_KIN33','ABS_WRENCH39','DELTA_WRENCH39']
        for heldout in parents:
            test = [r for r in rows if r['split_parent_group_evaluation_only'] == heldout]
            for cohort, candidates in cohorts.items():
                train = [r for r in candidates if r['split_parent_group_evaluation_only'] != heldout]
                assert not any(r['split_parent_group_evaluation_only'] == heldout for r in train)
                frozen = bundle(cohort, fitted(train))
                for method in methods:
                    for risk_mode in ['ON', 'OFF']:
                        for objective in OBJECTIVES:
                            check(deadline)
                            pred = predict(frozen, test[0]['context'], method, objective, risk_mode, cohort)
                            infer_calls += 1
                            cv.append(evaluate_choice(test[0], pred, test, method + '/RISK_' + risk_mode, cohort, heldout, objective))
                            if risk_mode == 'ON' and objective == 'JF_QUALIFIED':
                                for value in pred['predictions']:
                                    actual = next((r for r in test if r['action_recipe_sha256'] == value['recipe_sha256']), None)
                                    prediction_diagnostics.append({'cohort': cohort, 'method': method, 'heldout_parent': heldout,
                                        'tag': value['tag'], 'predicted': value,
                                        'actual_labels_evaluation_only': actual['labels_evaluation_only'] if actual else None})
                for representation in dimensions:
                    for control in ['CONSTANT_B','BEST_FIXED','IF_STUMP','NEAREST']:
                        for objective in OBJECTIVES:
                            check(deadline)
                            pred = predict_control(frozen,test[0]['context'],control,objective,cohort,representation=representation)
                            infer_calls += 1
                            cv.append(evaluate_choice(test[0],pred,test,control+'/'+representation,cohort,heldout,objective))

        full = {cohort: fitted(records) for cohort, records in cohorts.items()}
        frozen = {'schema': 'v8.a3.scoped_state_bundle.v1', 'menu': menu, 'cohorts': full, 'input_source_profiles': profiles, 'input_source_profile_paths': data['input_source_profile_paths'],
            'distance_limit': 3., 'minimum_support_contexts': 2, 'risk_threshold': .5,
            'primary': {'cohort': 'MERGED', 'method': 'ABS_WRENCH39', 'risk_mode': 'ON', 'objective': 'JF_QUALIFIED'},
            'primary_was_prespecified_not_chosen_on_CV': True, 'data_sha256': sha(data_path),
            'contract_sha256': sha(contract_path), 'source_manifest_sha256': sha(manifest_path), 'frozen_unix': time.time(),
            'all_contexts_development_exposed': True, 'sealed_validation_outcomes_read': False,
            'risk_calibrated_or_safety_certificate': False, 'new_physics': 0, 'physical_attempt_savings': 0}
        check(deadline)
        write(run / 'A3_FROZEN_BUNDLE_V1.json', frozen)
        write(run / 'DEVELOPMENT_LOCO_V1.json', {'rows': cv, 'prediction_diagnostics': prediction_diagnostics,
            'independent_test': False, 'fit_parent_groups': parents, 'missing_current_labels_not_imputed': True})
        status = 'COMPLETED_FROZEN_BEFORE_SEALED_VALIDATION'
        versions = {'numpy': np.__version__, 'scipy': scipy.__version__}
    except BaseException as failure:
        status, error = 'FAILED_PRESERVED_NO_AUTOMATIC_RETRY', {'type': type(failure).__name__, 'message': str(failure), 'traceback': traceback.format_exc()}
        versions = None
        raise
    finally:
        after = resource.getrusage(resource.RUSAGE_SELF)
        write(run / 'FIT_AND_RESOURCE_AUDIT_V1.json', {'status': status, 'error': error, 'pid': os.getpid(), 'start_ticks': pid_ticks,
            'start_unix': started_unix, 'end_unix': time.time(), 'wall_s': time.monotonic() - started_mono,
            'cpu_user_s': after.ru_utime - before.ru_utime, 'cpu_system_s': after.ru_stime - before.ru_stime, 'peak_RSS_KiB': after.ru_maxrss,
            'fit_ledger': ledger, 'prediction_api_calls': infer_calls, 'unique_fitted_training_sets': len(cache),
            'versions': versions, 'python': sys.executable, 'threads': {k: os.environ.get(k) for k in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']},
            'new_physics': 0, 'new_native_steps': 0, 'init_or_training_before_approval': False,
            'ridge_spread_not_calibrated_uncertainty': True, 'source_manifest_sha256': sha(manifest_path)})
    print(json.dumps({'status': status, 'bundle_sha256': sha(run / 'A3_FROZEN_BUNDLE_V1.json'), 'fit_ledger_entries': len(ledger)}))


if __name__ == '__main__':
    main()
