"""Isolated one-factor duration intervention, with a fresh original certificate."""
from dataclasses import replace
import numpy as np
from round_planner import RoundPlanner, FixedDuration

class EarlyReturnPlanner(RoundPlanner):
 def decide(self, **kw):
  previous=self.previous_executed_delta_q_rad.copy()
  original=super().decide(**kw)
  intent=getattr(self,'early_return_intent',None)
  if intent is None:return original
  assert kw['phase'].value=='RETURN'
  factor=float(intent['duration_factor']);assert 1.0<=factor<=1.30
  target=np.asarray(original.executed.target_q_rad)
  if np.max(abs(target-self.reference_phase_goal(kw['phase'])))<=1e-10:raise ValueError('EARLY_RETURN_MUST_BE_INTERNAL')
  old=original.executed.schedule;duration=float(np.ceil((old.duration_s*factor)/.005-1e-10)*.005)
  velocity=old.candidate.dq_waypoint_rad_s.copy()
  self.previous_executed_delta_q_rad=previous
  native=self.scheduler;self.scheduler=FixedDuration(native,duration);self.round_forced_velocity=velocity
  try:
   alt=self._evaluate(label='early_return_duration_v1',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed
  if alt.feasible:
   assert abs(chosen.schedule.duration_s-duration)<1e-12
   assert np.max(abs(chosen.target_q_rad-target))<1e-12
   assert np.max(abs(chosen.schedule.candidate.dq_waypoint_rad_s-velocity))<1e-12
  meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,phase='RETURN',slot=intent['slot'],duration_factor=factor,original_duration_s=old.duration_s,new_duration_s=duration,original_target_rad=target,unchanged_pass_velocity_rad_s=velocity,all_18D_parameters_unchanged=True,T_suffix_rule_unchanged=True,D_posture_rule_unchanged=True,fresh_fixed_duration_contract=True,truth_consumed=False)
  chosen=replace(chosen,execution_screen={**chosen.execution_screen,'early_return_duration':meta})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='early_return_duration_'+meta['status'],evaluations=original.evaluations+(chosen,))
