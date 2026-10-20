"""Final preservation, processes, budget and artifact verification. No physics."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,shutil,ast
P=Path(__file__).resolve().parents[1];S=P.parent;MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
LOCAL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git():return {k:subprocess.check_output(['git','-C',str(MAIN),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()}
ac=read('ATTEMPT_ACCOUNTING.json');assert ac['all_attempts_accounted'] and ac['physical_START']==ac['physical_END'] and ac['physical_START']<=40
assert ac['native_steps_exact']
owned=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit() or int(d.name)==os.getpid():continue
 try:
  argv=(d/'cmdline').read_bytes().split(b'\0');environ=(d/'environ').read_bytes().split(b'\0')
 except (OSError,PermissionError):continue
 iscampaign=any(a in [str(P/'control/campaign.py').encode(),str(P/'control/own_campaign.py').encode()] for a in argv)
 inherits=(b'TMPDIR='+str(P/'tmp').encode()) in environ
 if iscampaign or inherits:owned.append(dict(pid=int(d.name),argv=[a.decode(errors='replace') for a in argv if a]))
assert not owned,('OWNED_PROCESSES_REMAIN',owned)
owner_records=[read(str(f.relative_to(P))) for f in P.glob('*_OWNER.json')]
assert all(r['joined'] for r in owner_records)
before=read('audit/GIT_BEFORE.json');after=git();assert before==after,'GIT_STATE_CHANGED'
put('audit/GIT_AFTER.json',after)
metadata=read('audit/HISTORY_METADATA_BEFORE.json');metabad=[]
for name,old in metadata.items():
 f=Path(name)
 if 'symlink' in old:
  if not f.is_symlink() or os.readlink(f)!=old['symlink']:metabad.append(name)
 elif not f.is_file():metabad.append(name)
 else:
  st=f.stat()
  if st.st_size!=old['size'] or st.st_mtime_ns!=old['mtime_ns']:metabad.append(name)
hashes=read('audit/PROTECTED_SHA_BEFORE.json');bad=[]
for i,(name,h) in enumerate(hashes.items()):
 f=Path(name)
 if not f.is_file() or sha(f)!=h:bad.append(name)
 if i%20000==0:print('PROTECTION_HASH',i,len(hashes),flush=True)
manifest=read('EXECUTION_CODE_MANIFEST.json');frozenbad=[]
for name,h in manifest['files'].items():
 f=P/name
 if not f.is_file() or sha(f)!=h:frozenbad.append(name)
assert not frozenbad,('EXECUTION_CLOSURE_CHANGED',frozenbad)
historical=read('audit/HISTORICAL_MANIFEST_CHECK.json');assert not historical['missing'] and not historical['mismatch']
# Reversal of only the recorded root relocation recovers every historical source byte hash.
H=S/'ihear_overnight_research_retrospective_v1';hm=json.loads((H/'CODE_MANIFEST.json').read_text());semantics=[]
for name,h in hm.items():
 f=P/name
 if not f.is_file():semantics.append(dict(path=name,error='missing'));continue
 content=f.read_bytes()
 if f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:content=content.replace(str(P).encode(),str(H).encode())
 if hashlib.sha256(content).hexdigest()!=h:semantics.append(dict(path=name,error='changed beyond root relocation'))
assert not semantics,semantics
assert not metabad and not bad,('HISTORICAL_PROTECTION_FAILURE',metabad[:20],bad[:20])
for f in (P/'control').glob('*.py'):ast.parse(f.read_text(),filename=str(f))
repro=read('BASELINE_REPRODUCTION.json');val=read('VALIDATION_RESULTS.json')
assert val['historical_primary_motion']['PASS']==0 and val['historical_primary_motion']['denominator']==4
assert val['no_reselection'] and val['no_parameter_update']
assert read('audit/HISTORICAL_FAILURE_RECOMPUTATION.json')['motion_PASS']==0
assert read('audit/INTENT_TO_ACTUAL_EXECUTION.json')['status']=='PASS'
if repro['status']=='PASS':assert read('audit/INDEPENDENT_reproduction.json')['status']=='PASS'
else:assert val['new_pairs']==0
for r in val['rows']:assert read('audit/INDEPENDENT_'+r['condition']+'.json')['status']=='PASS'
assert all(r['full_pair_state_equal'] for r in val['rows'])
assert sha(P/'FROZEN_18D.json')==read('reproduction_PAIR_GATE.json')['parameter_sha256'] if repro['status']=='PASS' else True
plan=read('RUN_PLAN.json');start_times=[r['START_unix'] for r in ac['rows']];end_times=[r['END_unix'] for r in ac['rows']]
assert not start_times or max(start_times)<plan['dispatch_cutoff_unix']
assert time.time()<plan['hard_stop_unix']
required=['REPORT.md','METHOD_DEFINITION.md','PARAMETER_MAP.json','SOURCE_AND_RESULT_LINEAGE.md','BASELINE_REPRODUCTION.json','REPRODUCTION_AUDIT.md','VALIDATION_RESULTS.json','ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md']
assert all((P/n).is_file() and (P/n).stat().st_size for n in required)
for f in P.glob('*.json'):json.loads(f.read_text())
protection=dict(status='PASS',unix=time.time(),git_equal=True,branch=before['branch'].strip(),HEAD=before['head'].strip(),history_metadata_checked=len(metadata),metadata_mismatches=metabad,protected_sha_checked=len(hashes),sha_mismatches=bad,execution_manifest_unchanged=True,historical_original_manifest_entries=historical['entries'],source_byte_equivalent_after_reversing_path_relocation=True,source_semantic_errors=semantics,active_owned_processes=owned,owners=owner_records,new_physical_starts_in_closeout=0)
put('audit/FINAL_PROTECTION_AND_EXIT.json',protection)
put('PHYSICS_STOP.json',dict(unix=time.time(),reason='Completed frozen finite qualification set or reproduction gate stop; no next study',all_owned_physical_exited=True))
put('STATE.json',dict(status='STOP',phase='CLOSED',physics_starts=ac['physical_START'],physics_ends=ac['physical_END'],owned_active=0,next_action='none; new research requires a separate user-authorized study',decision=read('NEXT_RESEARCH_DECISION.json')))
put('PACKAGE_VERIFICATION.json',dict(status='PASS',unix=time.time(),meaning='artifact/protection/process/budget checks only; not a scientific robustness PASS',required_files_present=True,required=required+['PACKAGE_VERIFICATION.json'],physical_START=ac['physical_START'],physical_END=ac['physical_END'],actual_new_native_steps=ac['actual_new_native_steps'],all_owned_physical_exited=True,active_owned_processes=owned,git_equal=True,history_metadata_checked=len(metadata),history_SHA_checked=len(hashes),historical_manifest_entries=historical['entries'],frozen_code_manifest_verified=True,source_semantics_preserved=True,parameter_identity_preserved=True,original_motion_protocol_preserved=True,reproduction_status=repro['status'],new_validation_pairs=val['new_pairs'],new_motion_PASS=val['motion_PASS'],historical_motion_PASS='0/4 retained',six_hour_limit_met=True,last_hour_no_new_START=True,last_START_unix=max(start_times,default=None),last_END_unix=max(end_times,default=None),package_bytes=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()),disk_free_bytes=shutil.disk_usage(P).free,limitations='PHYSICAL_LEVEL1 only; no patient/Native LEVEL2/host-clock LEVEL3/hardware/clinical qualification',protection_details='audit/FINAL_PROTECTION_AND_EXIT.json',no_git_mutation=True))
files={}
for f in P.rglob('*'):
 if not f.is_file() or f.is_symlink() or 'tmp' in f.relative_to(P).parts or f.name in ['EVIDENCE_MANIFEST.json','REVIEW_MIRROR_MANIFEST.json']:continue
 files[str(f.relative_to(P))]=dict(bytes=f.stat().st_size,sha256=sha(f))
put('EVIDENCE_MANIFEST.json',dict(files=files,excludes='self-reference, review mirror manifest and temporary runtime cache; original historical inputs separately SHA protected',canonical=str(P)))
# This mirror is review material; complete source/results remain in canonical WSL.
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl']:shutil.copy2(f,LOCAL/f.name)
for name in ['control','provenance','derived','reports','audit','logs']:
 for f in (P/name).rglob('*'):
  if not f.is_file():continue
  dst=LOCAL/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
mirror={str(f.relative_to(LOCAL)):sha(f) for f in LOCAL.rglob('*') if f.is_file() and f.name!='REVIEW_MIRROR_MANIFEST.json'}
put('REVIEW_MIRROR_MANIFEST.json',dict(canonical=str(P),mirror=str(LOCAL),full_raw_mirrored=False,files=mirror));shutil.copy2(P/'REVIEW_MIRROR_MANIFEST.json',LOCAL/'REVIEW_MIRROR_MANIFEST.json')
print(json.dumps(dict(status='PASS',files=len(files),protected=len(hashes),metadata=len(metadata),owned_active=0,START=ac['physical_START'],END=ac['physical_END'],decision=read('NEXT_RESEARCH_DECISION.json')['branch'])),flush=True)
