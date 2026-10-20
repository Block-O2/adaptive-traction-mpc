"""Close one bounded package, then hash and verify only its own files."""
from pathlib import Path
import os,sys,json,time,hashlib,shutil,subprocess
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(n,x):
 p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');t.replace(p)
def close():
 ledger=json.loads((S/'TASK_LEDGER.json').read_text());plan=json.loads((S/'RUN_PLAN.json').read_text());assert not any(x['status']=='RUNNING' for x in ledger.values())
 assert time.time()<plan['hard_stop_unix']
 rows=[]
 for p in (S/'code').glob('*.py'):compile(p.read_text(),str(p),'exec');rows.append(p.name)
 # Module import and two scalar reductions: no model instance or physical step.
 sys.path.insert(0,str(S/'build'));import numpy as np,fast_native,mujoco
 for value in (False,True):
  x=fast_native.small_bool_reduce(np.asarray([value],dtype=bool),False)
  assert type(x) is type(np.all(np.asarray([value],dtype=bool))) and bool(x)==value
  assert x.tobytes()==np.bool_(value).tobytes()
 save('reports/FINAL_ENTRY_AND_NATIVE_CHECK.json',dict(status='PASS',syntax_compiled_files=len(rows),python=sys.version,numpy=np.__version__,mujoco=mujoco.__version__,native=str(fast_native.__file__),native_sha256=sha(Path(fast_native.__file__)),scalar_truth_bytes_type_correct=True,physical_steps=0,model_API_calls=0))
 now=time.time();save('PACKAGE_CLOSED.json',dict(status='CLOSED_WITH_NEGATIVE_B_RUNTIME_RESULT',unix=now,t0_unix=plan['t0_unix'],physics_starts=len(ledger),B_qualified=False,M2=False,training_updates=0,reason='Evidence-supported numerical, causal-clock, IPC, repeatability and scheduler branches completed; original R2 HOLD remains false. No unchanged failing heavy reruns for time filling. Report and read-only recovery remain available.',new_physical_dispatch=False))
 state=json.loads((S/'STATE.json').read_text());state.update(status='COMPLETED_RESEARCH_B_NOT_QUALIFIED',phase='FINAL_VERIFICATION',updated_unix=now,elapsed_h=(now-plan['t0_unix'])/3600,physics_attempts=len(ledger),active=[],BEST_RUNTIME=None,M2=False,Q=False,training_updates=0,next_action='Read-only recovery/manifest verification. Sole new research direction: bounded original HOLD handoff critical path; retain original R2 and authority.')
 save('STATE.json',state);save('checkpoints/CLOSING_DONE.json',dict(unix=now,stop_owned_closing_monitor=True,physics_worker_active=False))
 print('PACKAGE_CLOSED',len(ledger),flush=True)
def manifest():
 assert (S/'PACKAGE_CLOSED.json').is_file()
 shutil.copy2(Path(__file__),S/'authoring/seal_package.py')
 code_manifest=json.loads((S/'FINAL_CODE_MANIFEST.json').read_text());code_manifest['files']['authoring/seal_package.py']=sha(S/'authoring/seal_package.py');save('FINAL_CODE_MANIFEST.json',code_manifest)
 # Check owned runtime processes only, without killing or changing any process.
 found=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  except OSError:continue
  if str(S) in cmd and any(name in cmd for name in ('run_one.py','fast_dispatch.py','cohort_dispatch.py','closing_monitor.py')):found.append(dict(pid=int(p.name),command=cmd))
 assert not found,'OWNED_PROCESS_NOT_JOINED'
 save('reports/FINAL_PROCESS_RECLAMATION.json',dict(status='PASS',unix=time.time(),owned_runtime_processes_remaining=found,unknown_processes_not_killed=True))
 state=json.loads((S/'STATE.json').read_text());now=time.time();state.update(phase='SEALED',updated_unix=now,elapsed_h=(now-state['t0_unix'])/3600,completed_dispatches=list(json.loads((S/'TASK_LEDGER.json').read_text())),full_tasks_qualified=[],completed_field_means='Finished dispatch/export, not physical/R2 qualification; consult TASK_LEDGER worker status and individual original task result.');save('STATE.json',state)
 files={};links={};excluded={'FULL_PACKAGE_MANIFEST.json','reports/FULL_PACKAGE_VERIFICATION.json','runner.lock'}
 for p in sorted(S.rglob('*')):
  rel=str(p.relative_to(S))
  if p.is_symlink():links[rel]=os.readlink(p);continue
  if not p.is_file() or rel in excluded or '__pycache__' in p.parts:continue
  files[rel]=dict(sha256=sha(p),bytes=p.stat().st_size)
 save('FULL_PACKAGE_MANIFEST.json',dict(unix=time.time(),root=str(S),files=files,links=links,excluded=sorted(excluded),note='Only current package files; no scan/copy of historical raw library. Symlink targets remain protected by prior manifest/key authorities. Verification report/self and advisory dead lock PID excluded to avoid recursive self hashes.'))
 bad=[]
 for rel,row in files.items():
  p=S/rel
  if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:bad.append(rel)
 assert not bad
 save('reports/FULL_PACKAGE_VERIFICATION.json',dict(status='PASS',unix=time.time(),files=len(files),manifest_sha256=sha(S/'FULL_PACKAGE_MANIFEST.json'),hashed_regular_file_bytes=sum(v['bytes'] for v in files.values()),failures=bad,all_owned_runtime_children_joined=True,physics_steps=0,model_API_calls=0))
 # Small local delivery; raw archives remain canonical in the requested study.
 names=('REPORT.md','RESUME.md','RUN_PLAN.json','STATE.json','PACKAGE_CLOSED.json','FINAL_CODE_MANIFEST.json','FULL_PACKAGE_MANIFEST.json')
 for n in names:shutil.copy2(S/n,W/n)
 out=W/'delivery_reports';out.mkdir(exist_ok=True)
 for n in ('RESULTS_OVERVIEW.json','HOLD_ROOT_CAUSE.json','FINAL_EXCLUSIVE_BUDGET.json','R3_TO_FAST.patch','R3_TO_FAST_CHANGES.json','FINAL_COMPUTE_ACCOUNT.json','FINAL_ARCHIVE_AND_RECEIPT_VERIFICATION.json','FINAL_RESOURCE_ACCOUNT.json','FINAL_DATA_ACCOUNT.json','ORIGINAL_SOURCE_MATHEMATICS_PRESERVATION.json','ENGINEERING_PRE_REJECT_GUARD_AUDIT.json','PROVENANCE_NOTES.json','MOVING_ORIGINAL_ESCAPE_AUDIT.json','FINAL_ENTRY_AND_NATIVE_CHECK.json','FINAL_PROCESS_RECLAMATION.json','FULL_PACKAGE_VERIFICATION.json'):
  shutil.copy2(S/'reports'/n,out/n)
 shutil.copy2(S/'preservation/FINAL_PRESERVATION.json',out/'FINAL_PRESERVATION.json')
 code=W/'delivery_code';code.mkdir(exist_ok=True)
 for p in (S/'code').glob('*.py'):shutil.copy2(p,code/p.name)
 shutil.copy2(S/'native/fast_native.cpp',code/'fast_native.cpp')
 (W/'DELIVERY_LOCATION.txt').write_text('Canonical full evidence: '+str(S)+'\nWindows delivery contains report, verified manifests, implementation source and compact evidence. Raw results are not duplicated.\n')
 print('FULL_PACKAGE_SEALED_AND_VERIFIED',len(files),sum(v['bytes'] for v in files.values()),flush=True)
if __name__=='__main__':
 assert sys.argv[1] in ('close','manifest')
 close() if sys.argv[1]=='close' else manifest()
