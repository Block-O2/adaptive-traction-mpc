"""C14: exact pure fixed-HOLD reference/model mapping, no current-state cache.

The original candidate validator executes on every call. History, observer,
feedback, geometry safety and final native admission stay in their original
paths. Every returned mapped result is a fresh private copy and binds the
actual candidate object. Changed complete values cause original recomputation.
"""
import io,pickle,collections,dataclasses
CACHE=collections.OrderedDict();COUNTS=collections.Counter();INSTALLED=False
def key(self,candidate):
 from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1 as C
 from traction_mpc_stage4.cuff_allocator import CurrentForceMinimizingAllocator,CuffAwareSagittalAllocator
 from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
 from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
 if type(self) is not C or candidate.phase.value!='HOLD' or candidate.execution_context.value!='TASK' or type(self.cuff_allocator) not in (CurrentForceMinimizingAllocator,CuffAwareSagittalAllocator):return None
 from loaded_context_reuse import raw
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True
 encoder.dump(raw((self.spec,self.human_model,self.cuff_allocator,candidate,CONTROLLER_NOMINAL_INTERFACE,STAGE5_GEOMETRY)))
 return stream.getvalue()
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1 as C
 original=C.prepare
 def prepare(self,candidate):
  k=key(self,candidate)
  if k is None:return original(self,candidate)
  self._validate_candidate(candidate)  # Original live model/task bounds.
  if k in CACHE:
   COUNTS['exact_value_hit']+=1;CACHE.move_to_end(k)
   return dataclasses.replace(pickle.loads(CACHE[k]),candidate=candidate)
  COUNTS['exact_value_miss']+=1;value=original(self,candidate);CACHE[k]=pickle.dumps(value,protocol=5)
  if len(CACHE)>8:CACHE.popitem(last=False)
  return value
 C.prepare=prepare;INSTALLED=True
def reset():CACHE.clear();COUNTS.clear()
def evidence():return dict(counters=dict(COUNTS),cache_entries=len(CACHE),live_candidate_validation=True,no_current_state_or_certificate_cache=True)
