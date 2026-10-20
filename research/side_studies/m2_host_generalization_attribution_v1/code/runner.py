"""One durable sequential owner; failed dispatches count, finished IDs never replay."""
from pathlib import Path
import json,time,subprocess,os,sys,signal,hashlib,fcntl,shutil,traceback
from accounting import record,attempts,migrate
STUDY=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1');L=STUDY/'output';Q=STUDY/'queue';Q.mkdir(exist_ok=True)
def save(p,x):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)
def sample(owner=None,filename='RESOURCE_LOG.jsonl'):
 mem={k:int(v.split()[0])*1024 for k,v in [line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines()]}
 vm=dict(line.split() for line in Path('/proc/vmstat').read_text().splitlines())
 proc=[];parent={}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   d=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line);parent[int(p.name)]=int(d['PPid'])
  except (OSError,ValueError):pass
 owned={os.getpid()}
 for role in ('runner','controller'):
  try:
   pid=int((STUDY/(role+'.lock')).read_text());p=Path('/proc')/str(pid);cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode();cwd=(p/'cwd').resolve()
   if role+'.py' in cmd and (cwd==STUDY or '/b_native_learning_matrix_v1/'+role+'.py' in cmd or str(STUDY/'code'/(role+'.py')) in cmd):owned.add(pid)
  except (OSError,ValueError):pass
 while True:
  nxt=owned|{p for p,pp in parent.items() if pp in owned}
  if nxt==owned:break
  owned=nxt
 for pid in owned:
  try:
   p=Path('/proc')/str(pid);sm=dict(line.split(':',1) for line in (p/'smaps_rollup').read_text().splitlines()[1:]);proc.append(dict(pid=pid,ppid=parent.get(pid),PSS=int(sm['Pss'].split()[0])*1024,cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),cpu_ticks=[int(v) for v in (p/'stat').read_text().rsplit(') ',1)[1].split()[11:13]]))
  except OSError:pass
 win=None
 try:
  cmd=['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-Command',"$osr=Get-CimInstance Win32_OperatingSystem; $m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; @{available=[double]$osr.FreePhysicalMemory*1024;commit_headroom=[double]$m.CommitLimit-[double]$m.CommittedBytes;disk_c=(Get-PSDrive C).Free}|ConvertTo-Json -Compress"]
  win=json.loads(subprocess.check_output(cmd,text=True,timeout=20))
 except Exception as e:win={'error':str(e)}
 row=dict(cpu_load=os.getloadavg(),cpu_ticks_system=[int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:]],clock_ticks=os.sysconf('SC_CLK_TCK'),unix=time.time(),owner=owner,mem_available=mem['MemAvailable'],swap_used=mem['SwapTotal']-mem['SwapFree'],swap_in=int(vm['pswpin']),swap_out=int(vm['pswpout']),oom_kill=int(vm.get('oom_kill',0)),psi=Path('/proc/pressure/memory').read_text(),disk_free=shutil.disk_usage(STUDY).free,windows=win,processes=proc,process_count=len(parent),owned_count=len(proc),PSS=sum(p['PSS'] for p in proc))
 with (L/filename).open('a') as f:f.write(json.dumps(row)+'\n')
 return row
def main():
 lock=(STUDY/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.write(str(os.getpid()));lock.flush()
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text()) if (STUDY/'TASK_LEDGER.json').exists() else {}
 migrate()
 # Interrupted attempts never silently rerun; explicit retry gets another ID.
 for item in ledger.values():
  if item['status']=='RUNNING':item.update(status='INTERRUPTED',ended_unix=time.time())
 save(STUDY/'TASK_LEDGER.json',ledger)
 child=None;last_sample=0;last_progress=0;history=[];pause_since=None;healthy=0;recovery_check=None;recovery_level=0;stop_sent=None
 try:
  while time.time()<cfg['deadline_unix']-900:
   if (STUDY/'STOP_DISPATCH').exists():break
   now=time.time()
   if now>=cfg['dispatch_cutoff_unix'] and child is None:break
   if now-last_sample>=45:
    row=sample(None if child is None else child.pid);history.append(row);history=history[-5:];last_sample=now
    immediate=row['mem_available']<.35*2**30 or row['windows'].get('commit_headroom',10*2**30)<.35*2**30 or (len(history)>1 and row['oom_kill']>history[-2]['oom_kill'])
    pressure=len(history)>=4 and row['unix']-history[-4]['unix']>=120 and all(x['mem_available']<1.25*2**30 for x in history[-4:]) and (row['swap_in']-history[-4]['swap_in']+row['swap_out']-history[-4]['swap_out']>4096)
    if immediate or pressure:
     if pause_since is None:pause_since=now;recovery_level=0;recovery_check=now+300
     healthy=0;save(STUDY/'RESOURCE_STATE.json',dict(state='RECOVER' if immediate else 'PAUSE_DISPATCH',since=pause_since,row=row))
     if immediate and child is not None and stop_sent is None:os.killpg(child.pid,signal.SIGINT);stop_sent=now
    elif pause_since is not None:
     healthy+=1
     if healthy>=4 and now>=recovery_check:pause_since=None;recovery_check=None;save(STUDY/'RESOURCE_STATE.json',dict(state='HEALTHY',unix=now,healthy_samples=healthy))
    if pause_since is not None and now>=recovery_check:
     recovery_level=min(2,recovery_level+1);recovery_check=now+[300,600,1200][recovery_level];save(STUDY/'RESOURCE_BACKOFF.json',dict(since=pause_since,next_check_unix=recovery_check,level=recovery_level,healthy_samples=healthy,rule='5 -> 10 -> 20 minutes; resource samples continue every45s'))
    if pause_since is not None and now-pause_since>=3600:break
   if child is not None and child.poll() is not None:
    code=child.wait();log.close();result=Path(current['result_path']);item=ledger[current['id']]
    item.update(status='COMPLETE' if result.exists() else 'FAILED_NO_RESULT',returncode=code,ended_unix=time.time())
    if result.exists():
     result_record=json.loads(result.read_text());item['worker_status']=result_record['status'];item['result_sha256']=hashlib.sha256(result.read_bytes()).hexdigest()
    save(STUDY/'TASK_LEDGER.json',ledger);child=None;stop_sent=None
    record('END',current['id'],status=item['status'],worker_status=item.get('worker_status'),returncode=code)
    # Joined parent implies no further valid work in any unfinished child ID.
    rows=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ended={r['id'] for r in rows if r['event']=='END'}
    for event in rows:
     if event['event']=='START' and event['id'] not in ended and event.get('config',{}).get('group')==current.get('group') and event['id']!=current['id']:record('END',event['id'],status='INTERRUPTED_PARENT_EXIT',reason='parent joined; branch did not produce its own END')
   if child is not None and child.poll() is None:
    rows=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];latest=max([r['unix'] for r in rows if r['id']==current['id'] or r.get('config',{}).get('group')==current.get('group')] or [ledger[current['id']]['started_unix']])
    # Quiet complete episodes and branches have sparse logs. Allow >=20/30min
    # and eight times recent comparable wall times before diagnosing a stall.
    ended={r['id']:r for r in rows if r['event']=='END'};recent=[]
    for event in rows:
     if event['event']=='START' and event['id'] in ended and ended[event['id']]['unix']>event['unix']:
      config=event.get('config',{});comparable=('snapshot' in config) if current.get('mode') in ('branches','audit','synergy') else config.get('mode','table')==current.get('mode','table')
      if comparable:recent.append(ended[event['id']]['unix']-event['unix'])
    threshold=max(1800 if current.get('mode') in ('branches','audit','synergy') else 1200,8*max(recent[-12:] or [150]))
    if now-latest>threshold and stop_sent is None:
     save(STUDY/'TIMEOUT_'+current['id']+'.json',dict(unix=now,last_activity_unix=latest,threshold_s=threshold,recent_walls_s=recent[-12:],reason='generous same-stage quiet timeout; original wall clock retained'));os.killpg(child.pid,signal.SIGINT);stop_sent=now
    if stop_sent is not None and now-stop_sent>60:os.killpg(child.pid,signal.SIGTERM)
   if now-last_progress>=900:
    (STUDY/'PROGRESS.md').write_text(f'Updated {time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(now))} UTC\nElapsed {(now-cfg["start_unix"])/3600:.3f} h /9 h\nAttempts including branches {attempts()}/160\nCurrent {None if child is None else current["id"]}\nCompleted top-level tasks {sum(x["status"]=="COMPLETE" for x in ledger.values())}\nNext: oldest unattempted queued task; campaign controller maintains method stages.\n')
    last_progress=now
   if child is None and pause_since is None and now<cfg['dispatch_cutoff_unix']:
    pending=[p for p in sorted(Q.glob('*.json')) if p.stem not in ledger]
    if pending:
     if attempts()>=cfg['max_physics_attempts']:break
     current=json.loads(pending[0].read_text());assert current['id']==pending[0].stem
     assert current.get('kind','physics')=='physics','ONLY_COUNTED_PHYSICS_QUEUE'
     row=history[-1] if history else sample()
     estimated=current.get('estimated_output_bytes',120*2**20)
     if min(row['disk_free'],row['windows'].get('disk_c',row['disk_free']))<estimated+1024**3:pause_since=now;healthy=0;recovery_level=0;recovery_check=now+300;continue
     ledger[current['id']]=dict(status='RUNNING',started_unix=now,input_sha256=hashlib.sha256(pending[0].read_bytes()).hexdigest(),config=current)
     record('START',current['id'],config=current,input_sha256=ledger[current['id']]['input_sha256'],code_manifest_sha256=hashlib.sha256((STUDY/'CODE_MANIFEST.json').read_bytes()).hexdigest())
     save(STUDY/'TASK_LEDGER.json',ledger)
     log=(L/(current['id']+'_WORKER.log')).open('w')
     child=subprocess.Popen([sys.executable,'-u',str(STUDY/'code/worker.py'),str(pending[0])],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
     print(json.dumps(dict(dispatch=current['id'],attempts=attempts(),unix=now)),flush=True)
   time.sleep(1)
 finally:
  if child is not None:
   try:os.killpg(child.pid,signal.SIGINT)
   except ProcessLookupError:pass
   try:child.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=20)
   log.close();ledger[current['id']].update(status='INTERRUPTED_AT_CLOSEOUT',ended_unix=time.time());save(STUDY/'TASK_LEDGER.json',ledger)
  save(STUDY/'RUNNER_STOP.json',dict(unix=time.time(),attempts=attempts(),elapsed_s=time.time()-cfg['start_unix'],reason='wall/resource/budget/explicit stop marker'))
if __name__=='__main__':main()
