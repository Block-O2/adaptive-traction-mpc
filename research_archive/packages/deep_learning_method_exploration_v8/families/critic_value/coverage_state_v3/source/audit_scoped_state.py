"""获批<=90s原payload/源码审计；纯stdlib，0fit/forward/physics。"""
from pathlib import Path
import ast
import hashlib
import json
import math
import os
import resource
import time

P = Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
OUT = P / 'families/critic_value/coverage_state_v3'
GROUPS = ['EARLYN01', 'EARLYL01', 'EARLYH01', 'CFACTORH01', 'CFACTORL01', 'HOLDSS03', 'V8CTX01', 'V8CTX02', 'V8CTX03', 'V8CTX04']
MANIFEST = {}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    path = path.resolve();raw = path.read_bytes()
    MANIFEST[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def source(path):
    raw = path.read_bytes();MANIFEST[str(path.resolve())] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    ast.parse(raw)
    return raw.decode()


def write(relative, value):
    path = OUT / relative;path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write('\n')


def main():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    start = time.monotonic();before = resource.getrusage(resource.RUSAGE_SELF)
    activation = read(P / 'ACTIVATION.json');assert time.time() < activation['hard_stop_unix']
    # 只读取已批准的源码及十个OUT0原payload；不读TASK结果、trace或native truth。
    base = 'runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/'
    relatives = ['source/v7_causal_context.py', 'source/v6_features.py', 'runtime/code/study_common.py',
        'runtime/code/matched_harness.py', base + 'task_observation.py', base + 'controller_interface.py',
        base + 'full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py',
        base + 'full3d_adaptive_integration_v1/clearance_feedback.py']
    capture_text = source(P / relatives[0])
    capture_tree = ast.parse(capture_text)
    names = ast.literal_eval(next(n.value for n in capture_tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FEATURE_NAMES' for t in n.targets)))
    assert len(names) == 77
    for relative in relatives[1:]:
        source(P / relative)
    bkeys = sorted({n.slice.value for n in ast.walk(capture_tree) if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == 'b' and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)})
    assert not any(k in bkeys for k in ['plant', 'truth', 'physical_human', 'physical_geometry'])
    beta = [n for n in names if n.startswith('estimated_beta_')]
    geometry = [n for n in names if n.startswith('estimated_geometry_')]
    residual = [n for n in names if n.startswith('residual_weight_')]
    comm = beta + geometry + residual
    kin = list(names[:8])
    wrench = list(names[14:20])
    guard = ['session_guard_calls', 'session_guard_active', 'session_guard_unsatisfied', 'session_guard_peak_correction']
    subsets = {'COMMISSION25': comm, 'KIN33': comm + kin, 'WRENCH39': comm + kin + wrench, 'SOFTWARE_GUARD43': comm + kin + wrench + guard}
    records, checks = [], []
    for group in GROUPS:
        package = P if group.startswith('V8CTX') else P.parent / 'autonomous_learning_smoothness_v7'
        config = read(package / 'experiments' / (group + '.json'))
        job_source = read(package / 'jobs' / group / 'SOURCE_MANIFEST.json')
        source(package / 'source' / config['worker'])
        # 与实际job冻结源码逐hash核对，不能仅凭当前文件名称推认旧运行版本。
        for relative in relatives:
            actual_path = package / relative
            expected = job_source['files'].get(relative)
            assert expected is not None and hashlib.sha256(actual_path.read_bytes()).hexdigest() == expected, (group, relative)
            source(actual_path)
        path = package / 'history' / (group + '_PREFORK_CAUSAL_CONTEXT.json')
        payload = read(path);values = dict(zip(payload['feature_names'], payload['features']))
        body = {k: v for k, v in payload.items() if k != 'causal_payload_sha256'}
        check = {'checksum': digest(body) == payload['causal_payload_sha256'], 'schema77': payload['feature_names'] == list(names),
            'OUT0': payload['phase'] == 'OUTBOUND' and payload['task_s'] == 0. and values['decision_slot'] == 0.,
            'before_selection': payload['capture_position'] == 'parent request boundary BEFORE fork loop/candidate selection/control mutation',
            'capture_read_only': payload['model_prediction_or_observe_calls'] == 0 and payload['hidden_or_future_inputs_used'] is False,
            'legacy_invalid_preserved': payload['model_vector_valid'] is False,
            'only_expected_OUT1_registration_error': payload['causality_errors'] == ['capture_is_not_registered_OUT1_boundary'],
            'QA_present': payload['quality_missing'] == {} and all(isinstance(v, (int,float)) and math.isfinite(v) for v in payload['quality'].values()),
            'observation_interface_request_current': payload['quality']['observation_age'] == payload['quality']['interface_age'] == values['request_source_age'] == 0.}
        assert all(check.values()), (group, check)
        for subset in subsets.values():
            assert all(isinstance(values[n], (int,float)) and math.isfinite(values[n]) for n in subset)
        records.append({'schema': 'v8.out0.scoped_state_record.v1', 'group_evaluation_only': group,
            'source_payload_path': str(path), 'source_payload_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_payload_body_checksum': payload['causal_payload_sha256'], 'physical_s_evaluation_only': payload['physical_s'],
            'task_s': 0., 'phase': 'OUTBOUND', 'legacy77_valid': False, 'QA': payload['quality'],
            'checks': check, 'subsets': {name: {'feature_names': fields, 'features': [values[n] for n in fields]} for name, fields in subsets.items()},
            'unavailable_fields': [n for n in names if values[n] is None],
            'finite_audit_only_fields': {n: values[n] for n in names if values[n] is not None and n not in subsets['SOFTWARE_GUARD43']}})
        checks.append({'group': group, **check, 'worker_source': config['worker'], 'original_model_vector_valid': payload['model_vector_valid']})
    stats = {}
    for n in subsets['SOFTWARE_GUARD43']:
        vals = [r['subsets']['SOFTWARE_GUARD43']['features'][subsets['SOFTWARE_GUARD43'].index(n)] for r in records]
        stats[n] = {'finite_contexts': len(vals), 'unique_exact': len(set(vals)), 'minimum': min(vals), 'maximum': max(vals),
            'range': max(vals) - min(vals), 'constant_exact': max(vals) == min(vals),
            'near_zero_machine_scale': max(abs(v) for v in vals) < 1e-12}
    # 只用预先写明的物理单位尺度作描述距离，不拟合normalizer或模型。
    unit_scales = [.1] * 5 + [1.] * 2 + [.1] * 4 + [.005] * 4 + [.05] * 10 + [.05] * 8 + [10.] * 3 + [1.] * 3 + [100., 10., 1., 1.]
    pairs = []
    for i, a in enumerate(records):
        for b in records[i+1:]:
            entry = {'a': a['group_evaluation_only'], 'b': b['group_evaluation_only'], 'distance_semantics': 'RMS / fixed explicit unit scales; no fitted normalizer/no predictor'}
            for name, fields in subsets.items():
                av, bv = a['subsets'][name]['features'], b['subsets'][name]['features']
                entry[name] = (sum(((x-y)/s)**2 for x,y,s in zip(av,bv,unit_scales[:len(fields)]))/len(fields))**.5
            pairs.append(entry)
    write('data/SCOPED_OUT0_STATES_V1.json', {'schema':'v8.out0.scoped_state_dataset.v1','records':records,'subsets':subsets,
        'includes_current_or_future_TASK_result':False,'includes_native_truth':False,'training_or_forward_done':False,
        'legacy77_remains_invalid':True,'software_guard_is_not_physical_risk':True})
    write('analysis/FIELD_VARIATION_AND_DISTANCE_V1.json', {'field_statistics':stats,'pairs':pairs,'unit_scales':dict(zip(subsets['SOFTWARE_GUARD43'],unit_scales)),
        'labels_read':False,'linear_separability_tested':False,'model_fit_or_forward':0})
    after = resource.getrusage(resource.RUSAGE_SELF)
    write('analysis/AVAILABILITY_AUDIT_V1.json', {'checks':checks,'capture_b_subscript_keys':bkeys,
        'missing_TASK_history_not_zero_filled':True,'emitted_reference_missing_not_relabelled':True,
        'governor_scheduler_not_in_payload':True,'fit':0,'forward':0,'physics':0,
        'wall_s':time.monotonic()-start,'cpu_user_s':after.ru_utime-before.ru_utime,'cpu_system_s':after.ru_stime-before.ru_stime,
        'RSS_peak_KiB':after.ru_maxrss,'single_cpu_affinity':sorted(os.sched_getaffinity(0))})
    write('data/SOURCE_MANIFEST_V1.json', {'files':MANIFEST,'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'dataset_sha256':hashlib.sha256((OUT/'data/SCOPED_OUT0_STATES_V1.json').read_bytes()).hexdigest(),
        'never_opened_TASK_result_or_trace':True,'fit_or_forward_or_physics':0})
    print(json.dumps({'contexts':len(records),'subsets':{k:len(v) for k,v in subsets.items()},
        'dataset_sha256':hashlib.sha256((OUT/'data/SCOPED_OUT0_STATES_V1.json').read_bytes()).hexdigest(),'wall_s':time.monotonic()-start}))


if __name__ == '__main__':
    main()
