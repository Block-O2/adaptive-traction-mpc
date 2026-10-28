"""Finite queue owner with live-job adoption and per-job descendant stopping."""
from pathlib import Path
import os,sys,time,signal,json,subprocess,shutil
from acl2_shared import P,R,read,put,utc,sha
A=read('ACTIVATION.json');deadline=A['hard_stop_unix']
def alive(pid,command=None):
 try:
  stat=Path('/proc',str(pid),'stat').read_text();state=stat[stat.rfind(')')+2:].split()[0]
  if state=='Z':return False
  if command and str(command).encode() not in Path('/proc',str(pid),'cmdline').read_bytes():return False
  return True
 except OSError:return False
def descendants(root):
 result={root};parents={}
 for f in Path('/proc').glob('[0-9]*/stat'):
  try:s=f.read_text();parents[int(f.parent.name)]=int(s[s.rfind(')')+2:].split()[1])
  except (OSError,ValueError):pass
 for _ in range(20):
  new={pid for pid,ppid in parents.items() if ppid in result}
  if new<=result:break
  result |= new
 return result
def stop_job(root):
 for sig,grace in [(signal.SIGINT,8),(signal.SIGTERM,5),(signal.SIGKILL,0)]:
  ids=descendants(root)
  for pid in sorted(ids,reverse=True):
   try:os.kill(pid,sig)
   except ProcessLookupError:pass
  end=time.time()+grace
  while time.time()<end and alive(root):time.sleep(.2)
  if not alive(root):return
def completed_status(j,code):
 if code is not None:return 'COMPLETED' if code==0 else 'FAILED_PRESERVED'
 if j['script'].startswith('acl2_worker') and j.get('args'):
  config=read(j['args'][0]);done=P/'jobs'/config['group']/'WORKER_DONE.json'
  if done.exists():return 'COMPLETED' if json.loads(done.read_text())['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS' else 'FAILED_PRESERVED'
 return 'INTERRUPTED_OR_EXIT_STATUS_UNKNOWN_PRESERVED'
def main():
 if len(sys.argv)>1:
  old=int(sys.argv[1]);put('owned/SUPERVISOR_V2_READY.json',dict(pid=os.getpid(),utc=utc(),adopt_from_pid=old))
  for _ in range(100):
   if not alive(old):break
   time.sleep(.1)
  assert not alive(old),'OLD_OWNER_STILL_ALIVE'
 put('owned/SUPERVISOR_START_v2.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline,source_sha256=sha(__file__),original_T0=A['T0_utc']))
 for tick in range(20000):
  if time.time()>=deadline-20 or (P/'END.json').exists() or (P/'STOP_REQUESTED').exists():break
  for f in sorted((P/'queue').glob('*.json')):
   j=json.loads(f.read_text());jid=j['id'];out=P/'jobs'/jid
   if (out/'END.json').exists():continue
   if (P/'STOP_REQUESTED').exists():break
   adopted=(out/'START.json').exists();proc=None;start=None;info=None
   if adopted:
    info=read('jobs/'+jid+'/START.json');root=info['pid'];command=info['command'][1];start=info.get('start_unix',info['absolute_deadline_unix']-j['timeout_s']);local_deadline=info['absolute_deadline_unix']
    if not alive(root,command):
     put('jobs/'+jid+'/END.json',dict(status=completed_status(j,None),utc=utc(),adopted_after_prior_owner_exit=True,no_retry_or_duplicate_native=True));continue
    put('jobs/'+jid+'/OWNER_ADOPTION.json',dict(utc=utc(),original_pid=root,new_owner_pid=os.getpid(),original_deadline_unix=local_deadline,original_T0=A['T0_utc'],no_process_or_physics_restart=True))
   else:
    if j.get('requires') and not all((P/x).exists() for x in j['requires']):continue
    if time.time()<j.get('not_before_unix',0):continue
    if time.time()>min(j['latest_start_unix'],deadline-j['timeout_s']):put('jobs/'+jid+'/END.json',dict(status='NOT_RUN_DEADLINE',utc=utc()));continue
    if shutil.disk_usage(P).free<18*2**30:put('jobs/'+jid+'/END.json',dict(status='NOT_RUN_DISK_FLOOR',utc=utc()));continue
    out.mkdir(exist_ok=True);cmd=[sys.executable,str(P/'source'/j['script'])]+j.get('args',[]);env=os.environ.copy();env.update(ACL2_PACKAGE=str(P),ACL2_OWNER=A['identity'],PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(R/'tmp'),MPLCONFIGDIR=str(R/'tmp/mpl'))
    stdout=(out/'stdout.log').open('ab');stderr=(out/'stderr.log').open('ab');proc=subprocess.Popen(cmd,env=env,stdout=stdout,stderr=stderr,start_new_session=True,cwd=P);stdout.close();stderr.close();root=proc.pid;command=cmd[1];start=time.time();local_deadline=min(start+j['timeout_s'],deadline)
    put('jobs/'+jid+'/START.json',dict(id=jid,pid=root,owner_pid=os.getpid(),utc=utc(),start_unix=start,command=cmd,source_sha256=sha(P/'source'/j['script']),absolute_deadline_unix=local_deadline))
   while alive(root,command):
    if time.time()>local_deadline or time.time()>deadline-10 or (P/'STOP_REQUESTED').exists():stop_job(root);break
    put('STATUS.json',dict(status='RUNNING',job=jid,pid=root,queue_owner_pid=os.getpid(),elapsed_h=(time.time()-A['t0_unix'])/3600,remaining_h=(deadline-time.time())/3600,utc=utc(),adopted_live_job=adopted))
    time.sleep(2)
   code=proc.wait() if proc is not None else None
   put('jobs/'+jid+'/END.json',dict(status=completed_status(j,code),returncode=code,wall_s=time.time()-start,utc=utc(),adopted_live_process=adopted,exit_status_from_worker_record=adopted))
  time.sleep(2)
 put('owned/SUPERVISOR_END_v2.json',dict(pid=os.getpid(),utc=utc(),status='STOP'))
if __name__=='__main__':main()
