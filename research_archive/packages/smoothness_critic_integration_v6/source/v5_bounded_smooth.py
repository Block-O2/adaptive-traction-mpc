"""Reference jerk optimization using only the original common modal speed coordinate."""
from dataclasses import replace
import numpy as np
from acl2_modal_retimed import RetimedModalPlanner
from v5_smooth_planner import jerk_energy
from round_planner import FixedDuration
class ReferenceSmoothBoundedPlanner(RetimedModalPlanner):
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy();original=super().decide(**kw);strength=float(getattr(self,'smooth_strength',0.))
  if strength==0 or kw['phase'].value not in ['OUTBOUND','RETURN']:return original
  assert 0<=strength<=1;old=original.executed.schedule;target=np.asarray(original.executed.target_q_rad);goal=self.reference_phase_goal(kw['phase'])
  if np.max(abs(target-goal))<=1e-10:return original
  modal=original.executed.execution_screen.get('coordination_modal_v2')
  if modal is None:return original
  weight=float(modal['weight']);native_v=np.asarray(modal['original_pass_velocity'],float);index=6 if kw['phase'].value=='OUTBOUND' else 7;old_c=float(self.coordination_modes[index]);assert -1<=old_c<=1
  q0=old.start_q_rad;v0=old.start_dq_rad_s;T=old.duration_s
  energy=lambda c:float(np.sum(jerk_energy(q0,v0,target,native_v*(1.+.12*c*weight),T)))
  f0,fp,fm=energy(0.),energy(1.),energy(-1.);quadratic=.5*(fp+fm-2*f0);linear=.5*(fp-fm)
  optimal=float(np.clip(-linear/(2*quadratic),-1.,1.)) if quadratic>1e-14 else old_c;c=old_c+strength*(optimal-old_c)
  proposed=native_v*(1.+.12*c*weight);self.previous_executed_delta_q_rad=previous;native=self.scheduler;self.scheduler=FixedDuration(native,T);self.round_forced_velocity=proposed
  try:
   alt=self._evaluate(label='v5_reference_jerk_original_modal_domain',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed;record=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,strength=strength,original_modal_speed_coordinate=old_c,proposed_modal_speed_coordinate=c,native_parent_pass_velocity=native_v,weight=weight,coordinate_bounds=[-1.,1.],same_common_speed_coordinate=True,original_pass_velocity_rad_s=old.candidate.dq_waypoint_rad_s,proposed_pass_velocity_rad_s=proposed,original_duration_s=T,target_unchanged=True,original_reference_jerk_energy=jerk_energy(q0,v0,target,old.candidate.dq_waypoint_rad_s,T),proposed_reference_jerk_energy=jerk_energy(q0,v0,target,proposed,T),future_truth_used=False,action_permission_valid=True)
  chosen=replace(chosen,execution_screen={**original.executed.execution_screen,**chosen.execution_screen,'v5_reference_smooth':record});self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='v5_reference_smooth_bounded_'+record['status'],evaluations=original.evaluations+(chosen,))
