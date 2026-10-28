"""Close this attended frozen package and seal exact file hashes. Never runs physics."""
from pathlib import Path
import os,time,json,hashlib,datetime
from research_common import ROOT,RUNTIME,read,atomic,sha,now,pid_identity,same_pid,resources
REQUIRED=['REPORT.md','STD_ABLATION_PROTOCOL.md','STD_ABLATION_RESULTS.json','ACTION_DISTRIBUTION_AUDIT.md','H2_R1_COMPARISON.md','REWARD_RESEARCH_PROPOSALS.md','UNATTENDED_CAMPAIGN_PLAN.md','UNATTENDED_EXECUTION_READINESS.json','AUTONOMOUS_HANDOFF.md','ATTEMPT_ACCOUNTING.json','RESOURCE_USAGE.json','NEXT_RESEARCH_DECISION.md']
EXCLUDED={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'}

def running_package_python():
 result=[]
 for path in Path('/proc').iterdir():
  if not path.name.isdigit() or int(path.name)==os.getpid():continue
  try:
   argv=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');cwd=(path/'cwd').resolve();exe=(path/'exe').resolve()
   if 'python' not in exe.name.lower() or not same_pid(pid_identity(int(path.name))):continue
   if str(ROOT) in argv or cwd.is_relative_to(ROOT):result.append(dict(identity=pid_identity(int(path.name)),command=argv))
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 return result

def main():
 results=read(ROOT/'STD_ABLATION_RESULTS.json');account=read(ROOT/'ATTEMPT_ACCOUNTING.json');assert results['status']=='COMPLETE' and account['pass_'] and read(ROOT/'audit/FINAL_FROZEN_RECHECK.json')['pass_']
 hist=read(ROOT/'audit/HISTORICAL_PROTECTION_END.json');assert hist and hist['pass_']
 for name in REQUIRED:assert (ROOT/name).is_file(),name
 manifest=read(RUNTIME/'FROZEN_CONTRACT_MANIFEST.json')['files'];changed=[n for n,h in manifest.items() if sha(RUNTIME/n)!=h];assert not changed
 records=[read(p) for p in (ROOT/'owned').glob('*.json') if not p.name.endswith('_WATCHDOG_STOP.json')];assert all(not same_pid(r.get('worker')) for r in records)
 assert not list((RUNTIME/'jobs').glob('**/*.zip')),'UNEXPECTED_NEW_MODEL_CHECKPOINT'
 closing=ROOT/'END.json'
 if not closing.exists():
  atomic(ROOT/'RESEARCH_STATE.json',dict(status='STOP',time_utc=now(),training_started=False,next='Read AUTONOMOUS_HANDOFF; no automatic next campaign'))
  atomic(ROOT/'STOP.json',dict(time_utc=now(),reason='ATTENDED_FROZEN_ABLATION_COMPARISON_AND_HANDOFF_COMPLETE'))
  atomic(closing,dict(time_utc=now(),physical_attempts=28,training_attempts=0,Adam_updates=0,hard_stop_utc=read(ROOT/'START.json')['hard_stop_utc'],next_training_started=False,final_campaign_started=False))
 watch=read(ROOT/'WATCHDOG_START.json',{}).get('identity')
 for _ in range(50):
  if not same_pid(watch):break
  time.sleep(.2)
 assert not same_pid(watch),'WATCHDOG_STILL_LIVE'
 end=read(closing);end.update(finalized_utc=now(),owned_workers_and_watchdog_exited=True);atomic(closing,end)
 usage=read(ROOT/'RESOURCE_USAGE.json');usage['elapsed_wall_h_at_report_generation']=usage['elapsed_wall_h'];usage['closed_utc']=end['finalized_utc'];usage['elapsed_wall_h']=(datetime.datetime.fromisoformat(end['finalized_utc']).timestamp()-datetime.datetime.fromisoformat(read(ROOT/'START.json')['t0_utc']).timestamp())/3600;usage['final_current']=resources();atomic(ROOT/'RESOURCE_USAGE.json',usage)
 processes=running_package_python();assert not processes,processes
 atomic(ROOT/'audit/PROCESS_EXIT_AUDIT.json',dict(time_utc=now(),all_registered_workers_exited=True,watchdog_exited=True,watchdog_identity=watch,unregistered_package_python=processes,finalizer=pid_identity(os.getpid()),finalizer_exit_requires_fresh_observer=True))
 atomic(ROOT/'audit/CLOSURE_IDENTITY.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),source_sha256=sha(Path(__file__))))
 files=[]
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file():continue
  name=str(p.relative_to(ROOT))
  if name in EXCLUDED:continue
  files.append(dict(path=name,bytes=p.stat().st_size,sha256=sha(p)))
 atomic(ROOT/'OUTPUT_MANIFEST.json',dict(time_utc=now(),files=files,excluded=sorted(EXCLUDED),exclusion_reason='Manifest cannot hash itself; independently written final verification contains the manifest hash and exit observation'))
 verification=dict(time_utc=now(),required_missing=[],runtime_447_unchanged=True,runtime_mismatches=changed,historical_files_verified=hist['files_checked'],historical_mismatches=hist['mismatches'],all_native_receipt_force_motion_rechecked=True,frozen_evaluations_rechecked=28,all_START_END_closed=account['checks']['all_START_END_closed'],new_training_attempts=0,new_Adam_updates=0,no_new_model_checkpoint_written=True,all_owned_workers_and_watchdog_exited=True,no_unregistered_package_compute=True,finalizer_identity=pid_identity(os.getpid()),manifest_entries=len(files),manifest_sha256=sha(ROOT/'OUTPUT_MANIFEST.json'),independent_final_verification_pending=True,hard_stop_utc=read(ROOT/'START.json')['hard_stop_utc'],next_campaign_started=False,G4_STRICT_PASS='FAIL',NEW_LIVE_MATCHED_READY='NOT_READY',STAGE2_READY='NOT_READY',FINAL_CAMPAIGN_READY='NOT_READY')
 atomic(ROOT/'PACKAGE_VERIFICATION.json',verification);print(json.dumps(dict(sealed=len(files),manifest_sha256=verification['manifest_sha256'],owned_exited=True)))

if __name__=='__main__':main()
