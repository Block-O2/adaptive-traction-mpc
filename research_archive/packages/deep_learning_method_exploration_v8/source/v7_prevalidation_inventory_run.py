"""Freeze and verify the registered exposed-history inventory before validation.

No physical/model imports or dispatch. The identity auditor itself is unchanged.
Run once through v7_offline_owned_v2.py after both early transfer jobs close.
"""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import time

P = Path(__file__).resolve().parents[1]
W = P.parent
OUT = P / 'analysis/KNOWN_EXPOSED_INVENTORY_PREVALIDATION_V2.json'
START = P / 'audit/PREVALIDATION_EXPOSURE_INVENTORY_V2_START.json'
CHECK = P / 'audit/PREVALIDATION_EXPOSURE_INVENTORY_V2_INPUT_CHECK.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    assert not path.exists(), 'REFUSE_OVERWRITE:' + str(path)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


assert not any(f.exists() for f in [OUT, START, CHECK]), 'UNIQUE_EXECUTION_ONLY'
for group in ['EARLYN01', 'EARLYL01']:
    end = read(P / 'owned' / (group + '_SUPERVISOR_END.json'))
    assert end['worker_exit_code'] == 0 and not end['survivors']
    assert read(P / 'jobs' / group / 'WORKER_DONE.json')['all_children_joined']
for group in ['PFXV01', 'PFXV02', 'HOLDSS01']:
    assert not (P / 'jobs' / group / 'SOURCE_MANIFEST.json').exists(), 'TEST_ALREADY_STARTED'
sys.path.insert(0, str(P / 'source'))
import v7_parent_identity_v2 as auditor

assert sha(P / 'source/v7_parent_identity_v2.py') == '0b05d0240d6ca7212eec88c93478fc8ca943b441f23e19e1fb6aee74ea75141e'
cutoff = time.time()
paths = {Path(__file__), P / 'source/v7_parent_identity_v2.py', P / 'ACTIVATION.json'}
missing = []
snapshots = []
for name in auditor.HISTORICAL + [auditor.V7]:
    package = W / name
    for snapshot in sorted((package / 'runtime/reports').glob('*_SNAPSHOT.json')):
        ident = snapshot.name[:-len('_SNAPSHOT.json')]
        if name == auditor.V7 and not auditor.allowed_v7(ident):
            continue
        assert snapshot.stat().st_mtime <= cutoff
        snapshots.append(str(snapshot))
        paths.add(snapshot)
        for extra in [package / 'attempts' / (ident + '_RESULT.json'),
                      package / 'runtime/source/results' / ident / 'trace.npz']:
            if extra.is_file():
                paths.add(extra)
            else:
                missing.append(str(extra))
        configs = [f for f in (package / 'experiments').glob('*.json') if ident.startswith(f.stem + '_')]
        if configs:
            paths.add(max(configs, key=lambda f: len(f.stem)))
for group in ['EARLYN01', 'EARLYL01']:
    paths.add(P / 'owned' / (group + '_SUPERVISOR_END.json'))
    paths.add(P / 'jobs' / group / 'WORKER_DONE.json')
inputs = {str(f): {'sha256': sha(f), 'size': f.stat().st_size} for f in sorted(paths)}
save(START, {'branch': 'PREVALIDATION_EXPOSURE_INVENTORY_V2', 'start_unix': cutoff,
             'budget_wall_s': 1200, 'deadline_unix': read(P / 'ACTIVATION.json')['deadline_unix'],
             'inputs': inputs, 'frozen_snapshot_paths': snapshots,
             'missing_retained': missing, 'validation_data_opened': False,
             'source_sha256': sha(Path(__file__))})
sys.argv = [str(P / 'source/v7_parent_identity_v2.py'), 'inventory', '--workspace', str(W),
            '--start', str(START), '--out', str(OUT), '--with-traces']
runpy.run_path(str(P / 'source/v7_parent_identity_v2.py'), run_name='__main__')
changed = [str(f) for f in paths if not f.is_file() or sha(f) != inputs[str(f)]['sha256']]
result = read(OUT)
save(CHECK, {'status': 'PASS' if not changed and not result['errors'] else 'FAIL',
             'checked_unix': time.time(), 'input_count': len(inputs), 'changed': changed,
             'inventory_errors': result['errors'], 'inventory_sha256': sha(OUT),
             'snapshot_count': len(result['snapshot_rows']), 'missing_retained': missing,
             'validation_data_opened': False, 'source_sha256': sha(Path(__file__))})
assert not changed and not result['errors'], 'EXPOSED_INVENTORY_IDENTITY_FAILURE'
print('PREVALIDATION_INPUT_IDENTITY_PASS', len(inputs), len(result['snapshot_rows']), flush=True)
