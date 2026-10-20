from pathlib import Path
import os,sys,json,subprocess,time,signal
P=Path(__file__).resolve().parents[1];plan=json.loads((P/'RUN_PLAN.json').read_text());record=dict(owner_pid=os.getpid(),start_unix=time.time(),kind='baseline audit only')
cmd=['/home/hank/envs/adaptive-online-rl-v1/bin/python','-B','-u',str(P/'control/baseline_runner.py')]
with (P/'logs/baseline.log').open('w') as log:
 child=subprocess.Popen(cmd,cwd=P,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);record.update(pid=child.pid,command=cmd);(P/'control/BASELINE_OWNER.json').write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
 try:code=child.wait(timeout=min(1300,max(1,plan['physics_hard_stop_unix']-time.time()-60)))
 except BaseException as e:
  record['exception']=repr(e)
  if child.poll() is None:
   os.killpg(child.pid,signal.SIGINT)
   try:code=child.wait(timeout=30)
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGTERM)
    try:code=child.wait(timeout=15)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=10)
  else:code=child.returncode
record.update(returncode=code,end_unix=time.time(),joined=True);(P/'control/BASELINE_OWNER.json').write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
sys.exit(0 if code==0 else 1)
