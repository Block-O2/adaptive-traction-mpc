from pathlib import Path
import json,hashlib,subprocess,os,time,datetime,shutil
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_terminal_response_repair_v1';P=S/L.name;M=Path('/home/hank/coding/adaptive-traction-mpc-learning')
assert not P.exists(),'NEVER_OVERWRITE'
P.mkdir()
for d in ['audit','control','analysis','reports','output','motion_series','logs','derived','tmp']:(P/d).mkdir()
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
os.environ['GIT_OPTIONAL_LOCKS']='0'
git={k:subprocess.check_output(['git','-C',str(M),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()};put('audit/GIT_BEFORE.json',git)
metadata={};protected={}
for root in [M,S]:
 for f in root.rglob('*'):
  if P in f.parents or '.git' in f.parts or '__pycache__' in f.parts or not f.is_file() or f.is_symlink():continue
  st=f.stat();metadata[str(f)]=[st.st_size,st.st_mtime_ns]
  if f.suffix in ['.py','.json','.md','.xml','.toml','.yaml','.yml','.sha256','.npz','.gz','.jsonl'] or f.name in ['HEAD','config']:protected[str(f)]=sha(f)
put('audit/HISTORY_METADATA_BEFORE.json',metadata);put('audit/PROTECTED_SHA_BEFORE.json',protected)
print('PROTECTION',len(metadata),len(protected),flush=True)
old=json.loads((A/'EXECUTION_CODE_MANIFEST.json').read_text());bad=[n for n,h in old['files'].items() if sha(A/n)!=h];assert not bad,bad
put('audit/PREVIOUS_EXECUTION_MANIFEST_VERIFIED.json',dict(status='PASS',count=len(old['files']),manifest_sha256=sha(A/'EXECUTION_CODE_MANIFEST.json')))
for d in ['source','code','deps','weights']:
 shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
(P/'source/results').mkdir()
rebased=[]
for d in ['source','code','deps']:
 for f in (P/d).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.yaml','.yml','.toml']:continue
  try:t=f.read_text()
  except UnicodeError:continue
  new=t.replace(str(A),str(P))
  if t!=new:
   before=sha(f);f.write_text(new);rebased.append(dict(path=str(f.relative_to(P)),before=before,after=sha(f)))
put('audit/PATH_ONLY_REBASE.json',rebased)
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','PARAMETER_MAP.json','METHOD_DEFINITION.md']:shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['campaign.py','own_campaign.py','independent_recompute.py']:shutil.copy2(A/'control'/n,P/'control'/n)
shutil.copy2(L/'control/bootstrap.py',P/'analysis/bootstrap.py')
t0=datetime.datetime.fromisoformat('2026-10-17T06:47:58+00:00').timestamp()
put('RUN_PLAN.json',dict(t0='2026-10-17T14:47:58+08:00',t0_unix=t0,hard_stop_unix=t0+14400,no_new_physics_after_unix=t0+11700,physics_START_limit=30,physics_budget=30,dispatch_cutoff_unix=t0+11700,physics_hard_stop_unix=t0+13200,physical_timeout_s=900,seed=2026101901,question='Frozen T=1.5 expanded lawful prefix validation after timing contract audit',validation_conditions=[dict(name='V1',seed=2026101901,prefix={'OUTBOUND':[[-.045,-.075,-.055]]},role='new frozen validation'),dict(name='V2',seed=2026101902,prefix={'OUTBOUND':[[-.09,-.03,-.065]]},role='new frozen validation')],primary='Every condition full live parent B/E/T pairing; complete task, motion/fairness, safety, causal, >=1% force reduction vs matched B. No reselection.',stop='Timing/state/pairing gate fail: no physics. Absolute safety/task/causal fail: stop. Motion fail: diagnose frozen condition without tuning. At most two new conditions, deterministic repeats do not add states.'))
put('ENVIRONMENT.json',dict(python='/home/hank/envs/adaptive-online-rl-v1/bin/python',canonical=str(P),review=str(L),historical_source=str(A),created_unix=time.time()))
print('BOOTSTRAP_READY',P,flush=True)
