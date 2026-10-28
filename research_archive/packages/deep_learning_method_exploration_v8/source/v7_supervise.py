"""One bounded owned job; descendant identity, deadline, RAM/disk and recovery guard."""
from pathlib import Path
import os,sys,json,time,subprocess,signal,hashlib,fcntl
P=Path(__file__).resolve().parents[1];cfg=sys.argv[1];c=json.loads((P/cfg).read_text());a=json.loads((P/'ACTIVATION.json').read_text());g=c['group']
def info(pid):
 try:
  z=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,ppid=int(z[1]),start_ticks=int(z[19]),state=z[0])
 except (FileNotFoundError,ProcessLookupError):return None
def put(n,d):
 p=P/n;p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.'+str(os.getpid())+'.tmp');q.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');q.replace(p)
lock=(P/'owned'/('JOB_'+g+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (P/'owned'/(g+'_SUPERVISOR.json')).exists(),'EXISTING_JOB_REQUIRES_UNIQUE_ID_AND_REVIEW'
cut=min(a['deadline_unix'],time.time()+c.get('job_wall_cap_s',7200));start=time.time();owned={};reason=None
assert cut-time.time()>60,'INSUFFICIENT_TIME'
env=dict(os.environ,ACL2_PACKAGE=str(P),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
log=(P/'logs'/(g+'_worker.log')).open('x')
proc=subprocess.Popen([sys.executable,'-B',str(P/'source'/c['worker']),cfg],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
owned[proc.pid]=info(proc.pid)
put('owned/'+g+'_SUPERVISOR.json',dict(state='RUNNING',identity=info(os.getpid()),worker=owned[proc.pid],activation=a['activation_id'],cutoff_unix=cut,config_sha256=hashlib.sha256((P/cfg).read_bytes()).hexdigest(),started_unix=start))
last=0
try:
 while proc.poll() is None:
  rows=[i for p in Path('/proc').iterdir() if p.name.isdigit() if (i:=info(int(p.name)))];known=set(owned)
  while True:
   extra={r['pid']:r for r in rows if r['ppid'] in known and r['pid'] not in known}
   if not extra:break
   owned.update(extra);known.update(extra)
  mem=dict(z.split(':',1) for z in Path('/proc/meminfo').read_text().splitlines());ram=int(mem['MemAvailable'].split()[0])*1024;disk=os.statvfs(P).f_bavail*os.statvfs(P).f_frsize
  if time.time()-last>10:
   last=time.time();live=[i for pid,old in owned.items() if (i:=info(pid)) and old and i['start_ticks']==old['start_ticks']]
   row=dict(unix=time.time(),owned=live,available_ram_bytes=ram,disk_free_bytes=disk)
   with (P/'logs'/(g+'_RESOURCES.jsonl')).open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
   put('owned/'+g+'_DESCENDANTS.json',dict(known_owned=owned,updated_unix=time.time()))
  if time.time()>=cut:reason='LOCAL_OR_GLOBAL_DEADLINE';break
  if ram<6*2**30 or disk<20*2**30:reason='RAM_OR_DISK_FLOOR';break
  if (P/'STOP_REQUESTED').exists():reason='STOP_REQUESTED';break
  time.sleep(.5)
finally:
 if proc.poll() is None:
  for pid,old in reversed(list(owned.items())):
   cur=info(pid)
   if old and cur and cur['start_ticks']==old['start_ticks'] and cur['state']!='Z':
    try:os.kill(pid,signal.SIGINT)
    except ProcessLookupError:pass
  try:proc.wait(timeout=20)
  except subprocess.TimeoutExpired:
   for pid,old in reversed(list(owned.items())):
    cur=info(pid)
    if old and cur and cur['start_ticks']==old['start_ticks'] and cur['state']!='Z':
     try:os.kill(pid,signal.SIGTERM)
     except ProcessLookupError:pass
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:
    for pid,old in reversed(list(owned.items())):
     cur=info(pid)
     if old and cur and cur['start_ticks']==old['start_ticks']:
      try:os.kill(pid,signal.SIGKILL)
      except ProcessLookupError:pass
    proc.wait(timeout=10)
 survivors=[]
 for pid,old in owned.items():
  cur=info(pid)
  if old and cur and cur['start_ticks']==old['start_ticks'] and cur['state']!='Z':survivors.append(cur)
 put('owned/'+g+'_SUPERVISOR_END.json',dict(state='STOP',reason=reason or 'FINITE_REGISTERED_MENU_COMPLETED',worker_exit_code=proc.returncode,known_owned=owned,survivors=survivors,started_unix=start,ended_unix=time.time(),wall_s=time.time()-start))
 print(g,'END',proc.returncode,reason,'wall',time.time()-start,flush=True)
sys.exit(proc.returncode or int(bool(survivors)))
