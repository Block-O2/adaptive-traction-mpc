"""主审另批外部单CPU/timeout launcher；不修改已冻结 fit source。"""
from pathlib import Path
import hashlib
import json
import os
import time

P=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
S=P/'families/il_dagger_sac/discrete_sac_v1/solver_floor_v7'
approval=S/'MAIN_APPROVAL_V7.json'
assert hashlib.sha256(approval.read_bytes()).hexdigest()=='979b4c0565eb851d6f626788372c60e41ae54932b3b351399e8dff2e3950fcde'
assert not (S/'EXECUTION_ATTEMPT_V1.json').exists() and not (S/'fit_run_v7').exists()
assert time.time()<1793114740.
before=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{min(before)})
actual=sorted(os.sched_getaffinity(0));assert actual==[min(before)]
env=dict(os.environ)
env['PYTHONDONTWRITEBYTECODE']='1'
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):env[key]='1'
argv=['/usr/bin/timeout','--signal=TERM','--kill-after=2s','60s',
      '/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/offline-env/bin/python','-B',
      str(S/'source/execute_approved_once.py'),'--package',str(P),'--approval',
      'families/il_dagger_sac/discrete_sac_v1/solver_floor_v7/MAIN_APPROVAL_V7.json']
with (S/'EXTERNAL_LAUNCH_AFFINITY_V1.json').open('x') as f:
    json.dump({'schema':'v8.exact_terminal_critic.external_affinity_launcher.v1','PID_before_exec':os.getpid(),
               'wall_unix':time.time(),'affinity_before':before,'actual_affinity_after_set':actual,
               'exec_inherits_same_PID_CPU_affinity':True,'argv':argv,
               'threads':{k:env[k] for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS')},
               'approval_sha256':hashlib.sha256(approval.read_bytes()).hexdigest(),
               'launcher_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'new_physics':0,'automatic_retry':False},f,ensure_ascii=False,indent=2)
    f.write('\n');f.flush();os.fsync(f.fileno())
os.execve(argv[0],argv,env)
