"""New isolated package and immutable campaign contract. No physics."""
from pathlib import Path
import json, shutil, time, hashlib, subprocess, datetime
L=Path(__file__).resolve().parents[1]
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
P=S/L.name; OLD=S/'force_mechanism_waypoint_v3'
assert not P.exists(), 'Never overwrite an existing study'
P.mkdir()
for d in ['source','code','deps','weights','tests','control']:
 shutil.copytree(OLD/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for d in ['output','motion_series','series','reports','audit','tmp','logs','figures','derived','evidence','provenance']:(P/d).mkdir()
for n in ['MOTION_ACCEPTANCE_PROTOCOL.json','CERTIFICATION_TEST_RESULTS.json','DENSITY_MATH_TESTS.json']:
 shutil.copy2(OLD/n,P/n)
shutil.copy2(OLD/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
(P/'key_traces').symlink_to((OLD/'key_traces').resolve(),target_is_directory=True)
relocations=[]
for d in ['source','code','deps','tests','control']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(OLD) in s:
    before=hashlib.sha256(f.read_bytes()).hexdigest();f.write_text(s.replace(str(OLD),str(P)))
    relocations.append(dict(file=str(f.relative_to(P)),before=before,after=hashlib.sha256(f.read_bytes()).hexdigest()))
for f in (L/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
t0=datetime.datetime(2026,10,16,18,12,56,tzinfo=datetime.timezone.utc).timestamp()
put('RUN_PLAN.json',dict(t0_unix=t0,t0_Asia_Shanghai='2026-10-17 02:12:56',target_hours=[8,10],hard_stop_unix=t0+11*3600,dispatch_cutoff_unix=t0+10*3600,physics_hard_stop_unix=t0+10*3600+600,seed=2026101303,physics_budget=120,development_cap=90,validation_reserve=30,physical_timeout_s=600,package_target_bytes=5*2**30,package_hard_bytes=8*2**30,question='Does bounded targeted smoothing complement exact historical 18D coordination?',clock='SCIENTIFIC_SIMULATION',truth_firewall='archived truth for offline design and post-run evaluation only; runtime registered constants and original causal belief',qualification='unchanged task, absolute safety, motion/fairness, current path certificate and receipt ownership',promotion=dict(force_min_gain_vs_matched_base_N_s=0.5,motion_route='18D force retained within 0.1 N s, full actual velocity TV reduced >=1%, combined jerk RMS nonincreasing; all original gates PASS',no_reselection_after_validation=True),stop='3-5 candidates without new information; no blind density search; no physics in final hour',validation='new legal native-prefix pairs, frozen before exposure; baseline and candidates fork complete identical live parent; no state reconstruction',protected='formal B, dynamics, task and phase duration, thresholds, controller gains, 40ms bridge, 100ms lifecycle, current admission, ownership, carry/fallback; no RL/Q or Git mutation'))
put('STATE.json',dict(phase='A_HISTORICAL_AUDIT',physics_starts=0,t0_unix=t0,next_action='recompute archives and design four-group interventions',owned_pids=[]))
put('audit/PATH_RELOCATION.json',relocations)
main=Path('/home/hank/coding/adaptive-traction-mpc-learning');git={}
for k,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
 b=subprocess.check_output(['git','-C',str(main),*args]);(P/'audit'/('git_'+k+'_before.txt')).write_bytes(b);git[k]=dict(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
 if k in ['head','branch']:git[k]['value']=b.decode().strip()
put('audit/PROTECTION_BEFORE.json',dict(git=git,main_files={str(f.relative_to(main)):[f.stat().st_size,f.stat().st_mtime_ns] for f in main.rglob('*') if f.is_file() and '.git' not in f.relative_to(main).parts},source_files={str(OLD/f.relative_to(P)):hashlib.sha256((OLD/f.relative_to(P)).read_bytes()).hexdigest() for d in ['source','code','deps','weights','tests'] for f in (P/d).rglob('*') if f.is_file()}))
for name in ['adaptive_continuous_coordination_interface_v1','adaptive_continuous_coordination_optimization_v1','force_motion_coupling_diagnosis_v2','force_mechanism_waypoint_v3','ihear_overnight_research_retrospective_v1']:
 shutil.copy2(S/name/'REPORT.md',P/'provenance'/(name+'__REPORT.md'))
for n in ['FROZEN_SELECTION.json','VALIDATION_RESULTS.json']:
 shutil.copy2(S/'ihear_overnight_research_retrospective_v1'/n,P/'provenance'/('18D_'+n))
shutil.copy2(L/'REQUEST.txt',P/'REQUEST.txt')
put('FROZEN_SELECTION.json',dict(status='NOT_YET_ELIGIBLE',PRIMARY=None,SECONDARY=None))
put('VALIDATION_RESULTS.json',dict(status='NOT_RUN',new_pairs=0,historical_18D_motion='0/4; not upgraded'))
print('PREPARED_NO_PHYSICS',P)
