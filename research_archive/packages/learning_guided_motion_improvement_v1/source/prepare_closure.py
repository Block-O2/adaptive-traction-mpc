from pathlib import Path
import json,hashlib,shutil,os,subprocess,re,datetime,time
P=Path('/tmp/lgmi_active_package').read_text().strip();P=Path(P)
ROOT=P.parent; G=ROOT/'rl_b_matched_recovery_stability_v1/github'; H=G/'research/side_studies/ihear_history_to_next_trial_learning_v1'; M=G/'research/side_studies/ihear_overnight_control_learning_transition_v1'
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
# Content hashes for protected scientific artifacts, metadata for every old file.
protected={}; n=0
for root in sorted(ROOT.glob('rl_b_*')):
 if not root.is_dir():continue
 for base,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if d not in ['cpu-env','offline-env','.venv','venv','__pycache__','.git','node_modules']]
  for name in files:
   f=Path(base)/name
   if f.is_symlink():continue
   st=f.stat(); row={'size':st.st_size,'mtime_ns':st.st_mtime_ns}
   if f.suffix in ['.py','.xml','.obj','.stl','.so','.zip','.pt'] or f.name in ['AGENTS.md','REPORT.md'] or 'MANIFEST' in name or 'CONTRACT' in name or 'CHECKPOINT' in name:
    row['sha256']=sha(f)
   protected[str(f)]=row;n+=1
put('audit/HISTORY_START.json',protected)
put('audit/GIT_START.json',{'head':subprocess.check_output(['git','-C',str(G),'rev-parse','HEAD'],text=True).strip(),'branch':subprocess.check_output(['git','-C',str(G),'branch','--show-current'],text=True),'status':subprocess.check_output(['git','-C',str(G),'status','--porcelain=v1','--untracked-files=all'],text=True),'index_sha256':sha(G/'.git/index')})
print('PROTECTED',n,flush=True)
for d in ['code','control','deps','source']:
 shutil.copytree(H/d,P/'runtime'/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'),dirs_exist_ok=False)
# Restore only absent original model assets from the recovered original B/H150 tree.
restored=[]
for f in (M/'source').rglob('*'):
 if not f.is_file() or 'results' in f.relative_to(M/'source').parts:continue
 dest=P/'runtime/source'/f.relative_to(M/'source')
 if not dest.exists() and f.suffix in ['.xml','.obj','.stl','.png','.mtl']:
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest);restored.append({'from':str(f),'to':str(dest.relative_to(P)),'sha256':sha(f)})
for name in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','ACTION_SET.json','FROZEN_SELECTION.json']:
 src=H/name
 if not src.exists():src=M/name
 if src.exists():shutil.copyfile(src,P/'runtime'/name)
(P/'runtime/output').mkdir();(P/'runtime/reports').mkdir();(P/'runtime/audit').mkdir();(P/'runtime/tmp').mkdir();(P/'runtime/source/results').mkdir()
for name in ['RUN_PLAN.json','D01R_PLAN.json']:
 if name=='D01R_PLAN.json':shutil.copyfile(M/name,P/'history'/name)
start=json.loads((P/'START.json').read_text()); t0=datetime.datetime.fromisoformat(start['T0_utc']).timestamp()
plan={'t0_unix':t0,'dispatch_cutoff_unix':t0+6.25*3600,'no_new_physics_after_unix':t0+6.25*3600,'physics_hard_stop_unix':t0+6.5*3600,'hard_stop_unix':t0+7*3600,'physical_timeout_s':600,'physics_budget':80,'native_step_cap':8000000,'development_cap':60,'seed':2026102103,'all_physics_serial':True}
put('runtime/RUN_PLAN.json',plan)
# Register relocations; only runtime path strings are touched.
rebased=[]
for d in ['code','control','deps','source']:
 for f in (P/'runtime'/d).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.toml','.yaml','.yml']:continue
  try:s=f.read_text()
  except UnicodeError:continue
  before=sha(f)
  s2=re.sub(r'/home/hank/coding/adaptive-traction-mpc-side-studies/[A-Za-z0-9_\-]+',str(P/'runtime'),s)
  s2=s2.replace('/home/hank/coding/adaptive-traction-mpc-learning',str(P/'runtime/source'))
  if s2!=s:f.write_text(s2);rebased.append({'path':str(f.relative_to(P)),'before':before,'after':sha(f)})
put('audit/CLOSURE_RELOCATION.json',{'origin':str(H),'missing_assets_restored':restored,'path_only_files':rebased,'no_historical_files_changed':True})
shutil.copyfile(__file__,P/'source/prepare_closure.py')
print('CLOSURE_PREPARED',len(restored),len(rebased),flush=True)
