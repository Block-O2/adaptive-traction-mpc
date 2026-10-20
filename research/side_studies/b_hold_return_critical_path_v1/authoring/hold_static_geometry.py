"""C16b: reuse exact q/model geometry inside original HOLD prepare only.

Reference velocity, loaded equilibrium, inverse dynamics and all original
candidate checks execute afresh. Every geometry/factor hit is a private copy.
No observed live pose, native admission or safety certificate is cached.
"""
import contextvars,collections,pickle,io
SCOPE=contextvars.ContextVar('original_hold_mapping_static_geometry',default=None)
CACHE=collections.OrderedDict();COUNTS=collections.Counter();INSTALLED=False
def values(x):
 # Complete original dataclass values; memoized serialization is conservative
 # about alias differences and avoids building a duplicate Python value tree.
 return pickle.dumps(x,protocol=5)
def qvalues(q):return (q.dtype.str,q.shape,q.tobytes())
def reusable(q):
 s=SCOPE.get()
 return s is not None and qvalues(q)==s['qvalues']
def cached(kind,inputs,calculate):
 k=(kind,inputs)
 if k in CACHE:
  COUNTS[kind+'_hit']+=1;CACHE.move_to_end(k);return pickle.loads(CACHE[k])
 COUNTS[kind+'_miss']+=1;out=calculate();CACHE[k]=pickle.dumps(out,protocol=5)
 if len(CACHE)>64:CACHE.popitem(last=False)
 return out
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1 as C
 from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry as G,BaseParameterHumanModel as H
 from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator as A
 from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel as R
 original_prepare=C.prepare;original_pose=G.cuff_pose;original_factors=A._prepare_factors
 def pose(self,q):
  s=SCOPE.get()
  if type(self) is not G or not reusable(q) or self is not s['geometry']:return original_pose(self,q)
  return cached('pose',(s['geometry_key'],s['qvalues']),lambda:original_pose(self,q))
 def factors(self,q,human):
  s=SCOPE.get()
  if type(self) is not A or type(human) not in (H,R) or not reusable(q) or human is not s['human'] or self is not s['allocator']:return original_factors(self,q,human)
  return cached('allocator_factors',(s['model_allocator_key'],s['qvalues']),lambda:original_factors(self,q,human))
 def prepare(self,candidate):
  if type(self) is not C or candidate.phase.value!='HOLD' or candidate.execution_context.value!='TASK':return original_prepare(self,candidate)
  # The exact immutable model objects are read once within this original pure
  # prepare invocation. They have no mutable/live-plant reads or side effects.
  token=SCOPE.set(dict(qvalues=qvalues(candidate.q_waypoint_rad),geometry=self.human_model.geometry,human=self.human_model,allocator=self.cuff_allocator,geometry_key=values(self.human_model.geometry),model_allocator_key=values((self.human_model,self.cuff_allocator))))
  try:return original_prepare(self,candidate)
  finally:SCOPE.reset(token)
 G.cuff_pose=pose;A._prepare_factors=factors;C.prepare=prepare;INSTALLED=True
def reset():CACHE.clear();COUNTS.clear()
def evidence():return dict(counters=dict(COUNTS),cache_entries=len(CACHE),scope='Only exact reference q within original HOLD prepare',original_candidate_validation=True,fresh_original_velocity_equilibrium_inverse_dynamics=True,no_live_state_or_native_certificate_cache=True)
