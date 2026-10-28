"""Main-invoked metadata installation/binding; never dispatches physics.

install: only after all old frozen jobs close, add two exact new case files and
four new source versions. Existing bytes must match; no overwrite or clock reset.
bind GROUP: after generic preparation, enforce the registered explicit case and
B-first menu. This closes the optional-case-path fallback in the generic worker.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

P = Path(__file__).resolve().parents[1]
mode = sys.argv[1]
started = time.time()
stat = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
identity = {'pid': os.getpid(), 'start_ticks': int(stat[19])}
job = 'FACTORIAL_METADATA_' + str(time.time_ns())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def put(path, value):
    assert not path.exists(), 'REFUSE_OVERWRITE:' + str(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def live(old):
    try:
        s = (Path('/proc') / str(old['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
        return int(s[19]) == old['start_ticks'] and s[0] != 'Z'
    except FileNotFoundError:
        return False


put(P / 'owned' / (job + '_START.json'), dict(identity, started_unix=started,
    source_sha256=sha(Path(__file__)), arguments=sys.argv[1:], branch='FACTORIAL_CASE_INTERFACE_ENGINEERING_V1'))
try:
    assert time.time() < read(P / 'ACTIVATION.json')['deadline_unix'] - 600
    assert not (P / 'STOP_REQUESTED').exists()
    payload_file = P / 'freeze/FACTORIAL_CASE_PAYLOADS_V1.json'
    payload = read(payload_file)
    rows = {r['group']: r for r in payload['rows']}
    assert set(rows) == {'CFACTORH01', 'CFACTORL01'}
    configs = {g: read(P / 'experiments' / (g + '.json')) for g in rows}
    for g in rows:
        assert sha(P / 'experiments' / (g + '.json')) == read(P / 'freeze' / (g + '.json'))['config_sha256']
        assert configs[g]['frozen_artifacts']['freeze/FACTORIAL_CASE_PAYLOADS_V1.json'] == sha(payload_file)
    if mode == 'install':
        for g in ['PFXV01', 'PFXV02', 'EARLYABL01', 'EARLYPH01', 'HOLDSS01']:
            end = read(P / 'owned' / (g + '_SUPERVISOR_END.json'))
            assert end['state'] == 'STOP' and not end['survivors'], 'OLD_JOB_NOT_CLOSED:' + g
            assert not any(live(x) for x in end['known_owned'].values()), 'OLD_OWNED_STILL_LIVE:' + g
            for f in (P / 'audit').glob(g + '*_ERROR.json'):
                assert 'TRUE_NATIVE_SAFETY_CONTRACT_FAILURE' not in str(read(f).get('error')), 'UNRESOLVED_HARD_SAFETY_FAILURE'
        # Verify the original SS frozen artifact closure before adding new versions.
        for rel, expected in read(P / 'freeze/SHORT_SEGMENTS_EXECUTION_V2.json')['frozen_artifacts'].items():
            assert sha(P / rel) == expected, 'OLD_FROZEN_ARTIFACT_CHANGED:' + rel
        additions = []
        for row in rows.values():
            raw = row['exact_utf8_text'].encode()
            assert hashlib.sha256(raw).hexdigest() == row['case_sha256']
            additions.append((P / row['relative_case_path'], raw, row['case_sha256']))
        for name in ['v7_case_adapter_v3.py', 'v7_worker_v9.py', 'v7_scorer_replay_v2.py', 'v7_audit_batch_v2.py']:
            src = P / 'agent_reviews/factorial_case_interface' / name
            expected = configs['CFACTORH01']['frozen_artifacts']['source/' + name]
            assert sha(src) == expected
            additions.append((P / 'source' / name, src.read_bytes(), expected))
        for dest, raw, expected in additions:
            if dest.exists():
                assert dest.is_file() and not dest.is_symlink() and sha(dest) == expected, 'CONFLICT_NO_OVERWRITE:' + str(dest)
            else:
                temp = dest.with_name(dest.name + '.install.tmp')
                assert not temp.exists(), 'PENDING_INSTALL_REQUIRES_REVIEW:' + str(temp)
                temp.write_bytes(raw)
                assert sha(temp) == expected
                temp.replace(dest)
        done = P / 'audit/FACTORIAL_INSTALL_DONE.json'
        record = dict(status='PASS_INSTALLED_NO_PHYSICS', unix=time.time(), process=identity,
            source_sha256=sha(Path(__file__)), payload_sha256=sha(payload_file),
            installed_sha256={str(f.relative_to(P)): h for f, _, h in additions},
            old_frozen_closure_unchanged=True, new_model_env_train_physics=0)
        if done.exists():
            assert read(done)['installed_sha256'] == record['installed_sha256']
        else:
            put(done, record)
    elif mode == 'bind':
        g = sys.argv[2]
        assert g in rows
        assert read(P / 'audit/FACTORIAL_INSTALL_DONE.json')['status'] == 'PASS_INSTALLED_NO_PHYSICS'
        c = configs[g]
        row = rows[g]
        assert not (P / 'jobs' / g / 'SOURCE_MANIFEST.json').exists(), 'ALREADY_STARTED'
        for key, expected in [('case_path', row['relative_case_path']), ('case_sha256', row['case_sha256']), ('case_key', row['case_key']), ('worker', 'v7_worker_v9.py'), ('algorithm', 'v7_early_sequence_v1')]:
            assert c[key] == expected, 'EXPLICIT_BINDING_MISMATCH:' + key
        assert (P / c['case_path']).read_bytes() == row['exact_utf8_text'].encode()
        menu = read(P / 'freeze/FACTORIAL_POLICY_MENU_V1.json')
        assert c['actions'] == menu['actions'] and len(c['actions']) == 7
        assert c['B'] == menu['B'] and c['H150'] == menu['H150']
        assert c['actions'][0]['tag'] == 'B' and c['actions'][0]['action'] == {'family': 'B'}
        assert c['required_qualified_controls'] == ['B']
        assert c['required_repeat_controls'] == [] and c['historical_repeats'] == {}
        assert c['fork_phase'] == 'OUTBOUND' and type(c['fork_slot']) is int and c['fork_slot'] == 0
        for rel, expected in c['frozen_artifacts'].items():
            assert sha(P / rel) == expected, 'FROZEN_ARTIFACT_CHANGED:' + rel
        cf = P / 'experiments' / (g + '.json')
        assert (P / 'runtime' / (g + '_TEST_PLAN.json')).read_bytes() == cf.read_bytes()
        assert read(P / 'audit' / (g + '_PRELAUNCH.json'))['config_sha256'] == sha(cf)
        put(P / 'audit' / (g + '_CASE_AND_MENU_BINDING.json'), dict(status='PASS', unix=time.time(),
            process=identity, source_sha256=sha(Path(__file__)), config_sha256=sha(cf),
            payload_sha256=sha(payload_file), explicit_case_path_hash_key=True,
            B_first_qualification_required=True, exact_seven_policy_menu=True,
            frozen_artifacts_checked=len(c['frozen_artifacts']), model_env_train_physics=0))
    else:
        raise ValueError('EXPECTED_INSTALL_OR_BIND')
    put(P / 'owned' / (job + '_END.json'), dict(identity, status='PASS', ended_unix=time.time(),
        wall_s=time.time()-started, source_sha256=sha(Path(__file__)), arguments=sys.argv[1:]))
    print('FACTORIAL_METADATA_PASS', mode, sys.argv[2:], flush=True)
except BaseException as error:
    put(P / 'owned' / (job + '_END.json'), dict(identity, status='FAILED_PRESERVED', ended_unix=time.time(),
        error=str(error), source_sha256=sha(Path(__file__)), arguments=sys.argv[1:]))
    raise
