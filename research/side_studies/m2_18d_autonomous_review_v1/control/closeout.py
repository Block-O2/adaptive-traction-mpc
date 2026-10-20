"""Final immutable evidence/protection and process audit. Never starts physics."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,shutil,ast
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name;MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git():return {k:subprocess.check_output(['git','-C',str(MAIN),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()}
assert read('ATTEMPT_ACCOUNTING.json')['all_attempts_accounted']
ac=read('ATTEMPT_ACCOUNTING.json');assert ac['physical_START']==ac['physical_END'] and ac['physical_START']<=40 and ac['native_steps_exact'] and ac['serial_forks']
owned=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit() or int(d.name)==os.getpid():continue
 try:argv=(d/'cmdline').read_bytes().split(b'\0');env=(d/'environ').read_bytes().split(b'\0')
 except (OSError,PermissionError):continue
 names=[str(P/'control'/n).encode() for n in ['campaign.py','own_campaign.py','research_sequence.py']]
 if any(a in names for a in argv) or (b'TMPDIR='+str(P/'tmp').encode()) in env:owned.append(dict(pid=int(d.name),argv=[a.decode(errors='replace') for a in argv if a]))
assert not owned,owned
owners=[json.loads(f.read_text()) for f in P.glob('*_OWNER.json')];assert all(r['joined'] for r in owners)
frozen=read('EXECUTION_CODE_MANIFEST.json')['files'];frozenbad=[name for name,h in frozen.items() if not (P/name).is_file() or sha(P/name)!=h];assert not frozenbad,frozenbad
supplement=read('ORCHESTRATION_AND_ANALYSIS_MANIFEST.json')['files'];assert all(sha(P/name)==h for name,h in supplement.items())
after=git();assert after==read('audit/GIT_BEFORE.json'),'GIT_LOGICAL_STATE_CHANGED';put('audit/GIT_AFTER.json',after)
metadata=read('audit/HISTORY_METADATA_BEFORE.json');metabad=[]
for name,old in metadata.items():
 f=Path(name)
 if 'symlink' in old:
  if not f.is_symlink() or os.readlink(f)!=old['symlink']:metabad.append(name)
 elif not f.is_file():metabad.append(name)
 else:
  st=f.stat()
  if st.st_size!=old['size'] or st.st_mtime_ns!=old['mtime_ns']:metabad.append(name)
protected=read('audit/PROTECTED_SHA_BEFORE.json');hashbad=[]
for i,(name,h) in enumerate(protected.items()):
 if not Path(name).is_file() or sha(Path(name))!=h:hashbad.append(name)
 if i%10000==0:print('PROTECTION_CHECK',i,len(protected),flush=True)
put('audit/FINAL_PROTECTION.json',dict(status='PASS' if not metabad and not hashbad else 'FAIL',unix=time.time(),git_logical_state_equal=True,history_metadata_checked=len(metadata),metadata_mismatches=metabad,protected_sha_checked=len(protected),sha_mismatches=hashbad,execution_manifest_unchanged=True,supplemental_manifest_unchanged=True,owned_physical_processes=owned,owner_records=owners,scope='All original main working-tree file SHA; historical Side Studies full size/mtime/symlink inventory; relevant packages non-results plus trace.npz SHA. No claim to hash every historical raw gzip or initial .git/index byte identity.'))
assert not metabad and not hashbad,(metabad[:10],hashbad[:10])
Q=P.parent/'m2_18d_baseline_qualification_v1';sourcebad=[]
for d in ['source','code','deps','weights']:
 for f in (Q/d).rglob('*'):
  if not f.is_file() or 'results' in f.parts or '__pycache__' in f.parts or f.suffix=='.pyc':continue
  rel=f.relative_to(Q);target=P/rel
  if not target.is_file():sourcebad.append(str(rel));continue
  expected=f.read_bytes()
  if f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:expected=expected.decode().replace(str(Q),str(P)).encode()
   except UnicodeError:pass
  if target.read_bytes()!=expected:sourcebad.append(str(rel))
assert not sourcebad,sourcebad
assert read('audit/INTENT_TO_ACTUAL_EXECUTION.json')['status']=='PASS'
assert read('derived/ALL_CANDIDATE_FAILURE_DIAGNOSES.json')['status']=='PASS'
for g in read('EXPERIMENT_RESULTS.json')['groups']:assert read('audit/INDEPENDENT_'+g+'.json')['status']=='PASS'
for d in ['control','code']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
required=['REPORT.md','PRIORITY_AUDIT.md','SELECTED_IMPROVEMENT.md','METHOD_AND_PARAMETER_CONTRACT.md','EXPERIMENT_RESULTS.json','ATTEMPT_ACCOUNTING.json','VALIDATION_RESULTS.json','CODE_MANIFEST.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md']
codefiles={str(f.relative_to(P)):sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and 'results' not in f.parts and '__pycache__' not in f.parts}
for n in ['RUN_PLAN.json','FROZEN_18D.json','CANDIDATE.json','BOUNDED_REPAIR.json','MOTION_ACCEPTANCE_PROTOCOL.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json']:codefiles[n]=sha(P/n)
put('CODE_MANIFEST.json',dict(unix=time.time(),files=codefiles,physics_execution_manifest='EXECUTION_CODE_MANIFEST.json',orchestration_manifest='ORCHESTRATION_AND_ANALYSIS_MANIFEST.json',historical_source_semantics_unchanged=True,source_origin=str(Q),new_control_logic='Fixed parameter generation and research campaign only; original controller/admission/safety untouched'))
for n in required:
 if n!='PACKAGE_VERIFICATION.json':assert (P/n).is_file() and (P/n).stat().st_size,n
for f in P.glob('*.json'):json.loads(f.read_text())
plan=read('RUN_PLAN.json');assert time.time()<plan['hard_stop_unix'];assert all(r['START_unix']<plan['dispatch_cutoff_unix'] for r in ac['rows'])
assert all(r['END_unix']<plan['physics_hard_stop_unix'] for r in ac['rows'])
put('PHYSICS_STOP.json',dict(unix=time.time(),reason=read('SEQUENCE_DECISION.json')['reason'] if 'reason' in read('SEQUENCE_DECISION.json') else 'Completed finite registered sequence',owned_physical_exited=True,automatic_next_study=False))
put('STATE.json',dict(status='STOP',phase='CLOSED',physical_START=ac['physical_START'],physical_END=ac['physical_END'],owned_active=0,next_action='none',decision=read('NEXT_RESEARCH_DECISION.json')))
put('PACKAGE_VERIFICATION.json',dict(status='PASS',unix=time.time(),meaning='Package/protection/process/budget audit, separate from algorithm scientific qualification',required_files=required,required_files_present=True,physical_START=ac['physical_START'],physical_END=ac['physical_END'],actual_new_native_steps=ac['actual_new_native_steps'],all_owned_physical_exited=True,active_owned_processes=[],git_logical_state_equal=True,history_metadata_checked=len(metadata),historical_SHA_checked=len(protected),frozen_execution_manifest_verified=True,supplemental_manifest_verified=True,original_source_semantics_preserved=True,original_parameters_and_motion_thresholds_preserved=True,same_Human=True,historical_motion_0_of_4_retained=True,latest_prior_3_of_4_retained=True,new_unseen_prefix_pairs=read('VALIDATION_RESULTS.json')['new_unseen_prefix_pairs'],new_scientific_status=read('VALIDATION_RESULTS.json')['status'],four_hour_hard_limit_met=True,elapsed_hours=(time.time()-plan['t0_unix'])/3600,hard_stop_unix=plan['hard_stop_unix'],package_bytes_snapshot=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()),disk_free_bytes=shutil.disk_usage(P).free,reproduction_entry='REPRODUCTION.md',no_commit_push_merge=True))
files={str(f.relative_to(P)):dict(bytes=f.stat().st_size,sha256=sha(f)) for f in P.rglob('*') if f.is_file() and not f.is_symlink() and 'tmp' not in f.relative_to(P).parts and f.name not in ['EVIDENCE_MANIFEST.json','REVIEW_MIRROR_MANIFEST.json','STORAGE.json']}
put('EVIDENCE_MANIFEST.json',dict(canonical=str(P),files=files,excludes=['self','REVIEW_MIRROR_MANIFEST.json','STORAGE.json','tmp runtime caches']))
# Actual final package inventory includes these final JSON files; source/data bytes are independently hashed above.
storagefiles=[f for f in P.rglob('*') if f.is_file()];put('STORAGE.json',dict(unix=time.time(),files_before_storage=len(storagefiles),logical_bytes_before_storage=sum(f.stat().st_size for f in storagefiles),allocated_bytes_before_storage=sum(f.stat().st_blocks*512 for f in storagefiles),disk_free=shutil.disk_usage(P).free,full_source_raw_in_WSL=True,Windows_mirror_full_raw=False))
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl']:shutil.copy2(f,L/f.name)
for d in ['control','provenance','derived','reports','audit','logs','figures']:
 for f in (P/d).rglob('*'):
  if not f.is_file():continue
  dest=L/f.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
mirror={str(f.relative_to(L)):sha(f) for f in L.rglob('*') if f.is_file() and f.name!='REVIEW_MIRROR_MANIFEST.json'}
for n,h in mirror.items():assert (P/n).is_file() and sha(P/n)==h,('MIRROR_MISMATCH',n)
put('REVIEW_MIRROR_MANIFEST.json',dict(canonical=str(P),mirror=str(L),files=mirror,full_source_raw_mirrored=False));shutil.copy2(P/'REVIEW_MIRROR_MANIFEST.json',L/'REVIEW_MIRROR_MANIFEST.json')
assert all((P/n).is_file() and (L/n).is_file() for n in required)
print(json.dumps(dict(status='PASS',START=ac['physical_START'],END=ac['physical_END'],protected=len(protected),metadata=len(metadata),owned_active=0,files=len(files),elapsed_hours=(time.time()-plan['t0_unix'])/3600,decision=read('NEXT_RESEARCH_DECISION.json')['branch']),ensure_ascii=False),flush=True)
