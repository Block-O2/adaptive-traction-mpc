"""RETURN5 hip duration contrast; the knee reference must already be constant."""
from dataclasses import replace
import numpy as np
from early_return_planner import EarlyReturnPlanner
from round_planner import FixedDuration

class TerminalTimingPlanner(EarlyReturnPlanner):
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy();original=super().decide(**kw)
  intent=getattr(self,'terminal_timing_intent',None)
  if intent is None:return original
  assert kw['phase'].value=='RETURN' and intent['slot']==5
  factor=float(intent['duration_factor']);assert .75<=factor<=1.5
  target=np.asarray(original.executed.target_q_rad);old=original.executed.schedule
  start=np.asarray(kw['current_reference_state']);velocity=old.candidate.dq_waypoint_rad_s.copy()
  assert abs(target[1]-start[1])<1e-10 and abs(start[3])<1e-10 and abs(velocity[1])<1e-10,'KNEE_REFERENCE_MUST_BE_CONSTANT'
  assert np.max(abs(target-self.reference_phase_goal(kw['phase'])))<1e-10,'TASK_ENDPOINT_MUST_BE_RETAINED'
  duration=float(np.ceil(old.duration_s*factor/.005-1e-10)*.005)
  self.previous_executed_delta_q_rad=previous;native=self.scheduler;self.scheduler=FixedDuration(native,duration);self.round_forced_velocity=velocity
  try:
   alt=self._evaluate(label='terminal_hip_timing_v1',state=np.asarray(kw['current_deployable_state']),reference_state=start,phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed
  meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,phase='RETURN',slot=5,duration_factor=factor,original_duration_s=old.duration_s,new_duration_s=duration,unchanged_target_rad=target,knee_reference_constant=True,truth_consumed=False,fresh_certificate_required=True)
  if alt.feasible:
   ss=[chosen.schedule.sample(t) for t in np.linspace(0,duration,101)]
   assert max(abs(s.q_rad[1]-target[1]) for s in ss)<1e-10
   assert max(abs(s.dq_rad_s[1]) for s in ss)<1e-10
  chosen=replace(chosen,execution_screen={**chosen.execution_screen,'terminal_hip_timing':meta})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='terminal_hip_timing_'+meta['status'],evaluations=original.evaluations+(chosen,))
