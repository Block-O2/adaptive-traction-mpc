"""TEST_ONLY: synthetic 20ms acceleration authority input during real MuJoCo.
No plant/safety threshold/action changes. This is not a natural safety failure.
"""
from common import ROOT,put
import os,time,numpy as np
from dataclasses import replace
if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('GUARD_REQUIRED')
from runtime_setup import install
install()
from ready_env import ReadyEnv
out=ROOT/'runs/repair_safety_TEST_ONLY_01/physics';out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
class Injected(ReadyEnv):
 def tick(self,t,interface,observation,state,spec):
  super().tick(t,interface,observation,state,spec)
  if t>=1. and not getattr(self,'injected',False):
   self.injected=True;monitor=self.capture['runtime']['monitor'];original=monitor.update
   def injected_update(**kwargs):
    sample=original(**kwargs)
    if not sample.human_motion_valid:raise RuntimeError('TEST_ONLY_INJECTION_REQUIRES_VALID_HISTORY')
    synthetic=np.asarray(spec.task_joint_acceleration_limit_rad_s2)*1.01
    put(out/'INJECTION.json',{'category':'TEST_ONLY_SYNTHETIC_MONITOR_VALUE','task_s':t,'source':'20ms acceleration field only','original':sample.human_motion_acceleration_rad_s2,'synthetic':synthetic,'thresholds':spec.task_joint_acceleration_limit_rad_s2,'real_physics_changed':False,'natural_failure':False})
    return replace(sample,human_motion_acceleration_rad_s2=synthetic)
   monitor.update=injected_update
env=Injected(out/'env',retain_trace=True);rows=[]
try:
 obs,info=env.reset(seed=20261021);term=False
 for i in range(16):
  action=np.ones(2,np.float32);before=obs.copy();obs,r,term,trunc,info=env.step(action);rows.append((before,action,r,obs.copy(),term,trunc))
  if term or trunc:break
 assert term and not trunc and info['abort_reason']=='TASK_ACCELERATION_LIMIT' and np.all(obs==0)
 m=env.metrics();m.update(status=info['status'],abort_reason=info['abort_reason'],success=info['success'],terminated=term,truncated=trunc)
 np.savez_compressed(out/'transitions_0.npz',obs=[x[0] for x in rows],actions=[x[1] for x in rows],rewards=[x[2] for x in rows],next_obs=[x[3] for x in rows],terminated=[x[4] for x in rows],truncated=[x[5] for x in rows])
 put(out/'RESULT.json',{'category':'TEST_ONLY_AUTHORITY_INPUT_WITH_REAL_MUJOCO','pass':True,'episodes':[m],'natural_safety_qualification':False,'assertions':'original authority threshold -> runtime ABORTED -> step terminated, zero terminal observation, no success'})
finally:env.close()
