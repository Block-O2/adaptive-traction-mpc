"""Single finite owned worker; fixed deadline and identity-checked descendant cleanup."""
from pathlib import Path
import os,sys,json,time,subprocess,signal,hashlib
P=Path(__file__).resolve().parents[1];cfg=sys.argv[1];c=json.loads((P/cfg).read_text());a=json.loads((P/'ACTIVATION.json').read_text());group=c['group'];out=P/'owned'/(group+'_SUPERVISOR.json');assert not out.exists(),'UNIQUE_JOB_ID'
def info(pid):
 try:
  s=(Path('/proc')/str(pid)/'stat').read_text();parts=s[s.rindex(')')+2:].split();return dict(pid=pid,ppid=int(parts[1]),start_ticks=int(parts[19]),state=parts[0])
 except (FileNotFoundError,ProcessLookupError):return None
def put(path,d):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(path)
cut=min(a['hard_stop_unix']-2400,time.time()+c.get('job_wall_cap_s',5400));env=dict(os.environ,ACL2_PACKAGE=str(P),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');start=time.time();owned={};stop=None
log=(P/'logs'/(group+'_worker.log')).open('w');proc=subprocess.Popen([sys.executable,str(P/'source/v4_worker.py'),cfg],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);owned[proc.pid]=info(proc.pid);put(out,dict(pid=os.getpid(),identity=info(os.getpid()),worker=owned[proc.pid],activation=a['id'],cutoff_unix=cut,config_sha256=hashlib.sha256((P/cfg).read_bytes()).hexdigest(),state='RUNNING'));last=0
try:
 while proc.poll() is None:
  rows=[i for p in Path('/proc').iterdir() if p.name.isdigit() if (i:=info(int(p.name)))];known=set(owned)
  while True:
   extra={r['pid']:r for r in rows if r['ppid'] in known and r['pid'] not in known}
   if not extra:break
   owned.update(extra);known.update(extra)
  if time.time()-last>15:
   last=time.time();mem=dict(z.split(':',1) for z in Path('/proc/meminfo').read_text().splitlines());row=dict(unix=time.time(),worker_pid=proc.pid,owned=[i for pid in owned if (i:=info(pid)) and i['start_ticks']==owned[pid]['start_ticks']],available_ram_bytes=int(mem['MemAvailable'].split()[0])*1024,disk_free_bytes=os.statvfs(P).f_bavail*os.statvfs(P).f_frsize)
   with (P/'logs'/(group+'_RESOURCES.jsonl')).open('a') as f:f.write(json.dumps(row)+'\n')
  if time.time()>=cut:stop='LOCAL_OR_GLOBAL_DEADLINE';break
  if (P/'STOP_REQUESTED').exists():stop='STOP_REQUESTED';break
  time.sleep(.5)
finally:
 if proc.poll() is None:
  for pid,old in owned.items():
   cur=info(pid)
   if cur and cur['start_ticks']==old['start_ticks'] and cur['state']!='Z':
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
  try:proc.wait(timeout=15)
  except subprocess.TimeoutExpired:
   for pid,old in owned.items():
    cur=info(pid)
    if cur and cur['start_ticks']==old['start_ticks']:
     try:os.kill(pid,signal.SIGKILL)
     except ProcessLookupError:pass
   proc.wait(timeout=10)
 survivors=[]
 for pid,old in owned.items():
  cur=info(pid)
  if cur and cur['start_ticks']==old['start_ticks'] and cur['state']!='Z':
   survivors.append(cur)
   try:os.kill(pid,signal.SIGTERM)
   except ProcessLookupError:pass
 put(P/'owned'/(group+'_SUPERVISOR_END.json'),dict(state='STOP',worker_exit_code=proc.returncode,reason=stop or 'FINITE_QUEUE_COMPLETED',wall_s=time.time()-start,known_owned=owned,survivors_found_and_terminated=survivors,activation=a['id']))
 print(group,'END',proc.returncode,'wall',time.time()-start,flush=True)
sys.exit(proc.returncode or 0)
