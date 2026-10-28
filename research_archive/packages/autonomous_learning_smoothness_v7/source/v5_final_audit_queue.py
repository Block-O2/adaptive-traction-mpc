"""Finite, read-only post-physics audit queue. Never dispatches simulation jobs."""
from pathlib import Path
import os,sys,json,time,subprocess,datetime,hashlib
sys.dont_write_bytecode=True
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix']-600
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]);put('owned/FINAL_AUDIT_QUEUE_START.json',dict(pid=os.getpid(),start_ticks=ticks,utc=utc(),deadline_unix=deadline,maximum_new_physical_START=0,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
results=[];reason='FINITE_POST_PHYSICS_AUDITS_COMPLETED'
try:
 for _ in range(max(1,int(deadline-time.time()))):
  if time.time()>deadline-1800:raise TimeoutError('AUDIT_WAIT_RESERVE')
  if (P/'owned/TAIL_RESCUE_QUEUE_END.json').exists():break
  time.sleep(1)
 else:raise TimeoutError('AUDIT_PREDECESSOR_NOT_FINISHED')
 for _ in range(180):
  missing=[]
  for f in (P/'attempts').glob('*_RESULT.json'):
   r=json.loads(f.read_text())
   if r['complete']:
    ident=r['id']
    for n in ['extended','execution']:
     if not (P/'analysis'/n/(ident+'.json')).exists():missing.append(ident+':'+n)
    cfg=json.loads((P/'experiments'/(ident.split('_')[0]+'.json')).read_text())
    if 'v5_native_wrench.install()' in (P/'source'/cfg['worker']).read_text() and not (P/'analysis/native_wrench'/(ident+'.json')).exists():missing.append(ident+':native_wrench')
  if not (P/'analysis/tail/TAILRESCUE01.json').exists():missing.append('TAILRESCUE01:tail_analysis')
  if not missing:break
  time.sleep(1)
 assert not missing,missing
 tasks=[('v5_validation_summary.py',240),('v5_locked_figure.py',240),('v5_supplement_analysis.py',240),('v5_tail_policy_audit.py',240),('v5_freeze_audit.py',240),('v5_native_integral_aux.py',240),('v5_report.py',240),('v5_checkpoint_index.py',240),('v5_metric_coverage.py',360),('v5_audit_sources.py',360),('receipt_audit_v4.py',1200),('v5_verify_history.py',360)]
 for script,limit in tasks:
  assert time.time()+min(limit,120)<deadline,'AUDIT_DEADLINE'
  args=[sys.executable,'-B',str(P/'source'/script)]
  if script=='v5_verify_history.py':args.append('FINAL')
  start=time.time()
  with (P/'logs'/('FINAL_'+script+'.log')).open('w') as log:
   child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
   put('owned/FINAL_AUDIT_QUEUE_CURRENT.json',dict(pid=child.pid,script=script,started_unix=start))
   try:code=child.wait(timeout=min(limit,max(1,int(deadline-time.time()))))
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,15)
    try:child.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(child.pid,9);child.wait(timeout=10)
    raise TimeoutError('FINITE_AUDIT_TIMEOUT:'+script)
  results.append(dict(script=script,returncode=code,wall_s=time.time()-start))
  put('audit/FINAL_AUDIT_QUEUE_PROGRESS.json',dict(utc=utc(),results=results))
  assert code==0,'AUDIT_FAILED:'+script
except BaseException as error:reason=type(error).__name__+':'+str(error);raise
finally:put('owned/FINAL_AUDIT_QUEUE_END.json',dict(pid=os.getpid(),start_ticks=ticks,utc=utc(),reason=reason,results=results,maximum_new_physical_START=0))
