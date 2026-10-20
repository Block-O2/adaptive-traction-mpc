"""Frozen-Q SCI stability via the already implemented native persistent session.

No actual-clock or adaptation claim. Same plant/updater/measurement state is
retained by native carryover_runtime_fields; native settle/hold is counted.
"""
from task_bootstrap import *
def run_many(outer):
 import worker,study_common as sc,consecutive_worker as regular
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_coordination_residual_v2 as rt,runtime_sac_expert_v1 as orig
 from traction_mpc_stage4 import estimator_v2 as accounting
 import numpy as np
 context={};records=[];original_main=worker.main;native_runs={rt:rt.run_executed_case,orig:orig.run_executed_case};index=[0]
 def inject(fn):
  def call(*args,**kw):
   assert kw['execution_mode']=='SCIENTIFIC_SIMULATION','CONTINUOUS_ACTUAL_CLOCK_UNSUPPORTED_BY_FROZEN_NATIVE_SOURCE'
   kw['session_context']=context;return fn(*args,**kw)
  return call
 for module,fn in native_runs.items():module.run_executed_case=inject(fn)
 def stop_check():
  if time.time()>=START+8.25*3600:raise RuntimeError('CONTINUOUS_SAFE_CLOSEOUT')
 def state():
  if 'runtime' not in context:return None
  p=context['runtime']['plant'];belief=context['updater'].snapshot()
  return dict(physical_time_s=float(p.data.time),plant_identity=id(p),updater_identity=id(context['updater']),updater_sequence=context['updater'].sequence,belief_beta=np.asarray(belief.beta).tolist(),belief_residual=np.asarray(belief.state_residual_weights_nm).tolist(),native_qpos=np.asarray(p.data.qpos).tolist(),native_qvel=np.asarray(p.data.qvel).tolist())
 def one():
  j=index[0];index[0]+=1;req=json.loads(Path(sys.argv[1]).read_text());before_boundary=state();boundary=None
  try:
   stop_check()
   if j:
    boundary=rt.advance_inter_rep_boundary(context,max_wait_s=2.,stop_check=stop_check)
    assert boundary['physical_object_unchanged']
    save(STUDY/'output'/(req['id']+'_INTER_REP_BOUNDARY.json'),sc.clean(boundary))
   initial=state();main_before=getattr(accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0);t=time.time();original_main();end=state()
   path=Path(req['result_path']);result=json.loads(path.read_text());m=result.get('metric',{})
   if end:
    start_physics=0. if initial is None else initial['physical_time_s'];new_s=end['physical_time_s']-start_physics
    m['fresh_episode_compatibility_accounting_before_session_fix']={k:m.get(k) for k in ('actual_new_simulation_seconds','actual_new_native_physics_steps','actual_new_main_model_inverse_dynamics_api_calls')}
    m.update(actual_new_simulation_seconds=new_s,actual_new_native_physics_steps=round(new_s/rt.NOMINAL_PHYSICS_DT_S),actual_new_main_model_inverse_dynamics_api_calls=getattr(accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0)-main_before,continuous_session=True,repetition_index=j+1,inter_rep_physics_seconds=0. if boundary is None else boundary['end_time_s']-boundary['start_time_s'],inter_rep_force_cost=None if boundary is None else sc.clean(boundary['cost']))
    if initial:assert initial['plant_identity']==end['plant_identity'] and initial['updater_identity']==end['updater_identity'],'CONTINUOUS_NATIVE_OWNER_CHANGED'
   row=dict(id=req['id'],repetition=j+1,method=req['method'],status=result['status'],valid=m.get('valid',False),J_F=m.get('J_F'),moment_integral=m.get('moment_integral'),moment_peak=m.get('moment_peak'),wall_seconds=time.time()-t,before_boundary=before_boundary,initial=initial,end=end,frozen_Q_sha256=req.get('weights_sha256'),Q_updated=False,physics_clock='SCIENTIFIC_SIMULATION',inter_rep_boundary=boundary is not None)
   result['continuous_session_evidence']=row;save(path,result)
   if m:save(STUDY/'output'/(req['id']+'.json'),m)
   records.append(row)
   if result['status']!='COMPLETE' or not m.get('valid'):del outer['consecutive_requests'][j+1:]
  except BaseException as e:
   result=dict(id=req['id'],status='FAILED',error=str(e),inputs=req,wall_seconds=0.,continuous_session=True,failed_boundary_only=True)
   save(Path(req['result_path']),result);records.append(dict(id=req['id'],status='FAILED',error=str(e),before_boundary=before_boundary,end=state()));del outer['consecutive_requests'][j+1:]
 worker.main=one
 try:regular.run_many(outer)
 finally:
  worker.main=original_main
  for module,fn in native_runs.items():module.run_executed_case=fn
  save(STUDY/'output'/(outer['id']+'_CONTINUOUS_SESSION.json'),dict(rows=records,native_physical_carryover=True,native_Human_belief_carryover=True,native_measurement_filter_and_rng_carryover=True,native_inter_rep_settle_hold_retained=True,frozen_Q=True,adaptation_pilot=False,actual_clock_qualification=False,scope='Exposed nominal Human; frozen-Q SCI repetition stability, not independent Human generalization',boundary_costs_separate=True))
