"""C9: cache the original pure HOLD schedule; check CURRENT budget natively.

Only reference-contract continuous HOLD is eligible. All scheduler input values,
reference q/dq and full candidate are keyed. Phase elapsed affects validation and
maximum search steps; these are checked at each actual request. The cached
shortest original duration can be returned only if the identical original search
would still include it. Original model/current-state admission remains intact.
"""
import pickle,io,math,collections
CACHE=collections.OrderedDict();COUNTS=collections.Counter();INSTALLED=False
def signature(self,kw):
 from loaded_context_reuse import raw
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1 as C
 from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1 as G
 if type(self) is not C or type(self.clearance_evaluator) is not G:return None
 if set(kw)!={'current_q_hat_rad','current_dq_hat_rad_s','candidate','phase_elapsed_s','use_legacy_nominal_tracking_preview'}:return None
 if kw['candidate'].phase.value!='HOLD' or kw['use_legacy_nominal_tracking_preview'] or not getattr(self,'continuous_hold_reference',False):return None
 state=dict(vars(self));geometry=state.pop('clearance_evaluator');geometry_state=dict(vars(geometry))
 # The source's certified_minimum writes this diagnostic result and never
 # reads it as an input. Preserve its exact post-call side effect on every hit.
 geometry_state.pop('last_certificate',None)
 arguments={k:v for k,v in kw.items() if k!='phase_elapsed_s'}
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True
 encoder.dump(raw((type(self),state,type(geometry),geometry_state,arguments)))
 return stream.getvalue()
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1 as C,_vector
 original=C._plan
 def plan(self,**kw):
  k=signature(self,kw)
  if k is None:return original(self,**kw)
  # These original checks depend on actual elapsed phase budget and remain live.
  q=_vector('current_q_hat_rad',kw['current_q_hat_rad']);dq=_vector('current_dq_hat_rad_s',kw['current_dq_hat_rad_s'])
  self._validate_request(q,dq,kw['candidate'],kw['phase_elapsed_s'])
  if k in CACHE:
   value,certificate,steps=CACHE[k]
   available_s=self.spec.phase_timeout_s-kw['phase_elapsed_s']
   maximum_steps=int(math.floor(available_s/self.reference_period_s+1.0e-12))
   if maximum_steps>=steps:
    COUNTS['exact_input_current_budget_hit']+=1;CACHE.move_to_end(k)
    schedule=pickle.loads(value)
    object.__setattr__(self.clearance_evaluator,'last_certificate',pickle.loads(certificate))
    return schedule
   COUNTS['insufficient_current_budget_fallback']+=1
  else:COUNTS['exact_input_miss']+=1
  value=original(self,**kw)
  steps=int(round(value.duration_s/self.reference_period_s))
  if value.duration_s==steps*self.reference_period_s:
   certificate=getattr(self.clearance_evaluator,'last_certificate',None)
   CACHE[k]=(pickle.dumps(value,protocol=5),pickle.dumps(certificate,protocol=5),steps)
   if len(CACHE)>8:CACHE.popitem(last=False)
  return value
 C._plan=plan;INSTALLED=True
def evidence():return dict(counters=dict(COUNTS),cache_entries=len(CACHE),current_phase_budget_checked=True,original_scheduler_algorithm_retained=True)
