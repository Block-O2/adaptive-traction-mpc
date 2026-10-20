"""Seal serial physics, account all attempts, and independently rehash protected history."""
from pathlib import Path
import os,json,time,hashlib,subprocess,fcntl,shutil
R=Path(__file__).resolve().parents[1];SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=SIDE/R.name;MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''):h.update(b)
 return h.hexdigest()
groups=['Dev','Ctrl','W2'];owners={g:read(P/(g+'_OWNER.json')) for g in groups};workers={g:read(P/(g+'_WORKER_EXIT.json')) for g in groups}
assert all(v['joined'] for v in owners.values());assert all(v.get('active_child') is None for v in workers.values())
locks=[]
for n in ['PHYSICS.lock','OWNER.lock']:
 f=(P/n).open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(f)
ps=subprocess.check_output(['ps','-eo','pid=,ppid=,stat=,args=']).decode();live=[]
for line in ps.splitlines():
 if str(P) in line and any('/control/'+n in line for n in ['campaign.py','campaign_v2.py','owner.py','owner_v2.py']):live.append(line)
assert not live,live
put('PHYSICS_STOP_v2.json',dict(reason='RESEARCH_COMPLETE_NO_FURTHER_STARTS',unix=time.time(),frozen_primary='H150',validation_consumed='W2',no_next_package=True))
put('PHYSICS_CLOSED.json',dict(status='CLOSED',unix=time.time(),both_execution_versions_stopped=True,owner_and_physics_locks_acquired=True,owned_processes_live=live))
put('audit/OWNED_PROCESS_EXIT.json',dict(status='PASS',unix=time.time(),owners=owners,workers=workers,physics_and_owner_lock_free=True,live_owned_physics_processes=live,pid_reuse_not_treated_as_ownership=True))
records=[json.loads(l) for l in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in records if r['event']=='START'];ends=[r for r in records if r['event']=='END'];rows=[]
assert len(starts)==len(ends)<=80
for s in starts:
 es=[r for r in ends if r['id']==s['id']];assert len(es)==1;e=es[0];assert e['unix']>=s['unix'] and e.get('joined')
 g=s['group'];plan=read(P/(g+'_PLAN.json'));assert sha(P/(g+'_PLAN.json'))==s['group_plan_sha256']
 arm=s['id'].removeprefix(g+'_');candidate=next((x for x in plan['arms'] if x['id']==arm),None)
 out=P/'output'/(s['id']+'_DATA.json');partial=P/'output'/(s['id']+'_PARTIAL_COMPUTE.json')
 if out.exists():data=read(out);metric=data['metric'];step=metric['actual_new_native_physics_steps'];status='COMPLETE_FULL_TASK';reason=None
 else:metric=read(partial);step=metric['actual_new_native_physics_steps'];status='PARTIAL_UNRANKED';reason=e.get('error') or read(P/'reports'/(s['id']+'_ERROR.json')).get('error')
 assert step>=0
 rows.append(dict(id=s['id'],kind=s['kind'],group=g,mode=s['mode'],start_unix=s['unix'],end_unix=e['unix'],returncode=e['returncode'],joined=e['joined'],actual_new_native_steps=step,inherited_native_steps=metric.get('native_physics_steps',0)-step,status=status,partial_reason=reason,candidate_hash=candidate.get('candidate_hash') if candidate else 'ORIGINAL_B_LEGAL_COLD_PARENT',control_mode=candidate.get('controller',{}).get('mode','REFERENCE_ONLY') if candidate else 'ORIGINAL_B_PARENT',candidate=candidate,parent_snapshot_sha=s.get('snapshot_hash'),code_manifest_sha256=s['code_manifest_sha256'],group_plan_sha256=s['group_plan_sha256'],candidate_identity_join='START -> frozen group_plan_sha256 -> exact arm/candidate_hash; original append-only START record preserved'))
# Parent remains suspended while a single child advances; no child intervals overlap.
forks=sorted([r for r in rows if r['kind']=='FULL_TASK_FORK'],key=lambda r:r['start_unix']);assert all(a['end_unix']<=b['start_unix'] for a,b in zip(forks,forks[1:]))
parent_intervals=sorted([r for r in rows if r['kind']=='LEGAL_COLD_PARENT'],key=lambda r:r['start_unix']);assert all(a['end_unix']<=b['start_unix'] for a,b in zip(parent_intervals,parent_intervals[1:]))
plan=read(P/'RUN_PLAN.json');assert max(r['unix'] for r in starts)<plan['no_new_physics_after_unix']-plan['physical_timeout_s']
acc=dict(status='PASS_CLOSED',START=len(starts),END=len(ends),budget=80,remaining_unused=80-len(starts),complete_runs=sum(r['status']=='COMPLETE_FULL_TASK' for r in rows),partial_failed_runs=sum(r['status']=='PARTIAL_UNRANKED' for r in rows),actual_new_native_steps=sum(r['actual_new_native_steps'] for r in rows),actual_new_simulation_seconds=sum(r['actual_new_native_steps'] for r in rows)*.00025,all_physics_serial=True,parent_fork_semantics='Waiting parent performs no physics while each serial child advances; complete shared prefix is inherited, not replayed',all_starts_before_frozen_cutoff=True,partial_costs_excluded_from_ranking=True,rows=rows)
put('ATTEMPT_ACCOUNTING.json',acc);print('PHYSICS_SEALED',len(starts),flush=True)
before=read(P/'audit/HISTORY_BEFORE.json');current={};changed=[];started=time.time();total=0
for root in [MAIN,SIDE]:
 for f in sorted(root.rglob('*')):
  if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts:continue
  st=f.stat();entry=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(f));current[str(f)]=entry;total+=st.st_size
  if str(f) in before and entry!=before[str(f)]:changed.append(dict(path=str(f),before=before[str(f)],after=entry))
  if len(current)%20000==0:print('PROTECTED_REHASH',len(current),flush=True)
missing=sorted(set(before)-set(current));added=sorted(set(current)-set(before))
put('audit/HISTORY_AFTER.json',current);put('audit/HISTORY_PROTECTION.json',dict(status='PASS' if not (changed or missing or added) else 'FAIL',method='Every protected file re-read and SHA256 recomputed; size and mtime also compared',files_before=len(before),files_after=len(current),bytes_rehashed=total,changed=changed,missing=missing,added=added,elapsed_s=time.time()-started,before_sha256=sha(P/'audit/HISTORY_BEFORE.json'),after_sha256=sha(P/'audit/HISTORY_AFTER.json')))
env=dict(os.environ,GIT_OPTIONAL_LOCKS='0');git={n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]};old=read(P/'audit/GIT_BEFORE.json')
put('audit/GIT_AFTER.json',git);put('audit/GIT_LOGICAL_STATE.json',dict(status='PASS' if git==old else 'FAIL',fields_exact={k:git[k]==old[k] for k in old},head=git['head'].strip(),branch=git['branch'].strip(),preexisting_changes_preserved=True,no_git_mutating_commands=True))
assert not (changed or missing or added);assert git==old
put('STATE.json',dict(phase='PHYSICS_CLOSED_FINAL_DELIVERY_REVIEW',physics_starts=len(starts),no_next_package=True))
print('HISTORY_AND_GIT_PASS',len(current),total,flush=True)
