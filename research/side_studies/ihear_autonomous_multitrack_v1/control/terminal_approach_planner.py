"""Isolated pre-deceleration knee pass-velocity intent; original certificate path."""
from dataclasses import replace
import numpy as np
from early_return_planner import EarlyReturnPlanner
from round_planner import FixedDuration

class TerminalApproachPlanner(EarlyReturnPlanner):
 def decide(self, **kw):
  previous=self.previous_executed_delta_q_rad.copy()
  original=super().decide(**kw)
  intent=getattr(self,'terminal_approach_intent',None)
  if intent is None:return original
  assert kw['phase'].value=='RETURN' and int(intent['slot'])==3
  factor=float(intent['knee_velocity_factor']);assert .8<=factor<=1.
  target=np.asarray(original.executed.target_q_rad);old=original.executed.schedule
  assert np.max(abs(target-self.reference_phase_goal(kw['phase'])))>1e-10
  velocity=old.candidate.dq_waypoint_rad_s.copy();assert velocity[1]<-1e-8
  new_velocity=velocity.copy();new_velocity[1]*=factor
  self.previous_executed_delta_q_rad=previous;native=self.scheduler
  self.scheduler=FixedDuration(native,old.duration_s);self.round_forced_velocity=new_velocity
  try:
   alt=self._evaluate(label='terminal_approach_knee_velocity_v1',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed
  if alt.feasible:
   assert abs(chosen.schedule.duration_s-old.duration_s)<1e-12
   assert np.max(abs(chosen.target_q_rad-target))<1e-12
   assert np.max(abs(chosen.schedule.candidate.dq_waypoint_rad_s-new_velocity))<1e-12
  # Preserve factual parent intervention receipts, not the old curve certificate.
  inherited={k:v for k,v in original.executed.execution_screen.items() if k in ['second_round_posture','early_return_duration','terminal_duration_intervention']}
  meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,phase='RETURN',slot=3,knee_velocity_factor=factor,old_pass_velocity_rad_s=velocity,new_pass_velocity_rad_s=new_velocity,unchanged_target_rad=target,unchanged_selected_duration_s=old.duration_s,parent_18D_T_D_Early_RETURN_rules_frozen=True,fresh_original_certificate_required=True,truth_consumed=False)
  chosen=replace(chosen,execution_screen={**chosen.execution_screen,**inherited,'terminal_approach_velocity':meta})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='terminal_approach_velocity_'+meta['status'],evaluations=original.evaluations+(chosen,))
