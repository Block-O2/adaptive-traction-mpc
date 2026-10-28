"""主批准 known12 只读 parity 的唯一外部启动器；无训练/物理/部署。"""
from pathlib import Path
import copy
import hashlib
import json
import os
import resource
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())


def main():
    P = Path(__file__).resolve().parent
    package = P.parents[2]
    initial = resource.getrusage(resource.RUSAGE_SELF)
    entered = time.time()
    authority_path = P / 'KNOWN12_PARITY_MAIN_AUTHORITY_V3.json'
    authority_sha = '220a79b3a25c91266a4b989c9fd28afc32e9c098111fddf022dfd31a6ac83469'
    assert sha(authority_path) == authority_sha
    authority = json.loads(authority_path.read_text())
    assert authority['status'] == 'APPROVED_BY_MAIN_ONE_READONLY_KNOWN12_PARITY_V3'
    execution = P / 'KNOWN12_PARITY_EXECUTION_APPROVAL_V3.json'
    out = P / 'known12_parity_once_v3'
    assert not execution.exists() and not out.exists(), 'NO_RETRY_OR_CLOCK_RESET'
    assert not (P / 'KNOWN12_PARITY_EXTERNAL_START_V3.json').exists()
    fields = copy.deepcopy(authority['fixed_execution_approval_fields'])
    for name in ('parity_contract', 'parity_source_manifest', 'readonly_contract'):
        item = fields[name]
        assert sha(package / item['path']) == item['sha256']
    manifest = json.loads((package / fields['parity_source_manifest']['path']).read_text())
    for relative, expected in manifest['required_files_sha256'].items():
        assert sha(package / relative) == expected
    assert sha(P / 'run_known12_readonly_parity_candidate_v3.py') == fields['runner_source_sha256']
    python = '/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python'
    assert sha(Path(python).resolve()) == fields['expected_binary_sha256']
    before = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {min(before)})
    actual = sorted(os.sched_getaffinity(0))
    assert actual == [min(before)]
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    thread_keys = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                   'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
    for key in thread_keys:
        env[key] = '1'
    stdout = (P / 'KNOWN12_PARITY_EXTERNAL_STDOUT_V3.log').open('x')
    stderr = (P / 'KNOWN12_PARITY_EXTERNAL_STDERR_V3.log').open('x')
    # 此处才创建唯一执行时钟；写完批准后立即启动，不等待后续工具。
    launch_now = time.time()
    assert launch_now < 1793114740.
    fields.update(parent_authority_path=str(authority_path),
                  parent_authority_sha256=authority_sha,
                  execution_clock_created_unix=launch_now,
                  expires_unix=min(launch_now + 29.9, 1793114740.))
    write_new(execution, fields)
    execution_sha = sha(execution)
    argv = ['/usr/bin/timeout', '--signal=TERM', '--kill-after=2s', '30s', python, '-B',
            str(P / 'run_known12_readonly_parity_candidate_v3.py'), '--package', str(package),
            '--approval', str(execution.relative_to(package)), '--approval-sha', execution_sha,
            '--output', str(out)]
    write_new(P / 'KNOWN12_PARITY_EXTERNAL_START_V3.json', {
        'launcher_PID': os.getpid(), 'entered_unix': entered,
        'actual_launch_clock_unix': launch_now, 'expires_unix': fields['expires_unix'],
        'affinity_before': before, 'actual_affinity': actual, 'AS_bytes': 1024**3,
        'argv': argv, 'threads': {k: env[k] for k in thread_keys},
        'execution_approval_sha256': execution_sha, 'parent_authority_sha256': authority_sha,
        'launcher_sha256': sha(__file__), 'readonly_known12_parity_attempts_authorized': 1,
        'training_physics_or_deployment_authorized': False})
    child = None; code = None; paid = None; error = None
    try:
        child = subprocess.Popen(argv, env=env, stdout=stdout, stderr=stderr, close_fds=True)
        pid, status, paid = os.wait4(child.pid, 0)
        assert pid == child.pid
        code = os.waitstatus_to_exitcode(status)
        child.returncode = code
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        stdout.close(); stderr.close()
        final = resource.getrusage(resource.RUSAGE_SELF)
        model_start = json.loads((out / 'START.json').read_text()) if (out / 'START.json').is_file() else None
        write_new(P / 'KNOWN12_PARITY_EXTERNAL_RESOURCE_V3.json', {
            'status': 'RETURNED' if error is None else 'LAUNCH_OR_WAIT_FAILED_NO_RETRY',
            'error': error, 'returncode': code, 'launcher_PID': os.getpid(),
            'timeout_PID': None if child is None else child.pid, 'model_START': model_start,
            'entered_unix': entered, 'actual_launch_clock_unix': launch_now,
            'final_unix': time.time(), 'launcher_wall_s': time.time() - entered,
            'launch_to_return_wall_s': time.time() - launch_now,
            'launcher_CPU_user_s': final.ru_utime - initial.ru_utime,
            'launcher_CPU_system_s': final.ru_stime - initial.ru_stime,
            'launcher_peak_RSS_KiB': final.ru_maxrss, 'actual_affinity': actual,
            'wait4_timeout_tree_paid_usage': None if paid is None else {
                'CPU_user_s': paid.ru_utime, 'CPU_system_s': paid.ru_stime,
                'peak_RSS_KiB': paid.ru_maxrss},
            'RESULT_sha256': sha(out / 'RESULT.json') if (out / 'RESULT.json').is_file() else None,
            'FAILED_paid_sha256': sha(out / 'FAILED_PARITY_PAID_PREFIX_V3.json') if (out / 'FAILED_PARITY_PAID_PREFIX_V3.json').is_file() else None,
            'failed_or_killed_work_after_last_durable_artifact': 'UNKNOWN_NOT_ZERO_IF_NO_FINAL_ACCOUNTING',
            'approved_readonly_parity_attempts': 1, 'training_physics_or_deployment': 0,
            'automatic_retry': False})
    if code != 0:
        raise SystemExit(code if code is not None else 1)


if __name__ == '__main__':
    main()
