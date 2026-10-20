"""Isolated study setup only; no physics. Run with canonical WSL Python."""
from pathlib import Path
import os, sys, json, time, hashlib, shutil, subprocess
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
Q=S/'m2_18d_baseline_qualification_v1'
P=S/'m2_18d_autonomous_review_v1'
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
LOCAL=Path(__file__).resolve().parents[1]
T0=1792214779.0
assert not P.exists(), 'Never overwrite a research package'
P.mkdir()
for d in ['audit','provenance','control','reports','output','motion_series','logs','derived','tmp']: (P/d).mkdir()
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''): h.update(b)
 return h.hexdigest()
def put(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def git():
 return {k:subprocess.check_output(['git','-C',str(MAIN),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()}
put('audit/GIT_BEFORE.json',git())
inventory={};protected={}
important=['m2_18d_baseline_qualification_v1','m2_18d_waypoint_smoothing_overnight_v1','adaptive_continuous_coordination_interface_v1','force_mechanism_waypoint_v3','force_motion_coupling_diagnosis_v2','ihear_overnight_research_retrospective_v1']
for root in [MAIN,S]:
 for f in root.rglob('*'):
  if P in f.parents or '.git' in f.parts or '__pycache__' in f.parts: continue
  if f.is_symlink(): inventory[str(f)]={'symlink':os.readlink(f)}; continue
  if not f.is_file(): continue
  st=f.stat();inventory[str(f)]={'size':st.st_size,'mtime_ns':st.st_mtime_ns}
  rel=f.relative_to(root)
  keyraw=root==S and len(rel.parts)>1 and rel.parts[0] in important and ('results' not in rel.parts or f.name=='trace.npz')
  if root==MAIN or keyraw: protected[str(f)]=sha(f)
put('audit/HISTORY_METADATA_BEFORE.json',inventory);put('audit/PROTECTED_SHA_BEFORE.json',protected)
put('ENVIRONMENT.json',dict(t0_unix=T0,setup_unix=time.time(),hard_stop_unix=T0+14400,python=sys.executable,version=sys.version,main=str(MAIN),canonical=str(P),disk=shutil.disk_usage(S)._asdict(),processes=subprocess.check_output(['ps','-eo','pid,ppid,pgid,args']).decode(),protected_files=len(protected),metadata_files=len(inventory)))
for d in ['source','code','deps','weights']:
 shutil.copytree(Q/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
(P/'source/results').mkdir()
rebase=[]
for d in ['source','code','deps']:
 for f in (P/d).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.yaml','.yml','.toml']: continue
  try: txt=f.read_text()
  except UnicodeError: continue
  new=txt.replace(str(Q),str(P))
  if new!=txt:
   before=sha(f);f.write_text(new);rebase.append(dict(path=str(f.relative_to(P)),before=before,after=sha(f)))
put('audit/PATH_ONLY_REBASE.json',rebase)
for n in ['campaign.py','own_campaign.py','independent_recompute.py']:
 shutil.copy2(Q/'control'/n,P/'control'/n)
for f in (LOCAL/'control').glob('*.py'):
 if f.name!='bootstrap.py': shutil.copy2(f,P/'control'/f.name)
shutil.copy2(LOCAL/'control/bootstrap.py',P/'control/bootstrap.py')
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','METHOD_DEFINITION.md','MOTION_ACCEPTANCE_PROTOCOL.json']:
 shutil.copy2(Q/n,P/n)
shutil.copy2(Q/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
line=[]
for pkg in important:
 for n in ['REPORT.md','RUN_PLAN.json','VALIDATION_RESULTS.json','FROZEN_SELECTION.json','CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST.json','METHOD_DEFINITION.md','BASELINE_REPRODUCTION.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md','HISTORICAL_18D_MECHANISM.md']:
  f=S/pkg/n
  if f.is_file():
   dest=P/'provenance'/(pkg+'__'+n);shutil.copy2(f,dest);line.append(dict(source=str(f),copy=str(dest.relative_to(P)),sha256=sha(f)))
shutil.copy2(MAIN/'CURRENT_RESEARCH_BASELINE.md',P/'provenance/CURRENT_RESEARCH_BASELINE.md')
put('audit/SOURCE_LINEAGE.json',line)
old=json.loads((P/'FROZEN_18D.json').read_text()); cand=json.loads(json.dumps(old));cand['id']='O_velocity_neutral_v1'
for i in [3,4,13]: cand['free_parameters'][i]=0.;cand['normalized_parameters'][i]=0.
put('CANDIDATE.json',cand)
repair=json.loads(json.dumps(old));repair['id']='O_all_half_v1'
for i in [0,1,2,3,4,10,11,12,13]: repair['free_parameters'][i]*=.5;repair['normalized_parameters'][i]*=.5
put('BOUNDED_REPAIR.json',repair)
conditions=[dict(name='N2',seed=2026101702,prefix={'OUTBOUND':[[-.06,-.06,-.06]]},role='exposed mechanism development'),dict(name='U1',seed=2026101801,prefix={'OUTBOUND':[[-.075,-.045,-.05]]},role='unseen fixed validation'),dict(name='U2',seed=2026101802,prefix={'OUTBOUND':[[.08,.03,.04]]},role='unseen fixed validation'),dict(name='U3',seed=2026101803,prefix={'OUTBOUND':[[.12,-.08,.025]]},role='unseen fixed validation')]
put('RUN_PLAN.json',dict(t0_unix=T0,hard_stop_unix=T0+14400,dispatch_cutoff_unix=T0+10800,physics_hard_stop_unix=T0+12000,physical_timeout_s=600,physics_budget=40,seed=2026101303,validation_conditions=conditions,single_physics_owner=True,candidate='CANDIDATE.json',primary_question='Does removal of OUTBOUND terminal-velocity bias reduce N2 knee acceleration burden while retaining force gains and unchanged full-task constraints?',development_gate='B/E exact historical reproduction; N2 C all task/safety/motion/causal PASS, gain vs B >=1%, knee acceleration maximum <=1.10 matched B; exact C repeat.',validation_gate='Frozen C, no reselection: all 3 unseen lawful prefixes full motion/safety/task/causal PASS, force gain >=1% each; development full C also passes.',repair='Only if C scientific motion hypothesis fails: one predeclared O_all_half_v1 development test; do not per-state tune. A failed repair stops physical search.',meaningful_force='No new force milestone claimed unless >=1 N s additional gain vs E and >=0.1% matched B, reproducible and all qualification PASS. Motion reliability is separate value.',no_training=True,truth_firewall='No evaluation truth enters candidate choice; fixed global parameters only. Original live fork and causal B preserved.',limits='Same Human; shared native prefix full JF included; unconsumed policy suffix validation only; PHYSICAL_LEVEL1, no host/clinical claims.',stop='Any task/safety/causal/matched-state failure stops new physics. Motion failure retained. No threshold changes. No commit/push/merge.'))
put('STATE.json',dict(phase='SETUP_NO_PHYSICS',physics_starts=0))
print(json.dumps(dict(package=str(P),protected=len(protected),metadata=len(inventory),rebase=len(rebase),disk_free=shutil.disk_usage(S).free)))
