from pathlib import Path
import hashlib,json,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');S=P.parent;D=S/'force_motion_coupling_diagnosis_v2';H=S/'ihear_overnight_research_retrospective_v1';O=S/'adaptive_continuous_coordination_optimization_v1';L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
(P/'provenance').mkdir(exist_ok=True);rows={}
groups=[(D,['REPORT.md','REPRODUCTION.md','CANDIDATES.md','SOURCE_MANIFEST.json','CANDIDATE_PARAMETERS_AND_QUALIFICATION.json','provenance/18D_FROZEN_SELECTION.json','provenance/18D_CONFIG.json']),(H,['code/rich_planner.py','code/free_planner.py','code/overnight_runner.py']),(O,['REPORT.md','METRICS_CONTRACT.md','PARENT_FORK_GATE.json'])]
for root,names in groups:
 for name in names:
  f=root/name;dest=P/'provenance'/(root.name+'__'+name.replace('/','__'));shutil.copy2(f,dest);rows[str(f)]=dict(size=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),copy=str(dest.relative_to(P)))
shutil.copy2(L/'REPRODUCTION.md',P/'REPRODUCTION.md')
(P/'audit/ADDITIONAL_SOURCE_REFERENCES.json').write_text(json.dumps(dict(files=rows,registration_scope='Supplemental read-only source references hashed after analysis, not claimed as a T0 byte snapshot. Core raw input hashes were frozen at initial analysis; execution closure separately frozen before physics.'),indent=2))
for f in (L/'control').glob('*.py'):compile(f.read_text(),str(f),'exec')
print('PROVENANCE_COPIED',len(rows),'ALL_ANALYSIS_SOURCES_COMPILE')
