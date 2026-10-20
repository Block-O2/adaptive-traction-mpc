from prepare import *
import gzip,collections,signal
import numpy as np
REQUIRED=['REPORT.md','EXPERIMENT_PROTOCOL.json','PRE_INTERVENTION_ATTRIBUTION.md','PRE_INTERVENTION_ATTRIBUTION.json','MATCHED_STATE_VALIDATION.md','MATCHED_STATE_VALIDATION.json','PHASE_ISOLATION_RESULTS.json','BIDIRECTIONAL_COMPARISON.json','MOTION_FORCE_TRADEOFFS.json','NATIVE_EXECUTION_LINEAGE.json','VALIDATION_RESULTS.json','PACKAGE_VERIFICATION.json']
def processes():
 exclude={os.getpid()};pid=os.getpid()
 while pid>1:
  try:
   parent=int(next(x.split()[1] for x in Path('/proc',str(pid),'status').read_text().splitlines() if x.startswith('PPid:')))
  except (FileNotFoundError,StopIteration):break
  exclude.add(parent);pid=parent
 found=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name) in exclude:continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S) in cmd and ('python' in cmd or 'matched_harness' in cmd):found.append(dict(pid=int(p.name),cmd=cmd))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 return found
def main():
 assert time.time()<T0+10800,'HARD_DEADLINE'
 assert not processes(),'TASK_OWNED_PROCESS_STILL_ACTIVE'
 events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];assert len(starts)<=18;assert collections.Counter(r['id'] for r in starts)==collections.Counter(r['id'] for r in ends),'UNJOINED_ATTEMPT'
 protocol_hashes=[json.loads((S/name).read_text())['protocol_sha256'] for name in ['HARNESS_REPAIR.json','CONTINUATION_REGISTRATION.json','DEPENDENCY_COMPLETION_REGISTRATION.json']];assert all(v==sha(S/'EXPERIMENT_PROTOCOL.json') for v in protocol_hashes),'PROTOCOL_MUTATED'
 before=json.loads((S/'preservation/PROTECTED_BEFORE.json').read_text());changed=[];missing=[]
 for path,v in before.items():
  p=Path(path)
  if not p.exists():missing.append(path)
  elif p.stat().st_size!=v['bytes'] or sha(p)!=v['sha256']:changed.append(path)
 names=set(Path(p).relative_to(BASE).parts[0] for p in before);current={str(p) for name in names for p in (BASE/name).rglob('*') if p.is_file()};added=sorted(current-set(before));removed=sorted(set(before)-current)
 after=git();save(S/'preservation/GIT_AFTER.json',after);git_equal=after==json.loads((S/'preservation/GIT_BEFORE.json').read_text())
 scientific=[];science_diffs=[]
 for d in ['source/stages','deps','native','build','weights']:
  for p in (S/d).rglob('*'):
   if not p.is_file():continue
   old=OLD/p.relative_to(S)
   if not old.is_file():science_diffs.append(str(p.relative_to(S))+':missing old counterpart');continue
   if p.suffix=='.py':
    restored=p.read_text().replace(str(S),str(OLD)).replace('m2_matched_bidirectional_exploration_v1','m2_coordination_space_exploration_v1');equal=restored==old.read_text()
   else:equal=sha(p)==sha(old)
   if not equal:science_diffs.append(str(p.relative_to(S)))
   scientific.append(str(p.relative_to(S)))
 for name in ['study_common.py','interfaces.py','native_method.py','native_core.py','native_inference.py','mode_metadata.py','streaming_reuse.py']:
  p=S/'code'/name;old=OLD/'code'/name;assert p.is_file() and old.is_file();restored=p.read_text().replace(str(S),str(OLD)).replace('m2_matched_bidirectional_exploration_v1','m2_coordination_space_exploration_v1');
  if restored!=old.read_text():science_diffs.append('code/'+name)
 crc=[];integrals=[]
 for p in (S/'source/results').rglob('runtime_artifacts.json.gz'):
  h=hashlib.sha256();bytes_read=0
  with gzip.open(p,'rb') as f:
   for b in iter(lambda:f.read(2**20),b''):h.update(b);bytes_read+=len(b)
  crc.append(dict(path=str(p.relative_to(S)),EOF_CRC_PASS=True,uncompressed_sha256=h.hexdigest(),uncompressed_bytes=bytes_read))
 for p in (S/'output').glob('*_DATA.json'):
  r=json.loads(p.read_text());ident=r['id'];trace=S/'source/results'/ident/'trace.npz'
  with np.load(trace) as z:
   ix=z['stage']=='TASK';t=z['time_s'][ix];f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1);jf=float(f[:-1]@np.diff(t));mi=float(m[:-1]@np.diff(t));delta=jf-r['metric']['J_F'];mdelta=mi-r['metric']['moment_integral'];assert abs(delta)<1e-8 and abs(mdelta)<1e-8,'RAW_INTEGRAL_ERROR'
  measured=json.loads((S/'reports'/(ident+'_MEASURED.json')).read_text());line=json.loads((S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')).read_text());assert line['status']=='PASS' and measured['axes']['PHYSICAL_TASK_VALID']=='PASS';assert measured['axes']['HOST_EXECUTION_CAUSAL_VALID']=='NOT_EVALUABLE';assert abs(sum(x['J_F_N_s'] for x in measured['phase_cost']['phases'].values())-jf)<1e-8
  integrals.append(dict(id=ident,raw_J_F=jf,error_N_s=delta,moment_error_Nm_s=mdelta,phase_closure=True,native_ownership='PASS',physical_task='PASS'))
 motion_identity=sha(S/'MOTION_ACCEPTANCE_PROTOCOL.json')==sha(OLD/'MOTION_ACCEPTANCE_PROTOCOL.json');qidentity=sha(S/'weights/frozen_Q_v1/weights.npz')=='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9'
 state=json.loads((S/'MATCHED_STATE_VALIDATION.json').read_text());parents=[json.loads(p.read_text()) for p in (S/'reports').glob('*_PARENT_CHECKS.json')];forks=[json.loads(p.read_text()) for p in (S/'reports').glob('*_FORK_RESTORED.json')];allparent=all(r['unchanged'] for group in parents for r in group);allfork=all(r['status']=='PASS' and r['before']==r['after'] for r in forks)
 inherited=json.loads((S/'preservation/INHERITED_MAIN_GIT_PROTECTION.json').read_text());echeck=json.loads((S/'preservation/FROZEN_E_REFERENCE_RECHECK.json').read_text())
 checks=dict(primary_git_unchanged=git_equal,inherited_complete_main_worktree_diff_and_all_untracked_equal=all(inherited[k] for k in ['working_diff_equal','all_untracked_status_equal','HEAD_equal','branch_equal','staged_equal']),frozen_E_reference_hashes_unchanged=echeck['status']=='PASS',historical_bytes_hashes_unchanged=not changed and not missing,historical_file_sets_unchanged=not added and not removed,scientific_source_path_relocation_only=not science_diffs,frozen_Q_identity=qidentity,motion_acceptance_byte_identical=motion_identity,protocol_hash_unchanged=True,all_generated_gzip_EOF_CRC=True,full_phase_integrals_close=True,all_complete_native_ownership_PASS=True,all_complete_original_physical_audit_PASS=True,all_immediate_forks_restore_full_hash=allfork,all_parent_after_child_full_hash_unchanged=allparent,full_matched_OUTBOUND_hash_identical=state['all_full_OUTBOUND_request_hashes_equal'],RETURN_entry_complete_hash_identical=state['same_RETURN_entry_complete_hash_equal'],attempt_cap=len(starts)<=18,START_END_balanced=True,all_dispatch_before_cutoff=all(r['unix']<T0+9600 for r in starts),no_task_owned_process=not processes(),required_files_present=all((S/p).exists() for p in REQUIRED if p!='PACKAGE_VERIFICATION.json'))
 result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,registered_budget=dict(start_unix=T0,deadline_unix=T0+10800,dispatch_cutoff_unix=T0+9600,cap=18),elapsed_s=time.time()-T0,attempts=len(starts),complete_runs=len(integrals),failed_attempts=[r for r in ends if r.get('returncode')!=0],protected_files=len(before),protected_bytes=sum(v['bytes'] for v in before.values()),historical_changed=changed,historical_missing=missing,historical_added=added,historical_removed=removed,scientific_copied_files=len(scientific),scientific_differences=science_diffs,primary_git=after,weights_sha256=sha(S/'weights/frozen_Q_v1/weights.npz'),source_and_protocol_manifest='CURRENT_CODE_MANIFEST.json + FINAL_PACKAGE_MANIFEST.json',gzip=crc,raw_integral_recalculation=integrals,worker_exit=processes(),denominators_note='complete descendants retain copied prefix; actual-new native steps separate in ATTEMPT_EVIDENCE_INDEX; duplicate rows are not independent experimental conditions',scientific_qualification_is_separate=True,git_mutations=0,Q_training=0,G_P=0,online_adaptation=0,new_Human=0,limitations=['main Git state/index/staged verified; a separate startup content hash for every dirty main worktree file was not collected','failed parents did not emit complete raw trace; generated partial compute/logs plus unchanged sibling prefix are retained','scientific route cannot qualify host 40ms wall bridge or OS schedule'])
 save(S/'PACKAGE_VERIFICATION.json',result)
 save(S/'PROCESS_EXIT_CONFIRMATION.json',dict(unix=time.time(),status='PASS' if not processes() else 'FAIL',active_task_processes=processes(),attempt_START_END_balanced=True,unrelated_processes_untouched=True))
 assert result['status']=='PASS',json.dumps(checks)
 closed=dict(unix=time.time(),elapsed_s=time.time()-T0,attempts=len(starts),complete_runs=len(integrals),status=json.loads((S/'FINAL_RESEARCH_JUDGMENT.json').read_text())['status'],STOP=True,no_auto_followup=True,protection='PASS',workers='EXIT_VERIFIED')
 save(S/'PACKAGE_CLOSED.json',closed)
 manifests={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and p.name not in ['FINAL_PACKAGE_MANIFEST.json','DELIVERY_VERIFICATION.json']};save(S/'FINAL_PACKAGE_MANIFEST.json',dict(canonical=str(S),files=manifests,exclusion='manifest cannot include its own hash, delivery verification is generated after copying'))
 shutil.copytree(S,WIN,dirs_exist_ok=True)
 mismatches=[name for name,v in manifests.items() if not (WIN/name).is_file() or sha(WIN/name)!=v['sha256']];assert not mismatches,'DELIVERY_HASH_MISMATCH'
 save(WIN/'DELIVERY_VERIFICATION.json',dict(status='PASS',copied_files=len(manifests),canonical=str(S),all_bytes_match=True,manifest_sha256=sha(S/'FINAL_PACKAGE_MANIFEST.json'),mismatches=mismatches))
 print(json.dumps(dict(status=result['status'],research=closed['status'],attempts=len(starts),complete=len(integrals),protected=len(before),exported_files=len(manifests),elapsed_s=time.time()-T0)),flush=True)
if __name__=='__main__':main()
