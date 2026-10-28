"""SOURCE_ONLY one-shot authority/timeout/PID launcher; no launch on import."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = 'families/learning_assisted/common_out0_v2/'
MANIFEST = REL + 'ACTUAL_BUNDLE_E2_CANARY_SOURCE_MANIFEST_V1.json'
CONTRACT = REL + 'ACTUAL_BUNDLE_E2_CANARY_CONTRACT_V1.json'
OUT = REL + 'canaries/actual_bundle_e2_v1'
STOP = 1793114740.0
PYTHON = '/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python'


def need(test, reason):
    if not test:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def proc(pid):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        parts = raw[raw.rindex(')') + 2:].split()
        return dict(pid=pid, start_ticks=int(parts[19]), state=parts[0], ppid=int(parts[1]))
    except (FileNotFoundError, ProcessLookupError):
        return None


def new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def main():
    started = time.monotonic();cpu_started = time.process_time()
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True);parser.add_argument('--approval', required=True)
    parser.add_argument('--approval-sha256', required=True)
    args = parser.parse_args();root = Path(args.package).resolve();approval_path = Path(args.approval).resolve()
    need(root == ROOT and approval_path.is_relative_to(root), 'PARITY_LAUNCH_EXACT_PATHS')
    need(sys.dont_write_bytecode and Path(sys.executable).resolve() == Path(PYTHON).resolve(),
         'PARITY_LAUNCH_MAIN_VENV_MINUS_B')
    need(sha(approval_path) == args.approval_sha256, 'PARITY_LAUNCH_EXACT_APPROVAL')
    approval = load(approval_path);contract = load(root / CONTRACT);manifest = load(root / MANIFEST)
    need(approval.get('schema') == 'v8.E2.actual_bundle_canary_approval.v1' and
         approval.get('status') == 'ROOT_APPROVED_ACTUAL_BUNDLE_E2_CANARY_ONCE_V1' and
         approval.get('contract_sha256') == sha(root / CONTRACT) and
         approval.get('source_manifest_sha256') == sha(root / MANIFEST) and
         approval.get('output') == OUT and approval.get('actual_bundle_only') is True and
         approval.get('real_weight_read_authorization') is True and
         approval.get('old_development_INDEX_read_authorization') is True and
         approval.get('actual_OUT0_wrapper_call_authorization') is False and
         approval.get('A3_call_authorization') is False and
         approval.get('fit_authorization') is False and approval.get('physics_authorization') is False and
         approval.get('budget') == contract['budget'], 'PARITY_LAUNCH_MAIN_AUTHORITY_REQUIRED')
    allowed = {REL + name for name in ('actual_bundle_canary_e2_candidate_v1.py',
        'launch_actual_bundle_canary_e2_once_v1.py', 'frozen_live_e2_candidate_v2.py',
        'e2_models_candidate_v1.py', 'ACTUAL_BUNDLE_E2_CANARY_CONTRACT_V1.json')}
    allowed.update({'ACTIVATION.json', REL+'fits/e2_v1/FROZEN_E2_BUNDLE.json',
                    REL+'data/fulltask_e2_v1/INDEX.json', REL+'FROZEN_LIVE_E2_CONTRACT_V2.json',
                    REL+'FROZEN_LIVE_E2_SOURCE_MANIFEST_V2.json'})
    need(set(manifest['files_sha256']) == allowed, 'ACTUAL_CANARY_LAUNCH_EXACT_WEIGHT_INDEX_ALLOWLIST')
    for relative, expected in manifest['files_sha256'].items():
        path = (root / relative).resolve()
        need(path.is_relative_to(root) and sha(path) == expected, 'PARITY_LAUNCH_SOURCE_CHANGED')
    activation = load(root / 'ACTIVATION.json')
    need(activation['activation_id'] == 'deep_learning_method_exploration_v8_20261027T032540Z'
         and activation['hard_stop_unix'] == STOP and activation['clock_must_not_reset'] is True,
         'PARITY_LAUNCH_ORIGINAL_CLOCK')
    deadline = min(started + 30., started + STOP - time.time())
    need(time.monotonic() < deadline and not (root / OUT).exists(), 'PARITY_LAUNCH_ONE_SHOT_NO_RESET')
    prefix = HERE / 'ACTUAL_BUNDLE_E2_CANARY_EXTERNAL_V1'
    files = {key: Path(str(prefix) + suffix) for key, suffix in (
        ('start', '.START.json'), ('time', '.time.txt'), ('stdout', '.stdout.txt'),
        ('stderr', '.stderr.txt'), ('receipt', '.execution.json'))}
    need(all(not path.exists() for path in files.values()), 'PARITY_LAUNCH_NO_OVERWRITE_OR_RETRY')
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    new(files['start'], dict(schema='v8.E2.actual_bundle_canary_launch_start.v1',
        launcher_identity=proc(os.getpid()), approval_sha256=args.approval_sha256,
        start_monotonic=started, unchanged_deadline_monotonic=deadline,
        original_global_stop_unix=STOP, affinity=sorted(os.sched_getaffinity(0))))
    remaining = deadline - time.monotonic();need(remaining > 0., 'PARITY_LAUNCH_CAP_EXHAUSTED')
    cmd = ['/usr/bin/time', '-v', '-o', str(files['time']), 'timeout', '--signal=TERM',
           '--kill-after=2s', str(remaining) + 's', 'env', 'PYTHONDONTWRITEBYTECODE=1',
           'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', PYTHON, '-B',
           str(HERE / 'actual_bundle_canary_e2_candidate_v1.py'), '--package', str(root),
           '--approval', str(approval_path), '--approval-sha256', args.approval_sha256,
           '--owner-deadline-monotonic', str(deadline)]
    seen = {}
    with files['stdout'].open('x') as stdout, files['stderr'].open('x') as stderr:
        child = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
        while True:
            pending = [child.pid];visited = set()
            while pending:
                pid = pending.pop()
                if pid in visited:continue
                visited.add(pid);identity = proc(pid)
                if identity:
                    key = (pid, identity['start_ticks'])
                    item = seen.setdefault(key, dict(**identity, first_observed_unix=time.time(),
                        last_nonempty_cmdline='', cmdline_transitions=[]))
                    try:
                        command = Path('/proc', str(pid), 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                        if command and command != item['last_nonempty_cmdline']:
                            item['cmdline_transitions'].append(command)
                            item['last_nonempty_cmdline'] = command
                    except (FileNotFoundError, ProcessLookupError):pass
                    try:pending.extend(int(v) for v in Path('/proc', str(pid), 'task', str(pid), 'children').read_text().split())
                    except (FileNotFoundError, ProcessLookupError):pass
            exit_code = child.poll()
            if exit_code is not None:break
            time.sleep(.01)
        child.wait()
    for (pid, ticks), item in seen.items():
        after = proc(pid);item['postcheck'] = after
        item['same_identity_still_alive'] = bool(after and after['start_ticks'] == ticks and after['state'] != 'Z')
    runners = [item for item in seen.values() if item['last_nonempty_cmdline'].startswith(PYTHON + ' -B ')]
    receipt = dict(schema='v8.E2.actual_bundle_canary_external_execution.v1',
        approval_sha256=args.approval_sha256, command=cmd, one_shot_attempts=1,
        exit_code=exit_code, identities=list(seen.values()), exact_runner_identities=runners,
        all_observed_pid_startticks_closed=all(not item['same_identity_still_alive'] for item in seen.values()),
        launcher_identity=proc(os.getpid()), launcher_CPU_seconds=time.process_time() - cpu_started,
        wall_seconds=time.monotonic() - started,
        original_deadline_monotonic=deadline, real_bundle_JSON_loads='FROM_RUNNER_RESULT_OR_FAILED_RECEIPT_NOT_ASSUMED_ZERO', actual_A3_calls=0, fit=0, physics=0,
        files_sha256={key: sha(path) for key, path in files.items() if key != 'receipt' and path.exists()})
    new(files['receipt'], receipt)
    print(json.dumps(dict(exit_code=exit_code, receipt_sha256=sha(files['receipt']),
        exact_runner_identities=[dict(pid=item['pid'], start_ticks=item['start_ticks']) for item in runners],
        all_observed_pid_startticks_closed=receipt['all_observed_pid_startticks_closed'])))
    print(files['stdout'].read_text());print(files['stderr'].read_text())
    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
