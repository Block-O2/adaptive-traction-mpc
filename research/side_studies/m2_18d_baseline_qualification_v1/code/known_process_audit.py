"""Read-only check of recorded owned PID/command identities, including IPC."""
from task_bootstrap import *
from closeout_package import process
import os

def audit(allow_runner=False):
 recorded={}
 for name in ('RESOURCE_LOG.jsonl','OFFLINE_RESOURCE_LOG.jsonl'):
  p=STUDY/'output'/name
  if not p.exists():continue
  for line in p.read_text().splitlines():
   r=json.loads(line)
   for item in r.get('processes',[]):
    key=(item['pid'],item['cmd']);recorded[key]=max(recorded.get(key,0),r['unix'])
 runner_pid=int((STUDY/'runner.lock').read_text());alive=[];allowed=[]
 for (pid,cmd),last in recorded.items():
  if pid==os.getpid():continue
  current=process(pid)
  if current is None or current['cmd']!=cmd:continue
  row=dict(pid=pid,cmd=cmd,last_recorded_owned_unix=last,current_cwd=current['cwd'])
  if allow_runner and pid==runner_pid and str(STUDY/'code/runner.py') in cmd:allowed.append(row)
  else:alive.append(row)
 return dict(status='ONLY_EXPECTED_MONITOR_ALIVE' if allow_runner and not alive else 'ALL_RECORDED_OWNED_IDENTITIES_ABSENT' if not alive else 'RECORDED_OWNED_IDENTITY_STILL_ALIVE',unix=time.time(),recorded_pid_command_identities=len(recorded),allowed_monitor=allowed,unexpected_live_recorded_identities=alive,unknown_processes_killed=False,physics_attempts_added=0,scope='Matches only originally recorded verified-owner/descendant PID plus exact command bytes, including generic multiprocessing spawn/resource-tracker commands that need not contain the study path. Zombie processes count as exited. PIDs without a current matching command are not treated as task-owned. No start-time identity was recorded in the original samples, so this is a bounded additional check, not a universal ownership attestation.')

def main():
 out=audit(allow_runner=not (STUDY/'STOP_DISPATCH').exists());save(STUDY/'reports/KNOWN_PROCESS_CLOSEOUT_AUDIT.json',out);print(json.dumps(out));assert not out['unexpected_live_recorded_identities']
if __name__=='__main__':main()
