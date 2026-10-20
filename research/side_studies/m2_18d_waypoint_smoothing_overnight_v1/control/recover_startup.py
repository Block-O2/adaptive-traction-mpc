from pathlib import Path
import sys,json,shutil,hashlib,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
(P/'motion_series').mkdir(exist_ok=True)
for n in ['PHYSICAL_FAILURE.json','WORKER_EXIT.json','STATE.json','PROGRESS.json','EXECUTION_CODE_MANIFEST.json']:
 if (P/n).exists():shutil.copy2(P/n,P/'audit'/('startup_'+n))
sys.path.insert(0,str(P/'code'))
import analyze_matched as am
m=am.measure('targeted_B0');comp=am.compare(m,m)
(P/'audit/RECOVERED_COMPLETED_B.json').write_text(json.dumps(dict(status='COMPLETE_EVALUATION_RECOVERED_WITHOUT_NEW_PHYSICS',J_F=m['J_F_N_s'],comparison=comp,original_failure='missing new output motion_series directory; completed physical trace preserved'),indent=2))
plan=json.loads((P/'RUN_PLAN.json').read_text());plan['physics_budget']=14;plan['engineering_amendment']='Before any nonzero arm: first parent stopped at TASK entry after completed B fork due missing motion_series output dir. Preserve both STARTs, re-evaluate saved B without physics, and allow exactly two extra engineering STARTs for a fresh complete parent/B pair. Scientific candidate budget is unchanged.'
(P/'RUN_PLAN_REPAIR1.json').write_text(json.dumps(plan,indent=2));shutil.copy2(P/'RUN_PLAN.json',P/'audit/RUN_PLAN_original.json');(P/'RUN_PLAN.json').write_text(json.dumps(plan,indent=2))
src=(P/'control/targeted_campaign.py').read_text().replace("ib.GROUP='targeted'","ib.GROUP='targeted2'").replace("name='targeted'","name='targeted2'").replace('targeted_parent','targeted2_parent').replace('targeted_B0','targeted2_B0').replace("'targeted_'+tag","'targeted2_'+tag")
(P/'control/targeted_campaign_repair1.py').write_text(src)
manifest={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['source','code','deps','weights','control','tests'] for p in (P/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(P/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(dict(files=manifest,executable_plan_sha256=hashlib.sha256((P/'EXECUTABLE_PLAN.json').read_bytes()).hexdigest(),run_plan_sha256=hashlib.sha256((P/'RUN_PLAN.json').read_bytes()).hexdigest(),original_plan_sha256=hashlib.sha256((P/'CANDIDATE_PLAN.json').read_bytes()).hexdigest()),indent=2))
print('RECOVERED_B',m['J_F_N_s'],'motion',comp['acceptance_pass'],'NEW_START_CAP',plan['physics_budget'])
