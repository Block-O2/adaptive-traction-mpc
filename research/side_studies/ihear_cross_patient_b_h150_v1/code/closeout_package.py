"""Graceful closeout only after the authorized7h target and all159 ENDs."""
from task_bootstrap import *
import os
def process(pid):
 p=Path('/proc')/str(pid)
 try:
  if (p/'stat').read_text().split(') ',1)[1].split()[0]=='Z':return None
  return dict(pid=pid,cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),cwd=str((p/'cwd').resolve()))
 except (OSError,ValueError):return None
def main():
 now=time.time();assert START+7*3600<=now<START+9*3600,'CLOSEOUT_REQUIRES7H_TARGET_WITHIN9H_CAP'
 events=[json.loads(l) for l in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if l.strip()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];assert len(starts)==len(ends)==159
 assert len({r['id'] for r in starts})==159 and {r['id'] for r in starts}=={r['id'] for r in ends}
 ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text());pending=[p.name for p in (STUDY/'queue').glob('*.json') if p.stem not in ledger];assert not pending,pending
 pid=int((STUDY/'runner.lock').read_text());owner=process(pid);assert owner and str(STUDY/'code/runner.py') in owner['cmd'],'VERIFY_KNOWN_RUNNER_IDENTITY'
 (STUDY/'STOP_DISPATCH').write_text('Final graceful closeout;159 counted physics attempts joined; no adaptation qualification; no automatic dispatch/resume.\n')
 began=time.time()
 while process(pid) is not None and time.time()-began<60:time.sleep(.5)
 assert process(pid) is None,'RUNNER_MUST_EXIT_GRACEFULLY_NO_UNKNOWN_KILLS'
 remaining=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  r=process(int(p.name))
  if r and (str(STUDY) in r['cmd'] or r['cwd']==str(STUDY)) and 'python' in r['cmd']:remaining.append(r)
 assert not remaining,remaining
 from known_process_audit import audit
 identities=audit(allow_runner=False);assert not identities['unexpected_live_recorded_identities'],identities
 save(STUDY/'reports/KNOWN_PROCESS_CLOSEOUT_AUDIT.json',identities)
 stopped=json.loads((STUDY/'RUNNER_STOP.json').read_text());assert stopped['attempts']==159 and stopped['unix']>=now
 plan=json.loads((STUDY/'RUN_PLAN.json').read_text());save(STUDY/'reports/RUN_PLAN_PREREGISTERED.json',plan);plan.update(phase='CLOSED',status='STOPPED_AND_RECONCILED',closed_unix=time.time(),physics_attempts=159,scientific_equivalence='PASS',actual_host_qualification='NOT_QUALIFIED',adaptation='NOT_RUN',dispatch_disabled=True,auto_resume=False);save(STUDY/'RUN_PLAN.json',plan)
 (STUDY/'RESUME.md').write_text('# Closed package\n\n159 START and159 END; no pending queued owners; known runner exited gracefully. STOP_DISPATCH remains present. No automatic resume, scheduled automation, Q update or adaptation.\n\nAll raw traces remain in this WSL study. Do not initialize/reset this harness or rerun failed IDs. This package reached its7h target, with1 unused slot under the160 cap; the unused slot is not an instruction to dispatch.\n\nAny future work needs a newly authorized scope and budget. Preserve the recorded public-B two-repair ceiling and original control, physical clock, candidate authority, safety/R2 thresholds and Q semantics. Use the report/source guide to review the public commissioning/current-model revalidation bottleneck first.\n')
 out=dict(status='STOPPED_AND_RECONCILED',unix=time.time(),elapsed_h=(time.time()-START)/3600,attempts=159,ended=159,pending_queue=pending,active_physics=[],known_runner_pid=pid,known_runner_cmd=owner['cmd'],runner_exit_verified=True,known_controllers_and_offline_jobs_joined=True,remaining_owned_python_processes=remaining,STOP_DISPATCH_retained=True,no_scheduled_automation_created=True,auto_resume=False,scientific_equivalence='PASS',actual_host_qualification='NOT_QUALIFIED',adaptation='NOT_RUN',Q_updates=0,unused_physics_slots=1,closeout_reason='Completed authorized7h work target; bounded diagnostics/scientific stability/clock/source/raw/export review complete. Realtime negative result retained; no filler physics or semantic change.')
 save(STUDY/'reports/CLOSEOUT_STATUS.json',out);print(json.dumps(out))
if __name__=='__main__':main()
