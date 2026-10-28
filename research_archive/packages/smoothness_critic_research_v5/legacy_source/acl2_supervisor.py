"""Server-owned finite queue; survives SSH and never changes activation time."""
import os,sys,time,signal,subprocess,traceback,shutil
from pathlib import Path
from acl2_shared import P,R,put,read,utc,append
A=read('ACTIVATION.json');deadline=A['hard_stop_unix'];os.environ['ACL2_OWNER']=A['identity']
def owned():
 out=[]
 for f in Path('/proc').glob('[0-9]*/environ'):
  try:
   if ('ACL2_OWNER='+A['identity']).encode()+b'\0' in f.read_bytes():out.append(int(f.parent.name))
  except (OSError,PermissionError):pass
 return out
def stop_pids(pids,sig):
 for pid in pids:
  if pid==os.getpid():continue
  try:os.kill(pid,sig)
  except ProcessLookupError:pass
def watchdog():
 put('owned/WATCHDOG_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline))
 for _ in range(40000):
  if (P/'END.json').exists():break
  if time.time()>=deadline or (P/'STOP_ALL').exists():
   put('STOP_REQUESTED',dict(utc=utc(),reason='HARD_DEADLINE_OR_EXPLICIT_STOP'));pids=owned();stop_pids(pids,signal.SIGTERM);time.sleep(5);stop_pids(owned(),signal.SIGKILL)
   put('WATCHDOG_END.json',dict(status='STOP',utc=utc(),owned_signalled=pids));return
  time.sleep(2)
 put('WATCHDOG_END.json',dict(status='STOP',utc=utc(),reason='END_OR_FINITE_LIMIT'))
def supervisor():
 put('owned/SUPERVISOR_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline))
 # The queue can receive further finite, preregistered jobs while this owner lives.
 for tick in range(20000):
  if time.time()>=deadline-20 or (P/'END.json').exists() or (P/'STOP_REQUESTED').exists():break
  for f in sorted((P/'queue').glob('*.json')):
   j=__import__('json').loads(f.read_text());jid=j['id'];out=P/'jobs'/jid
   if (out/'END.json').exists():continue
   if (out/'START.json').exists():
    put('jobs/'+jid+'/END.json',dict(status='INTERRUPTED_NOT_AUTO_RETRIED',utc=utc()));continue
   if j.get('requires') and not all((P/x).exists() for x in j['requires']):continue
   if time.time()>min(j['latest_start_unix'],deadline-j['timeout_s']):
    put('jobs/'+jid+'/END.json',dict(status='NOT_RUN_DEADLINE',utc=utc()));continue
   if shutil.disk_usage(P).free<18*2**30:
    put('jobs/'+jid+'/END.json',dict(status='NOT_RUN_DISK_FLOOR',utc=utc()));continue
   out.mkdir(exist_ok=True);cmd=[sys.executable,str(P/'source'/j['script'])]+j.get('args',[])
   env=os.environ.copy();env.update(ACL2_PACKAGE=str(P),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(R/'tmp'),MPLCONFIGDIR=str(R/'tmp/mpl'))
   with (out/'stdout.log').open('ab') as stdout,(out/'stderr.log').open('ab') as stderr:
    proc=subprocess.Popen(cmd,env=env,stdout=stdout,stderr=stderr,start_new_session=True,cwd=P)
    start=time.time();put('jobs/'+jid+'/START.json',dict(id=jid,pid=proc.pid,owner_pid=os.getpid(),utc=utc(),command=cmd,source_sha256=__import__('acl2_shared').sha(P/'source'/j['script']),absolute_deadline_unix=min(start+j['timeout_s'],deadline)))
    while proc.poll() is None:
     if time.time()>min(start+j['timeout_s'],deadline-10) or (P/'STOP_REQUESTED').exists():
      # Forked physical children establish sessions; environment identity closes
      # all task descendants while leaving this supervisor/watchdog alive.
      pids=[p for p in owned() if p not in [os.getpid(),read('owned/WATCHDOG_START.json')['pid']]]
      stop_pids(pids,signal.SIGINT);time.sleep(5);stop_pids([p for p in pids if Path('/proc',str(p)).exists()],signal.SIGTERM)
      try:proc.wait(timeout=15)
      except subprocess.TimeoutExpired:stop_pids(pids,signal.SIGKILL);proc.wait()
      break
     put('STATUS.json',dict(status='RUNNING',job=jid,pid=proc.pid,elapsed_h=(time.time()-A['t0_unix'])/3600,remaining_h=(deadline-time.time())/3600,utc=utc()))
     time.sleep(2)
   put('jobs/'+jid+'/END.json',dict(status='COMPLETED' if proc.returncode==0 else 'FAILED_PRESERVED',returncode=proc.returncode,wall_s=time.time()-start,utc=utc()))
   if (P/'END.json').exists():break
  time.sleep(2)
 put('owned/SUPERVISOR_END.json',dict(pid=os.getpid(),utc=utc(),status='STOP'))
if __name__=='__main__':
 if sys.argv[1]=='watchdog':watchdog()
 else:supervisor()
