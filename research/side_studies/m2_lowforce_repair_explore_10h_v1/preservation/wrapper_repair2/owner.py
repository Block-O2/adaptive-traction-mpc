from pathlib import Path
import os,sys,json,time,subprocess,signal,fcntl,traceback
S=Path(sys.argv[1]);PY=sys.executable
def put(n,x):
 p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');t.replace(p)
def ledger():return [json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()] if (S/'ATTEMPTS.jsonl').exists() else []
def run(cmd,label,timeout):
 plan=json.loads((S/'RUN_PLAN.json').read_text());remaining=plan['hard_stop_unix']-time.time()-120
 if remaining<=0:raise RuntimeError('HARD_STOP_CLOSEOUT')
 with (S/'logs'/(label+'.log')).open('a') as log:
  p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  put('OWNER.json',dict(pid=os.getpid(),active_pid=p.pid,active_pgid=p.pid,phase=label,unix=time.time(),status='RUNNING'))
  try:rc=p.wait(timeout=min(timeout,remaining))
  except subprocess.TimeoutExpired:
   sub=S/'PIPELINE_CHILD.json'
   if sub.exists():
    info=json.loads(sub.read_text())
    if info.get('parent_pid')==p.pid and info.get('pgid'):
     try:os.killpg(info['pgid'],signal.SIGTERM)
     except ProcessLookupError:pass
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   started={r['id'] for r in ledger() if r['event']=='START'};ended={r['id'] for r in ledger() if r['event'] in ['END','FAIL','INTERRUPTED']}
   with (S/'ATTEMPTS.jsonl').open('a') as f:
    for ident in sorted(started-ended):f.write(json.dumps(dict(unix=time.time(),event='INTERRUPTED',id=ident,reason='OWNED_STAGE_TIMEOUT',joined=True))+'\n')
   raise RuntimeError('OWNED_STAGE_TIMEOUT:'+label)
  put('OWNER.json',dict(pid=os.getpid(),active_pid=None,phase=label,unix=time.time(),returncode=rc,status='JOINED'))
  if rc:raise RuntimeError('STAGE_FAILURE:'+label+':'+str(rc))
 print(json.dumps(dict(owner_phase_complete=label,attempts=sum(r['event']=='START' for r in ledger()))),flush=True)
lock=(S/'OWNER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
plan=json.loads((S/'RUN_PLAN.json').read_text());put('OWNER_STARTED.json',dict(pid=os.getpid(),unix=time.time(),monotonic=time.monotonic(),plan=plan))
try:
 first='recovery' if (S/'WRAPPER_REPAIR1_REGISTERED.json').exists() else 'baseline'
 run([PY,str(S/'code/worker.py'),first],first,2700)
 # Wait only for required implementation readiness, never to fill the research budget.
 deadline=min(time.time()+1200,plan['dispatch_cutoff_unix']-1800)
 while not (S/'PIPELINE_READY.json').exists():
  if time.time()>deadline:raise RuntimeError('PIPELINE_NOT_READY')
  time.sleep(2)
 run([PY,str(S/'code/pipeline.py')],'pipeline',plan['hard_stop_unix']-time.time()-180)
except BaseException as e:
 put('OWNER_ERROR.json',dict(unix=time.time(),reason=str(e),traceback=traceback.format_exc(),physics_stopped=True))
finally:
 if (S/'code/finalize.py').exists():
  try:run([PY,str(S/'code/finalize.py')],'finalize',900)
  except BaseException as e:put('FINALIZE_ERROR.json',dict(unix=time.time(),reason=str(e)))
 put('OWNER_EXITED.json',dict(pid=os.getpid(),unix=time.time(),elapsed_s=time.time()-plan['t0_unix'],owned_children_joined=True,status='STOPPED',no_followup=True))
