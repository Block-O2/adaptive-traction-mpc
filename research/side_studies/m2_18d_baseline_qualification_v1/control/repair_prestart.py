from pathlib import Path
import json,shutil,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1')
assert not (P/'ATTEMPTS.jsonl').exists(),'Pre-START-only repair'
V=P/'audit/prestart_launch1';V.mkdir()
for n in ['reproduction_OWNER.json','reproduction_OWNER_ACTIVE.json','logs/reproduction.log','EXECUTION_CODE_MANIFEST.json','PREPHYSICAL_CHECKS.json']:
 f=P/n;shutil.move(str(f),V/f.name)
shutil.copy2(P.parent/'ihear_overnight_research_retrospective_v1/output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
(P/'audit/ENGINEERING_EVENTS.json').write_text(json.dumps(dict(rows=[dict(unix=time.time(),stage='before physical START',error='Closure copy omitted output/SHARED_COORDINATION_ACTION_CONTRACT.json required by interface constructor',physics_starts=0,repair='Copy the exact historical contract; preflight now constructs MatchedInterface before passing',historical_write=False,scientific_change=False,original_log='audit/prestart_launch1/reproduction.log')]),indent=2)+'\n')
