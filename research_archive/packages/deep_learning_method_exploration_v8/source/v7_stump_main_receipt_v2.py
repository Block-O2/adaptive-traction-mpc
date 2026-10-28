"""Create a pre-outcome receipt; final ledger/file-time join remains mandatory."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

P = Path(__file__).resolve().parents[1]
GROUPS = {'CFACTORH01', 'CFACTORL01'}
MODEL_SHA = 'bf36d1cad7770a9328f0773745285235e0f20c301f55f283a21108d063b4919f'
WATCH_SHA = 'bbc20f798f73b35f47cba461f0c81eeb20d77fc5426363c603af01de466c9725'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def publish(path, value):
    tmp = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    with tmp.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        f.flush()
        os.fsync(f.fileno())
    try:
        os.link(tmp, path)
    finally:
        tmp.unlink()


def candidate_ends(raw, group):
    ids = []
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b'\n'):
            continue
        r = json.loads(line)
        if r.get('event') == 'END' and r.get('id', '').startswith(group + '_') and r['id'] != group + '_parent':
            ids.append({k: r.get(k) for k in ['id', 'unix', 'pid', 'start_ticks']})
    return ids


group = sys.argv[1]
assert group in GROUPS
out = P / 'audit' / (group + '_STUMP_MAIN_ADMISSIBILITY.json')
assert not out.exists(), 'NO_RETRY_OR_BACKFILL'
started = time.time()
mono_start = time.monotonic()
st = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
identity = {'pid': os.getpid(), 'start_ticks': int(st[19])}
record = {'status': 'NOT_TESTED', 'prediction_admissible': False, 'group': group,
          'process': identity, 'started_unix': started, 'started_monotonic': mono_start, 'reason': None,
          'source_sha256': sha(Path(__file__)), 'new_env_model_training_physics': 0}
try:
    base = P / 'predictions/CAUSAL_STUMPS_V1' / group
    assert not (base / 'WATCH_INVALIDATED.json').exists(), 'WATCH_INVALIDATED'
    files = {n: base / n for n in ['WATCH_START.json', 'WATCH_END.json', 'PREDICTION.json']}
    s, e, pred = [read(files[n]) for n in ['WATCH_START.json', 'WATCH_END.json', 'PREDICTION.json']]
    assert e['status'] == 'PREDICTION_SEALED_PENDING_MAIN_COMMIT_AUDIT'
    assert e['prediction_admissible'] is False and e['local_deadline_checks_passed'] is True
    assert e['requires_main_commit_time_audit'] is True
    assert s['group'] == e['group'] == pred['group'] == group
    assert s['expected_model_sha256'] == pred['model_sha256'] == e['model_sha256'] == MODEL_SHA
    assert s['source_sha256'] == pred['source_sha256'] == e['source_sha256'] == WATCH_SHA
    model_file = P / 'models/CAUSAL_STUMPS_V1/MODEL.json'
    watch_file = P / 'source/v7_causal_stump_watch_v2b.py'
    assert sha(model_file) == MODEL_SHA and sha(watch_file) == WATCH_SHA
    model = read(model_file)
    assert model['watcher_source_sha256'] == WATCH_SHA
    assert sha(P / 'source/v7_causal_context.py') == model['context_source_sha256']
    context = P / 'history' / (group + '_PREFORK_CAUSAL_CONTEXT.json')
    assert sha(context) == pred['input_context_sha256'] == e['input_context_sha256']
    assert sha(files['PREDICTION.json']) == e['prediction_sha256']
    activation = read(P / 'ACTIVATION.json')
    hard = min(e['deadline']['hard_wall'], s['deadline']['hard_wall'], s['started_unix'] + s['timeout_s'], activation['deadline_unix'])
    assert 0 < s['timeout_s'] <= 600
    assert s['started_unix'] <= pred['prepared_unix'] <= e['published_unix'] <= e['ended_unix'] < hard
    assert time.time() < hard and time.monotonic() < e['deadline']['hard_mono']
    assert all(s['started_unix'] <= f.stat().st_mtime < hard for f in files.values()), 'PUBLICATION_OUTSIDE_WINDOW'
    assert all(s['started_unix'] <= f.stat().st_ctime < hard for f in files.values()), 'PUBLICATION_CTIME_OUTSIDE_WINDOW'
    ledger_file = P / 'runtime/ATTEMPTS.jsonl'
    ledger = ledger_file.read_bytes()
    assert not candidate_ends(ledger, group), 'FIRST_CANDIDATE_ALREADY_ENDED'
    assert time.time() - started < 30 and time.monotonic() - mono_start < 30
    now = time.time()
    record.update(status='PREOUTCOME_RECEIPT_PENDING_FINAL_LEDGER_JOIN', reason='LOCAL_CHECKS_PASS',
                  captured_unix=now, captured_monotonic=time.monotonic(), hard_wall=hard, hard_mono=e['deadline']['hard_mono'],
                  ledger_prefix_length=len(ledger), ledger_prefix_sha256=hashlib.sha256(ledger).hexdigest(),
                  candidate_END_absent_at_capture=True,
                  input_sha256={str(f.relative_to(P)): sha(f) for f in [*files.values(), model_file, watch_file, context]},
                  prediction_file_mtime=files['PREDICTION.json'].stat().st_mtime,
                  watch_END_file_mtime=files['WATCH_END.json'].stat().st_mtime,
                  prediction_file_ctime=files['PREDICTION.json'].stat().st_ctime,
                  watch_END_file_ctime=files['WATCH_END.json'].stat().st_ctime,
                  final_join_must_check='Receipt/PREDICTION/WATCH_END filemtime and capture before earliest actual candidateEND unix and harddeadline; unchanged source/model/context/ledgerprefix; no invalidation marker.',
                  controller_deployment=False, attempt_savings=0)
except BaseException as error:
    record.update(reason=type(error).__name__ + ':' + str(error))
record['ended_monotonic'] = time.monotonic()
record['ended_unix'] = time.time()
record['postcommit_witness_required'] = True
record['wall_s'] = time.monotonic() - mono_start
publish(out, record)
post_wall, post_mono = time.time(), time.monotonic()
witness = {'status': 'NOT_TESTED', 'group': group, 'process': identity, 'receipt_sha256': sha(out), 'post_receipt_commit_wall': post_wall, 'post_receipt_commit_monotonic': post_mono, 'source_sha256': sha(Path(__file__)), 'prediction_admissible': False, 'reason': None}
try:
    assert record['status'] == 'PREOUTCOME_RECEIPT_PENDING_FINAL_LEDGER_JOIN'
    assert post_wall < record['hard_wall'] and post_mono < record['hard_mono'], 'RECEIPT_COMMIT_CROSSED_DEADLINE'
    assert post_mono - mono_start < 30 and post_wall - started < 30, 'RECEIPT_COMMIT_OVER_30S'
    current = (P / 'runtime/ATTEMPTS.jsonl').read_bytes()
    assert not candidate_ends(current, group), 'END_BEFORE_COMMIT_WITNESS'
    witness.update(status='RECEIPT_COMMIT_WITNESSED_PENDING_FINAL_JOIN', reason='POST_FSYNC_OBSERVED_WITHIN_BOTH_CLOCK_BOUNDS', ledger_prefix_length=len(current), ledger_prefix_sha256=hashlib.sha256(current).hexdigest())
except BaseException as error:
    witness['reason'] = type(error).__name__ + ':' + str(error)
publish(out.with_name(group + '_STUMP_MAIN_COMMIT_WITNESS.json'), witness)
print('STUMP_MAIN_RECEIPT', group, record['status'], record['reason'], flush=True)
