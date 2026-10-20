from pathlib import Path
import os,json,time,signal,subprocess,sys
P=Path(__file__).resolve().parents[1];plan=json.loads((P/'RUN_PLAN.json').read_text());group=sys.argv[1] if len(sys.argv)>1 else 'interface1'
assert not (P/'PHYSICS_STOP.json').exists()
cmd=['/home/hank/envs/adaptive-online-rl-v1/bin/python','-B','-u',str(P/'control/physical_runner.py'),group]
record=dict(owner_pid=os.getpid(),group=group,command=cmd,start_unix=time.time())
path=P/'control'/('OWNER_'+group+'.json')
with (P/'logs'/(group+'.log')).open('w') as log:
 child=subprocess.Popen(cmd,cwd=P,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);record['pid']=child.pid;path.write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
 try:code=child.wait(timeout=min(2500,max(1,plan['physics_hard_stop_unix']-time.time()-30)))
 except BaseException as e:
  record['owner_exception']=repr(e)
  if child.poll() is None:
   os.killpg(child.pid,signal.SIGINT)
   try:code=child.wait(timeout=30)
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGTERM)
    try:code=child.wait(timeout=15)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=10)
  else:code=child.returncode
record.update(end_unix=time.time(),returncode=code,joined=True);path.write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
sys.exit(0 if code==0 else 1)
