from common import *
import ast, zipfile, collections
from datetime import datetime,timezone,timedelta
def main():
 before=load(OUT/'PRESERVATION_BEFORE.json');checks=[]
 def check(name,ok,detail=None):
  checks.append(dict(name=name,pass_=bool(ok),detail=detail))
 protocol=load(OUT/'EXPERIMENT_PROTOCOL.json');ds=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json');rr=load(OUT/'RANKING_FEASIBILITY.json');manifest=load(OUT/'COUNTERFACTUAL_DATASET_MANIFEST.json');rows=ds['historical_rows']
 required=['REPORT.md','EXPERIMENT_PROTOCOL.json','MOTION_QUALITY_PROTOCOL.md','MOTION_QUALITY_PROTOCOL.json','STATE_RESTORATION_AUDIT.md','STATE_RESTORATION_AUDIT.json','COUNTERFACTUAL_DATASET_MANIFEST.json','COUNTERFACTUAL_BRANCH_RESULTS.json','RANKING_FEASIBILITY.md','RANKING_FEASIBILITY.json','COMMITTED_VS_REPLANNING_VALUE.md','COMMITTED_VS_REPLANNING_VALUE.json']
 check('required_deliverables',all((OUT/p).is_file() for p in required),required)
 check('historical_cohort_no_new_row',len(rows)==80 and ds['new_attempts']==[] and ds['new_valid_rows']==0)
 check('original_failed_and_excluded_preserved',len(ds['historical_failed_rows'])==3 and len(ds['historical_excluded_rows'])==8)
 check('original_source_inventory',len(manifest['sources'])==91)
 check('source_snapshot_grouping',len(set(r['snapshot'] for r in rows))==13 and len(set(r['parent'] for r in rows))==4)
 expected_phases=collections.Counter(load(MATRIX/'output'/(r['id']+'_DATA.json'))['branch_start']['context']['phase'] for r in load(OLD/'BRANCH_LABELS.json')['rows'])
 check('phase_coverage',collections.Counter(r['phase'] for r in rows)==expected_phases,dict(actual=dict(collections.Counter(r['phase'] for r in rows)),expected_from_original_DATA=dict(expected_phases)))
 # The actual cohort split is checked from the predecessor, never invented.
 old=load(OLD/'BRANCH_LABELS.json');check('exact_prior_row_and_split_identity',[(r['id'],r['snapshot'],r['split'],r['parent']) for r in rows]==[(r['id'],r['snapshot'],r['split'],r['parent']) for r in old['rows']])
 maxerr=max(abs(r['remaining_integral_check']['inclusive_trace_sum_error_N_s']) for r in rows);check('independent_native_remaining_integral_closure',maxerr<1e-5,dict(max_abs_error_N_s=maxerr))
 steps=[];dense_samples=0
 for r in rows:
  raw=load(MATRIX/'output'/(r['id']+'_DATA.json'))
  if r['remaining_J_F_N_s']!=raw['remaining_J_F']:raise AssertionError('LABEL_CHANGED')
  if not raw['metric']['valid'] or not raw['metric']['task_valid'] or not raw['metric']['matched_eligible']:raise AssertionError('INVALID_HISTORICAL_LABEL')
  if r['host_contract_status']!='NOT_EVALUABLE':raise AssertionError('HOST_PROMOTION')
  with np.load(r['derived_dense_trace']) as z:
   t=z['time_s'];q=z['true_q_rad'];v=z['true_dq_rad_s'];dense_samples+=len(t)
   if not np.all(np.diff(t)>0) or np.max(np.diff(t))>.000251:raise AssertionError('DENSE_TRACE_GAP')
   if not np.isfinite(q).all() or not np.isfinite(v).all():raise AssertionError('NONFINITE_MOTION')
   if np.max(abs(np.rad2deg(np.ptp(q,axis=0))-r['full_dose']['excursion_deg']))>1e-7:raise AssertionError('DOSE_MISMATCH')
  with np.load(r['execution']['command_receipt_file']) as z:
   native_steps=int(np.sum(z['native_steps']));steps.append(dict(id=r['id'],receipt_native_steps=native_steps,recorded_new_native_steps=r['execution']['metric_new_native_steps'],difference=native_steps-r['execution']['metric_new_native_steps']))
  for path,h in r['sources'].items():
   if sha(path)!=h:raise AssertionError('RAW_SOURCE_CHANGED:'+path)
 check('dense_trace_resolution_mapping_finite',True,dict(total_native_TASK_nodes=dense_samples,min_verified_mapping_nodes=min(r['quality']['common_verified_nodes'] for r in rows),all_mapping_indices=[r['quality']['mapping_q_indices'] for r in rows]))
 check('same_snapshot_fork_prefix_identity',all(s['prefix_max_q_dq_error']<1e-8 for s in rr['snapshots']))
 check('receipt_steps_close_new_native_steps',all(abs(s['difference'])<=20 for s in steps),dict(max_abs_step_difference=max(abs(s['difference']) for s in steps),per_branch=steps))
 check('scientific_causal_contract',all(r['scientific_causal_status']=='PASS' for r in rows),dict(status_counts=dict(collections.Counter(r['scientific_causal_status'] for r in rows)),raw_host_plan_age=dict(collections.Counter(str(r['raw_plan_age_condition']) for r in rows))))
 check('three_fixed_common_pool_strata',len(rr['matched_fixed_candidate_strata'])==3 and all(len(s['common_exact_plans'])==3 for s in rr['matched_fixed_candidate_strata']))
 check('frozen_test_regret_reproduced',abs(rr['split_regret']['test']['mean_fixed_regret_N_s']-1.6206677021641553)<1e-8)
 check('full_motion_gate_candidate_counts',all(rr['summary'][k]['eligible_rows']==13 for k in ['strict','moderate','wide']))
 check('ordinary_pool_separated_from_historical_G',rr['ordinary_pool_summary']['eligible_rows']==74 and rr['ordinary_pool_summary']['mean_fixed_regret_N_s']==0 and sum(r['candidate_pool_class']=='HISTORICAL_OFFLINE_G_HEAD' for r in rows)==6)
 hist=load(OUT/'HISTORICAL_ROLLING_CONTINUATION_AUDIT.json')
 check('historical_rolling_gap_recomputed',len(hist['results'])==2 and abs(hist['results'][0]['commit_minus_archived_rolling_N_s']-20.646403232713283)<1e-8 and hist['results'][1]['commit_minus_archived_rolling_N_s']==0 and hist['source_mode']=='SCIENTIFIC_SIMULATION')
 check('value_contract_host_not_promoted',load(OUT/'COMMITTED_VS_REPLANNING_VALUE.json')['V_replan']['measured_value_difference_N_s'] is None)
 check('zero_training_host_and_physical_calls',ds['new_attempts']==[] and protocol['budget']['host_clock_pairs']==0 and protocol['budget']['new_Q_training']==0)
 currentgit={p:git_state(Path(p)) for p in before['git']};save('GIT_AFTER.json',currentgit);check('git_branch_head_status_index_diff_staged_unchanged',currentgit==before['git'])
 changed=[]
 for r in before['files']:
  p=Path(r['path'])
  if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:changed.append(str(p))
 currentset={str(p) for pkg in protocol['sources'] for p in (ROOT/pkg).rglob('*') if p.is_file()};oldset={r['path'] for r in before['files']}
 check('protected_historical_bytes_and_file_set_unchanged',not changed and currentset==oldset,dict(protected_files=len(oldset),protected_bytes=sum(r['bytes'] for r in before['files']),changed=changed,added=sorted(currentset-oldset),removed=sorted(oldset-currentset)))
 weights=[ROOT/'m2_host_generalization_attribution_v1/weights/frozen_Q_v1/weights.npz',OLD/'models/Q_32.npz',OLD/'models/Q_16.npz']
 check('frozen_weight_identity',all(sha(p)==next(r['sha256'] for r in before['files'] if r['path']==str(p)) for p in weights),[dict(path=str(p),sha256=sha(p)) for p in weights])
 for p in (OUT/'code').glob('*.py'):ast.parse(p.read_text())
 check('audit_code_syntax',True)
 for p in OUT.rglob('*.json'):
  json.loads(p.read_text(),parse_constant=lambda v:(_ for _ in ()).throw(ValueError('NONFINITE_JSON:'+v)))
 check('strict_finite_JSON',True)
 process=subprocess.run(['ps','-eo','pid,ppid,etimes,args'],capture_output=True,text=True).stdout
 active=[s for s in process.splitlines() if str(OUT) in s and ('python' in s or 'worker' in s) and str(os.getpid()) not in s and 'bash -lc' not in s and 'wsl.exe' not in s]
 check('no_other_package_worker_or_physics_process',not active,active)
 check('within_wall_budget',time.time()<protocol['deadline_unix'],dict(elapsed_s=time.time()-protocol['start_unix'],cap_s=9000))
 save('PACKAGE_VERIFICATION.json',dict(status='PASS' if all(c['pass_'] for c in checks) else 'FAIL',meaning='Integrity, arithmetic and protection checks only; does not promote scientific, host-clock, hardware or clinical qualification.',checks=checks,created_unix=time.time()))
 save('FULL_PACKAGE_MANIFEST.json',dict(files=[dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['FULL_PACKAGE_MANIFEST.json','PACKAGE_CLOSED.json']]))
 local=datetime.now(timezone(timedelta(hours=8)))
 save('PACKAGE_CLOSED.json',dict(status='CLOSED' if all(c['pass_'] for c in checks) else 'VERIFICATION_FAILURE_REVIEW_REQUIRED',closed_local=local.isoformat(),elapsed_wall_min=(time.time()-protocol['start_unix'])/60,new_branch_attempts=0,new_valid_states=0,host_pairs=0,Q_training=0,package_process_policy='All prior audit commands joined/returned; this verifier exits immediately. Final external ps confirmation is performed before delivery.',recommended_direction='D'))
 print('VERIFICATION',[(c['name'],c['pass_']) for c in checks],flush=True)
 if not all(c['pass_'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
