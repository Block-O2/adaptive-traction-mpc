"""已关闭原始证据schema核验；无adapter/model/physics调用，无成本比较。"""
from pathlib import Path
import ast
import gzip
import hashlib
import json
import os
import resource
import time

P = Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
OUT = P / 'families/il_dagger_sac/discrete_sac_v1/analysis'
GROUPS = ['V8ENGH01', 'V8CTX01', 'V8CTX02']
HARD = ['force', 'moment', 'torque', 'human_speed', 'human_acceleration', 'robot_speed', 'session_clearance', 'true_clearance', 'measured_sleeve_clearance', 'no_shank_table_contact', 'no_human_rom_violation']
FILES = {}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(2 ** 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    raw = path.read_bytes()
    FILES[str(path.relative_to(P))] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def canonical(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def common(audit):
    return audit.get('unchanged_evaluator', {}).get('physical_task_result', {}).get('scorer_v2_common_conditions', {})


def main():
    begin = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    adapter = P / 'source/v8_onpolicy_receipt_adapter_v1.py'
    adapter_before = sha(adapter)
    ast.parse(adapter.read_bytes())  # 仅解析，不import或调用adapter。
    log = P / 'runtime/ATTEMPTS.jsonl'
    events = {}
    for raw in log.read_bytes().splitlines():
        ev = json.loads(raw)
        if any(ev.get('id', '').startswith(g + '_') for g in GROUPS) and ev['event'] in ['START', 'END']:
            events.setdefault(ev['id'], {}).setdefault(ev['event'], []).append({'event': ev, 'raw_line_without_newline_sha256': hashlib.sha256(raw).hexdigest(), 'canonical_record_sha256': canonical(ev)})
    schemas = []
    closures = []
    for group in GROUPS:
        closed = read(P / 'jobs' / group / 'WORKER_DONE.json')
        assert closed['status'] == 'PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'
        closures.append({'group': group, 'closed_status': closed['status']})
        config_path = P / 'experiments' / (group + '.json')
        config = read(config_path)
        source_path = P / 'jobs' / group / 'SOURCE_MANIFEST.json'
        source = read(source_path)
        for result_path in sorted((P / 'attempts').glob(group + '_*_RESULT.json')):
            row = read(result_path)
            ident = row['id']
            assert row['complete'] is True
            measured_path = P / row['metrics_path']
            m = read(measured_path)
            lp = Path(m['execution_lineage_path'])
            ln = read(lp)
            d = read(P / 'runtime/output' / (ident + '_DATA.json'))
            metric = d['metric']
            cc, dc = common(m['native_physical_audit']), common(metric['physical_audit'])
            ev = events[ident]
            assert len(ev['START']) == len(ev['END']) == 1
            start, end = ev['START'][0]['event'], ev['END'][0]['event']
            checks = {'one_original_START_END': True, 'event_order': start['unix'] <= end['unix'],
                      'START_config_SHA_exact': start['config_sha256'] == sha(config_path),
                      'START_source_manifest_SHA_exact': start['job_source_sha256'] == sha(source_path),
                      'group_exact': start['group'] == group, 'MEASURED_id_exact': m['id'] == ident,
                      'lineage_id_exact': ln['id'] == ident, 'DATA_metric_name_exact': metric['name'] == ident,
                      'lineage_absolute_inside_package': lp.is_absolute() and lp.resolve().is_relative_to(P),
                      'lineage_status_PASS': ln['status'] == 'PASS', 'ownership_error_count_zero': ln['ownership_error_count'] == 0,
                      'scientific_causal_axis_PASS': m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'] == 'PASS',
                      'MEASURED_DATA_common_identical': cc == dc,
                      'all_required_HARD_present_boolean': all(isinstance(cc.get(k), bool) for k in HARD),
                      'END_zero_join_parent_unchanged': end['returncode'] == 0 and end['joined'] is True and end['parent_hash_equal'] is True,
                      'saved_new_steps_equal_MEASURED': row['actual_new_native_steps'] == m['actual_new_native_steps']}
            assert all(checks.values()), (ident, checks)
            pred_path = P / 'predictions' / (ident + '.json')
            prediction_schema = None
            if pred_path.exists():
                pred = read(pred_path)
                prediction_schema = {'keys': list(pred), 'created_before_START': pred['created_unix'] <= start['unix'],
                                     'parent_hash_matches_START_snapshot_hash': pred['parent_hash'] == start['snapshot_hash'],
                                     'is_real_onpolicy_proposal_receipt': 'proposal_identity_sha256' in pred and 'proposal_path' in pred}
                assert prediction_schema['created_before_START']
            schemas.append({'id': ident, 'checks': checks, 'result_keys': list(row), 'MEASURED_keys': list(m),
                            'lineage_keys': list(ln), 'lineage_join_kind': ln['join_kind'],
                            'START_keys': sorted(start), 'END_keys': sorted(end),
                            'event_writer_pid_and_start_ticks_same': (start['pid'], start['start_ticks']) == (end['pid'], end['start_ticks']),
                            'event_record_hashes': {'START': {k: v for k, v in ev['START'][0].items() if k != 'event'}, 'END': {k: v for k, v in ev['END'][0].items() if k != 'event'}},
                            'hard_three_state_from_saved_schema': True if any(cc.get(k) is False for k in HARD) else False if all(cc.get(k) is True for k in HARD) else None,
                            'prediction_schema': prediction_schema,
                            'has_onpolicy_sampling_config': 'onpolicy_sampling' in config,
                            'new_steps': row['actual_new_native_steps'], 'lineage_archived_native_steps': ln['native_steps']})
    # 仅抽取原函数AST，在gzip/json命名空间执行读数组解析器，避免bootstrap/numpy/module副作用。
    parser_source = P / 'runtime/code/stream_runtime_evidence.py'
    tree = ast.parse(parser_source.read_bytes())
    function = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'array_items')
    namespace = {'gzip': gzip, 'json': json}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<isolated read-only array_items AST>', 'exec'), namespace)
    streams = []
    for ident in ['V8ENGH01_LATE_H150', 'V8CTX01_EARLY_PHASE', 'V8CTX02_LATE_PHASE']:
        raw_path = P / 'runtime/source/results' / ident / 'runtime_artifacts.json.gz'
        h = hashlib.sha256()
        total = positive = steps = null_request = 0
        fields = set()
        for r in namespace['array_items'](raw_path, 'command_receipts'):
            fields.update(r)
            h.update(json.dumps(r, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode() + b'\n')
            total += 1
            if r.get('request_id') is None or r.get('plan_request_id') is None:
                null_request += 1
            if r.get('applied') is True and isinstance(r.get('native_steps'), int) and r['native_steps'] > 0:
                positive += 1
                steps += r['native_steps']
        assert total > 0 and positive > 0
        streams.append({'id': ident, 'raw_gzip_sha256': sha(raw_path), 'canonical_receipt_stream_sha256': h.hexdigest(),
                        'receipt_count': total, 'positive_step_receipts': positive, 'positive_native_steps_including_prefix': steps,
                        'request_or_plan_request_null_receipts': null_request, 'receipt_field_names': sorted(fields),
                        'scope': '全归档流，包含继承commissioning/prefix；不得声称所有步归新proposal独占'})
    assert sha(adapter) == adapter_before, 'adapter在审查期间变化，须重审具体版本'
    out = {'status': 'CLOSED_SCHEMA_PASS_ONPOLICY_END_TO_END_NOT_TESTED', 'adapter_sha256': adapter_before,
           'authorized_closed_groups': GROUPS, 'closures': closures, 'closed_complete_rows_checked': len(schemas),
           'schemas': schemas, 'full_receipt_stream_samples': streams, 'files_sha256': FILES,
           'stream_parser_source_sha256': sha(parser_source),
           'review_attempts': [{'attempt': 1, 'status': 'DIAGNOSTIC_ASSERT_REJECTED_ACTUAL_SCHEMA', 'reason': '最初假设所有prediction.parent_hash均等于START.snapshot_hash；实际两个首B不同；修正为保留差异，不改raw或强行assert相等'}],
           'limitations': ['这些关闭配置不含onpolicy_sampling，现有预测不是genuine onpolicy proposal；不可伪装适配器实际端到端测试',
                           '没有新onpolicy proposal/source-receipt产生，adapter函数未调用',
                           '原lineage用unique positive-step interval重建并检查torque/native steps，非直接command_id/request_id唯一连接',
                           '未分析JF/JM收益或调整任何模型；只核schema/身份/资格证据字段'],
           'resources': {'wall_s': time.monotonic() - begin, 'cpu_user_s': resource.getrusage(resource.RUSAGE_SELF).ru_utime - usage.ru_utime,
                         'cpu_system_s': resource.getrusage(resource.RUSAGE_SELF).ru_stime - usage.ru_stime,
                         'peak_RSS_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'pid': os.getpid(),
                         'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])},
           'adapter_calls': 0, 'model_forward': 0, 'gradient_or_parameter_updates': 0, 'new_physics': 0}
    output = OUT / 'B_ONPOLICY_RECEIPT_ADAPTER_SCHEMA_EVIDENCE_V1.json'
    assert not output.exists()
    output.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': out['status'], 'complete_rows': len(schemas), 'streams': [{'id': r['id'], 'count': r['receipt_count'], 'positive_steps': r['positive_native_steps_including_prefix'], 'null_request_ids': r['request_or_plan_request_null_receipts']} for r in streams], 'wall_s': out['resources']['wall_s']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
