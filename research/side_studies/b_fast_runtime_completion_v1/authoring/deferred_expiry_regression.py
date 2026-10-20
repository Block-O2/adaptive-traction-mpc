"""C1d+C1b fake-clock source/lifecycle boundaries; no physical dispatch."""
from pathlib import Path
import sys,json,types,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc,causal_clock as c,deferred_receipt_prepare as d
from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp
from traction_mpc_stage5.full3d_adaptive_integration_v1.applied_reference_history import AppliedReferenceMotionHistory as H
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanLifecycle
c.install();d.install();rows=[]
for lifecycle in (False,True):
 for offset,cost in ((99974000,0),(99975000,0),(99975000,1),(99999999,2),(100000000,0),(100000001,0)):
  epoch=10**9;clock=types.SimpleNamespace(now=epoch+offset);plant=types.SimpleNamespace(data=types.SimpleNamespace(ctrl=np.array([1.]),time=0.),last_joint_torque=np.array([1.]))
  wall=wp.WallPhysicsSession.__new__(wp.WallPhysicsSession);wall.__dict__.update(clock=lambda:clock.now,epoch_ns=epoch,dt=.00025,dt_ns=250000,steps=0,origin_physics_s=0.,plant=plant,applied_commands=[dict(receipt_index=0,applied=True,native_steps=0,apply_ns=None)],active_receipt_index=0,limit_violations=[],native_states=[])
  history=H(lambda:plant.data.time,np.array([1.,1.]),np.zeros(2),0.);wall.runtime=dict(contract=types.SimpleNamespace(reference_motion_history=history),autonomous_recovery_options=dict(fixed_command_ready=True),model_sequence=7)
  wall.source_ns=lambda time:epoch+round(time*1e9);wall.catch_up=lambda why:None;events=[];written=[]
  def step():
   assert not hasattr(history,'_fast_prepared_reference_grid');events.append((wall.steps,wall.active_receipt_index,float(plant.data.ctrl[0])));wall.steps+=1;plant.data.time+=wall.dt
  wall._step=step;command=types.SimpleNamespace(joint_torque_command_nm=np.array([2.]));receipt=wall.prepare_apply(command,source_sample_time_s=0.)
  def write():written.append(clock.now);plant.data.ctrl[0]=2.;plant.last_joint_torque[0]=2.;clock.now+=cost
  if lifecycle:
   life=PlanLifecycle(clock=wall.clock,process_worker=False);life.capture(0.,epoch);request=life.request('TASK',0.,asynchronous=False);wall.runtime.update(plan_lifecycle=life,plan_to_activate=request)
  error=None
  try:
   if lifecycle:
    life.activate(request,lambda:wall.apply(command,write,source_sample_time_s=0.,prepared=receipt,catchup=False),effective_activation_ns=receipt['effective_activation_ns'],applied_receipt=receipt)
   else:wall.apply(command,write,source_sample_time_s=0.,prepared=receipt,catchup=False)
  except RuntimeError as e:error=str(e)
  assert not hasattr(history,'_fast_prepared_reference_grid') or (not written and lifecycle)
  # PlanLifecycle can reject before entering apply; subsequent prepare replaces
  # the private marker, and the original run aborts. Clear it for test disposal.
  d.clear(history)
  if receipt['applied']:
   assert receipt['effective_activation_ns']-epoch<100000000 if lifecycle else receipt['effective_activation_ns']-epoch<=100000000
   assert all(owner==0 and torque==1. for _,owner,torque in events)
   assert plant.data.ctrl[0]==2.
  else:
   assert wall.active_receipt_index==0 and plant.data.ctrl[0]==1. and not events
   assert error or lifecycle
  rows.append(dict(lifecycle=lifecycle,ready_offset_ns=offset,write_cost_ns=cost,write_count=len(written),applied=receipt['applied'],error=error,lifecycle_outcome=life.records()[0]['outcome'] if lifecycle else None,original_source_capture_ns=receipt['source_capture_ns'],effective_activation_ns=receipt['effective_activation_ns']))
out=dict(status='PASS',cases=len(rows),no_physics=True,source_and_lifecycle_limits_unchanged=True,expired_staged_writes_rolled_back_before_any_physics=True,rows=rows)
sc.save('C1d_EXPIRY_LOCAL_REGRESSION.json',out);print(json.dumps(out))
