"""Check a fresh RL-B environment using sealed import/unit tests only.

Copies the unchanged capsule into a new work directory and blocks physics APIs.
This never grants the physical qualification gates required by train.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GUARD = """import sys,runpy,mujoco
def forbidden(*a,**kw): raise RuntimeError('DEPLOYMENT_CHECK_FORBIDS_PHYSICS')
for name in ('mj_step','mj_step1','mj_step2','mj_forward','mj_inverse'):setattr(mujoco,name,forbidden)
sys.argv=[sys.argv[1]]
sys.path.insert(0,str(__import__('pathlib').Path(sys.argv[0]).parent))
runpy.run_path(sys.argv[0],run_name='__main__')
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--config', type=Path, default=ROOT / 'deployment/configs/rl_b_cpu_handoff_v1.json')
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    from reproducibility import repository_path
    config = json.loads(args.config.read_text())
    if config['schema'] != 'ihear.sealed_cpu_handoff.v1':
        parser.error('Unsupported sealed handoff configuration')
    package = repository_path(config['package_root'])
    if package != ROOT / 'research/rl_b_cpu_handoff_v1':
        parser.error('The sealed RL-B package identity is required')
    args.work_dir.mkdir(parents=True, exist_ok=False)
    capsule = args.work_dir.resolve() / 'capsule'
    shutil.copytree(package, capsule,
                    ignore=shutil.ignore_patterns('__pycache__', 'runs', 'cache', 'model_cache', 'model_path_cache', 'test_outputs', '.venv'))
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(PYTHONDONTWRITEBYTECODE='1', MPLBACKEND='Agg', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    checks = []
    for name in ('verify_package.py', 'test_guard.py', 'test_g4.py', 'test_execution_contract.py', 'preflight.py'):
        result = subprocess.run([args.python, '-B', '-c', GUARD, str(capsule / name)],
                                cwd=capsule, env=env, capture_output=True, text=True, timeout=90)
        (args.work_dir / (name + '.log')).write_text(result.stdout + '\nSTDERR\n' + result.stderr)
        checks.append(dict(check=name, status='PASS' if result.returncode == 0 else 'FAIL', returncode=result.returncode))
    result = subprocess.run([args.python, '-B', '-c',
                             'import json,platform,torch,importlib.metadata as m;print(json.dumps(dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,packages={p:m.version(p) for p in ("mujoco","numpy","scipy","gymnasium","stable_baselines3")})))'],
                            env=env, capture_output=True, text=True, timeout=90)
    runtime = json.loads(result.stdout) if result.returncode == 0 else dict(error=result.stderr)
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in checks) and result.returncode == 0 else 'FAIL',
                  scope='ENVIRONMENT_IMPORT_AND_UNIT_TESTS_ONLY', runtime=runtime, checks=checks,
                  physics_steps=0, training='NOT_RUN', physical_qualification='NOT_RUN',
                  cloud='UNVERIFIED', original_READINESS_json='UNCHANGED',
                  source_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
                  config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                  sealed_manifest_sha256=hashlib.sha256(repository_path(config['sealed_identity']).read_bytes()).hexdigest(),
                  dependency_lock_sha256=hashlib.sha256(repository_path(config['dependency_lock']).read_bytes()).hexdigest(),
                  training_seeds=config['seeds'], checkpoint_restore_execution='NOT_RUN_NO_ORIGINAL_RL_B_CHECKPOINT',
                  recent_german_server_version=config['recent_german_server_version'])
    (args.work_dir / 'RL_B_ENVIRONMENT_CHECK.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()
