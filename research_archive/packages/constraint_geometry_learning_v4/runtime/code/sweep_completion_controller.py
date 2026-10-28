"""Bounded same-task orchestration; one runner retains the physics owner."""
from task_bootstrap import *
import os
def main():
 (STUDY/'controller.lock').write_text(str(os.getpid()));limit=min(time.time()+4200,START+8.25*3600)
 while time.time()<limit and not (STUDY/'STOP_DISPATCH').exists():
  p=STUDY/'NONPHYSICS_JOBS.jsonl';jobs=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else [];job=next((j for j in reversed(jobs) if j['id']=='O10r1'),None)
  if job:
   if job['returncode']==0:
    import prepare_lean_host
    prepare_lean_host.main();save(STUDY/'SWEEP_CONTROLLER_STATUS.json',dict(status='FINISHED_DISPATCHED_QUIET_HOST_PAIRS',unix=time.time(),pid=os.getpid(),physics_owner='existing single runner',offline_job=job));return
   save(STUDY/'SWEEP_CONTROLLER_STATUS.json',dict(status='OFFLINE_DIAGNOSTIC_FAILED_NO_QUIET_HOST_DISPATCH',unix=time.time(),job=job));return
  save(STUDY/'SWEEP_CONTROLLER_STATUS.json',dict(status='WAITING_FOR_OFFLINE_JOIN',unix=time.time(),pid=os.getpid(),deadline_unix=limit,physics_owner='existing single runner'));time.sleep(20)
 save(STUDY/'SWEEP_CONTROLLER_STATUS.json',dict(status='SAFE_CLOSEOUT_NO_DISPATCH',unix=time.time(),pid=os.getpid()))
if __name__=='__main__':main()
