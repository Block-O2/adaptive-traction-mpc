"""R1: bounded full-input reuse; no cross-owner or partial-version authority."""
import sys,pickle,time,numpy as np
ROWS={'context_hit':0,'context_miss':0,'context_key_ns':0,'observer_hit':0,'observer_miss':0}
def key(x):return pickle.dumps(x,protocol=5)
def aliases(old,new):
 for module in list(sys.modules.values()):
  ns=getattr(module,'__dict__',None)
  if ns:
   for name,value in list(ns.items()):
    if value is old:ns[name]=new
def install(shadow=False):
 from traction_mpc_stage5 import loaded_execution as le,controller_interface as ci
 old=le.build_stage5_loaded_execution_context
 def context(**kw):
  plant=kw['plant'];robot=plant._measured_robot_model;begin=time.monotonic_ns()
  # Include the complete serialized private robot model, not just an address.
  # qpos/qvel are included to preserve the builder's configuration side effects.
  payload=key(({k:v for k,v in kw.items() if k!='plant'},id(plant),id(robot),robot.model,
   plant.neutral_robot_q,plant.torque_limits_nm,plant.attachment_from_cuff,
   plant.translational_velocity_feedback_source))
  ROWS['context_key_ns']+=time.monotonic_ns()-begin
  prior=getattr(plant,'_fast_loaded_context',None)
  current_configuration=(robot.data.qpos.tobytes(),robot.data.qvel.tobytes())
  if prior is not None and payload==prior[0] and current_configuration==prior[2]:
   ROWS['context_hit']+=1
   if shadow:
    expected=old(**kw);assert key(expected)==key(prior[1]),'CONTEXT_REUSE_NOT_BIT_EXACT'
   return prior[1]
  out=old(**kw);ROWS['context_miss']+=1
  plant._fast_loaded_context=(payload,out,(robot.data.qpos.tobytes(),robot.data.qvel.tobytes()))
  return out
 aliases(old,context)
 original=ci.InterfaceAwareHumanStateObserver.update
 def update(self,measurement,human_model,*,human_model_version):
  payload=key((measurement,human_model,human_model_version,self.parameters))
  prior=getattr(self,'_fast_observer',None)
  if prior is not None and payload==prior[0] and self._last is prior[1][1] and key(self._last)==prior[2]:
   ROWS['observer_hit']+=1
   if shadow:assert key(original(self,measurement,human_model,human_model_version=human_model_version))==key(prior[1]),'OBSERVER_REUSE_NOT_EXACT'
   return prior[1]
  out=original(self,measurement,human_model,human_model_version=human_model_version);ROWS['observer_miss']+=1;self._fast_observer=(payload,out,key(self._last));return out
 ci.InterfaceAwareHumanStateObserver.update=update
