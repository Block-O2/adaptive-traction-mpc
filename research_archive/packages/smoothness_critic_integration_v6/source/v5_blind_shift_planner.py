"""Registered fixed-sign perturbation control with no branch-risk information."""
from dataclasses import replace
import numpy as np
from v5_smooth_planner import ReferenceSmoothPlanner
from round_planner import FixedDuration
class BlindShiftPlanner(ReferenceSmoothPlanner):
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy();original=super().decide(**kw)
  if kw['phase'].value!='RETURN' or int(getattr(self,'coordination_slot',-1))!=1:return original
  delta=float(getattr(self,'blind_shift_delta_deg',0.));assert abs(delta)<=.02
  old=original.executed.schedule;target=np.asarray(original.executed.target_q_rad);locked=np.abs(target-self.reference_phase_goal(kw['phase']))<=1e-10
  shift=np.radians([delta,-delta]);shift[locked]=0.;native=self.scheduler;self.previous_executed_delta_q_rad=previous;self.scheduler=FixedDuration(native,old.duration_s);self.round_forced_velocity=old.candidate.dq_waypoint_rad_s.copy()
  try:
   alt=self._evaluate(label='v5_blind_fixed_relative_shift',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target+shift-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed;meta=dict(phase='RETURN',slot=1,delta_deg=delta,status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,branch_information_used=False,duration_preserved=True,endpoint_locks_preserved=True,truth_used=False)
  chosen=replace(chosen,execution_screen={**original.executed.execution_screen,**chosen.execution_screen,'v5_blind_shift':meta});self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='v5_blind_shift_'+meta['status'],evaluations=original.evaluations+(chosen,))
