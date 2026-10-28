from pathlib import Path
import subprocess,os,sys,time,json,signal,fcntl
P=Path(__file__).resolve().parents[1];group=sys.argv[1];mode=sys.argv[2] if len(sys.argv)>2 else 'development'
assert (P/(group+'_TEST_PLAN.json')).exists()
lock=(P/'OWNER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (P/(group+'_OWNER.json')).exists(),'Never overwrite group owner'
plan=json.loads((P/'RUN_PLAN.json').read_text());env=dict(os.environ,STUDY_GROUP=group,STUDY_MODE=mode,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
cmd=[sys.executable,'-B',str(P/'control/campaign_v3.py')]
with (P/'logs'/(group+'.log')).open('x') as out:
 child=subprocess.Popen(cmd,cwd=P,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 rec=dict(group=group,mode=mode,owner_pid=os.getpid(),child_pid=child.pid,command=cmd,start_unix=time.time(),log='logs/'+group+'.log')
 (P/(group+'_OWNER_ACTIVE.json')).write_text(json.dumps(rec,indent=2)+'\n')
 try:rc=child.wait(timeout=max(1,min(7200,plan['physics_hard_stop_unix']-time.time())))
 except BaseException:
  os.kill(child.pid,signal.SIGALRM)
  try:rc=child.wait(timeout=45)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);rc=child.wait(timeout=15)
  raise
 finally:
  rec.update(end_unix=time.time(),returncode=child.returncode,joined=child.poll() is not None)
  (P/(group+'_OWNER.json')).write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps(rec),flush=True)
raise SystemExit(rc)
