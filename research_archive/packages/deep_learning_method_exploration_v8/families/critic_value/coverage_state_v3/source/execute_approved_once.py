"""主审要求的执行资源外壳；不改已批准的 fit/API source。"""
from pathlib import Path
import hashlib
import json
import resource
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    approval = json.loads((ROOT / 'MAIN_APPROVAL_V1.json').read_text())
    assert approval['status'] == 'APPROVED_BY_MAIN_AGENT'
    assert hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest() == approval['python_identity']['python_binary_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == approval['execution_resource_wrapper_sha256']
    before, start = resource.getrusage(resource.RUSAGE_SELF), time.time()
    initial = {'wall_unix': start, 'cpu_user_s': before.ru_utime, 'cpu_system_s': before.ru_stime, 'RSS_peak_KiB': before.ru_maxrss}
    with (ROOT / 'analysis/EXECUTION_INITIAL_RESOURCE_V1.json').open('x') as stream:
        json.dump(initial, stream, indent=2);stream.write('\n')
    status = 'FAILED'
    try:
        sys.argv = [str(ROOT / 'source/run_training_candidate.py'), '--approval', str(ROOT / 'MAIN_APPROVAL_V1.json')]
        runpy.run_path(str(ROOT / 'source/run_training_candidate.py'), run_name='__main__')
        status = 'COMPLETED'
    finally:
        after = resource.getrusage(resource.RUSAGE_SELF)
        audit = {'status': status, 'initial': initial, 'final': {'wall_unix': time.time(), 'cpu_user_s': after.ru_utime,
            'cpu_system_s': after.ru_stime, 'RSS_peak_KiB': after.ru_maxrss}, 'wall_s': time.time() - start,
            'fit_source_unmodified': True, 'automatic_retry': False, 'new_physics': 0}
        with (ROOT / 'analysis/EXECUTION_INITIAL_FINAL_RESOURCE_V1.json').open('x') as stream:
            json.dump(audit, stream, indent=2);stream.write('\n')


if __name__ == '__main__':
    main()
