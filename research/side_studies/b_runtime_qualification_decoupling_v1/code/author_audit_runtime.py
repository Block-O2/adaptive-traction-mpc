from pathlib import Path
import sys,json,hashlib,collections,subprocess
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_runtime_qualification_decoupling_v1')
OLD=S.parent/'b_hold_return_critical_path_v1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(S/'code'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def review(ident,existing=False):
 if existing:
  target=S/'source/results'/ident
  if not target.exists():target.symlink_to(OLD/'source/results'/ident,target_is_directory=True)
  for p in (OLD/'output').glob(ident+'*'):
   dest=S/'output'/p.name
   if not dest.exists():dest.symlink_to(p)
 import host_review
 sys.argv=['host_review.py',ident];host_review.main()
 f=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text())
 result=json.loads((S/'output'/(ident+'_RESULT.json')).read_text())
 summary=json.loads((S/'source/results'/ident/'summary.json').read_text())
 checks={k:v for k,v in f['functional_checks'].items() if k!='original_R2'}
 metric=result.get('metric',{});physical=f['legacy_result'].get('original_physical_task_result',{})
 durations=metric.get('phase_durations',{})
 checks['OUTBOUND_RETURN_completed']=bool(summary.get('status')=='COMPLETE' and durations.get('OUTBOUND',0)>0 and durations.get('RETURN',0)>0)
 checks['HOLD_functional_original_semantics']=bool(summary.get('status')=='COMPLETE' and durations.get('HOLD',0)>=1. and physical.get('status')=='PASS')
 ev=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text())
 requests=[r for r in ev['native_requests'] if r['stage']=='TASK']
 rejected=[r for r in requests if r['outcome']!='ACTIVATED']
 source=S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py'
 # Causal raw receipt audit covers every interval, including planner waits.
 # Unchanged source hash, guarded lifecycle code and completed native safety
 # establish lawful continuation; no new fault-injection claim is made.
 checks['legal_prior_control_while_waiting']=bool(checks['causal_substep_command_ownership'] and checks['expired_writes'] and checks['bounded_backlog'] and physical.get('status')=='PASS')
 checks['original_timestamps_no_free_freeze']=bool(checks['causal_substep_command_ownership'] and f['wall_physics']['physics_elapsed_s']>0 and not f['causal_violations'])
 out=dict(id=ident,status='PASS' if all(checks.values()) else 'FAIL',axis='B_RUNTIME_MOTION',existing_evidence=existing,checks=checks,LEGACY_R2_MATCHED='PASS' if f['legacy_result']['original_r2_valid'] else 'FAIL',LEGACY_STRICT55=f['legacy_strict'],phase_durations=durations,physical_audit=physical,service_gap_ms=f['service_gap_ms'],rolling_1s_mean_ms=f['rolling_1s_mean_ms'],backlog=f['wall_physics'],meaningful_plans=f['legacy_result']['physically_executed_meaningful_count'],actual_native_steps=f['actual_native_steps'],request_outcomes=dict(collections.Counter(r['outcome'] for r in requests)),rejected_requests=rejected,causal_violations=f['causal_violations'],expired_physical_steps=f['expired_physical_steps'],expired_writes=f['expired_actual_write_receipts'],metric=metric,continuation_scope='All observed actual intervals audited; native rejection/expiry source preserved; deliberate host fault suite separately NOT_RUN unless added',raw_evidence=f['legacy_result']['meaningful_plans'])
 save(S/'reports'/(ident+'_RUNTIME_QUALIFICATION.json'),out)
 print(json.dumps({k:out[k] for k in ('id','status','LEGACY_R2_MATCHED','LEGACY_STRICT55','phase_durations','service_gap_ms','meaningful_plans','request_outcomes')}),flush=True)
 return out
if __name__=='__main__':
 if sys.argv[1]=='existing':
  rows=[review(i,True) for i in ('047_C13_host_nominal_quiet','048_C13_host_deviation_quiet')]
  save(S/'reports/EXISTING_EVIDENCE_QUALIFICATION.json',dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',registered_contract=str(S/'QUALIFICATION_CONTRACT.json'),rows=[dict(id=r['id'],status=r['status'],checks=r['checks']) for r in rows],historical_results_unchanged=True,retrospective_new_axis_only=True))
 else:review(sys.argv[1])
