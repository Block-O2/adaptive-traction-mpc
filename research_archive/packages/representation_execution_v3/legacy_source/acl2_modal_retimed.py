"""New reference permissions only; original evaluator/certificate/plant unchanged."""
from dataclasses import replace
import numpy as np
from terminal_planner import TerminalTimingPlanner
from round_planner import FixedDuration

MODE_NAMES=['O_common_path','O_relative_path','R_common_path','R_relative_path','O_local_time','R_local_time','O_pass_speed','R_pass_speed']
class ReplanDuration:
 def __init__(self,original,parent_duration,factor):self.original=original;self.parent_duration=parent_duration;self.factor=factor;self.record=None
 def __getattr__(self,n):return getattr(self.original,n)
 def plan_reference_contract(self,**kw):
  minimum=self.original.plan_reference_contract(**kw)
  duration=float(np.ceil(max(self.parent_duration,minimum.duration_s)*self.factor/.005-1e-10)*.005)
  self.record=dict(original_parent_duration_s=self.parent_duration,original_scheduler_minimum_s=minimum.duration_s,requested_factor=self.factor,requested_duration_s=duration,safety_limits_unchanged=True)
  return self.original.plan_fixed_duration_reference_contract(**kw,duration_s=duration)
 def plan_fixed_duration_reference_contract(self,**kw):return self.original.plan_fixed_duration_reference_contract(**kw)

class RetimedModalPlanner(TerminalTimingPlanner):
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy();original=super().decide(**kw)
  x=np.asarray(getattr(self,'coordination_modes',np.zeros(8)),float)
  assert x.shape==(8,) and np.all(np.isfinite(x)) and np.all(abs(x)<=1+1e-12),'MODAL_DOMAIN'
  phase=kw['phase'].value;slot=int(getattr(self,'coordination_slot',-1))
  if phase not in ['OUTBOUND','RETURN'] or not np.any(x):return original
  target=np.asarray(original.executed.target_q_rad);goal=self.reference_phase_goal(kw['phase'])
  if np.max(abs(target-goal))<=1e-10:return original
  # Per-request compact modes; indices are decision slots, not samples of an
  # unexecuted continuous high-dimensional curve. Interior full quintics execute.
  j=0 if phase=='OUTBOUND' else 2;k=4 if j==0 else 5;v=6 if j==0 else 7
  if not np.any(x[[j,j+1,k,v]]):return original
  weight=float(np.sin(np.pi*np.clip((slot+.5)/6,0,1))**2)
  direction=1. if phase=='OUTBOUND' else -1.
  shift=np.radians(.30)*weight*direction*np.array([x[j]+x[j+1],x[j]-x[j+1]])
  endpoint_locked=np.abs(target-goal)<=1e-10
  shift[endpoint_locked]=0.
  proposed=target+shift;old=original.executed.schedule
  factor=1.+.08*float(x[k])*weight
  duration=float(np.ceil(old.duration_s*factor/.005-1e-10)*.005)
  # Preserve the parent duration exactly when timing is zero.
  if x[k]==0:duration=float(old.duration_s)
  velocity=old.candidate.dq_waypoint_rad_s.copy()*(1.+.12*float(x[v])*weight)
  self.previous_executed_delta_q_rad=previous;native=self.scheduler
  proxy=ReplanDuration(native,old.duration_s,factor);self.scheduler=proxy;self.round_forced_velocity=velocity
  try:
   alt=self._evaluate(label='coordination_modal_v2',state=np.asarray(kw['current_deployable_state']),reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=proposed-np.asarray(kw['current_deployable_state'])[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
  finally:self.scheduler=native;self.round_forced_velocity=None
  chosen=alt if alt.feasible else original.executed
  meta=dict(schema='acl2.modal.retimed.v2',individual_joint_endpoint_locks=endpoint_locked,scheduler_duration_record=proxy.record,status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,parameters=x,phase=phase,slot=slot,weight=weight,original_target_rad=target,proposed_target_rad=proposed,original_duration_s=old.duration_s,proposed_duration_s=duration,original_pass_velocity=old.candidate.dq_waypoint_rad_s,proposed_pass_velocity=velocity,actually_selected_target_rad=chosen.target_q_rad,actually_selected_duration_s=chosen.schedule.duration_s if chosen.schedule is not None else None,actually_selected_pass_velocity=chosen.schedule.candidate.dq_waypoint_rad_s if chosen.schedule is not None else None,endpoints_and_HOLD_preserved=True,fresh_original_certificate=True,truth_used=False)
  chosen=replace(chosen,execution_screen={**chosen.execution_screen,'coordination_modal_v2':meta})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='coordination_modal_v2_'+meta['status'],evaluations=original.evaluations+(chosen,))
