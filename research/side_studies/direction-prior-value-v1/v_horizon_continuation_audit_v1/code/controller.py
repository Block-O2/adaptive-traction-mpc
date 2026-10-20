"""Durable phase controller; no physics, no neural imports, no nested coordinator."""
from freeze import *
import fcntl,sys,os
def complete_tasks(names):
 path=STUDY/'TASK_LEDGER.json';ledger=json.loads(path.read_text()) if path.exists() else {}
 def successful(name):
  candidates=[item for key,item in ledger.items() if key==name or item.get('config',{}).get('resume_of')==name]
  return any(item['status']=='COMPLETE' and item.get('worker_status')=='COMPLETE' for item in candidates)
 return all(successful(name) for name in names)
def physics_idle():
 p=STUDY/'ATTEMPTS.jsonl'
 if not p.exists():return True
 rows=[json.loads(x) for x in p.read_text().splitlines()];starts={r['id'] for r in rows if r['event']=='START'};ends={r['id'] for r in rows if r['event']=='END'}
 queued={q.stem for q in (STUDY/'queue').glob('*.json')};return starts<=ends and queued<=starts
def command(script,*args):
 logs=STUDY/'controller_logs';logs.mkdir(exist_ok=True);name=script.replace('.py','')+'_'+'_'.join(str(a) for a in args)
 with (logs/(name+'.log')).open('a') as log:
  code=subprocess.call([sys.executable,'-u',str(LOCAL/script),*[str(a) for a in args]],stdout=log,stderr=subprocess.STDOUT)
 if code:raise RuntimeError(name+' failed: '+str(code))
def main():
 handle=(STUDY/'controller.lock').open('w');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);handle.write(str(os.getpid()));handle.flush()
 path=STUDY/'CONTROLLER_STATE.json';state=json.loads(path.read_text()) if path.exists() else dict(phase='WAIT_INITIAL_DATA',started_unix=time.time(),version=1)
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());save(path,state)
 last_progress=0
 while time.time()<cfg['dispatch_cutoff_unix']:
  if (STUDY/'STOP_CONTROLLER').exists():break
  try:
   if time.time()-last_progress>=900:
    command('checkpoint.py',state['phase']);last_progress=time.time()
   if state['phase']=='WAIT_INITIAL_DATA' and complete_tasks(['010_parent_train_0','011_parent_dev_0','012_P_completion_allowance_regression','014_streaming_fork_v2_regression']) and physics_idle():
    command('streaming_gate.py',2);command('encoder_gate.py');command('qualify_P.py');command('train.py',1,2026100601);state.update(phase='FIT_V1_COMPLETE',version=1);save(path,state)
   elif state['phase']=='FIT_V1_COMPLETE':
    command('prepare_comparison.py',1,'core');state['phase']='WAIT_V1_CORE';save(path,state)
   elif state['phase']=='WAIT_V1_CORE':
    names=[p.stem for p in (STUDY/'queue').glob('030_v1_core_*.json')]
    if len(names)==16 and complete_tasks(names) and physics_idle():
     command('analyze.py',1,'core');state['phase']='V1_CORE_COMPLETE';save(path,state)
   elif state['phase']=='V1_CORE_COMPLETE':
    command('diagnose.py',1)
    # Preregistered extra parent provides legal deviations and the 12-state
    # coverage; it never uses held-out results as supervised targets.
    command('prepare_data.py','extension');state['phase']='WAIT_DATA_EXTENSION';save(path,state)
   elif state['phase']=='WAIT_DATA_EXTENSION' and complete_tasks(['020_parent_train_1']) and physics_idle():
    command('train.py',2,2026100602);state.update(phase='FIT_V2_COMPLETE',version=2);save(path,state)
   elif state['phase']=='FIT_V2_COMPLETE':
    command('prepare_comparison.py',2,'final');state['phase']='WAIT_V2_FINAL';save(path,state)
   elif state['phase']=='WAIT_V2_FINAL':
    names=[p.stem for p in (STUDY/'queue').glob('060_v2_final_*.json')]
    if len(names)==16 and complete_tasks(names) and physics_idle():
     command('analyze.py',2,'final');state['phase']='CORE_AND_FINAL_COMPLETE';save(path,state)
   elif state['phase']=='CORE_AND_FINAL_COMPLETE':
    command('prepare_audit.py');command('prepare_known_synergy.py');state['phase']='WAIT_HELDOUT_AUDIT';save(path,state)
   elif state['phase']=='WAIT_HELDOUT_AUDIT' and complete_tasks(['080_audit_0_normal','080_audit_1_deviation','085_known_nonmyopic_synergy']) and physics_idle():
    command('analyze_audit.py');command('analyze_known_synergy.py');command('train.py',2,2026100603);state['phase']='INDEPENDENT_INITIALIZATION_COMPLETE';save(path,state)
   elif state['phase']=='INDEPENDENT_INITIALIZATION_COMPLETE':
    command('prepare_comparison.py',2,'independent');command('prepare_comparison.py',2,'fresh');state['phase']='WAIT_RESERVED_VALIDATION';save(path,state)
   elif state['phase']=='WAIT_RESERVED_VALIDATION':
    names=[p.stem for prefix in ('090_v2_independent_','100_v2_fresh_') for p in (STUDY/'queue').glob(prefix+'*.json')]
    if len(names)==64 and complete_tasks(names) and physics_idle():
     command('analyze.py',2,'independent');command('analyze.py',2,'fresh');state['phase']='RESERVED_VALIDATION_COMPLETE';state['next_action']='root checks preregistered pilot promotion and remaining time';save(path,state);break
  except BaseException as error:
   state.update(error=str(error),error_unix=time.time(),recoverable=True);save(path,state);print(json.dumps(state),flush=True);break
  time.sleep(30)
 print(json.dumps(state),flush=True)
if __name__=='__main__':main()
