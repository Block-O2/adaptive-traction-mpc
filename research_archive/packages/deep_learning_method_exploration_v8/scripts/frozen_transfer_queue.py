"""Only the already frozen four-case queue; never invent the next experiment."""
from pathlib import Path
import os,sys,json,time,subprocess,signal,hashlib
P=Path(__file__).resolve().parents[1];start=time.time()
signal.alarm(4*3600)
def put(n,d):
 p=P/n;p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
identity={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'started_unix':start,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
assert not (P/'owned/FROZEN_TRANSFER_QUEUE_START.json').exists()
put('owned/FROZEN_TRANSFER_QUEUE_START.json',identity)
groups=['V8CTX01','V8CTX02','V8CTX03','V8CTX04'];completed=[];status='FAILED_PRESERVED'
deadline=json.loads((P/'ACTIVATION.json').read_text())['hard_stop_unix']-2400
try:
 audit=json.loads((P/'families/critic_value/analysis/V8_FROZEN_SELECTOR_STATIC_REVIEW_V1.json').read_text())
 # Review bytes are preserved; the worker separately enforces exact frozen inputs.
 for i,g in enumerate(groups):
  if i==0:
   end=P/'owned'/f'{g}_SUPERVISOR_END.json'
   while not end.exists():
    assert time.time()<min(deadline,start+3600),'FIRST_JOB_OR_GLOBAL_DEADLINE'
    if (P/'STOP_REQUESTED').exists():raise RuntimeError('STOP_REQUESTED')
    time.sleep(3)
   result=json.loads(end.read_text());assert result['worker_exit_code']==0 and not result['survivors'],'FIRST_FROZEN_JOB_FAILED_REVIEW_REQUIRED'
  else:
   assert time.time()<deadline-900,'INSUFFICIENT_NEXT_JOB_TIME'
   config='experiments/'+g+'.json'
   subprocess.run([sys.executable,'-B',str(P/'source/v7_prepare_job.py'),config],check=True,cwd=P.parent,timeout=60)
   subprocess.run([sys.executable,'-B',str(P/'source/v7_supervise_v3.py'),config],check=True,cwd=P.parent,timeout=3660)
  completed.append(g);put('queue/FROZEN_TRANSFER_PROGRESS.json',{'completed':completed,'updated_unix':time.time(),'next':groups[i+1] if i+1<len(groups) else None})
  print('FROZEN_QUEUE_CLOSED',g,flush=True)
 status='COMPLETED_FROZEN_QUEUE'
finally:
 put('owned/FROZEN_TRANSFER_QUEUE_END.json',{**identity,'ended_unix':time.time(),'status':status,'completed':completed})
