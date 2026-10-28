"""Serial validation only; no PPO. First infrastructure failure stops dispatch."""
from pathlib import Path
import json,subprocess,sys,datetime
ROOT=Path(__file__).resolve().parent;PY='/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python'
plan=[('repair_random_01','run_rollout.py',['--policy','random']),('repair_hold_01','run_rollout.py',['--policy','hold']),('repair_return_hold_01','cloud_g4_cases.py',['--case','return_hold']),('repair_outbound_TEST_ONLY_01','cloud_g4_cases.py',['--case','outbound_timeout_injection']),('repair_return_TEST_ONLY_01','cloud_g4_cases.py',['--case','return_timeout_injection'])]
plan.append(('repair_safety_TEST_ONLY_01','safety_TEST_ONLY.py',[]))
for name,script,extra in plan:
 now=datetime.datetime.now(datetime.timezone.utc)
 if now>=datetime.datetime.fromisoformat('2026-10-20T10:17:23+00:00'):raise RuntimeError('FINAL_30_MINUTE_PHYSICS_LOCKOUT')
 ends=list((ROOT/'runs').glob('*/END.json'))
 if any(json.loads(x.read_text()).get('error') or json.loads(x.read_text()).get('returncode') for x in ends):raise RuntimeError('PRIOR_INFRASTRUCTURE_FAILURE_REQUIRES_REVIEW')
 out='runs/'+name;argv=[PY,'resource_guard.py','--out',out,'--seconds','240','--',PY,script,'--enable',*extra,'--out',out+'/physics']
 print('DISPATCH',name,now.isoformat(),flush=True)
 r=subprocess.run(argv,cwd=ROOT)
 if r.returncode:raise RuntimeError('GUARDED_RUN_FAILED:'+name)
 print('CLOSED',name,datetime.datetime.now(datetime.timezone.utc).isoformat(),flush=True)
