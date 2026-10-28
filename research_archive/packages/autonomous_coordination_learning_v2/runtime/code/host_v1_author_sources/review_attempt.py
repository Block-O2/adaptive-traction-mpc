from pathlib import Path
import sys,os,json,collections,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime');sys.path.insert(0,str(S/'code'))
import numpy as np
from stream_runtime_evidence import array_items
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def phase_cost(ident,metric):
 folder=S/'source/results'/ident;summary=json.loads((folder/'summary.json').read_text())
 with np.load(folder/'trace.npz') as z:
  mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
 trans={r['to']:r['time_s'] for r in summary['task']['phase_transitions']}
 if not all(k in trans for k in ('HOLD','RETURN','COMPLETE')):return dict(status='INCOMPLETE_NOT_VALID_COST')
 bounds=[t[0],trans['HOLD'],trans['RETURN'],trans['COMPLETE']];rows={}
 for phase,a,b in zip(('OUTBOUND','HOLD','RETURN'),bounds,bounds[1:]):
  dt=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a));used=dt>0;duration=float(dt.sum());jf=float(f[:-1]@dt);mi=float(m[:-1]@dt)
  rows[phase]=dict(J_F_N_s=jf,moment_integral_Nm_s=mi,phase_clock_duration_s=metric['phase_durations'][phase],integrated_trace_duration_s=duration,mean_force_N=jf/duration,mean_moment_Nm=mi/duration,force_peak_N=float(f[:-1][used].max()),moment_peak_Nm=float(m[:-1][used].max()))
 assert abs(sum(r['J_F_N_s'] for r in rows.values())-metric['J_F'])<1e-8
 assert abs(sum(r['moment_integral_Nm_s'] for r in rows.values())-metric['moment_integral'])<1e-8
 return dict(status='COMPLETE_RAW_CLOSURE_PASS',phases=rows,raw_full_J_F_N_s=metric['J_F'],raw_full_moment_integral_Nm_s=metric['moment_integral'],method='original left-endpoint full TASK quadrature partitioned at actual transitions; no cut or added time',integrated_trace_duration_s=float(t[-1]-t[0]),final_completion_after_last_evaluation_sample_s=float(trans['COMPLETE']-t[-1]))
def main():
 ident=sys.argv[1]
 import host_review
 host_review.sys.argv=['host_review.py',ident];host_review.main()
 f=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text());result=json.loads((S/'output'/(ident+'_RESULT.json')).read_text());metric=result.get('metric',{})
 if f.get('status')!='REVIEWED':
  save(S/'reports'/(ident+'_AXES.json'),dict(id=ident,PHYSICAL_TASK_VALID='FAIL',HOST_EXECUTION_CAUSAL_VALID='NOT_EVALUABLE',FAST_RUNTIME_ENGINEERING_QUALIFIED='NOT_EVALUABLE',worker_status=result['status'],error=result.get('error')));return
 checks=f['functional_checks'];engineering=['service_gap_p50','service_gap_p95','service_gap_p99','gap_over_10ms_fraction','missed_grid_fraction','rolling_1s_service_mean','bounded_backlog'];causal=['causal_substep_command_ownership','quantization_delay','expired_writes','original_current_state_admission']
 physical=bool(checks['full_OUT_HOLD_RETURN'] and checks['original_physical_safety'] and result['status']=='COMPLETE')
 ev=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());task={r['request_id']:r for r in ev['native_requests'] if r['stage']=='TASK'}
 rows=[];coordinator=S/'output'/(ident+'_HOST_COORDINATOR.json');receiptpath=S/'source/results'/ident/'runtime_artifacts.json.gz';receipts=list(array_items(receiptpath,'command_receipts'))
 summary=json.loads((S/'source/results'/ident/'summary.json').read_text());decisions=summary.get('decisions',[]);intervals=[]
 for r in summary.get('learning_records',[]):
  index=r.get('decision_index')
  if index is not None and index<len(decisions) and r.get('selected_plan_activated'):
   intervals.append((float(r['start_time_s']),float(r['end_time_s']),decisions[index].get('timing_request_id'),index))
 if coordinator.exists():
  co=json.loads(coordinator.read_text())
  for e in co['rows']:
   rid=e['request_id'];s=e.get('selection_row');req=task.get(rid,{});applied=[];record_index=[]
   for begin,end,owner,index in intervals:
    if owner!=rid:continue
    record_index.append(index)
    for r in receipts:
     if r.get('applied') and r.get('native_steps',0)>0 and begin<=r.get('start_physics_s',-1)<end:applied.append(r)
   applied={r['receipt_index']:r for r in applied};nsteps=sum(r['native_steps'] for r in applied.values())
   phase=None if s is None else s['context']['phase'];i=5 if s is None else s['count_before'][phase]
   action=np.zeros(3) if s is None or i>=5 else np.asarray(s['applied_plan'])[('OUTBOUND','RETURN').index(phase),i]
   proposed=np.zeros(3) if s is None or i>=5 else np.asarray(e['proposed_plan'])[('OUTBOUND','RETURN').index(phase),i]
   meta=[record.get('selected_plan',{}).get('execution_screen',{}).get('coordination_residual_v2',{}) for record in summary.get('learning_records',[]) if record.get('decision_index') in record_index and record.get('selected_plan_activated')]
   native_nonzero=any(m.get('status')=='ACCEPTED' and abs(m.get('delta',0))>1e-12 for m in meta)
   for m in meta:
    if m.get('status')=='ACCEPTED':
     diff=np.asarray(m['modified_progress'])-np.asarray(m['nominal_progress']);assert np.allclose(diff,[m['delta'],-m['delta']],atol=1e-12,rtol=0)
   executed=bool(s is not None and np.any(np.abs(action)>1e-12) and native_nonzero and req.get('outcome')=='ACTIVATED' and nsteps>0)
   rows.append(dict(request_id=rid,source_capture_ns=e['source_capture_ns'],source_inputs=e['source_inputs'],selection=s,candidate_identity=None if s is None else dict(index=s['selected_index'],source=s['selected_source']),proposed_current_K3=proposed.tolist(),applied_current_K3=action.tolist(),proposed_nonzero=bool(np.any(np.abs(proposed)>1e-12)),selected=s is not None,activated=req.get('outcome')=='ACTIVATED',actual_native_steps=nsteps,nonzero_survived_guard=bool(np.any(np.abs(action)>1e-12)),late_carry=e['admission']['late_carry'],lifecycle=req,worker=e,actual_command_receipts=[{k:r.get(k) for k in ('receipt_index','source_capture_ns','apply_ns','sensor_age_at_apply_ms','start_physics_s','end_physics_s','native_steps','q_ref_rad','dq_ref_rad_s','reference_version','command_torque_nm')} for r in applied.values()],native_coordination_metadata=meta,physically_executed_nonzero=executed,new_selected_Q_executed=bool(executed and not e['admission']['late_carry'] and s['selected_source']!='carry'),carried_learning_residual_executed=bool(executed and (e['admission']['late_carry'] or s['selected_source']=='carry')),receipt_join='original native half-open active segment and decision request ID, accepted nonzero native differential metadata, actual command receipts; no ACTIVATED-only proof'))
 age=f['legacy_result']['activation_age_ms'];a=json.loads((S/'reports'/(ident+'_AUDIT.json')).read_text())
 axis=dict(id=ident,label='RESEARCH_HOST_EXPERIMENT / RUNTIME_NOT_QUALIFIED',PHYSICAL_TASK_VALID='PASS' if physical else 'FAIL',HOST_EXECUTION_CAUSAL_VALID='PASS' if all(checks[k] for k in causal) else 'FAIL',FAST_RUNTIME_ENGINEERING_QUALIFIED='PASS' if all(checks[k] for k in engineering) else 'FAIL',LEGACY_R2_MATCHED='PASS' if checks['original_R2'] else 'FAIL',LEGACY_STRICT55='PASS' if age['n'] and age['max']<55 else 'FAIL',historical_engineering_composite=f['legacy_strict'],service_gap_ms=f['service_gap_ms'],miss_fraction=a['miss_rate'],rolling_1s_ms=f['rolling_1s_mean_ms'],backlog=f['wall_physics'],activation_age_ms=age,native_steps=f['actual_native_steps'],metric=metric,phase_cost=phase_cost(ident,metric) if physical else dict(status='NOT_VALID_FULL_TASK'),request_outcomes=dict(collections.Counter(r['outcome'] for r in task.values())),rejections=[r for r in task.values() if r['outcome']!='ACTIVATED'],nonzero_execution_count=sum(r['physically_executed_nonzero'] for r in rows),nonzero_native_steps=sum(r['actual_native_steps'] for r in rows if r['physically_executed_nonzero']),selection_count=sum(r['selected'] for r in rows),late_carry_count=sum(r['late_carry'] for r in rows),Q_calls=max([r['worker']['Q_calls'] for r in rows] or [0]),G_calls=0,Q_updates=0)
 save(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'),dict(id=ident,status='AUDITED' if coordinator.exists() else 'ZERO_RESIDUAL_NATIVE_B',rows=rows,actual_nonzero_count=axis['nonzero_execution_count'],actual_nonzero_native_steps=axis['nonzero_native_steps'],causal_axis=axis['HOST_EXECUTION_CAUSAL_VALID']))
 save(S/'reports'/(ident+'_AXES.json'),axis)
 print(json.dumps({k:axis[k] for k in ('id','PHYSICAL_TASK_VALID','HOST_EXECUTION_CAUSAL_VALID','FAST_RUNTIME_ENGINEERING_QUALIFIED','LEGACY_R2_MATCHED','LEGACY_STRICT55','nonzero_execution_count','nonzero_native_steps','selection_count','late_carry_count','request_outcomes')}),flush=True)
if __name__=='__main__':main()
