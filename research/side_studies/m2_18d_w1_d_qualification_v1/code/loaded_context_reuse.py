"""R3: transaction-local context reuse, with fresh private mechanics reads.

The borrowed allocator and Human model remain the current objects. Keys include
all raw inputs and newly computed velocity/J/bias; no live MjModel is serialized.
The cache lives only for one original _execute_interval invocation.
"""
import contextvars,pickle,sys,types,struct,enum,numpy as np
SCOPE=contextvars.ContextVar('complete_loaded_context_transaction',default=None)
ROWS={'hit':0,'miss':0,'fresh_mechanics':0,'mutated_output':0}
def raw(x):
 # Complete value tree without repeatedly serializing NumPy class metadata.
 if isinstance(x,np.ndarray):return (np.ndarray,x.dtype.str,x.shape,x.tobytes())
 if isinstance(x,enum.Enum):return (type(x),raw(x.value))
 if isinstance(x,type):return (type,x)
 if isinstance(x,float):return (type(x),struct.pack('d',x))
 if x is None or isinstance(x,(str,bytes,int,bool)):return (type(x),x)
 if isinstance(x,(list,tuple)):return (type(x),tuple(raw(v) for v in x))
 if isinstance(x,dict):return (dict,tuple((k,raw(v)) for k,v in x.items()))
 if hasattr(x,'__dict__'):return (type(x),raw(vars(x)))
 return (type(x),pickle.dumps(x,protocol=5))
def aliases(old,new):
 for module in list(sys.modules.values()):
  ns=getattr(module,'__dict__',None)
  if ns:
   for name,value in list(ns.items()):
    if value is old:ns[name]=new
def fingerprint(ctx):
 f=ctx.safety_filter_context
 return raw((ctx.target,ctx.actual_human_cuff,ctx.measured_robot_cuff,
  ctx.estimated_interface_state,ctx.robot_from_human_world_m,ctx.command_context,
  f.estimated_state,f.command_context,f.allocation_matrix,f.sagittal_null_vector,
  f.world_mapping,f.world_null_wrench))
def transaction(function):
 def wrapped(*args,**kwargs):
  token=SCOPE.set({})
  try:return function(*args,**kwargs)
  finally:SCOPE.reset(token)
 return wrapped
def install(shadow=False):
 from traction_mpc_stage5 import loaded_execution as le
 import study_common as sc
 original=le.build_stage5_loaded_execution_context
 def context(**kw):
  cache=SCOPE.get()
  if cache is None:return original(**kw)
  plant=kw['plant'];m=kw['measurement'];robot=plant._measured_robot_model
  # These are actual fresh private-model reads, including mj_forward. Model,
  # attachment, velocity-source or numeric configuration changes cannot hide.
  velocity=plant.control_feedback_velocity_snapshot(m)
  robot.set_configuration(m.robot_q_rad,m.robot_dq_rad_s)
  jac=robot.rigid_offset_jacobian(plant.attachment_from_cuff.translation)
  bias=robot.bias_torque_nm();ROWS['fresh_mechanics']+=1
  k=raw((id(plant),id(robot),id(kw['human_model']),id(kw['cuff_allocator']),
   {n:v for n,v in kw.items() if n not in ('plant','cuff_allocator')},
   plant.neutral_robot_q,plant.torque_limits_nm,plant.attachment_from_cuff,
   plant.translational_velocity_feedback_source,le.DEFAULT_LOW_LEVEL_COMMAND_GAINS,
   velocity,jac,bias))
  prior=cache.get(k)
  if prior is not None and fingerprint(prior[0])==prior[1]:
   if shadow:assert fingerprint(original(**kw))==prior[1],'LOADED_CONTEXT_REUSE_NOT_EXACT'
   ROWS['hit']+=1;return prior[0]
  if prior is not None:ROWS['mutated_output']+=1
  # Original builder consumes precisely the fresh reads above, once. The
  # proxy is local and cannot escape in the returned numerical context.
  proxy_robot=types.SimpleNamespace(set_configuration=lambda *a:None,
   rigid_offset_jacobian=lambda *a:jac,bias_torque_nm=lambda:bias)
  proxy=types.SimpleNamespace(control_feedback_velocity_snapshot=lambda *a:velocity,
   _measured_robot_model=proxy_robot,attachment_from_cuff=plant.attachment_from_cuff,
   neutral_robot_q=plant.neutral_robot_q,torque_limits_nm=plant.torque_limits_nm)
  out=original(**(kw|{'plant':proxy}));cache[k]=(out,fingerprint(out));ROWS['miss']+=1
  if shadow:assert fingerprint(original(**kw))==fingerprint(out),'FRESH_MECHANICS_PROXY_NOT_EXACT'
  return out
 aliases(original,context)
 sc.rt._execute_interval=transaction(sc.rt._execute_interval)
 return context,original
