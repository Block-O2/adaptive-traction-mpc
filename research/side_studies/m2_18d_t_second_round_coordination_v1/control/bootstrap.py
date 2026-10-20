from pathlib import Path
import os,json,time,hashlib,subprocess,shutil
SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
A=SIDE/'m2_18d_terminal_expanded_prefix_validation_v1'
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
REVIEW=Path(__file__).resolve().parents[1]
P=SIDE/REVIEW.name
assert not P.exists(), 'EXISTS: audit and create a versioned directory before retrying'
P.mkdir()
for d in ['audit','analysis','control','logs','reports','derived','figures','output','motion_series','tmp','provenance']: (P/d).mkdir()
def put(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''): h.update(b)
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
manifest=json.loads((A/'EXECUTION_CODE_MANIFEST.json').read_text())['files']
checked=[]
for rel,h in manifest.items():
 f=A/rel; assert sha(f)==h,rel;checked.append(rel)
put('audit/PRIOR_EXECUTION_MANIFEST_CHECK.json',{'status':'PASS','source':str(A),'files':len(checked),'manifest_sha256':sha(A/'EXECUTION_CODE_MANIFEST.json')})
for d in ['source','code','deps','weights']:
 shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
rebased=[]
for d in ['source','code','deps','weights']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(A) in s:f.write_text(s.replace(str(A),str(P)));rebased.append(str(f.relative_to(P)))
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json']:
 shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['campaign.py','independent_recompute.py','own_campaign.py']:
 shutil.copy2(A/'control'/n,P/'control'/('base_'+n if n=='campaign.py' else n))
shutil.copy2(REVIEW/'control/bootstrap.py',P/'control/bootstrap.py')
for name in ['m2_18d_baseline_qualification_v1','m2_18d_terminal_response_repair_v1','m2_18d_terminal_expanded_prefix_validation_v1','m2_18d_waypoint_smoothing_overnight_v1']:
 for n in ['REPORT.md','VALIDATION_RESULTS.json','FROZEN_SELECTION.json','EVIDENCE_MANIFEST.json','EXECUTION_CODE_MANIFEST.json','CODE_MANIFEST.json','METHOD_DEFINITION.md']:
  f=SIDE/name/n
  if f.exists():shutil.copy2(f,P/'provenance'/(name+'__'+n))
shutil.copy2(MAIN/'CURRENT_RESEARCH_BASELINE.md',P/'provenance/CURRENT_RESEARCH_BASELINE.md')
t0=1792221891.0
put('RUN_PLAN.json',{'t0':'2026-10-17T15:24:51+08:00','t0_unix':t0,'hard_stop_unix':t0+21600,'no_new_physics_after_unix':t0+18900,'dispatch_cutoff_unix':t0+18900,'physics_hard_stop_unix':t0+18900,'physical_timeout_s':900,'physics_budget':40,'validation_reserved':10,'seed':2026101701,'validation_conditions':[],'all_physics_serial':True,'no_training':True})
put('ENVIRONMENT.json',{'canonical':str(P),'review':str(REVIEW),'python':'/home/hank/envs/adaptive-online-rl-v1/bin/python','historical_source':str(A),'created_unix':time.time()})
put('audit/PATH_REBASE.json',{'status':'PASS','path_only':rebased,'source':str(A)})
print(json.dumps({'status':'PASS','package':str(P),'protected_files':len(protected),'manifest_files':len(checked),'seconds_since_T0':time.time()-t0}),flush=True)
