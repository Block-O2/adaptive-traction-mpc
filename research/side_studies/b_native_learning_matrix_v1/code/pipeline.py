"""Durable phase advancement for the preregistered first dataset/matrix."""
from task_bootstrap import *
import fcntl,os,traceback
def main():
 lock=(STUDY/'controller.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.write(str(os.getpid()));lock.flush();last_sample=0
 statepath=STUDY/'PIPELINE_STATE.json';state=json.loads(statepath.read_text()) if statepath.exists() else dict(phase='WAIT_DATA')
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text())
 while time.time()<cfg['dispatch_cutoff_unix'] and not (STUDY/'STOP_CONTROLLER').exists():
  ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text());active=any(x['status']=='RUNNING' for x in ledger.values())
  if time.time()-last_sample>=45:
   from runner import sample
   sample(filename='RESOURCES_ALL_PROCESS_TREES.jsonl');last_sample=time.time()
   subprocess.run([sys.executable,str(STUDY/'code/compute_ledger.py')],stdout=subprocess.DEVNULL)
  if state['phase']=='WAIT_DATA':
   ids=['020_parent_'+x for x in ('train_0','train_1','dev_0')]+['030_zero_context_repair']
   if all(x in ledger and ledger[x]['status']!='RUNNING' for x in ids) and not active:
    failed=[x for x in ids if ledger[x].get('worker_status')!='COMPLETE']
    if failed:save(STUDY/'PIPELINE_ATTENTION.json',dict(failed=failed,next='read failures, minimal repair and explicit retries; no global scientific stop'));return
    regression=subprocess.run([sys.executable,str(STUDY/'code/repair_context.py'),'check'])
    if regression.returncode:save(STUDY/'PIPELINE_ATTENTION.json',dict(stage='CONTEXT_REPAIR_REGRESSION',returncode=regression.returncode));return
    pending=[p for p in (STUDY/'queue').glob('*.json') if p.stem not in ledger]
    if pending:time.sleep(2);continue
    state.update(phase='TRAIN_V1',updated_unix=time.time());save(statepath,state)
  if state['phase']=='TRAIN_V1' and not active:
   if not (STUDY/'LATEST_WEIGHTS.json').exists():
    with (STUDY/'logs/TRAIN_V1.log').open('w') as log:
     result=subprocess.run([sys.executable,'-u',str(STUDY/'code/train_native.py'),'v1','2026100611'],stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:save(STUDY/'PIPELINE_ATTENTION.json',dict(stage='TRAIN_V1',returncode=result.returncode,next='read training log, repair bounded implementation only'));return
   result=subprocess.run([sys.executable,str(STUDY/'code/prepare_matrix.py'),'v1'])
   if result.returncode:return
   state.update(phase='WAIT_MATRIX_V1',updated_unix=time.time());save(statepath,state)
  if state['phase']=='WAIT_MATRIX_V1':
   ids=[p.stem for p in (STUDY/'queue').glob('040_v1_*.json')]
   if len(ids)==20 and all(x in ledger and ledger[x]['status']!='RUNNING' for x in ids) and not active:
    state.update(phase='MATRIX_V1_COMPLETE',updated_unix=time.time());save(statepath,state);print('MATRIX_V1_READY_FOR_ANALYSIS',flush=True);return
  time.sleep(2)
 save(statepath,dict(**state,stop_unix=time.time()))
if __name__=='__main__':main()
