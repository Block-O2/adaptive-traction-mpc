"""SOURCE_ONLY：只有另批主authority才能创建A5唯一执行时钟并启动有限fit。"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import resource
import subprocess
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())


def main():
    initial = resource.getrusage(resource.RUSAGE_SELF); entered = time.time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authority', type=Path, required=True)
    parser.add_argument('--authority-sha', required=True)
    args = parser.parse_args()
    P = Path(__file__).resolve().parent
    authority_path = args.authority.resolve()
    assert authority_path.is_relative_to(P) and sha(authority_path) == args.authority_sha
    authority = json.loads(authority_path.read_text())
    assert authority['status'] == 'APPROVED_BY_MAIN_AGENT_ONE_A5_OFFLINE_RISK_FIT_ONLY'
    fields = copy.deepcopy(authority['fixed_execution_approval_fields'])
    assert fields['status'] == 'APPROVED_BY_MAIN_AGENT_FOR_A5_ONE_OFFLINE_RISK_FIT'
    assert fields['training_authorized'] is True and fields['new_physics_or_deployment_authorized'] is False
    execution = P / 'EXECUTION_APPROVAL_V1.json'
    out = P / 'fit_run_v1'
    assert not execution.exists() and not out.exists() and not (P / 'FIT_EXTERNAL_START_V1.json').exists(), 'A5_ONE_ATTEMPT_NO_RETRY_OR_RESET'
    contract_path = P / 'contracts/FIT_CONTRACT_PROPOSED_V1.json'
    manifest_path = P / 'SOURCE_CANDIDATE_MANIFEST_V1.json'
    data_path = P / 'data/OPERATIONAL_RISK50_DATASET_V1.json'
    assert sha(contract_path) == fields['contract_sha256']
    assert sha(manifest_path) == fields['source_manifest_sha256']
    assert sha(data_path) == fields['data_sha256']
    contract = json.loads(contract_path.read_text())
    assert contract['external_launcher_sha256'] == sha(Path(__file__))
    manifest = json.loads(manifest_path.read_text())
    for rel, expected in manifest['source_files_sha256'].items():
        assert sha(P / rel) == expected
    python = contract['python_proposed']
    assert sha(Path(python).resolve()) == fields['expected_binary_sha256'] == contract['expected_python_binary_sha256']
    before = sorted(os.sched_getaffinity(0)); os.sched_setaffinity(0, {min(before)})
    actual = sorted(os.sched_getaffinity(0)); assert actual == [min(before)]
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    env = dict(os.environ); env['PYTHONDONTWRITEBYTECODE'] = '1'
    threads = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
    for key in threads:
        env[key] = '1'
    stdout = (P / 'FIT_EXTERNAL_STDOUT_V1.log').open('x'); stderr = (P / 'FIT_EXTERNAL_STDERR_V1.log').open('x')
    # 唯一新时钟在真正外launch内生成；无任何等待工具或延长。
    launched = time.time(); assert launched < 1793114740.
    fields.update(parent_authority_path=str(authority_path), parent_authority_sha256=args.authority_sha,
                  execution_clock_created_unix=launched, expires_unix=min(launched + 59.9, 1793114740.))
    save(execution, fields)
    argv = ['/usr/bin/timeout', '--signal=TERM', '--kill-after=2s', '60s', python, '-B',
            str(P / 'source/run_training_candidate_v1.py'), '--approval', str(execution), '--approval-sha', sha(execution)]
    save(P / 'FIT_EXTERNAL_START_V1.json', {'launcher_PID': os.getpid(), 'actual_launch_unix': launched,
        'expires_unix': fields['expires_unix'], 'AS_bytes': 1024**3, 'affinity_before': before, 'actual_affinity': actual,
        'threads': {k: env[k] for k in threads}, 'argv': argv, 'launcher_sha256': sha(Path(__file__)),
        'parent_authority_sha256': args.authority_sha, 'execution_approval_sha256': sha(execution),
        'new_physics_or_deployment_authorized': False})
    child = None; code = None; paid = None; error = None
    try:
        child = subprocess.Popen(argv, env=env, stdout=stdout, stderr=stderr, close_fds=True)
        pid, status, paid = os.wait4(child.pid, 0); assert pid == child.pid
        code = os.waitstatus_to_exitcode(status); child.returncode = code
    except BaseException as exc:
        error = repr(exc); raise
    finally:
        stdout.close(); stderr.close(); final = resource.getrusage(resource.RUSAGE_SELF)
        save(P / 'FIT_EXTERNAL_RESOURCE_V1.json', {'status': 'RETURNED' if error is None else 'LAUNCH_OR_WAIT_FAILED_NO_RETRY',
            'error': error, 'returncode': code, 'launcher_PID': os.getpid(), 'timeout_PID': None if child is None else child.pid,
            'model_START': json.loads((out / 'START.json').read_text()) if (out / 'START.json').is_file() else None,
            'launch_unix': launched, 'final_unix': time.time(), 'launch_to_return_wall_s': time.time() - launched,
            'launcher_wall_s': time.time() - entered, 'launcher_CPU_user_s': final.ru_utime - initial.ru_utime,
            'launcher_CPU_system_s': final.ru_stime - initial.ru_stime, 'launcher_peak_RSS_KiB': final.ru_maxrss,
            'wait4_timeout_tree_usage': None if paid is None else {'CPU_user_s': paid.ru_utime,
                'CPU_system_s': paid.ru_stime, 'peak_RSS_KiB': paid.ru_maxrss},
            'COMPLETE_sha256': sha(out / 'COMPLETE.json') if (out / 'COMPLETE.json').is_file() else None,
            'FAILED_sha256': sha(out / 'FAILED_PAID_PREFIX_V1.json') if (out / 'FAILED_PAID_PREFIX_V1.json').is_file() else None,
            'after_last_durable_work_if_no_final_accounting': 'UNKNOWN_BOUNDED_NOT_ZERO',
            'fit_attempts_authorized': 1, 'new_physics': 0, 'automatic_retry': False})
    if code != 0:
        raise SystemExit(code if code is not None else 1)


if __name__ == '__main__':
    main()
