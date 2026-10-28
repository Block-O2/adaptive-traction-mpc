"""Small explicit causal schedule-risk selector; original guard is never changed."""
from dataclasses import replace
import numpy as np
from v5_smooth_planner import ReferenceSmoothPlanner,jerk_energy
from round_planner import FixedDuration

def risk(schedule,current_state,current_reference,geometry):
 t=np.arange(1,int(np.floor(schedule.duration_s/.005))+1)*.005
 t=t[t<=schedule.duration_s+1e-10]
 ss=[schedule.sample(float(x)) for x in t];q=np.array([s.q_rad for s in ss]);v=np.array([s.dq_rad_s for s in ss])
 # A deliberately small explicit model: observed tracking error decays at 0.1 s.
 # This is a candidate ranking heuristic, never a clearance safety certificate.
 error=np.asarray(current_state)-np.asarray(current_reference)
 decay=np.exp(-t/.1)[:,None];q=q+decay*error[:2];v=v+decay*error[2:]
 phi=q[:,0]-q[:,1];dr=v[:,0]-v[:,1];px,pz=geometry.plane_x_world[2],geometry.plane_z_world[2]
 axis=px*np.cos(phi)+pz*np.sin(phi);rate=(-px*np.sin(phi)+pz*np.cos(phi))*dr
 distance=abs(axis)-1e-5*abs(rate);index=int(np.argmin(distance));uncertainty=2e-4
 score=float(max(0.,(uncertainty-distance[index])/uncertainty))
 return dict(risk_score=score,min_distance_to_stencil=float(distance[index]),predicted_event_local_s=float(t[index]),predicted_axis_z=float(axis[index]),predicted_axis_rate_s_inv=float(rate[index]),uncertainty_band_axis=uncertainty,model='current signed schedule + causal estimated tracking error, exponential 0.1s persistence; original 5ms execution grid',safety_certificate=False,future_truth_used=False)

class AnticipatoryPlanner(ReferenceSmoothPlanner):
 def decide(self,**kw):
  previous=self.previous_executed_delta_q_rad.copy();original=super().decide(**kw)
  if kw['phase'].value not in ['OUTBOUND','RETURN']:return original
  target=np.asarray(original.executed.target_q_rad);goal=self.reference_phase_goal(kw['phase']);locked=np.abs(target-goal)<=1e-10
  if np.all(locked):return original
  old=original.executed.schedule;state=np.asarray(kw['current_deployable_state']);ref=np.asarray(kw['current_reference_state']);geometry=self.scheduler.human_model.geometry
  base=risk(old,state,ref,geometry);records=[dict(delta_deg=0.,feasible=True,risk=base)];chosen=original.executed;best_score=base['risk_score'];chosen_delta=0.;chosen_risk=base
  if base['risk_score']>0:
   native=self.scheduler;velocity=old.candidate.dq_waypoint_rad_s.copy()
   for delta in [-.02,-.005,.005,.02]:
    shift=np.radians([delta,-delta]);shift[locked]=0.;proposed=target+shift
    self.previous_executed_delta_q_rad=previous;self.scheduler=FixedDuration(native,old.duration_s);self.round_forced_velocity=velocity
    try:
     alt=self._evaluate(label='v5_anticipatory_relative_shift',state=state,reference_state=ref,phase=kw['phase'],phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],action=proposed-state[:2],execution_feasibility_checker=kw.get('execution_feasibility_checker'),value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
    finally:self.scheduler=native;self.round_forced_velocity=None
    rr=risk(alt.schedule,state,ref,geometry) if alt.feasible else None
    records.append(dict(delta_deg=delta,feasible=bool(alt.feasible),reason=alt.rejection_reason,risk=rr))
    score=rr['risk_score']+.01*(abs(delta)/.02)**2 if rr else float('inf')
    if score+1e-12<best_score:
     chosen=alt;best_score=score;chosen_delta=delta;chosen_risk=rr
  meta=dict(changed=bool(chosen_delta),delta_deg=chosen_delta,base_risk=base,selected_risk=chosen_risk,candidates=records,phase=kw['phase'].value,slot=int(getattr(self,'coordination_slot',-1)),source='execution-before candidate planning; causal estimated state and reference/scheduler only',guard_unchanged=True,target_shift_bound_deg=.02,duration_preserved=True,truth_used=False)
  chosen=replace(chosen,execution_screen={**original.executed.execution_screen,**chosen.execution_screen,'v5_anticipatory':meta})
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return replace(original,executed=chosen,selection_mode='v5_anticipatory_CHANGED' if chosen_delta else 'v5_anticipatory_KEEP',evaluations=original.evaluations+(chosen,))
