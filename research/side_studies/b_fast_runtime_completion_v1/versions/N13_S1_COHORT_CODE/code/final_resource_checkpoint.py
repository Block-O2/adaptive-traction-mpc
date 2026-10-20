"""One final sample/checkpoint after graceful runner exit; never restart owner."""
from task_bootstrap import *
import os

def main():
 close=json.loads((STUDY/'reports/CLOSEOUT_STATUS.json').read_text());assert close['status']=='STOPPED_AND_RECONCILED' and close['runner_exit_verified']
 pid=close['known_runner_pid'];p=Path('/proc')/str(pid)
 assert not p.exists() or p.joinpath('stat').read_text().split(') ',1)[1].split()[0]=='Z'
 import runner
 sample=runner.sample(owner='FINAL_POST_RUNNER_JOIN_READ_ONLY_REVIEW')
 import resource_summary
 resource_summary.main()
 import progress_update
 original=sys.argv;sys.argv=[original[0],'STOPPED_AND_RECONCILED;159 attempts/159 END; no active physics; no pending dispatch; actual qualification failed; adaptation NOT_RUN; no auto resume.']
 progress_update.main();sys.argv=original
 status=json.loads((STUDY/'CHECKPOINT.json').read_text());status.update(status='STOPPED_AND_RECONCILED',dispatch_disabled=True,auto_resume=False,closed_unix=close['unix'],actual_host_qualification='NOT_QUALIFIED',adaptation='NOT_RUN',Q_updates=0,known_runner_exit_verified=True)
 save(STUDY/'CHECKPOINT.json',status)
 print(json.dumps(dict(status='FINAL_SAMPLE_AND_CLOSED_CHECKPOINT_RECORDED',unix=sample['unix'],elapsed_h=(time.time()-START)/3600,runner_pid=pid,runner_restarted=False,physics_added=0)))
if __name__=='__main__':main()
