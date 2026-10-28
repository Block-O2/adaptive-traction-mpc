"""Run only the reviewed original-B persistent implementation gate after V1 transfer."""
from pathlib import Path
import os,sys,json,time,signal,subprocess,hashlib
P=Path(__file__).resolve().parents[1];started=time.time();signal.alarm(4*3600)
def put(n,x):
 p=P/n;p.write_text(json.dumps(x,indent=2)+'\n')
identity={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'started_unix':started,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
put('owned/POST_TRANSFER_PERSISTENT_START.json',identity);status='FAILED_PRESERVED'
try:
 end=P/'owned/FROZEN_TRANSFER_QUEUE_END.json'
 while not end.exists():
  assert time.time()<started+3*3600,'LOCAL_WAIT_DEADLINE'
  assert not (P/'STOP_REQUESTED').exists(),'STOP_REQUESTED'
  time.sleep(3)
 assert json.loads(end.read_text())['status']=='COMPLETED_FROZEN_QUEUE','TRANSFER_FAILED_REVIEW_REQUIRED'
 for i in range(1,5):
  d=json.loads((P/'owned'/f'V8CTX0{i}_SUPERVISOR_END.json').read_text())
  assert d['worker_exit_code']==0 and not d['survivors'],'PHYSICS_OWNER_STILL_ACTIVE_OR_FAILED'
 config='experiments/V8PERSISTB01.json'
 subprocess.run([sys.executable,'-B',str(P/'source/v7_prepare_job.py'),config],check=True,cwd=P.parent,timeout=60)
 subprocess.run([sys.executable,'-B',str(P/'source/v7_supervise_v3.py'),config],check=True,cwd=P.parent,timeout=1860)
 status='COMPLETED_REVIEWED_PERSISTENT_GATE'
finally:put('owned/POST_TRANSFER_PERSISTENT_END.json',{**identity,'ended_unix':time.time(),'status':status})
