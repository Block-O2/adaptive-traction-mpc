"""W3 exact allocation-output reuse within ONE immutable original TASK.

Every schedule sample and original inverse-dynamics API call still executes.
The complete original model object and exact torque/q key every allocation;
changed inputs miss and each result is independently owned. No cross-request
reuse or sensor/plant access exists here.
"""
import copy
INSTALLED=False
ENABLED=True
def install():
 global INSTALLED
 if INSTALLED:return
 import fast_task_owner as owner,loaded_context_reuse as values
 from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel as C
 original=C.allocate_generalized_action
 def allocation(self,torque,q):
  scope=owner.SCOPE.get()
  if scope is None or not ENABLED:return original(self,torque,q)
  key=values.raw((self,torque,q))
  cache=scope.setdefault('allocation_cache',{});counts=scope.setdefault('numerical_counts',{})
  if key in cache:
   counts['allocation_hit']=counts.get('allocation_hit',0)+1
   return copy.deepcopy(cache[key])
  out=original(self,torque,q);cache[key]=copy.deepcopy(out)
  counts['allocation_miss']=counts.get('allocation_miss',0)+1
  return out
 C.allocate_generalized_action=allocation;INSTALLED=True
 return original,allocation
