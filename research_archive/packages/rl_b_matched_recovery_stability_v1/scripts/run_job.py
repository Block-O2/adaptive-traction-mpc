from pathlib import Path
import os,sys,time,json,subprocess,signal,hashlib,shutil
r=Path(__file__).resolve().parents[1];name=sys.argv[1];limit=int(sys.argv[2]);cmd=sys.argv[3:];p=r/'audit/jobs'/name;p.mkdir(parents=True,exist_ok=False)
t=time.time();start={'unix':t,'command':cmd,'cwd':os.getcwd(),'timeout_s':limit,'pid':os.getpid(),'new_training_authorized':False};(p/'START.json').write_text(json.dumps(start,indent=2))
env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
reason=None
with (p/'stdout.log').open('wb') as out,(p/'stderr.log').open('wb') as err:
 child=subprocess.Popen(cmd,stdout=out,stderr=err,env=env,start_new_session=True);start['child_pid']=child.pid;(p/'START.json').write_text(json.dumps(start,indent=2))
 while child.poll() is None:
  now=time.time();study=json.loads((r/'audit/STUDY_START.json').read_text())
  if now-t>limit:reason='PROCESS_TIMEOUT'
  elif now>__import__('datetime').datetime.fromisoformat(study['hard_deadline']).timestamp():reason='STUDY_DEADLINE'
  elif (r/'audit/RESOURCE_STOP').exists():reason='RESOURCE_STOP'
  if reason:
   os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
   break
  time.sleep(1)
 code=child.wait()
(p/'END.json').write_text(json.dumps({'unix':time.time(),'wall_s':time.time()-t,'exit_code':code,'stop_reason':reason,'child_pid':child.pid,'child_joined':True},indent=2))
print(json.dumps({'job':name,'exit_code':code,'stop_reason':reason,'wall_s':time.time()-t,'logs':str(p)}));sys.exit(code if code>=0 else 1)
