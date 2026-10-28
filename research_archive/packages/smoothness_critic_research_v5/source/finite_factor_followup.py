from pathlib import Path
import os,sys,json,subprocess,time,hashlib
P=Path(__file__).resolve().parents[1];a=json.loads((P/'ACTIVATION.json').read_text());freeze=json.loads((P/'analysis/LOCKED_FACTOR_VALIDATION_FREEZE.json').read_text());deadline=a['hard_stop_unix']-2400;cfg='experiments/VAL_C.json';out=P/'owned/FACTOR_VALIDATION_QUEUE_START.json';assert not out.exists();out.write_text(json.dumps(dict(pid=os.getpid(),start_ticks=Path('/proc/self/stat').read_text().split()[21],activation=a['id'],deadline_unix=deadline,config_sha256=freeze['config_sha256']),indent=2)+'\n');reason='WAIT_PREVIOUS_QUEUE'
try:
 while not (P/'owned/FOLLOWUP_QUEUE_END.json').exists():
  assert time.time()<deadline-600 and not (P/'STOP_REQUESTED').exists(),'DEADLINE_OR_STOP'
  time.sleep(2)
 prior=json.loads((P/'owned/FOLLOWUP_QUEUE_END.json').read_text());assert prior['reason']=='FINITE_PREREGISTERED_QUEUE_COMPLETED','PREVIOUS_QUEUE_FAILED'
 assert hashlib.sha256((P/cfg).read_bytes()).hexdigest()==freeze['config_sha256'],'FROZEN_CONFIG_CHANGED'
 rc=subprocess.run([sys.executable,str(P/'source/supervise_v2.py'),cfg]).returncode;assert rc==0,'FACTOR_VALIDATION_FAILED';reason='FINITE_VAL_C_COMPLETED'
except BaseException as e:reason=repr(e)
finally:(P/'owned/FACTOR_VALIDATION_QUEUE_END.json').write_text(json.dumps(dict(state='STOP',reason=reason,ended_unix=time.time(),pid=os.getpid(),activation=a['id']),indent=2)+'\n')
