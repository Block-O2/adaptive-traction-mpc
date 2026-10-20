"""Close attempt ledgers and recheck protected history; never invokes physics."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning');SIDE=P.parent
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''):h.update(b)
 return h.hexdigest()
rs=[json.loads(l) for l in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in rs if r['event']=='START'];ends=[r for r in rs if r['event']=='END'];rows=[]
assert len(starts)<=40
assert len({r['code_manifest_sha256'] for r in starts})==1
assert {r['code_manifest_sha256'] for r in starts}=={sha(P/'EXECUTION_CODE_MANIFEST.json')}
for r in starts:assert r['group_plan_sha256']==sha(P/(r['group']+'_PLAN.json'))
assert read('NEW_PREFIX_VALIDATION_PROTOCOL.json')['selection_sha256']==sha(P/'FROZEN_SELECTION.json')
assert read('FROZEN_SELECTION.json')['selection_rule_sha256']==sha(P/'SELECTION_RULE.json')
assert read('FROZEN_SELECTION.json')['frozen_unix']<min(r['unix'] for r in starts if r['mode']=='validation')
assert read('REFINEMENT_PROTOCOL.json')['frozen_unix']<next(r['unix'] for r in starts if r['id']=='refine_P_corridor')
assert not any(r['id'].startswith('W2_') or r['id'].startswith('W1_P_corridor') for r in starts)
assert all(r['unix']<=read('PHYSICS_STOP.json')['unix'] for r in starts)
forks=sorted([r for r in starts if r['kind']=='FULL_TASK_FORK'],key=lambda r:r['unix'])
for a,b in zip(forks,forks[1:]):assert next(r['unix'] for r in ends if r['id']==a['id'])<=b['unix'],'OVERLAPPING_FORK_PHYSICS'
assert read('audit/HISTORICAL_MANIFESTS_VERIFIED.json')['status']=='PASS'
assert read('audit/INDEPENDENT_VERIFICATION.json')['status']=='PASS'
assert {r['id'] for r in read('audit/INDEPENDENT_VERIFICATION.json')['checks']}=={r['id'] for r in ends if r['returncode']==0}
assert read('audit/INTERVENTION_EXECUTION_AUDIT.json')['status']=='PASS'
assert read('audit/FIGURE_QA.json')['status']=='PASS'
for f in P.glob('*_PAIR_GATE.json'):
 g=json.loads(f.read_text());assert g['status']=='PASS' and g['all_parent_unchanged'];assert len(set(g['hashes'].values()))==1
for s in starts:
 ident=s['id'];es=[r for r in ends if r['id']==ident];assert len(es)==1,(ident,es);end=es[0]
 out=P/'output'/(ident+'_DATA.json');part=P/'output'/(ident+'_PARTIAL_COMPUTE.json')
 data=json.loads(out.read_text()) if out.exists() else None;partial=json.loads(part.read_text()) if part.exists() else None
 error=P/'reports'/(ident+'_ERROR.json');err=json.loads(error.read_text()) if error.exists() else None
 if data:
  metric=data['metric'];new=metric['actual_new_native_physics_steps'];total=metric['native_physics_steps'];branch=data['branch_start'];parent=ident.split('_')[0]+'_parent' if s['kind']=='FULL_TASK_FORK' else None
  source=dict(kind=s['kind'],parent=parent,condition=data['condition'],full_parent_hash=None if branch is None else branch['full_hash'],native_parent_hash=None if branch is None else branch['native_hash'],fork_physics_s=None if branch is None else branch['physical_time_s'],inherited_native_steps=total-new)
 else:
  new=None if partial is None else partial['actual_new_native_physics_steps'];total=None if partial is None else partial['native_physics_steps'];source=dict(kind=s['kind'],snapshot_hash=s.get('snapshot_hash'),source='preserved START and partial error; no successful complete sample')
 rows.append(dict(id=ident,START=s,END=end,returncode=end['returncode'],partial=data is None,actual_new_native_steps=new,total_native_steps=total,parent_state_source=source,failure_reason=None if end['returncode']==0 else err or end.get('error'),partial_compute=partial))
assert len(starts)==len(ends) and len({r['id'] for r in starts})==len(starts)
put('ATTEMPT_ACCOUNTING.json',dict(status='PASS',physical_START=len(starts),physical_END=len(ends),limit=40,validation_reserved=10,actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in rows),partial_count=sum(r['partial'] for r in rows),attempts=rows))
if not (P/'PHYSICS_STOP.json').exists():put('PHYSICS_STOP.json',dict(reason='finite preregistered directions concluded; no further physics authorized in this closed package',unix=time.time(),new_START_forbidden=True))
put('PHYSICS_CLOSED.json',dict(reason='frozen validation motion stop preserved; no further physics in this package',original_stop=read('PHYSICS_STOP.json'),unix=time.time(),new_START_forbidden=True))
env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
git={n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
assert git==read('audit/GIT_BEFORE.json'),'GIT_LOGICAL_STATE_CHANGED'
put('audit/GIT_FINAL.json',dict(status='PASS',head=git['head'],branch=git['branch'],logical_state_exact=True,git_actions='no commit/push/merge/reset/stash/clean/stage/branch switch'))
before=read('audit/HISTORY_BEFORE.json');diff=[];sha_bad=[];n=0
for name,rec in before.items():
 f=Path(name)
 if not f.exists():diff.append(dict(path=name,reason='missing'));continue
 st=f.stat()
 if st.st_size!=rec['size'] or st.st_mtime_ns!=rec['mtime_ns']:diff.append(dict(path=name,reason='metadata changed'))
 if sha(f)!=rec['sha256']:sha_bad.append(name)
 n+=1
 if n%20000==0:print('HISTORY_RECHECKED',n,flush=True)
after={str(f) for root in [MAIN,SIDE] for f in root.rglob('*') if f.is_file() and not f.is_relative_to(P) and '.git' not in f.parts}
added=sorted(after-set(before));removed=sorted(set(before)-after)
put('audit/HISTORY_FINAL.json',dict(status='PASS' if not(diff or sha_bad or added or removed) else 'FAIL',files_checked=n,metadata_changes=diff,sha_changes=sha_bad,new_historical_files=added,missing_historical_files=removed))
assert not(diff or sha_bad or added or removed),'HISTORY_PROTECTION_FAIL'
# Only inspect study-owned process commands. The current closeout process is expected.
proc=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit() or int(d.name)==os.getpid():continue
 try:cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if str(P) in cmd and any(x in cmd for x in ['/control/owner.py','/control/campaign.py','native_executor']):proc.append(dict(pid=int(d.name),command=cmd))
assert not proc,proc
put('audit/OWNED_PROCESS_FINAL.json',dict(status='PASS',owned_physical_processes_remaining=proc,all_owner_records_joined=all(read(f.name)['joined'] for f in P.glob('*_OWNER.json')),scope='owned physics/launcher/native executor; independent closeout is current process'))
for rel,h in read('EXECUTION_CODE_MANIFEST.json')['files'].items():assert sha(P/rel)==h,rel
verification=dict(status='PASS',unix=time.time(),evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',audit_status_not_scientific_promotion=True,scientific_validation_status=read('VALIDATION_RESULTS.json')['status'],candidate_new_prefix_qualification_established=False,git_logical_state_exact=True,history_files_sha_and_metadata_unchanged=n,execution_manifest_unchanged=True,selection_rule_and_primary_unchanged=True,serial_fork_physics_verified=True,START_END_closed=True,all_owned_physics_exited=True,physical_START=len(starts),physical_END=len(ends),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in rows),elapsed_minutes=(time.time()-read('RUN_PLAN.json')['t0_unix'])/60,hard_budget_respected=time.time()<read('RUN_PLAN.json')['hard_stop_unix'],new_START_cutoff_respected=all(r['unix']<read('RUN_PLAN.json')['no_new_physics_after_unix'] for r in starts),independent_audit='separate arithmetic implementation in one agent, not a second person or agent',unresolved=['candidate new-prefix qualification','T wider legal-state motion domain','cross-patient','Native LEVEL2 / host LEVEL3 / strict55 / R2 / FAST prior failures','hardware and clinical qualification'])
put('PACKAGE_VERIFICATION.json',verification)
put('STATE.json',dict(phase='STOP',owned_pids=[],physics_starts=len(starts),physics_ends=len(ends),next_action='none; no automatic training or next study',unix=time.time()))
print(json.dumps(verification),flush=True)
