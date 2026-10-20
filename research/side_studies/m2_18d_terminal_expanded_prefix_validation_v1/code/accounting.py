from pathlib import Path
import json,time,os,fcntl,hashlib
STUDY=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_expanded_prefix_validation_v1')
def rows():
 p=STUDY/'ATTEMPTS.jsonl';return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
def attempts():return sum(x['event']=='START' for x in rows())
def record(event,id,**extra):
 with (STUDY/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  history=rows()
  if event=='START':
   assert not any(x['event']=='START' and x['id']==id for x in history),'ATTEMPT_ID_ALREADY_USED'
   assert sum(x['event']=='START' for x in history)<160,'PHYSICS_ATTEMPT_CAP'
  row=dict(event=event,id=id,unix=time.time(),pid=os.getpid(),**extra)
  with (STUDY/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 if event=='END':
  from compute_ledger import main as append_compute
  append_compute()
 return row
def migrate():
 if (STUDY/'ATTEMPTS.jsonl').exists():return
 p=STUDY/'TASK_LEDGER.json'
 if p.exists():
  for id,item in json.loads(p.read_text()).items():
   record('START',id,migrated=True,original_started_unix=item['started_unix'],input_sha256=item['input_sha256'])
   if item['status']!='RUNNING':record('END',id,migrated=True,status=item['status'],worker_status=item.get('worker_status'))
