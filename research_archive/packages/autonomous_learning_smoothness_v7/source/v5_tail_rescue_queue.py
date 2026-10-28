"""Finite replay of a newly exposed failure, after all pre-registered primary experiments."""
from pathlib import Path
import os,sys,json,time,subprocess,datetime,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];deadline=json.loads((P/'ACTIVATION.json').read_text())['hard_stop_unix']-2700
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
cfg='experiments/TAILRESCUE01.json';sha=hashlib.sha256((P/cfg).read_bytes()).hexdigest()
put('owned/TAIL_RESCUE_QUEUE_START.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),deadline_unix=deadline,maximum_new_physical_START=6,config_sha256=sha,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),predecessor='owned/PPO_REPAIR_QUEUE_END.json',known_failure_replay_not_new_blind_validation=True))
done=[];reason='FINITE_NEW_FAILURE_REPLAY_COMPLETED'
try:
 for _ in range(max(1,int(deadline-time.time())+1)):
  if time.time()>deadline or (P/'STOP_REQUESTED').exists():raise TimeoutError('TAIL_RESCUE_QUEUE_DEADLINE')
  f=P/'owned/PPO_REPAIR_QUEUE_END.json'
  if f.exists():
   e=json.loads(f.read_text());assert e['reason'] in ['FINITE_SUPPLEMENTAL_STUDY_COMPLETED','SUPPLEMENTAL_DEV_COMPLETED_NO_GAIN_VALIDATION_NOT_RUN'],'PREDECESSOR_NOT_CLOSED';break
  time.sleep(1)
 else:raise TimeoutError('PREDECESSOR_NOT_FINISHED')
 assert time.time()<deadline-1800,'NO_TIME_FOR_COMPLETE_TAIL_RESCUE_AND_AUDIT'
 assert hashlib.sha256((P/cfg).read_bytes()).hexdigest()==sha,'FROZEN_RESCUE_CONFIG_CHANGED'
 with (P/'logs/TAILRESCUE01_supervisor.log').open('w') as log:
  child=subprocess.Popen([sys.executable,'-B',str(P/'source/supervise_v2.py'),cfg],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  put('owned/TAIL_RESCUE_QUEUE_CURRENT.json',dict(pid=child.pid,group='TAILRESCUE01'));rc=child.wait(timeout=max(1,int(deadline-time.time())))
 assert rc==0,'TAIL_RESCUE_JOB_FAILED';done.append('TAILRESCUE01')
except BaseException as error:reason=type(error).__name__+':'+str(error);raise
finally:put('owned/TAIL_RESCUE_QUEUE_END.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason=reason,completed=done))
