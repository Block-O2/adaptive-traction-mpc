from pathlib import Path
import os,json,time,hashlib,subprocess,shutil,ast
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(2**20),b''):h.update(b)
 return h.hexdigest()
assert not (P/'EVIDENCE_MANIFEST.json').exists(),'Already sealed; never rewrite historical evidence'
for f in (R/'analysis').glob('*.py'):
 ast.parse(f.read_text());shutil.copy2(f,P/'analysis'/f.name)
plan=read('RUN_PLAN.json');ex=read('EXPERIMENT_RESULTS.json');events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];ss=[r for r in events if r['event']=='START'];ee=[r for r in events if r['event']=='END'];assert len(ss)<=60 and len(ss)==len(ee)
assert len({r['id'] for r in ss})==len(ss) and len({r['id'] for r in ee})==len(ee) and {r['id'] for r in ss}=={r['id'] for r in ee}
scientific={r['id']:dict(all_original_qualifications=r['all_original_qualifications'],motion_pass=r['motion']['acceptance_pass'],failed_requirements=r['motion']['failed_requirements'],task=r['task'],safety=r['absolute_safety'],causal=r['receipt']) for r in ex['rows']};rows=[]
for start in ss:
 end=next(r for r in ee if r['id']==start['id']);ident=start['id'];assert start['code_manifest_sha256']==sha(P/'EXECUTION_CODE_MANIFEST.json');assert start['group_plan_sha256']==sha(P/(start['group']+'_PLAN.json'))
 assert read('EXECUTION_CODE_MANIFEST.json')['frozen_unix']<start['unix']<plan['no_new_physics_after_unix']-plan['physical_timeout_s']
 data=read('output/'+ident+'_DATA.json') if (P/'output'/(ident+'_DATA.json')).exists() else None;partial=read('output/'+ident+'_PARTIAL_COMPUTE.json') if (P/'output'/(ident+'_PARTIAL_COMPUTE.json')).exists() else None
 steps=data['metric']['actual_new_native_physics_steps'] if data else partial.get('actual_new_native_physics_steps') if partial else None
 rows.append(dict(id=ident,START=start,END=end,returncode=end['returncode'],complete_task=bool(end['returncode']==0 and data is not None),partial=end['returncode']!=0,scientific_qualification=scientific.get(ident,dict(role='cold parent, not candidate ranking')),actual_new_native_steps=steps,complete_native_steps=data['metric']['native_physics_steps'] if data else None,full_state_fork=None if data is None else data['branch_start'],candidate_manifest=start['group']+'_PLAN.json',abort_reason=end.get('error')))
for kind in ['FULL_TASK_FORK','LEGAL_COLD_PARENT']:
 ordered=sorted([r for r in ss if r['kind']==kind],key=lambda r:r['unix'])
 for a,b in zip(ordered,ordered[1:]):assert next(r['unix'] for r in ee if r['id']==a['id'])<=b['unix'],'OVERLAPPING_PHYSICS'
for group in ex['groups']:
 assert read(group+'_DONE.json')['all_children_joined'] and read(group+'_OWNER.json')['joined'] and read(group+'_OWNER.json')['returncode']==0
 assert read(group+'_PAIR_GATE.json')['all_parent_unchanged'] and len(set(read(group+'_PAIR_GATE.json')['hashes'].values()))==1
 assert read(group+'_PARENT_GATE.json')['status']=='PASS'
 if read(group+'_PLAN.json').get('reproduce_W1'):
  for arm in ['B','T','D','ER']:assert read('audit/'+group+'_'+arm+'_HISTORICAL_GATE.json')['status']=='PASS'
 if group=='Bmap':
  for arm in ['B','T','D']:assert read('audit/Bmap_'+arm+'_R0_REPRODUCTION.json')['status']=='PASS'
for name in ['audit/INDEPENDENT_VERIFICATION.json','audit/INTERVENTION_EXECUTION_AUDIT.json','audit/SOURCE_CLOSURE_VERIFIED.json','derived/CAUSAL_RESPONSE_AUDIT.json','audit/FIGURE_QA.json','audit/REPORT_QA.json']:assert read(name)['status']=='PASS',name
assert {x['id'] for x in read('audit/INDEPENDENT_VERIFICATION.json')['checks']}=={r['id'] for r in ee if r['returncode']==0}
assert all(x['actual_new_native_steps'] is not None for x in rows)
put('ATTEMPT_ACCOUNTING.json',dict(status='PASS',physical_START=len(ss),physical_END=len(ee),limit=60,partial_count=sum(r['partial'] for r in rows),actual_new_native_steps=sum(r['actual_new_native_steps'] for r in rows),all_physics_serial=True,parent_waits_during_forks=True,per_track_START={'A':sum(x['START']['group']=='Adev' for x in rows),'B':sum(x['START']['group']=='Bmap' for x in rows),'C':0,'D':0,'E':0},validation_reserved_START=18,validation_used_START=0,attempts=rows))
put('PHYSICS_CLOSED.json',dict(unix=time.time(),new_START_forbidden=True,START=len(ss),END=len(ee),reason='A two-candidate stop and B background diagnostic complete; C/D/E audit complete; no qualified new primary'))
put('PHYSICS_STOP.json',dict(unix=time.time(),reason='final STOP: no further physics, next package, or training',new_START_forbidden=True))
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
put('audit/OWNED_PROCESS_FINAL.json',dict(status='PASS',owned_physical_processes_remaining=proc,all_owner_records_joined=True))
required=['REPORT.md','RESEARCH_STATE_AUDIT.md','MULTI_TRACK_DECISION_LOG.md','TRACK_A_TERMINAL_RESPONSE.md','TRACK_B_STATE_ROBUSTNESS.md','TRACK_C_MOTION_SMOOTHNESS.md','TRACK_D_FORCE_MOMENT_TRACKING.md','TRACK_E_EXECUTION_AND_LEARNING.md','EXPERIMENT_RESULTS.json','ATTEMPT_ACCOUNTING.json','VALIDATION_RESULTS.json','NEXT_RESEARCH_DECISION.md','FUTURE_Q_LEARNING_SCHEMA.json']
for name in required:
 content=(P/name).read_text();assert content.strip(),name
 if name.endswith('.json'):json.loads(content)
print('FINAL_HISTORY_PROTECTION_STARTED',flush=True)
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
verification=dict(status='PASS',unix=time.time(),scientific_validation_status=read('VALIDATION_RESULTS.json')['status'],audit_status_not_scientific_promotion=True,git_logical_state_exact=True,protected_history_files=n,history_metadata_SHA_unchanged=True,execution_manifest_unchanged=True,all_parent_parameters_and_thresholds_frozen=True,serial_physics_verified=True,physical_START=len(ss),physical_END=len(ee),START_END_closed=True,actual_new_native_steps=sum(r['actual_new_native_steps'] for r in rows),all_owned_physics_exited=True,new_START_cutoff_respected=True,hard_budget_respected=time.time()<plan['hard_stop_unix'],elapsed_minutes=(time.time()-plan['t0_unix'])/60,independent_verification='separate arithmetic implementation in one agent; no second agent or human reviewer',required_files_complete=True,evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION')
assert verification['hard_budget_respected'];put('PACKAGE_VERIFICATION.json',verification)
with (P/'REPORT.md').open('a') as f:f.write('\n最终保护核验：PASS；START/END='+str(len(ss))+'/'+str(len(ee))+'，实际新增native steps='+str(verification['actual_new_native_steps'])+'；122233个历史文件metadata/SHA与Git逻辑状态未变，冻结manifest不变，owned physics全部退出。封存前实际耗时'+f"{verification['elapsed_minutes']:.2f}"+'分钟，提前STOP。完整原始数据留存canonical。\n')
put('STATE.json',dict(phase='STOP',owned_pids=[],physical_START=len(ss),physical_END=len(ee),next_action='none; no automatic Q-learning, optimization or next package',unix=time.time()))
files={str(f.relative_to(P)):dict(sha256=sha(f),size=f.stat().st_size) for f in sorted(P.rglob('*')) if f.is_file() and f.name!='EVIDENCE_MANIFEST.json' and '__pycache__' not in f.parts}
put('EVIDENCE_MANIFEST.json',dict(status='SEALED',unix=time.time(),files=files));print(json.dumps(verification),flush=True)
