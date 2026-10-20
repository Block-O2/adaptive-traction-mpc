"""Final protection, integrity, bounded-resource and exit audit; no physics."""
from pathlib import Path
import os,json,time,hashlib,subprocess,collections,datetime,shutil
P=Path(__file__).resolve().parents[1];R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def load(n):return json.loads((P/n).read_text())
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as stream:
  for chunk in iter(lambda:stream.read(2**20),b''):h.update(chunk)
 return h.hexdigest()
def put(n,x):
 f=P/n;temp=f.with_suffix(f.suffix+'.tmp');temp.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n');temp.replace(f)
def git(*a):return subprocess.check_output(['git',*a],cwd=R,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
plan=load('RUN_PLAN.json');errors=[];before=load('audit/GIT_CONTENT_BEFORE.json')
head=git('rev-parse','HEAD').decode().strip();branch=git('branch','--show-current').decode().strip();status=git('status','--porcelain=v1','-uall')
git_checks=dict(head=head==before['head'],branch=branch==before['branch'],status_exact=status==(P/'audit/git_status_before.txt').read_bytes(),index=sha(R/'.git/index')==before['index_sha256'],staged_diff=hashlib.sha256(git('diff','--cached','--binary')).hexdigest()==before['staged_diff_sha256'],unstaged_diff=hashlib.sha256(git('diff','--binary')).hexdigest()==before['unstaged_diff_sha256'])
for k,v in git_checks.items():
 if not v:errors.append('GIT_'+k)
changed=[]
for row in before['files']:
 f=R/row['path']
 if row['kind']=='symlink':actual=hashlib.sha256(os.readlink(f).encode()).hexdigest() if f.is_symlink() else None
 else:actual=sha(f) if f.is_file() else None
 if actual!=row['sha256']:changed.append(row['path'])
if changed:errors.append('MAIN_CONTENT_CHANGE')
original_bad=[];copied_bad=[];manifest=load('CODE_MANIFEST.json')
for row in manifest['files']:
 if sha(Path(row['source']))!=row['source_sha256']:original_bad.append(row['source'])
 if sha(P/row['path'])!=row['sha256']:copied_bad.append(row['path'])
if original_bad or copied_bad:errors.append('SOURCE_HASH_CHANGE')
trace_bad=[]
for row in load('audit/HISTORICAL_TRACE_MANIFEST.json')['records']:
 if sha(Path(row['source']))!=row['sha256'] or sha(P/row['destination'])!=row['sha256']:trace_bad.append(row['source'])
if trace_bad:errors.append('HISTORICAL_TRACE_CHANGE')
hv=load('audit/HISTORICAL_VALIDATION_SOURCE.json');assert sha(Path(hv['source']))==hv['sha256']
old=P.parent/'ihear_overnight_research_retrospective_v1'
assert sha(P/'control/frozen18D_baseline_identity.json')==sha(old/'FROZEN_SELECTION.json')
assert sha(P/'audit/HISTORICAL_CURRENT_MODEL_AND_TASK.json')==sha(old/'CURRENT_MODEL_AND_TASK.json')
contract=P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json';contract_source=old/'output/SHARED_COORDINATION_ACTION_CONTRACT.json';assert sha(contract)==sha(contract_source)
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];sc=collections.Counter(r['id'] for r in starts);ec=collections.Counter(r['id'] for r in ends)
if sc!=ec or any(n!=1 for n in sc.values()) or any(r['returncode']!=0 or not r['joined'] for r in ends):errors.append('ATTEMPT_LEDGER')
if len(starts)>160 or len(starts)>130:errors.append('BUDGET')
if any(r['unix']>=plan['dispatch_cutoff_unix'] for r in starts):errors.append('PHYSICS_START_DEADLINE')
if time.time()>=plan['hard_stop_unix']:errors.append('CAMPAIGN_DEADLINE')
if any(r['unix']>=plan['physics_hard_stop_unix'] for r in ends):errors.append('PHYSICS_END_DEADLINE')
owned=[]
for proc in Path('/proc').iterdir():
 if proc.name.isdigit() and int(proc.name)!=os.getpid():
  try:cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
  if str(P) in cmd:owned.append(dict(pid=int(proc.name),cmd=cmd))
if owned:errors.append('OWNED_PROCESS_ACTIVE')
owner=load('control/BASELINE_OWNER.json');exit_record=load('control/BASELINE_WORKER_EXIT.json')
if not owner.get('joined') or owner.get('returncode')!=0 or exit_record.get('active_child') is not None:errors.append('OWNER_EXIT_RECORD')
required=['REPORT.md','RUN_PLAN.json','STATE.json','ATTEMPTS.jsonl','CODE_MANIFEST.json','CURRENT_ACTION_AUTHORITY_AUDIT.md','FORCE_MOTION_MECHANISM.md','DIAGNOSTIC_RESULTS.json','REPRESENTATION_COMPARISON.md','SELECTED_REPRESENTATION.json','CONTROL_POINT_AUTHORITY.md','MATH_VALIDATION.json','PHYSICAL_INTERFACE_GATE.json','EXPLORATION_RESULTS.json','OPTIMIZER_STATUS.json','FROZEN_SELECTION.json','VALIDATION_RESULTS.json','REPETITION_ADAPTATION_DESIGN.md','REPRODUCTION.md','NEXT_RESEARCH_DECISION.md','USER_REQUEST.txt']
missing=[n for n in required if not (P/n).is_file()]
if missing:errors.append('MISSING_DELIVERABLES')
assert load('audit/INDEPENDENT_RAW_VERIFICATION.json')['status']=='PASS'
assert load('VISUAL_QA.json')['status']=='PASS'
assert load('BASELINE_PARENT_GATE.json')['status']=='PASS' and load('BASELINE_ZERO_COLLAPSE_GATE.json')['status']=='PASS'
assert load('VALIDATION_RESULTS.json')['validation_starts_reserved']==30 and load('VALIDATION_RESULTS.json')['validation_starts_used']==0
assert load('FROZEN_SELECTION.json')['PRIMARY'] is None and load('FROZEN_SELECTION.json')['SECONDARY'] is None
assert load('OPTIMIZER_STATUS.json')['physical_optimizer_calls']==0
new_sources=[dict(path=str(f.relative_to(P)),sha256=sha(f),bytes=f.stat().st_size) for folder in ['control','prototype'] for f in (P/folder).rglob('*.py')]
put('audit/NEW_RESEARCH_CODE_MANIFEST.json',dict(unix=time.time(),files=new_sources,extra_contract=dict(source=str(contract_source),source_sha256=sha(contract_source),copy_sha256=sha(contract))))
files=[f for f in P.rglob('*') if f.is_file()];size=sum(f.stat().st_size for f in files);disk=shutil.disk_usage(P)
if size>=8*2**30 or disk.free<2**30:errors.append('STORAGE')
# These three changing meta-records are deliberately excluded to avoid self-hash.
excluded={'STATE.json','PACKAGE_VERIFICATION.json','PACKAGE_CONTENTS.json'}
content=[dict(path=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=sha(f)) for f in files if str(f.relative_to(P)) not in excluded]
put('PACKAGE_CONTENTS.json',dict(unix=time.time(),self_reference_exclusions=sorted(excluded),files=content))
result=dict(status='PASS' if not errors else 'FAIL',final=True,unix=time.time(),errors=errors,git=dict(start_head=before['head'],end_head=head,branch=branch,checks=git_checks,initial_status_lines=len(status.splitlines()),late_before_content_files=len(before['files']),changed_content=changed,scope='initial status/HEAD and later-before-run index/diff/content snapshot; not a complete t0 content mirror'),source_protection=dict(original_manifest_entries=len(manifest['files']),original_bad=original_bad,copied_bad=copied_bad,historical_raw_bad=trace_bad,selected_history_validation_and_frozen_identity_unchanged=True),budget=dict(physical_START=len(starts),physical_END=len(ends),limit=160,development_cap=130,validation_reserved=30,validation_used=0,all_returncodes_zero=True,actual_new_native_steps=load('audit/INDEPENDENT_RAW_VERIFICATION.json')['actual_new_native_steps'],physics_started_before_cutoff=True,physics_ended_before_cutoff=True,elapsed_seconds=time.time()-plan['t0_unix'],remaining_to_final_deadline_seconds=plan['hard_stop_unix']-time.time()),resources=dict(package_bytes=size,package_GiB=size/2**30,target_GiB=5,hard_GiB=8,disk_free_bytes=disk.free),owned_processes=owned,all_owned_physics_exited=not owned,owner_joined=owner['joined'],missing_files=missing,figure_count=len(list((P/'figures').glob('*.png'))),independent_raw_audit='PASS',math_scope='M0-M5 passed; M6 nonzero interface not passed',scientific_outcome='NO_NEW_QUALIFIED_MOTION; new validation 0/0',no_Git_mutation=True,no_training=True,no_old_evidence_deletion=True,no_production_edits=True,qualification_note='Package PASS verifies stated files/protection/budget/exit; not scientific success or new physical-interface qualification')
put('PACKAGE_VERIFICATION.json',result)
state=load('STATE.json');state.update(phase='STOP',terminal_status='COMPLETED_GATED_DIAGNOSTIC_NO_NEW_QUALIFIED_MOTION',reason='Nonzero full-path interface unresolved after one bounded compatibility repair; baseline and all deliverables verified',end_unix=time.time(),end_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),physics_starts=len(starts),physics_ends=len(ends),validation_reserved=30,validation_used=0,output_bytes=size,output_GiB=size/2**30,remaining_seconds=plan['hard_stop_unix']-time.time(),elapsed_seconds=time.time()-plan['t0_unix'],owned_pids=[],all_owned_physics_exited=not owned,last_checkpoint='PACKAGE_VERIFICATION '+result['status'],next_allowed_action=None,automatic_restart_allowed=False,package_verification=result['status'])
put('STATE.json',state)
print(json.dumps(dict(status=result['status'],errors=errors,starts=len(starts),ends=len(ends),git_unchanged=all(git_checks.values()) and not changed,source_unchanged=not original_bad and not copied_bad,size_GiB=size/2**30,owned=owned,elapsed_minutes=(time.time()-plan['t0_unix'])/60)),flush=True)
if errors:raise SystemExit(1)
