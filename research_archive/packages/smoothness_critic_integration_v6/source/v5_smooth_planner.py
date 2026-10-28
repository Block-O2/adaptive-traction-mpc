"""Bounded reference-only terminal-velocity optimization, original evaluator intact."""
from dataclasses import replace
import numpy as np
from acl2_modal_retimed import RetimedModalPlanner
from round_planner import FixedDuration
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import hermite

def jerk_energy(q0,v0,q1,v1,T):
 c=hermite(np.asarray(q0),np.asarray(v0),np.zeros(2),np.asarray(q1),np.asarray(v1),np.zeros(2),T)
 j=c[:,3:]*np.array([6.,24.,60.])
 H=1./(np.arange(3)[:,None]+np.arange(3)[None,:]+1.)
 return np.einsum('bi,ij,bj->b',j,H,j)/T**5

class ReferenceSmoothPlanner(RetimedModalPlanner):
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy();original=super().decide(**kw)
  strength=float(getattr(self,'smooth_strength',0.))
  if strength==0 or kw['phase'].value not in ['OUTBOUND','RETURN']:return original
  assert 0<=strength<=1
  old=original.executed.schedule;target=np.asarray(original.executed.target_q_rad);goal=self.reference_phase_goal(kw['phase'])
  if np.max(abs(target-goal))<=1e-10:return original
  q0=np.asarray(old.start_q_rad);v0=np.asarray(old.start_dq_rad_s);v1=old.candidate.dq_waypoint_rad_s.copy();T=old.duration_s
  baseline=jerk_energy(q0,v0,target,v1,T);fp=jerk_energy(q0,v0,target,v1+1.,T);fm=jerk_energy(q0,v0,target,v1-1.,T)
  curvature=.5*(fp+fm-2*baseline);slope=.5*(fp-fm)
  optimal=v1-np.divide(slope,2*curvature,out=np.zeros_like(slope),where=curvature>1e-14)
  bound=.12*np.abs(v1);proposed=v1+strength*np.clip(optimal-v1,-bound,bound)
  locked=np.abs(target-goal)<=1e-10;proposed[locked]=v1[locked]
  self.previous_executed_delta_q_rad=previous;native=self.scheduler;self.scheduler=FixedDuration(native,T);self.round_forced_velocity=proposed
  try:
   alt=self._evaluate(label='v5_reference_minimum_jerk_velocity',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=target-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed
  if alt.feasible:assert abs(chosen.schedule.duration_s-T)<1e-12 and np.max(abs(chosen.target_q_rad-target))<1e-12
  record=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,strength=strength,original_pass_velocity_rad_s=v1,proposed_pass_velocity_rad_s=proposed,original_duration_s=T,target_unchanged=True,original_reference_jerk_energy=baseline,proposed_reference_jerk_energy=jerk_energy(q0,v0,target,proposed,T),optimization_inputs='current signed causal schedule and task goal only',future_truth_used=False)
  chosen=replace(chosen,execution_screen={**original.executed.execution_screen,**chosen.execution_screen,'v5_reference_smooth':record})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='v5_reference_smooth_'+record['status'],evaluations=original.evaluations+(chosen,))
