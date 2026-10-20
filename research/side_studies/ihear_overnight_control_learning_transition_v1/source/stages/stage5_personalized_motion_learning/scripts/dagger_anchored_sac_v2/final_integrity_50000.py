"""Final read-only state/process checks and stable archive manifest after closeout."""
from common import *
import shutil
def run():
 frozen=read('FINAL_VERIFICATION_FREEZE_50000.json')['full_stopped_state']
 assert all(sha(p)==h for p,h in frozen.items()),'STOPPED_STATE_MUTATED'
 owned=[]
 names={'train.py','resume_36283.py','evaluate.py','evaluate_operational_v3.py','final_verification_50000.py','final_comparator_v3.py','resource_policy_v2.py','closeout_50000.py'}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:argv=(p/'cmdline').read_bytes().decode().split('\0')
  except (OSError,UnicodeDecodeError):continue
  if any(Path(a).name in names for a in argv) and any('python' in a for a in argv[:1]):owned.append(dict(pid=p.name,argv=argv))
 assert not owned,'WORKFLOW_PROCESSES_STILL_ACTIVE'
 assert read('STATE.json')['total_online_steps']==50000
 save('FINAL_INTEGRITY_50000.json',dict(status='PASS',stopped_learning_state_byte_unchanged=True,owned_training_evaluation_monitor_processes=[],collection_steps=50000,final_replays=25,plot_visual_QA='PASS: labels, axes, invalid-cost gap, capability-loss marker and final rescue curve inspected',report_sha256=sha(L/'DAGGER_ANCHORED_SAC_V2_50000_REPORT.md'),scientific_contract_sha256=sha(L/'PREREGISTRATION.json'),no_further_training=True))
 for p in P.glob('*.py'):shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
 # Prior closeout manifest included its live stdout log. Preserve it as evidence;
 # refresh only after that process exits, then never append to those logs.
 shutil.copy2(L/'ARCHIVE_MANIFEST_50000.json',L/'ARCHIVE_MANIFEST_50000_before_final_log_flush.json')
 excluded={'ARCHIVE_MANIFEST_50000.json','CONTINUATION_ARCHIVE_MANIFEST.json','ARCHIVE_MANIFEST.json'}
 manifest={str(p):sha(p) for root in (O,L,D,S/'scripts/dagger_anchored_sac_v2') for p in root.rglob('*') if p.is_file() and p.name not in excluded}
 save('ARCHIVE_MANIFEST_50000.json',dict(files=manifest,count=len(manifest),created_after_training_evaluation_closeout_process_exit=True))
 assert manifest[str(L/'DAGGER_ANCHORED_SAC_V2_50000_REPORT.md')]==read('FINAL_INTEGRITY_50000.json')['report_sha256']
 print(json.dumps(dict(status='PASS',files=len(manifest),budget=50000,training_evaluation_processes=0)),flush=True)
if __name__=='__main__':run()
