"""One bounded read-only audit of the closed fixed-recipe applicability probe."""
from pathlib import Path
import ast
import gzip
import hashlib
import itertools
import json
import os
import resource
import signal
import time
import numpy as np

P = Path(__file__).resolve().parents[1]
OUT = P / 'audit/PHASE_APPLICABILITY_CLOSED_REVIEW_V1.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def main():
    started = time.monotonic(); cpu = time.process_time()
    assert not OUT.exists()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('PHASE_AUDIT_CAP')))
    signal.alarm(120)
    assert time.time() < 1793114740.0
    a = load('experiments/V8COMPENG03.json'); b = load('experiments/V8PHAPP01.json')
    assert a['case_sha256'] == b['case_sha256'] and a['condition']['seed'] == b['condition']['seed']
    assert a['condition']['prefix'] == b['condition']['prefix']
    namespace = dict(np=np, itertools=itertools, gzip=gzip, json=json)
    copied = {}
    for relative, name in [('runtime/code/stream_runtime_evidence.py', 'array_items'),
                           ('runtime/control/base_campaign.py', 'compare_raw')]:
        tree = ast.parse((P / relative).read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        exec(compile(ast.Module(body=[function], type_ignores=[]), relative, 'exec'), namespace)
        copied[relative] = sha(P / relative)
    comparisons = {}
    for old, new in [('B', 'B'), ('EARLY_H150', 'H150')]:
        comparisons[new] = namespace['compare_raw'](P / ('runtime/source/results/V8COMPENG03_' + old),
                                                   P / ('runtime/source/results/V8PHAPP01_' + new))
        assert comparisons[new]['status'] == 'PASS', comparisons[new]
    phases = {}
    for tag in ['LATE_PHASE', 'EARLY_PHASE']:
        relative = 'history/V8PHAPP01_' + tag + '_APPLICABILITY_TIMING_APPLICABILITY.json'
        receipt = load(relative); assert receipt['rows']
        for row in receipt['rows']:
            assert row['truth_used'] is False and row['model_calls'] == 0
            assert row['original_threshold'] == 1e-10 and row['original_terminal_assertions_unchanged'] is True
            assert row['optional_timing_requested'] == (row['knee_at_public_goal'] and row['knee_reference_stationary'])
        original = load('attempts/V8COMPENG03_' + tag + '_RESULT.json')
        repaired = load('attempts/V8PHAPP01_' + tag + '_APPLICABILITY_RESULT.json')
        assert original['complete'] is False and repaired['complete'] is True and repaired['qualified'] is False
        old_action = original['action']; new_action = repaired['action'].copy()
        assert new_action.pop('terminal_timing_applicability') is True and new_action == old_action
        phases[tag] = dict(original_error=original['error'], original_complete=False,
            new_complete=True, new_qualified=False, motion_failure=repaired['motion_vs_B']['failed_requirements'],
            JF=repaired['JF'], JM=repaired['JM'], timing_receipt=dict(path=relative, sha256=sha(P / relative)),
            checks=receipt['rows'], suppressed=sum(not row['optional_timing_requested'] for row in receipt['rows']))
    ending = load('owned/V8PHAPP01_SUPERVISOR_END.json')
    assert ending['worker_exit_code'] == 0 and ending['survivors'] == []
    refs = ['experiments/V8COMPENG03.json', 'experiments/V8PHAPP01.json',
            'owned/V8PHAPP01_SUPERVISOR_END.json', 'audit/V8PHAPP01_PARENT_RAW_GATE.json',
            'freeze/PHASE_APPLICABILITY_PROBE_MAIN_APPROVAL_V1.json',
            'source/v8_worker_v2.py', str(Path(__file__).relative_to(P))]
    result = dict(schema='v8.fixed_phase_applicability_closed_audit.v1', status='PASS_SCOPED_INTERFACE_CAUSALITY_NOT_MOTION_QUALIFICATION',
        created_unix=time.time(), original_global_stop_unix=1793114740.0,
        exact_case_seed_prefix=True, original_B_H150_cross_job_full_raw=comparisons,
        original_function_bodies_AST_copied_without_physics_imports=copied,
        phases=phases, original_evidence_files_sha256={relative:sha(P / relative) for relative in refs},
        new_physics=0, new_model_calls=0, scoring_calls=0, raw_comparison_calls=2,
        wall_s=time.monotonic()-started, cpu_s=time.process_time()-cpu,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    with OUT.open('x') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False);stream.write('\n')
    print(json.dumps({key:result[key] for key in ['status','raw_comparison_calls','wall_s','cpu_s','max_rss_kib']}), flush=True)


if __name__ == '__main__':
    main()
