"""Final read-only full-content check; preserves every historical baseline hash."""
from pathlib import Path
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
ROOT = P.parent
OUT = P / 'audit/HISTORY_CONTENT_HASH_FINAL.json'
assert not OUT.exists(), 'FINAL_AUDIT_ALREADY_EXISTS_DO_NOT_OVERWRITE'
baseline_file = P / 'audit/HISTORY_CONTENT_HASH_START.json'
metadata_file = P / 'audit/HISTORY_PROTECTION_START.json'
baseline = json.loads(baseline_file.read_text())
metadata = json.loads(metadata_file.read_text())
assert baseline['status'] == 'PASS' and not baseline['errors']
assert set(baseline['files']) == set(metadata['files'])
assert not metadata['historical_files_modified_since_T0']
started = time.time()
stat = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
identity = {'pid': os.getpid(), 'start_ticks': int(stat[19])}
files = {}
errors = []
total_bytes = 0


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 2**20), b''):
            h.update(block)
    return h.hexdigest()


def meta(path):
    s = path.stat()
    return {'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns, 'mode': s.st_mode, 'inode': s.st_ino}


def save(status):
    payload = {'branch': 'FINAL_HISTORICAL_CONTENT_RECHECK_V1', 'status': status,
               'started_unix': started, 'updated_unix': time.time(), 'process': identity,
               'baseline_sha256': sha(baseline_file), 'metadata_baseline_sha256': sha(metadata_file),
               'source_sha256': sha(Path(__file__)), 'files': files, 'errors': errors,
               'bytes_hashed': total_bytes, 'checked_files': len(files),
               'expected_files': len(baseline['files']), 'wall_s': time.time() - started,
               'scope': 'Every file in protected inventory; full content and original metadata. Root journal checked separately as append-only. Baseline full hash was captured after T0, as documented, not claimed as T0 full hash.'}
    temp = OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temp.replace(OUT)


try:
    for index, (relative, expected_hash) in enumerate(baseline['files'].items()):
        f = ROOT / relative
        try:
            if meta(f) != metadata['files'][relative]:
                errors.append({'file': relative, 'error': 'METADATA_CHANGED_BEFORE_HASH'})
                continue
            actual = sha(f)
            files[relative] = actual
            total_bytes += metadata['files'][relative]['bytes']
            if actual != expected_hash:
                errors.append({'file': relative, 'error': 'HISTORICAL_CONTENT_HASH_CHANGED'})
            if meta(f) != metadata['files'][relative]:
                errors.append({'file': relative, 'error': 'FILE_CHANGED_DURING_HASH'})
        except OSError as error:
            errors.append({'file': relative, 'error': str(error)})
        if index % 10000 == 0:
            save('IN_PROGRESS')
finally:
    status = 'PASS' if not errors and len(files) == len(baseline['files']) else 'FAIL_OR_PARTIAL_PRESERVED'
    save(status)
print('FINAL_HISTORICAL_CONTENT', status, len(files), total_bytes, time.time() - started, flush=True)
assert status == 'PASS', 'HISTORICAL_PROTECTION_FINAL_FAILED'
