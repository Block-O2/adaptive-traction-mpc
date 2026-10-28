"""Root once-only launcher for the fully reviewed frozen arithmetic diagnostic."""
from pathlib import Path
import hashlib
import json
import os
import resource
import subprocess
import time

P = Path(__file__).resolve().parents[1]
H = 'families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/new_context_span_diagnostic_v1/'
PYTHON = '/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python'


def sha(rel):
    return hashlib.sha256((P / rel).read_bytes()).hexdigest()


def save(rel, value):
    with (P / rel).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def identity(pid):
    return dict(pid=pid, start_ticks=int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]))


def main():
    assert time.time() + 65 < 1793114740.0
    assert sha(H + 'SOURCE_MANIFEST_V1.json') == '259f535ee30bed037c4f6792d4beaa9c9ad56cb20d22786905ebbd188664599c'
    manifest = json.loads((P / H / 'SOURCE_MANIFEST_V1.json').read_text())
    for rel, expected in manifest['files_sha256'].items():
        assert sha(rel) == expected, rel
    for item in manifest['data_refs'].values():
        assert sha(item['path']) == item['sha256'], item['path']
    assert not (P / H / 'diagnostics/NEWCTX_ONCE_V1').exists()
    review = dict(status='ROOT_FULL_SOURCE_CONTRACT_INPUT_REVIEWED', created_unix=time.time(),
                  manifest_sha256=sha(H + 'SOURCE_MANIFEST_V1.json'),
                  helper_sha256=sha(H + 'run_new_context_span_candidate_v1.py'),
                  contract_sha256=sha(H + 'EXPERIMENT_CONTRACT_V1.json'),
                  scope='Frozen vector arithmetic and stored output alignment only; 111 dot26,48 dot2,14 2x2 solves; no new nonlinear mean, learner API, scorer, TASK outcomes, fit, RNG or physics',
                  endpoints_retained=6, new_contexts=2, no_selection_or_model_change=True,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    save('audit/NEW_CONTEXT_SPAN_MAIN_SOURCE_REVIEW_V1.json', review)
    authority = json.loads((P / H / 'MAIN_APPROVAL_TEMPLATE_REVIEW_ONLY_V1.json').read_text())
    now = time.time()
    authority.update(status='MAIN_APPROVED_ONCE_FROZEN_ARITHMETIC_NO_LEARNER_API',
                     source_manifest=dict(path=H + 'SOURCE_MANIFEST_V1.json', sha256=sha(H + 'SOURCE_MANIFEST_V1.json')),
                     input=manifest['input'], local_start_unix=now, local_stop_unix=now + 60.0,
                     root_source_review=dict(path='audit/NEW_CONTEXT_SPAN_MAIN_SOURCE_REVIEW_V1.json', sha256=sha('audit/NEW_CONTEXT_SPAN_MAIN_SOURCE_REVIEW_V1.json')))
    ar = 'audit/NEW_CONTEXT_SPAN_MAIN_APPROVAL_V1.json'
    save(ar, authority)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    owner = identity(os.getpid()); before = resource.getrusage(resource.RUSAGE_CHILDREN); started = time.time()
    command = ['/usr/bin/timeout', '--kill-after=2', '60', '/usr/bin/time', '-v', '-o', str(P / 'audit/NEW_CONTEXT_SPAN_EXTERNAL_RESOURCE_V1.txt'), PYTHON, '-B', str(P / H / 'run_new_context_span_candidate_v1.py'), '--package', str(P), '--approval', str(P / ar), '--approval-sha256', sha(ar)]
    child = subprocess.Popen(command, cwd=P, env=env)
    child_identity = identity(child.pid)
    save('audit/NEW_CONTEXT_SPAN_EXECUTION_START_V1.json', dict(owner=owner, child=child_identity, started_unix=started, command=command))
    rc = child.wait(timeout=65)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = dict(owner=owner, child=child_identity, returncode=rc, ended_unix=time.time(), inclusive_child_wall_s=time.time()-started,
                  inclusive_children_CPU_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                  root_prepare_CPU_s='UNKNOWN_NOT_ISOLATED_NOT_ZERO', helper_model_scorer_fit_RNG_physics_calls=0,
                  original_global_stop_unix=1793114740.0)
    save('audit/NEW_CONTEXT_SPAN_EXECUTION_END_V1.json', result)
    print(json.dumps(result))
    if rc:
        raise SystemExit(rc)


if __name__ == '__main__':
    main()
