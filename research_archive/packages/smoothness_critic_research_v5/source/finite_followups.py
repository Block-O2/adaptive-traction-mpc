"""Pre-registered finite followups; no model selection or new branch invention."""
from pathlib import Path
import os,sys,json,time,subprocess,signal,hashlib
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix']-2400
out=P/'owned/FOLLOWUP_QUEUE_START.json';assert not out.exists(),'UNIQUE_QUEUE'
configs=['experiments/FACT.json','experiments/VAL_A.json','experiments/VAL_B.json'];frozen={c:hashlib.sha256((P/c).read_bytes()).hexdigest() for c in configs}
out.write_text(json.dumps(dict(pid=os.getpid(),start_ticks=Path('/proc/self/stat').read_text().split()[21],deadline_unix=deadline,activation=A['id'],configs=frozen,finite_attempts=21),indent=2)+'\n');state='WAIT_DEV';reason=None
try:
 while not (P/'owned/DEV_SUPERVISOR_END.json').exists():
  if time.time()>=deadline or (P/'STOP_REQUESTED').exists():raise RuntimeError('STOP_BEFORE_FOLLOWUPS')
  time.sleep(2)
 d=json.loads((P/'owned/DEV_SUPERVISOR_END.json').read_text());assert d['worker_exit_code']==0,'DEV_FAILED'
 for cfg in configs:
  assert time.time()<deadline-600 and not (P/'STOP_REQUESTED').exists(),'STOP_BEFORE_DISPATCH'
  assert hashlib.sha256((P/cfg).read_bytes()).hexdigest()==frozen[cfg],'CONFIG_CHANGED'
  state=cfg
  r=subprocess.run([sys.executable,str(P/'source/supervise_v2.py'),cfg],check=False)
  assert r.returncode==0,'FOLLOWUP_WORKER_FAILED:'+cfg
 state='STOP';reason='FINITE_PREREGISTERED_QUEUE_COMPLETED'
except BaseException as e:reason=repr(e);state='STOP_AFFECTED_QUEUE'
finally:
 (P/'owned/FOLLOWUP_QUEUE_END.json').write_text(json.dumps(dict(pid=os.getpid(),state=state,reason=reason,ended_unix=time.time(),activation=A['id']),indent=2)+'\n')
 print(state,reason,flush=True)
