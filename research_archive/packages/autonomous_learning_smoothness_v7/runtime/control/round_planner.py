"""Additive middle-posture intent on byte-frozen 18D/T, through original checks."""
from dataclasses import replace
import numpy as np
from terminal_repair import TerminalRepairPlanner

class FixedDuration:
 def __init__(self,original,duration):self.original=original;self.duration=duration
 def __getattr__(self,n):return getattr(self.original,n)
 def plan_reference_contract(self,**kw):return self.original.plan_fixed_duration_reference_contract(**kw,duration_s=self.duration)
 def plan_fixed_duration_reference_contract(self,**kw):
  if abs(kw['duration_s']-self.duration)>1e-12:raise ValueError('SECOND_ROUND_DURATION_FROZEN')
  return self.original.plan_fixed_duration_reference_contract(**kw)

class RoundPlanner(TerminalRepairPlanner):
 def _waypoint_terminal_velocity(self,**kw):
  forced=getattr(self,'round_forced_velocity',None)
  return forced.copy() if forced is not None else super()._waypoint_terminal_velocity(**kw)
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy()
  original=super().decide(**kw)
  intent=getattr(self,'round_posture',None)
  if intent is None:return original
  target=np.asarray(original.executed.target_q_rad)
  if np.max(abs(target-self.reference_phase_goal(kw['phase'])))<=1e-10:raise ValueError('POSTURE_MUST_NOT_CHANGE_TASK_ENDPOINT')
  delta=np.radians(intent['delta_deg']);assert delta.shape==(2,) and np.max(abs(delta))<=np.radians(.3)+1e-12
  duration=original.executed.schedule.duration_s
  self.previous_executed_delta_q_rad=previous;native=self.scheduler;self.scheduler=FixedDuration(native,duration)
  self.round_forced_velocity=original.executed.schedule.candidate.dq_waypoint_rad_s.copy()
  try:
   alt=self._evaluate(label='second_round_middle_posture',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target+delta-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed
  if alt.feasible:assert abs(chosen.schedule.duration_s-duration)<1e-12
  meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,original_target_rad=target,proposed_target_rad=target+delta,delta_deg=intent['delta_deg'],original_duration_s=duration,outer_pass_velocity_unchanged=True,all_18D_parameters_unchanged=True,truth_consumed=False)
  chosen=replace(chosen,execution_screen={**chosen.execution_screen,'second_round_posture':meta})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='second_round_posture_'+meta['status'],evaluations=original.evaluations+(chosen,))
