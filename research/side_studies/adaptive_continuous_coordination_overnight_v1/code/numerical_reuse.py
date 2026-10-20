"""R2: cache an explicit pure numerical kernel, after fresh model/Jacobian reads."""
import pickle,sys,contextvars,numpy as np
SCOPE=contextvars.ContextVar('loaded_context_owner',default=None)
LAST=None;ROWS={'numerical_hit':0,'numerical_miss':0,'observer_hit':0,'observer_miss':0}
def key(x):return pickle.dumps(x,protocol=5)
def aliases(old,new):
 for module in list(sys.modules.values()):
  ns=getattr(module,'__dict__',None)
  if ns:
   for n,v in list(ns.items()):
    if v is old:ns[n]=new
def install(shadow=False):
 from traction_mpc_stage3 import executable_command as ec
 from traction_mpc_stage5 import loaded_execution as le,controller_interface as ci
 original=ec.prepare_executable_command_context
 def prepared(**kw):
  global LAST
  scope=SCOPE.get()
  if scope is None:return original(**kw)
  payload=key((scope,kw,kw.get('gains',ec.DEFAULT_LOW_LEVEL_COMMAND_GAINS)))
  if LAST is not None and LAST[0]==payload and key(LAST[1])==LAST[2]:
   ROWS['numerical_hit']+=1
   if shadow:assert key(original(**kw))==LAST[2],'PURE_NUMERICAL_REUSE_NOT_EXACT'
   return LAST[1]
  out=original(**kw);LAST=(payload,out,key(out));ROWS['numerical_miss']+=1;return out
 aliases(original,prepared)
 build=le.build_stage5_loaded_execution_context
 def context(**kw):
  observation=kw['observation'];measurement=kw['measurement']
  token=SCOPE.set((id(kw['plant']),id(kw['human_model']),observation.human_model_version,
   observation.sample_timestamp_s,measurement.sample_time_s,measurement.arrival_time_s))
  try:return build(**kw)
  finally:SCOPE.reset(token)
 aliases(build,context)
 observer=ci.InterfaceAwareHumanStateObserver.update
 def update(self,measurement,human_model,*,human_model_version):
  payload=key((measurement,human_model,human_model_version,self.parameters));prior=getattr(self,'_fast_observer_r2',None)
  if prior is not None and payload==prior[0] and self._last is prior[1][1] and key(self._last)==prior[2]:
   ROWS['observer_hit']+=1
   if shadow:assert key(observer(self,measurement,human_model,human_model_version=human_model_version))==key(prior[1]),'OBSERVER_REUSE_NOT_EXACT'
   return prior[1]
  out=observer(self,measurement,human_model,human_model_version=human_model_version);self._fast_observer_r2=(payload,out,key(self._last));ROWS['observer_miss']+=1;return out
 ci.InterfaceAwareHumanStateObserver.update=update
 return prepared,original
