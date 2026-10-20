from pathlib import Path
import sys,json,types,numpy as np,copy
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc,causal_clock,deferred_receipt_prepare as d
from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp
from traction_mpc_stage5.full3d_adaptive_integration_v1.applied_reference_history import AppliedReferenceMotionHistory as H
causal_clock.install();old_prepare,prepare,old_validate,validate=d.install();records=[]
for offset in (0,1,249999,250000,499999,4300123,19999999,20000001,99975000):
 for velocity in (np.zeros(2),np.array([.0001,-.0001]),np.array([10.,10.])):
  epoch=10**9;clock=types.SimpleNamespace(now=epoch+offset);plant=types.SimpleNamespace(data=types.SimpleNamespace(ctrl=np.array([1.]),time=0.),last_joint_torque=np.array([1.]))
  wall=wp.WallPhysicsSession.__new__(wp.WallPhysicsSession);wall.__dict__.update(clock=lambda:clock.now,epoch_ns=epoch,dt=.00025,dt_ns=250000,steps=0,origin_physics_s=0.,plant=plant,applied_commands=[dict(receipt_index=0,applied=True,native_steps=0,apply_ns=None)],active_receipt_index=0,limit_violations=[],native_states=[])
  history=H(lambda:plant.data.time,np.array([1.,1.]),np.zeros(2),0.)
  wall.runtime=dict(contract=types.SimpleNamespace(reference_motion_history=history),autonomous_recovery_options=dict(fixed_command_ready=True),model_sequence=7);wall.source_ns=lambda time:epoch+round(time*1e9);wall.catch_up=lambda why:None;events=[]
  def step():
   events.append(dict(index=wall.steps,owner=wall.active_receipt_index,torque=float(plant.data.ctrl[0])));wall.steps+=1;plant.data.time+=wall.dt;clock.now+=10000
  wall._step=step;command=types.SimpleNamespace(joint_torque_command_nm=np.array([2.]));receipt=prepare(wall,command,source_sample_time_s=0.)
  assert wall.steps==0 and plant.data.time==0. and plant.data.ctrl[0]==1.;prospective=receipt['prospective_ready_reference_time_s'];clock_before=history.clock
  # Independent original history at the exact target of original catch-up.
  reference=H(lambda:prospective,np.array([1.,1.]),np.zeros(2),0.);original_error=None;actual_error=None
  try:expected=old_validate(reference,np.ones(2),velocity,np.ones(2))
  except RuntimeError as e:original_error=str(e)
  try:actual=validate(history,np.ones(2),velocity,np.ones(2))
  except RuntimeError as e:actual_error=str(e)
  assert original_error==actual_error and history.clock is clock_before and not hasattr(history,'_fast_prepared_reference_grid')
  if original_error is None:
   assert sc.clean(expected)==sc.clean(actual)
   def write():plant.data.ctrl[0]=2.;plant.last_joint_torque[0]=2.;clock.now+=20000
   applied=causal_clock.apply(wall,command,write,source_sample_time_s=0.,prepared=receipt,catchup=False);step()
   assert applied['apply_ns']==epoch+offset+20000
   for event in events:
    if event['owner']==1:assert epoch+event['index']*250000>=applied['apply_ns'] and event['torque']==2.
    else:assert event['torque']==1.
   assert 0<=applied['quantization_delay_ns']<250000
  else:assert not events and plant.data.ctrl[0]==1. and not receipt['applied']
  records.append(dict(offset=offset,velocity=velocity.tolist(),original_rejection=original_error,old_intervals=len(events)-int(original_error is None),write_happened=original_error is None))
out=dict(status='PASS',cases=len(records),records=records,no_native_physics=True,reference_guard_bit_exact=True,all_pending_intervals_keep_old_command=True,original_source_age_unchanged=True,clock_restored_before_any_physical_step=True,scope='pure receipt ZOH check at original readiness grid; no projected observer/state/phase admission and no dropped old-control/sensor/safety intervals')
sc.save('C1d_DEFERRED_RECEIPT_LOCAL_REGRESSION.json',out);print(json.dumps(out))
