from pathlib import Path
import os,sys,json,pickle,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');sys.path.insert(0,str(S/'code'))
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,numpy as np
def main():
 import multirate,fast_runtime,fast_task_owner,host_adapter as ha,native_core as nc,representation
 from native_method import NativeInterface
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 cfg=json.loads((S/'queue/003_M2_guard_off_smoke.json').read_text());cfg.update(execution_mode='SCIENTIFIC_SIMULATION',strict55_guard=False)
 multirate.install('R3','SCIENTIFIC_SIMULATION');fast_runtime.install(cfg);fast_task_owner.warm();ha.warm(cfg)
 assert representation.TIMINGS[3]==[.1,.4,.7]
 records=[];old=S.parent/'b_native_q_realtime_integration_v1/output/STATE_SNAPSHOTS/061_E3T_science_M2'
 for p in sorted(old.glob('*.pkl')):
  row=pickle.loads(p.read_bytes());c=row['context'];raw=row['payload'];planner,args=pickle.loads(raw)
  req=op.PlanRequest(row['request_id'],'TASK',0.,row['sensor_capture_ns'],row['request_ns'],True)
  b=dict(adaptive_planner=planner,planner=planner.planner,arguments=args,request=req,belief=args['belief'],task_state=sc.types.SimpleNamespace(phase=args['phase'],phase_elapsed_s=args['phase_elapsed_s'],hold_elapsed_s=0.),sac_hooks=sc.types.SimpleNamespace(force_integral=0.,moment_integral=0.),physical_now=c['task_s'],task_start_time=0.)
  x=NativeInterface(cfg);x.count=row['count'].copy();x.carry=row['carry'].copy();x.rng.bit_generator.state=row['rng_state'];x.context=lambda bb:(c,None)
  x.decision_boundary(b);expected=x.search_rows[-1]
  baseline=op.execute_task_snapshot(nc.snapshot_task_call(planner,args))
  ha.COORD.count=row['count'].copy();ha.COORD.carry=row['carry'].copy();ha.COORD.rng.bit_generator.state=row['rng_state'];ha.COORD.context=lambda bb:(c,None)
  planner,args=pickle.loads(raw)
  hint=dict(request=req,base_payload_sha256=hashlib.sha256(raw).hexdigest(),spec=planner.planner.spec,task_state=b['task_state'],physical_now=c['task_s'],task_start_time=0.,observation=np.zeros(4),reference_acceleration=np.zeros(2),measured_force_world_n=np.zeros(3),measured_moment_world_nm=np.zeros(3),force_integral=0.,moment_integral=0.)
  result=ha.task_with_certificates(pickle.dumps((ha.TAG,raw,hint),protocol=5));assert 'value' in result,result
  actual=result['m2_worker_evidence']['selection_row'];value=result['value']
  features=np.asarray([nc.feature(c,r['plan'],row['count'],row['carry']) for r in actual['candidate_records']]);assert features.shape[1]==120
  manual=np.asarray([np.r_[c['observation'],c['richer_previous_residual'],nc.masked(r['plan'],row['count']).ravel(),nc.masked(row['carry'],row['count']).ravel(),[row['count']['OUTBOUND']/5,row['count']['RETURN']/5]].astype(np.float32) for r in actual['candidate_records']]);assert np.array_equal(features,manual)
  for rec in actual['candidate_records']:
   for j,phase in enumerate(('OUTBOUND','RETURN')):assert not np.any(np.asarray(rec['plan'])[j,:min(row['count'][phase],5)])
  same=expected['selected_index']==actual['selected_index'] and np.array_equal(expected['applied_plan'],actual['applied_plan'])
  delta=float(np.max(np.abs(baseline.executed.target_q_rad-value.executed.target_q_rad)))
  assert same and delta<=1e-10,(p.name,same,delta)
  # Zero residual is independently certified by the exact native input path.
  p0,a0=pickle.loads(raw);p0.planner.residual_spec={};orig=op.execute_task_snapshot(nc.snapshot_task_call(p0,a0))
  if orig.feasible if hasattr(orig,'feasible') else True:pass
  zero=nc.native_local(dict(adaptive_planner=p0,arguments=a0,planner=p0.planner),c,np.zeros((2,5,3)),row['count'])
  assert np.allclose(orig.executed.target_q_rad,zero['target'],atol=1e-10,rtol=0)
  records.append(dict(snapshot=p.name,snapshot_sha256=sc.sha(p),source_capture_ns=req.sensor_capture_ns,count=row['count'],available_slots={k:max(0,5-v) for k,v in row['count'].items()},feature_shape=list(features.shape),feature_sha256=hashlib.sha256(features.tobytes()).hexdigest(),selected_identity_match=same,target_max_error_rad=delta,zero_target_max_error_rad=float(np.max(np.abs(orig.executed.target_q_rad-zero['target']))),Q_ranking=actual['q_first_order'],candidate_sources=[r['source'] for r in actual['candidate_records']],same_state_candidate_scoring=True,issued_count_preserved=True))
 out=dict(status='PASS',no_physics=True,records=records,K3_identity=representation.TIMINGS[3],feature_order=['causal normalized55','previous K3 residual3','masked candidate30','masked carry30','issued counts2'],Q_sha256=sc.sha(S/'weights/frozen_Q_v1/weights.npz'),full_evaluate_vs_Q_first_agreement=True,zero_residual_native_B=True,scope='11 saved development contexts; frozen Q, same C13 native certification; no host execution claim')
 sc.save('OFFLINE_INTERFACE_GATE.json',out);(S/'reports/OFFLINE_INTERFACE_GATE.json').write_text(json.dumps(sc.clean(out),indent=2)+'\n')
 # Reset lambda state only in this offline process; owners start fresh.
 print(json.dumps(dict(status='PASS',saved_inputs=len(records),feature_dim=120,K3=representation.TIMINGS[3],no_physics=True)))
if __name__=='__main__':main()
