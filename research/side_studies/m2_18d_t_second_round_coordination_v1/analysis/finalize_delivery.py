from pathlib import Path
import os,sys,json,time,hashlib,shutil,subprocess,datetime
REVIEW=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/REVIEW.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''):h.update(b)
 return h.hexdigest()
assert read('PACKAGE_VERIFICATION.json')['status']=='PASS'
assert read('VALIDATION_RESULTS.json')['status']=='BLOCKED_BY_FROZEN_BASELINE_MOTION_GATE'
assert P.is_dir() and REVIEW.name==P.name and str(REVIEW).startswith('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/')
# Preserve authoring/arithmetic sources separately from immutable execution code.
for f in (REVIEW/'analysis').glob('*.py'):shutil.copy2(f,P/'analysis'/f.name)
put('ANALYSIS_MANIFEST.json',dict(files={str(f.relative_to(P)):sha(f) for f in (P/'analysis').glob('*.py')},not_in_physical_execution_closure=True,unused_positive_validation_branch=['analysis/validation_summary.py'],actual_validation_stop_report='analysis/diagnose_validation_stop.py',scope='Later arithmetic/plot/report/closure sources; execution code and selection remain frozen under EXECUTION_CODE_MANIFEST.json'))
required=['REPORT.md','BASELINE_CONTRACT.md','MECHANISM_DIAGNOSIS.md','INTERVENTION_PROTOCOL.md','EXPLORATION_RESULTS.jsonl','ATTEMPT_ACCOUNTING.json','FROZEN_SELECTION.json','VALIDATION_RESULTS.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md']
for n in required:assert (P/n).is_file()
for f in P.glob('*.json'):json.loads(f.read_text())
for line in (P/'EXPLORATION_RESULTS.jsonl').read_text().splitlines():json.loads(line)
excludes={'EVIDENCE_MANIFEST.json','REVIEW_MIRROR_MANIFEST.json','DELIVERY_VERIFICATION.json'}
files={}
for f in sorted(P.rglob('*')):
 if not f.is_file() or 'tmp' in f.relative_to(P).parts or '__pycache__' in f.parts or f.suffix=='.lock' or str(f.relative_to(P)) in excludes:continue
 files[str(f.relative_to(P))]=dict(size=f.stat().st_size,sha256=sha(f))
put('EVIDENCE_MANIFEST.json',dict(status='PASS',canonical=str(P),files=files,excluded=['tmp/ and lock/cache files',*sorted(excludes)],scope='Complete research evidence/source/raw/receipts including all failed/partial artifacts; generated manifest and delivery/self indices excluded to avoid cycles'))
# Export readable evidence only; canonical retains all runtime raw and full source closure.
selected=[]
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl'] and f.name not in ['REVIEW_MIRROR_MANIFEST.json','DELIVERY_VERIFICATION.json']:selected.append(f)
for directory in ['analysis','control','figures','derived','motion_series','reports','logs','output','provenance','audit']:
 for f in (P/directory).rglob('*'):
  if not f.is_file() or '__pycache__' in f.parts:continue
  if f.name in ['GIT_BEFORE.json','HISTORY_BEFORE.json']:continue
  selected.append(f)
mirror_bytes=sum(f.stat().st_size for f in set(selected));assert shutil.disk_usage(REVIEW).free>mirror_bytes+512*2**20,'MIRROR_DISK_RESERVE'
copied={}
for f in sorted(set(selected)):
 rel=f.relative_to(P);dst=REVIEW/rel;assert dst.resolve().is_relative_to(REVIEW.resolve())
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
 h=sha(f);assert sha(dst)==h,str(rel);copied[str(rel)]=dict(size=f.stat().st_size,sha256=h)
mirror=dict(status='PASS',files=copied,canonical_full_source_raw_receipts=str(P),scope='Readable reports, original measured metrics/receipt lineage, dense Human motion series, derived calculations, audit summaries and authoring/control scripts; complete runtime raw and full execution source/deps/weights remain canonical; heavy original Git/history snapshots remain canonical',excluded_self=['REVIEW_MIRROR_MANIFEST.json','DELIVERY_VERIFICATION.json'])
put('REVIEW_MIRROR_MANIFEST.json',mirror);shutil.copy2(P/'REVIEW_MIRROR_MANIFEST.json',REVIEW/'REVIEW_MIRROR_MANIFEST.json')
# Check every canonical evidence hash after export, without rerunning physics or metric tests.
for rel,rec in files.items():assert sha(P/rel)==rec['sha256'],rel
assert all(sha(P/rel)==h for rel,h in read('EXECUTION_CODE_MANIFEST.json')['files'].items())
assert sha(P/'FROZEN_SELECTION.json')==read('NEW_PREFIX_VALIDATION_PROTOCOL.json')['selection_sha256']
assert read('ATTEMPT_ACCOUNTING.json')['physical_START']==read('ATTEMPT_ACCOUNTING.json')['physical_END']==21
active=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if str(P) in cmd and any(k in cmd for k in ['/control/campaign.py','/control/owner.py','native_executor']):active.append(dict(pid=int(d.name),command=cmd))
assert not active,active
env=dict(os.environ,GIT_OPTIONAL_LOCKS='0');main='/home/hank/coding/adaptive-traction-mpc-learning';before=read('audit/GIT_BEFORE.json')
for key,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:assert subprocess.check_output(['git','-C',main,*args],env=env).decode()==before[key]
now=time.time();result=dict(status='PASS',finished_unix=now,finished_beijing=datetime.datetime.fromtimestamp(now,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),elapsed_minutes=(now-read('RUN_PLAN.json')['t0_unix'])/60,canonical_evidence_files=len(files),review_mirror_files=len(copied),required_files_present=True,all_evidence_hashes_verified_after_export=True,scientific_status=read('VALIDATION_RESULTS.json')['status'],audit_pass_does_not_promote_candidate=True,physical_START_END=[21,21],actual_new_native_steps=read('ATTEMPT_ACCOUNTING.json')['actual_new_native_steps'],all_owned_physics_exited=True,git_logical_state_unchanged=True,no_auto_learning_or_next_study=True,STOP=True)
put('DELIVERY_VERIFICATION.json',result);shutil.copy2(P/'DELIVERY_VERIFICATION.json',REVIEW/'DELIVERY_VERIFICATION.json')
print(json.dumps(result),flush=True)
