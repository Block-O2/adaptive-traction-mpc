from pathlib import Path
import json,subprocess,sys,time,os
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());groups=json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups']
while not (P/'owned/DEV_O1_SUPERVISOR_END.json').exists():
 assert time.time()<A['hard_stop_unix']-5400
 time.sleep(2)
assert json.loads((P/'owned/DEV_O1_SUPERVISOR_END.json').read_text())['worker_exit_code']==0,'DEV_REVIEW_REQUIRED'
for g in groups:
 assert time.time()<A['hard_stop_unix']-5400,'RESERVE_FROZEN_TEST'
 with (P/'logs'/f'{g}_supervisor.log').open('w') as f:
  rc=subprocess.run([sys.executable,'-B',str(P/'source/supervise_v2.py'),'experiments/'+g+'.json'],stdout=f,stderr=subprocess.STDOUT).returncode
 if rc: print('QUEUE_STOP',g,rc,flush=True);sys.exit(rc)
 print('TRAIN_DONE',g,flush=True)
(P/'jobs/TRAIN_QUEUE_DONE.json').write_text(json.dumps({'groups':groups,'unix':time.time()}))
