from pathlib import Path
import os,json,time,hashlib,subprocess,shutil,datetime
SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
A=SIDE/'m2_18d_t_second_round_coordination_v1'
REVIEW=Path(__file__).resolve().parents[1];P=SIDE/REVIEW.name
assert not P.exists(),'EXISTING_STUDY_REQUIRES_AUDIT_AND_NEW_VERSION'
P.mkdir()
for d in ['audit','analysis','control','logs','reports','derived','figures','output','motion_series','tmp','provenance']:(P/d).mkdir()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git():
 env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
 return {n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
put('audit/GIT_BEFORE.json',git())
protected={}
for root in [MAIN,SIDE]:
 for f in sorted(root.rglob('*')):
  if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts:continue
  st=f.stat();protected[str(f)]={'size':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':sha(f)}
put('audit/HISTORY_BEFORE.json',protected)
checks=[]
for name in ['m2_18d_baseline_qualification_v1','m2_18d_terminal_response_repair_v1','m2_18d_terminal_expanded_prefix_validation_v1','m2_18d_t_second_round_coordination_v1']:
 root=SIDE/name
 for mn in ['EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json']:
  obj=json.loads((root/mn).read_text());errors=[]
  for rel,entry in obj['files'].items():
   f=Path(rel) if Path(rel).is_absolute() else root/rel
   expected=entry if isinstance(entry,str) else entry['sha256']
   if not f.exists() or sha(f)!=expected:errors.append(str(f))
  checks.append(dict(study=name,manifest=mn,count=len(obj['files']),errors=errors,sha256=sha(root/mn)))
put('audit/HISTORICAL_MANIFESTS_VERIFIED.json',checks)
assert not any(x['errors'] for x in checks),checks
for d in ['source','code','deps','weights']:
 shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
rebased=[]
for d in ['source','code','deps','weights']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(A) in s:f.write_text(s.replace(str(A),str(P)));rebased.append(str(f.relative_to(P)))
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','FROZEN_SELECTION.json','SELECTION_RULE.json']:
 shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for f in (A/'control').glob('*.py'):
 if f.name!='bootstrap.py':shutil.copy2(f,P/'control'/f.name)
shutil.copy2(REVIEW/'control/bootstrap.py',P/'control/bootstrap.py')
for n in ['REPORT.md','W1_PLAN.json','W2_PLAN.json','VALIDATION_RESULTS.json','REFINEMENT_PROTOCOL.json','EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json','NEW_PREFIX_VALIDATION_PROTOCOL.json']:
 shutil.copy2(A/n,P/'provenance'/('previous__'+n))
shutil.copy2(MAIN/'AGENTS.md',P/'provenance/AGENTS.md')
t0=datetime.datetime.fromisoformat('2026-10-17T17:34:07+08:00').timestamp()
put('RUN_PLAN.json',dict(t0='2026-10-17T17:34:07+08:00',t0_unix=t0,hard_stop_unix=t0+14400,no_new_physics_after_unix=t0+11700,dispatch_cutoff_unix=t0+11700,physics_hard_stop_unix=t0+11700,physical_timeout_s=900,physics_budget=20,seed=2026102001,all_physics_serial=True,no_training=True))
put('ENVIRONMENT.json',dict(canonical=str(P),review=str(REVIEW),python='/home/hank/envs/adaptive-online-rl-v1/bin/python',historical_source=str(A),created_unix=time.time(),distribution=os.environ.get('WSL_DISTRO_NAME')))
put('audit/PATH_REBASE.json',dict(path_only=rebased,source=str(A)))
print(json.dumps(dict(status='PASS',protected_files=len(protected),manifest_checks=checks,seconds_since_T0=time.time()-t0)),flush=True)
