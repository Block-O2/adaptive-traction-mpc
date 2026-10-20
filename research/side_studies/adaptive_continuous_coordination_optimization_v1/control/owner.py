from pathlib import Path
import subprocess,os,json,time,signal
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');plan=json.loads((P/'RUN_PLAN.json').read_text());assert not (P/'PHYSICS_STOP.json').exists()
cmd=['/home/hank/envs/adaptive-online-rl-v1/bin/python','-B','-u',str(P/'control/campaign.py')]
record=dict(owner_pid=os.getpid(),command=cmd,start_unix=time.time())
with (P/'logs/campaign.log').open('w') as log:
 child=subprocess.Popen(cmd,cwd=P,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);record['pid']=child.pid;(P/'control/OWNER.json').write_text(json.dumps(record));print(json.dumps(record),flush=True)
 try:code=child.wait(timeout=max(1,plan['physics_hard_stop_unix']-time.time()))
 except BaseException as e:
  record['error']=repr(e);os.killpg(child.pid,signal.SIGINT)
  try:code=child.wait(timeout=20)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=10)
record.update(end_unix=time.time(),returncode=code,joined=True);(P/'control/OWNER.json').write_text(json.dumps(record,indent=2));print(json.dumps(record));raise SystemExit(code)
