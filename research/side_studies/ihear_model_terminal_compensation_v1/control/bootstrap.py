from pathlib import Path
import os,json,time,hashlib,subprocess,shutil,datetime
SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
R=Path(__file__).resolve().parents[1];P=SIDE/R.name;A=SIDE/'ihear_autonomous_multitrack_v1'
assert not P.exists(),'Never overwrite existing study'
P.mkdir()
for d in ['audit','analysis','control','logs','reports','derived','figures','output','motion_series','tmp','provenance']:(P/d).mkdir()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git():
 env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
 return {n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
t0=datetime.datetime.fromisoformat('2026-10-18T17:40:00+08:00').timestamp()
put('RUN_PLAN.json',dict(t0='2026-10-18T17:40:00+08:00',t0_unix=t0,hard_stop_unix=t0+28800,no_new_physics_after_unix=t0+25200,physics_hard_stop_unix=t0+25200,physical_timeout_s=900,physics_budget=80,development_cap=60,validation_reserved=20,all_physics_serial=True,no_training=True,early_finish_when_conclusive=True))
put('ENVIRONMENT.json',dict(canonical=str(P),review=str(R),python='/home/hank/envs/adaptive-online-rl-v1/bin/python',historical_source=str(A),created_unix=time.time(),distribution=os.environ.get('WSL_DISTRO_NAME')))
put('STATE.json',dict(phase='READ_ONLY_ARCHITECTURE_AUDIT',physics_starts=0,next='Audit model/control interfaces; causal historical prediction; preregister candidates before physics'))
put('audit/GIT_BEFORE.json',git())
for p in [Path('/AGENTS.md'),Path('/home/AGENTS.md'),Path('/home/hank/AGENTS.md'),Path('/home/hank/coding/AGENTS.md'),SIDE/'AGENTS.md']:
 if p.exists():print('ANCESTOR_INSTRUCTIONS',str(p),p.read_text(),flush=True)
protected={}
print('Protection snapshot started',flush=True)
for root in [MAIN,SIDE]:
 for f in sorted(root.rglob('*')):
  if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts:continue
  st=f.stat();protected[str(f)]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(f))
put('audit/HISTORY_BEFORE.json',protected)
checks=[]
for name in ['ihear_autonomous_multitrack_v1','m2_18d_early_return_motion_repair_v1','m2_18d_w1_d_qualification_v1','m2_18d_t_second_round_coordination_v1']:
 root=SIDE/name
 for mn in ['EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json']:
  obj=json.loads((root/mn).read_text());errors=[]
  for rel,entry in obj['files'].items():
   f=Path(rel) if Path(rel).is_absolute() else root/rel;expected=entry if isinstance(entry,str) else entry['sha256']
   if not f.exists() or sha(f)!=expected:errors.append(str(f))
  checks.append(dict(study=name,manifest=mn,count=len(obj['files']),errors=errors,sha256=sha(root/mn)))
put('audit/HISTORICAL_MANIFESTS_VERIFIED.json',checks);assert not any(x['errors'] for x in checks)
for d in ['source','code','deps','weights']:shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
rebased=[]
for d in ['source','code','deps','weights']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(A) in s:f.write_text(s.replace(str(A),str(P)));rebased.append(str(f.relative_to(P)))
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','FROZEN_SELECTION.json','SELECTION_RULE.json']:shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['base_campaign.py','round_planner.py','interface_base.py','independent_recompute.py','owner.py','early_return_planner.py']:shutil.copy2(A/'control'/n,P/'control'/n)
shutil.copy2(R/'control/bootstrap.py',P/'control/bootstrap.py')
shutil.copy2(MAIN/'AGENTS.md',P/'provenance/AGENTS.md')
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/56051565-8e48-4076-bb71-e8bb6b192c0e/已粘贴的文本.txt',P/'provenance/USER_REQUEST.txt')
for n in ['REPORT.md','Adev_PLAN.json','VALIDATION_RESULTS.json','EXECUTION_CODE_MANIFEST.json','HOLDOUT_REGISTRATION.json','NEXT_RESEARCH_DECISION.md']:shutil.copy2(A/n,P/'provenance'/('multitrack__'+n))
put('audit/PATH_REBASE.json',dict(path_only=rebased,source=str(A)))
put('audit/WRITING_REFERENCE.json',dict(status='No suitable writing references found in the returned results',style_source='User supplied Chinese task contract; no unrelated personal-source search'))
for f in [P/'ENVIRONMENT.json',P/'RUN_PLAN.json',P/'STATE.json']:shutil.copy2(f,R/f.name)
print(json.dumps(dict(status='PASS',protected_files=len(protected),checks=checks,seconds_since_T0=time.time()-t0)),flush=True)
