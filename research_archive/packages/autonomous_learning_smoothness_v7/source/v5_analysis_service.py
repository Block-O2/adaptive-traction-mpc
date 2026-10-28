"""Finite, deadline-bound zero-physics analysis of completed registered attempts."""
from pathlib import Path
import os,sys,time,json,traceback,datetime,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
import v5_metrics as metrics,v5_execution_analysis as execution,v5_tail_analysis as tail,v5_native_wrench_analysis as native
A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix']-2700;processed=set();errors=[]
def put(n,x):
 p=P/n;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
put('owned/ANALYSIS_SERVICE_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline,max_iterations=1200,zero_new_native_steps=True,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
try:
 for iteration in range(1200):
  if time.time()>=deadline or (P/'CLOSURE_START.json').exists() or (P/'END.json').exists():break
  count=0
  for f in sorted((P/'attempts').glob('*_RESULT.json')):
   ident=f.name[:-12]
   if ident in processed:continue
   r=json.loads(f.read_text());group=ident.split('_')[0]
   # The live optimizer writes its own extended score; avoid duplicate writes.
   if group.startswith('OPT') and not (P/'jobs'/group/'WORKER_DONE.json').exists():continue
   if not r['complete']:processed.add(ident);continue
   try:
    metrics.evaluate(ident);execution.analyze(ident)
    if not (P/'analysis/native_wrench'/(ident+'.json')).exists():native.analyze(ident)
    processed.add(ident);count+=1
   except BaseException as e:
    errors.append(dict(id=ident,utc=utc(),error=str(e),traceback=traceback.format_exc()));processed.add(ident)
    put('audit/ANALYSIS_ERRORS.json',errors);print('ANALYSIS_ERROR',ident,str(e),flush=True)
  for cfg in (P/'experiments').glob('TAIL*.json'):
   group=cfg.stem
   if not (P/'jobs'/group/'PHYSICS_DONE.json').exists() or (P/'analysis/tail'/(group+'.json')).exists():continue
   try:tail.group(group)
   except BaseException as e:
    errors.append(dict(group=group,utc=utc(),error=str(e),traceback=traceback.format_exc()));put('audit/ANALYSIS_ERRORS.json',errors);print('TAIL_ANALYSIS_ERROR',group,str(e),flush=True)
  if count:put('STATUS.json',dict(state='RUNNING',updated_UTC=utc(),activation=A['id'],completed_analysis=len(processed),analysis_errors=len(errors)))
  time.sleep(20)
finally:put('owned/ANALYSIS_SERVICE_END.json',dict(pid=os.getpid(),utc=utc(),processed=len(processed),errors=len(errors),zero_new_native_steps=True))
