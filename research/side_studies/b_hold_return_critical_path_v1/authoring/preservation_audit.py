"""Verify protected files, original Git state and complete attempt accounting."""
from pathlib import Path
import json,hashlib,subprocess,os,collections,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def save(name,x):p=S/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def git(*args):
 r=subprocess.run(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True,text=True);assert r.returncode==0,r.stderr;return r.stdout
def main():
 previous=json.loads((S/'GIT_BEFORE.json').read_text());current=dict(branch=git('branch','--show-current'),HEAD=git('rev-parse','HEAD'),status=git('status','--porcelain=v1'),index_sha256=sha(ROOT/'.git/index'),staged_diff=git('diff','--cached','--binary'))
 g={k:previous[k]==current[k] for k in previous};assert all(g.values()),g
 protected=json.loads((S/'preservation/PROTECTED_BEFORE.json').read_text());rows={p:dict(before=v,after=sha(Path(p))) for p,v in protected.items()};assert all(r['before']==r['after'] for r in rows.values())
 events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=collections.Counter(x['id'] for x in events if x['event']=='START');ends=collections.Counter(x['id'] for x in events if x['event']=='END');ledger=json.loads((S/'TASK_LEDGER.json').read_text())
 assert starts==ends and set(starts)==set(ledger) and max(starts.values())==1 and sum(starts.values())<=80
 assert not any(r['status']=='RUNNING' for r in ledger.values())
 configs={};result_checks={};source_at_import={};joins={};owner_pids=set()
 for ident,row in ledger.items():
  configs[ident]=sha(Path(row['durable_input_path']))==row['input_sha256'];assert configs[ident],ident
  result=Path(row['result_path'])
  result_checks[ident]=None if not result.exists() else sha(result)==row['result_sha256'];assert result_checks[ident] is not False,ident
  imp=S/'output'/f'{ident}_IMPORTED_SOURCES.json'
  if imp.exists():source_at_import[ident]=json.loads(imp.read_text())
  ipc=S/'output'/f'{ident}_DIRECT_IPC.json'
  if ipc.exists():
   raw=json.loads(ipc.read_text())['rows'];pidset={x['worker_pid'] for x in raw if 'worker_pid' in x};joined={x['worker_pid'] for x in raw if x.get('event')=='JOIN' and x.get('joined')};joins[ident]=dict(worker_pids=sorted(pidset),joined_pids=sorted(joined),all_observed_TASK_owners_joined=pidset<=joined);owner_pids|=pidset
   assert pidset<=joined,ident
 before=json.loads((S/'SOURCE_BEFORE.json').read_text());changes=[]
 for rel,old in before.items():
  p=S/rel
  if not p.exists() or sha(p)!=old:changes.append(dict(path=rel,before=old,after=sha(p) if p.exists() else None))
 scientific_changes=[x for x in changes if x['path'].startswith(('source/','deps/'))]
 assert [x['path'] for x in scientific_changes]==['source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py'],scientific_changes
 assert not any(x['path'].startswith(('native/','build/')) for x in changes),'Native model/kernel binary changed'
 proc=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S) in cmd and ('fast_dispatch.py' in cmd or 'run_one.py' in cmd or 'cohort_dispatch.py' in cmd):proc.append(dict(pid=int(p.name),cmd=cmd))
  except OSError:pass
 assert not proc,proc
 out=dict(status='PASS',unix=time.time(),Git_unchanged=g,branch=current['branch'].strip(),HEAD=current['HEAD'].strip(),status_sha256=hashlib.sha256(current['status'].encode()).hexdigest(),staged_diff_sha256=hashlib.sha256(current['staged_diff'].encode()).hexdigest(),index_sha256=current['index_sha256'],protected_files=rows,attempts=sum(starts.values()),START_END_bijection=True,durable_config_hashes_verified=configs,result_hashes_verified=result_checks,TASK_join_evidence=joins,no_active_study_dispatch_or_run_processes=True,source_dependency_changes=scientific_changes,all_preexisting_changes=changes,native_source_and_binary_unchanged=True,imported_source_hash_records=source_at_import,source_history_note='Early START manifests omit source/deps. End imported-source hashes plus preserved C11 source patch and per-version compiled owner sources are retained; no retrospective START hash is invented.')
 save('preservation/FINAL_PRESERVATION.json',out);print(json.dumps(dict(status=out['status'],Git_unchanged=g,protected_files=len(rows),attempts=out['attempts'],TASK_join_records=len(joins),scientific_source_changes=[x['path'] for x in scientific_changes])))
if __name__=='__main__':main()
