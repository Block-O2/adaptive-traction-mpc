"""Explicit, budget-preserving resume after all campaign processes have exited."""
from freeze import *
import fcntl,sys
sys.path.insert(0,str(STUDY/'code'))
from accounting import record
def main():
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());assert time.time()<cfg['dispatch_cutoff_unix'],'ORIGINAL_CAMPAIGN_DISPATCH_CLOCK_EXPIRED; a new campaign requires explicit new authorization'
 final=STUDY/'FINAL_STATUS.json'
 if final.exists():assert json.loads(final.read_text())['status']=='PARTIAL_RESUMABLE','CAMPAIGN_ALREADY_CLOSED'
 locks=[]
 for name in ('runner.lock','controller.lock'):
  lock=(STUDY/name).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(lock)
 live=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  except (OSError,UnicodeError):continue
  if str(STUDY/'code/worker.py') in command:live.append(int(p.name))
 assert not live,'OWNED_PHYSICS_WORKER_STILL_ALIVE:'+str(live)
 events=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ends={r['id'] for r in events if r['event']=='END'}
 for event in events:
  if event['event']=='START' and event['id'] not in ends:record('END',event['id'],status='INTERRUPTED_RECOVERY',reason='exclusive campaign locks, no owned physics worker alive; original attempt retained')
 ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text());created=[]
 successful={name for name,item in ledger.items() if item['status']=='COMPLETE' and item.get('worker_status')=='COMPLETE'}
 successful.update(item.get('config',{}).get('resume_of') for item in ledger.values() if item['status']=='COMPLETE' and item.get('worker_status')=='COMPLETE')
 for name,item in ledger.items():
  if name in successful:continue
  if '_retry' in name or item.get('config',{}).get('resume_of'):continue
  # Superseded preflight errors are retained evidence, not resumable tasks.
  if name.startswith(('000_','002_','005_','006_','007_','008_','009_')):continue
  old=STUDY/'queue'/(name+'.json');request=json.loads(old.read_text());number=1
  while (STUDY/'queue'/(name+'_retry'+str(number)+'.json')).exists():number+=1
  newname=name+'_retry'+str(number);request.update(id=newname,resume_of=name,result_path=str(STUDY/'output'/(newname+'_RESULT.json')),original_input_sha256=sha(old),resume_time=time.time());save(STUDY/'queue'/(newname+'.json'),request);created.append(newname)
  item['recovery_dispatch']=dict(retry=newname,original_status=item['status'],original_worker_status=item.get('worker_status'),unix=time.time())
 save(STUDY/'TASK_LEDGER.json',ledger);save(STUDY/'RECOVERY_'+str(int(time.time()))+'.json',dict(created_retries=created,original_start_unix=1791222386,no_budget_reset=True));print(json.dumps(created))
if __name__=='__main__':
 import os
 main()
