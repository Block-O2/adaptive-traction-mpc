"""Preserve import failure; supply the legacy manifest alias and a distinct retry id."""
from pathlib import Path
import json,shutil,time
P=Path('/home/hank/ihear-lab/representation_execution_v3/runtime')
assert not (P/'EXECUTION_CODE_MANIFEST.json').exists()
assert not (P/'ATTEMPTS.jsonl').exists()
shutil.copy2(P/'EXECUTION_CODE_MANIFEST_v2.json',P/'EXECUTION_CODE_MANIFEST.json')
owner=json.loads((P/'D01_OWNER.json').read_text())
# Conservatively charge the launch that failed before a plant was instantiated.
events=[dict(event='START',id='D01_import_failure',unix=owner['start_unix'],pid=owner['child_pid'],kind='IMPORT_FAILED_BEFORE_PHYSICS',group='D01',code_manifest='EXECUTION_CODE_MANIFEST_v2.json',retroactive_from_owned_launch_log=True),dict(event='END',id='D01_import_failure',unix=owner['end_unix'],pid=owner['child_pid'],returncode=1,joined=True,actual_new_native_steps=0,error='Missing legacy EXECUTION_CODE_MANIFEST.json alias',retroactive_from_owned_launch_log=True)]
(P/'ATTEMPTS.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in events))
plan=json.loads((P/'D01_PLAN.json').read_text());plan['condition']['name']='D01R';plan['condition']['parent_family']='D01';plan['retry_of']='D01 import-only failed launch; no physics or outcome consumed'
(P/'D01R_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
(P/'audit/IMPORT_FAILURE_REPAIR.json').write_text(json.dumps(dict(status='REPAIRED',unix=time.time(),original_log='logs/D01.log',original_owner='D01_OWNER.json',repair='Legacy alias is byte-identical to frozen v2 manifest; new group id D01R',scientific_change=False,conservative_START_charge=1,actual_native_steps=0),indent=2)+'\n')
print('MANIFEST_ALIAS_REPAIRED; CONSERVATIVE_START_CHARGE=1',flush=True)
