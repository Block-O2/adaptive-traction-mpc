from pathlib import Path
import os,json,time,hashlib,subprocess
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(2**20),b''):h.update(b)
 return h.hexdigest()
plan=read('RUN_PLAN.json');events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];ss=[r for r in events if r['event']=='START'];ee=[r for r in events if r['event']=='END'];assert len(ss)<=24 and len(ss)==len(ee)
assert len(set(r['id'] for r in ss))==len(ss) and len(set(r['id'] for r in ee))==len(ee) and {r['id'] for r in ss}=={r['id'] for r in ee}
scientific={r['id']:dict(all_original_qualifications=r['all_original_qualifications'],motion_pass=r['motion']['acceptance_pass'],failed_requirements=r['motion']['failed_requirements'],task=r['task'],safety=r['absolute_safety'],causal=r['receipt']) for r in read('EXPERIMENT_RESULTS.json')['rows']};rows=[]
for s in ss:
 end=next(r for r in ee if r['id']==s['id']);ident=s['id'];assert s['code_manifest_sha256']==sha(P/'EXECUTION_CODE_MANIFEST.json');assert s['group_plan_sha256']==sha(P/(s['group']+'_PLAN.json'))
 assert read('EXECUTION_CODE_MANIFEST.json')['frozen_unix']<s['unix']<plan['no_new_physics_after_unix']-plan['physical_timeout_s']
 data=read('output/'+ident+'_DATA.json') if (P/'output'/(ident+'_DATA.json')).exists() else None
 partial=read('output/'+ident+'_PARTIAL_COMPUTE.json') if (P/'output'/(ident+'_PARTIAL_COMPUTE.json')).exists() else None
 steps=data['metric']['actual_new_native_physics_steps'] if data else partial.get('actual_new_native_physics_steps') if partial else None
 rows.append(dict(id=ident,START=s,END=end,returncode=end['returncode'],complete_task=bool(end['returncode']==0 and data is not None),partial=end['returncode']!=0,scientific_qualification=scientific.get(ident,dict(role='cold parent or infrastructure-preserved B; not repair ranking')),actual_new_native_steps=steps,complete_native_steps=data['metric']['native_physics_steps'] if data else None,full_state_fork=None if data is None else data['branch_start']))
for kind in ['FULL_TASK_FORK','LEGAL_COLD_PARENT']:
 starts=sorted([r for r in ss if r['kind']==kind],key=lambda r:r['unix'])
 for a,b in zip(starts,starts[1:]):assert next(r['unix'] for r in ee if r['id']==a['id'])<=b['unix'],'OVERLAPPING_PHYSICS'
assert read('audit/INDEPENDENT_VERIFICATION.json')['status']=='PASS'
assert {x['id'] for x in read('audit/INDEPENDENT_VERIFICATION.json')['checks']}=={r['id'] for r in ee if r['returncode']==0}
assert read('audit/INTERVENTION_EXECUTION_AUDIT.json')['status']=='PASS'
assert read('audit/FIGURE_QA.json')['status']=='PASS'
assert read('audit/REPORT_QA.json')['status']=='PASS'
assert read('audit/SOURCE_CLOSURE_VERIFIED.json')['status']=='PASS'
assert read('derived/CAUSAL_RESPONSE_AUDIT.json')['status']=='PASS'
for g in read('EXPERIMENT_RESULTS.json')['groups']:
 assert read(g+'_DONE.json')['all_children_joined'] and read(g+'_OWNER.json')['joined'] and read(g+'_OWNER.json')['returncode']==0
 assert read(g+'_PAIR_GATE.json')['all_parent_unchanged'] and len(set(read(g+'_PAIR_GATE.json')['hashes'].values()))==1
 assert read(g+'_PARENT_GATE.json')['status']=='PASS'
 if read(g+'_PLAN.json').get('reproduce_W1'):
  for arm in ['B','T','D']:assert read('audit/'+g+'_'+arm+'_HISTORICAL_GATE.json')['status']=='PASS'
assert all(x['actual_new_native_steps'] is not None for x in rows),'UNKNOWN_PARTIAL_STEP_COUNT'
put('ATTEMPT_ACCOUNTING.json',dict(status='PASS',physical_START=len(ss),physical_END=len(ee),limit=24,partial_count=sum(r['partial'] for r in rows),infrastructure_failures_preserved=True,actual_new_native_steps=sum(r['actual_new_native_steps'] for r in rows),all_physics_serial=True,parent_waits_during_forks=True,attempts=rows))
put('PHYSICS_CLOSED.json',dict(unix=time.time(),new_START_forbidden=True,START=len(ss),END=len(ee),reason='bounded repair decision complete; no further search/training'))
if not (P/'PHYSICS_STOP.json').exists():put('PHYSICS_STOP.json',dict(unix=time.time(),reason='final STOP',new_START_forbidden=True))
env=dict(os.environ,GIT_OPTIONAL_LOCKS='0');git={n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
assert git==read('audit/GIT_BEFORE.json'),'GIT_LOGICAL_STATE_CHANGED'
put('audit/GIT_FINAL.json',dict(status='PASS',head=git['head'],branch=git['branch'],logical_state_exact=True,no_git_mutations=True))
proc=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit() or int(d.name)==os.getpid():continue
 try:cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if str(P) in cmd and any(x in cmd for x in ['/control/owner.py','/control/campaign.py','native_executor']):proc.append(dict(pid=int(d.name),command=cmd))
assert not proc,proc
for f in P.glob('*_OWNER.json'):assert json.loads(f.read_text())['joined']
put('audit/OWNED_PROCESS_FINAL.json',dict(status='PASS',owned_physical_processes_remaining=proc,all_owner_records_joined=True))
before=read('audit/HISTORY_BEFORE.json');bad=[];n=0
for name,r in before.items():
 f=Path(name)
 if not f.exists():bad.append(dict(path=name,error='MISSING'));continue
 st=f.stat()
 if st.st_size!=r['size'] or st.st_mtime_ns!=r['mtime_ns'] or sha(f)!=r['sha256']:bad.append(dict(path=name,error='METADATA_OR_SHA_CHANGED'))
 n+=1
 if n%10000==0:print('HISTORY_RECHECKED',n,flush=True)
after={str(f) for root in [MAIN,P.parent] for f in root.rglob('*') if f.is_file() and not f.is_relative_to(P) and '.git' not in f.parts};added=sorted(after-set(before));missing=sorted(set(before)-after)
put('audit/HISTORY_FINAL.json',dict(status='PASS' if not bad and not added and not missing else 'FAIL',files_checked=n,changed=bad,new_historical_files=added,missing_historical_files=missing));assert not bad and not added and not missing,'HISTORY_PROTECTION_FAIL'
for rel,h in read('EXECUTION_CODE_MANIFEST.json')['files'].items():assert sha(P/rel)==h,rel
verification=dict(status='PASS',unix=time.time(),scientific_validation_status=read('VALIDATION_RESULTS.json')['status'],audit_status_not_scientific_promotion=True,git_logical_state_exact=True,protected_history_files=n,history_metadata_SHA_unchanged=True,execution_manifest_unchanged=True,T_D_parameters_thresholds_frozen=True,serial_physics_verified=True,physical_START=len(ss),physical_END=len(ee),START_END_closed=True,actual_new_native_steps=sum(r['actual_new_native_steps'] for r in rows),all_owned_physics_exited=True,new_START_cutoff_respected=True,hard_budget_respected=time.time()<plan['hard_stop_unix'],elapsed_minutes=(time.time()-plan['t0_unix'])/60,independent_verification='separate arithmetic implementation in one agent; no second agent or human reviewer',evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION')
assert verification['hard_budget_respected'];put('PACKAGE_VERIFICATION.json',verification);put('STATE.json',dict(phase='STOP',owned_pids=[],physical_START=len(ss),physical_END=len(ee),next_action='none; no automatic Q-learning, optimization or next package',unix=time.time()))
files={str(f.relative_to(P)):dict(sha256=sha(f),size=f.stat().st_size) for f in sorted(P.rglob('*')) if f.is_file() and f.name!='EVIDENCE_MANIFEST.json' and '__pycache__' not in f.parts}
put('EVIDENCE_MANIFEST.json',dict(status='SEALED',unix=time.time(),files=files))
print(json.dumps(verification),flush=True)
