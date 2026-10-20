"""Launch one registered group and wait; preserve all child logs and failures."""
from pathlib import Path
import subprocess,os,sys,time,json,signal,fcntl
P=Path(__file__).resolve().parents[1]
group=sys.argv[1] if len(sys.argv)>1 else 'reproduction'
plan=json.loads((P/'RUN_PLAN.json').read_text())
assert group in ['reproduction','development']+[r['name'] for r in plan['validation_conditions']]
lock=(P/'OWNER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (P/(group+'_OWNER.json')).exists(),'Never overwrite group owner record'
env=dict(os.environ,STUDY_GROUP=group,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
command=[sys.executable,'-B',str(P/'control/campaign.py')];start=time.time()
with (P/'logs'/(group+'.log')).open('x') as out:
 child=subprocess.Popen(command,cwd=P,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 record=dict(group=group,owner_pid=os.getpid(),child_pid=child.pid,command=command,start_unix=start,log='logs/'+group+'.log')
 (P/(group+'_OWNER_ACTIVE.json')).write_text(json.dumps(record,indent=2)+'\n')
 try:rc=child.wait(timeout=max(1,min(1800,plan['physics_hard_stop_unix']-time.time())))
 except BaseException:
  # The campaign's signal handler owns/join its fork; give it time to exit first.
  os.kill(child.pid,signal.SIGALRM)
  try:rc=child.wait(timeout=45)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGTERM);rc=child.wait(timeout=15)
  raise
 finally:
  record.update(end_unix=time.time(),returncode=child.returncode,joined=child.poll() is not None)
  (P/(group+'_OWNER.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
raise SystemExit(rc)
