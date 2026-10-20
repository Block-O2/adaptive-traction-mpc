from common import *
import subprocess
if __name__=='__main__':
 assert read('zero_history_v2_GATE.json')['pass_'],'ZERO_HARD_STOP'
 steps=[('minimal regression','minimal_batch.py',dict(GATE_REV='history',ZERO_GATE='zero_history_v2_GATE.json')),('historical fixed then CEM','history.py',{}),('same-state branching','branches.py',{})]
 for stage,script,extra in steps:
  save('STATE.json',dict(status='RUNNING',phase=stage,training_steps=0,scientific_changes=False))
  print('START_STAGE '+stage,flush=True)
  environment={**os.environ,**extra}
  result=subprocess.run([sys.executable,'-u',str(W/script)],env=environment)
  if result.returncode:
   save('STATE.json',dict(status='REPAIR_REQUIRED',phase=stage,exit_code=result.returncode,training_steps=0));raise RuntimeError(stage+' failed')
  print('COMPLETE_STAGE '+stage,flush=True)
 save('STATE.json',dict(status='GATES_EXECUTED_PENDING_AUDIT',training_steps=0,next='final evidence audit, source integrity and report'))
