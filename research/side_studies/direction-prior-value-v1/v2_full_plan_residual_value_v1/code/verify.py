from common import *
import numpy as np,resource
def main():
 inventory=read(NEW/'V1_EVIDENCE_BEFORE.json');changed=[]
 for s,r in inventory.items():
  p=Path(s)
  if not p.exists():changed.append(dict(path=s,reason='MISSING'));continue
  st=p.stat()
  if st.st_size!=r['size'] or st.st_mtime_ns!=r['mtime_ns'] or ('sha256' in r and sha(p)!=r['sha256']):changed.append(dict(path=s,reason='SIZE_MTIME_OR_SHA'))
 added=[str(p) for p in OLD.rglob('*') if p.is_file() and not p.is_relative_to(NEW) and str(p) not in inventory]
 sourcechanges=[s for s,h in read(NEW/'MAIN_SOURCES_BEFORE.json').items() if not hostpath(s).exists() or sha(hostpath(s))!=h]
 gate=read(NEW/'ORACLE_GATE.json');protocol=read(NEW/'PROTOCOL.json');semantics=read(NEW/'SEMANTIC_SUITABILITY.json');decomp=read(NEW/'FULL_PLAN_ERROR_DECOMPOSITION.json');metrics=read(NEW/'V1_V2_COMPARISON.json')
 checks=dict(V1_and_audit_unchanged=not changed,V1_no_added_files=not added,main_git_unchanged=main_git()==read(NEW/'MAIN_GIT_BEFORE.json'),main_sources_unchanged=not sourcechanges,semantic_choice_before_oracle=protocol['registered_unix']<semantics['unix']<gate['unix'],primary_chosen_by_preregistered_rule=semantics['PRIMARY_V2_CONTRACT']=='ROLLING_P',gate_failed=gate['gate']=='FAIL',zero_training=gate['trained_networks']==0 and all(metrics['models'][name]['status']=='NOT_TRAINED' for name in ('ridge','MLP_2x128')),zero_new_physics=gate['new_physics']==0,no_oracle_controller=not gate['oracle_entered_online_controller'],all30_outcomes_qualified=all(m['qualified'] for r in decomp['rows'] for m in r['metric_metadata'].values()),all_cost_integrals_match=max(abs(m['metric_integral_error']) for r in decomp['rows'] for m in r['metric_metadata'].values())<1e-6,original_first_segment_proof_pass=read(AUDIT/'FIRST_SEGMENT_PAIR_VERIFICATION.json')['status']=='PASS')
 active=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(NEW) in cmd and any(word in cmd for word in ('worker.py','runner.py','train.py','native_worker')):active.append(dict(pid=int(p.name),command=cmd))
  except OSError:pass
 checks['no_owned_physics_or_training_process']=not active
 status='PASS' if all(checks.values()) else 'FAIL';save(NEW/'PRESERVATION_AND_VERIFICATION.json',dict(status=status,unix=time.time(),checks=checks,V1_files_checked=len(inventory),changed=changed,added=added,main_changes=sourcechanges,active=active))
 newbytes=sum(p.stat().st_size for p in NEW.rglob('*') if p.is_file());save(NEW/'COMPUTE_RESOURCE_LEDGER.json',dict(start_unix=START,end_unix=time.time(),elapsed_h=(time.time()-START)/3600,new_physics_attempts=0,new_native_steps=0,new_inverse_dynamics_calls=0,training_runs=0,NN_training_steps=0,new_model_weights=0,oracle_rescores=dict(states=5,distinct_candidate_rows=15,contracts=2),reused_complete_truth_outcomes=30,source_proof_reused_pairs=30,process_peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_bytes=newbytes,phase_decomposition_left_force_intervals='existing saved traces only; current package generates no large repeated physics trace',note='No physics owner spawned; verification/report processes only. No exact all-process wall-sum claim.'))
 print(json.dumps(dict(status=status,checks=checks,old_files=len(inventory),new_bytes=newbytes)));assert status=='PASS'
if __name__=='__main__':main()
