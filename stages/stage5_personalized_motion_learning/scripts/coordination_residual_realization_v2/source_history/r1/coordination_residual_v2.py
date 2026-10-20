"""High-level differential targets; no reference tape or phase-time spline."""
from dataclasses import replace
import numpy as np
from .terminal_reference import TerminalSetHumanWaypointPlannerV1
from ..task import TaskPhase

class NativeResidualPlannerV2(TerminalSetHumanWaypointPlannerV1):
 def decide(self,**kwargs):
  previous=self.previous_executed_delta_q_rad.copy()
  original=super().decide(**kwargs)
  phase=kwargs['phase'];action=getattr(self,'residual_spec',{})
  if phase is TaskPhase.HOLD or not action or not action.get(phase.value):return original
  target=np.asarray(original.executed.target_q_rad)
  start=np.asarray(self.spec.start_return_target_rad);goal=np.asarray(self.spec.outbound_goal_target_rad)
  span=goal-start
  if phase is TaskPhase.RETURN:start,span=goal,-span
  p=(target-start)/span;m=float(np.mean(p))
  knots=np.asarray(action[phase.value],float)
  if knots.ndim!=2 or knots.shape[1]!=2 or knots[0,0]!=0 or knots[-1,0]!=1 or knots[0,1]!=0 or knots[-1,1]!=0 or np.any(np.diff(knots[:,0])<=0) or not np.all(np.isfinite(knots)):raise ValueError('INVALID_RESIDUAL_GRAPH')
  endpoint=np.max(np.abs(target-self.reference_phase_goal(phase)))<=1e-10
  delta=0. if endpoint else float(np.interp(m,knots[:,0],knots[:,1]))
  if delta==0:return original
  modified=p+np.array([delta,-delta])
  meta=dict(version='native_residual_v2',phase=phase.value,nominal_progress=p,nominal_common=m,delta=delta,modified_progress=modified,common_error=float(np.mean(modified)-m),nominal_target=target,proposed_target=start+span*modified,endpoint_zero=endpoint,semantics='sample differential graph at native nominal target progress; native scheduler owns q/dq/ddq',status='PROPOSED')
  if np.any(modified<0) or np.any(modified>1):
   meta.update(status='REJECTED',reason='NORMALIZED_TARGET_OUT_OF_RANGE')
   alt=original.executed
  else:
   self.previous_executed_delta_q_rad=previous
   alt=self._evaluate(label='coordination_residual_v2',state=np.asarray(kwargs['current_deployable_state']),reference_state=np.asarray(kwargs['current_reference_state']),phase=phase,phase_elapsed_s=kwargs['phase_elapsed_s'],phase_remaining_s=kwargs['phase_remaining_s'],action=start+span*modified-np.asarray(kwargs['current_deployable_state'])[:2],execution_feasibility_checker=kwargs.get('execution_feasibility_checker'),value_state_or_belief=kwargs.get('value_state_or_belief'),candidate_value_evaluator=kwargs.get('candidate_value_evaluator'))
   meta.update(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason)
  if meta['status']=='REJECTED':
   chosen=replace(original.executed,execution_screen={**original.executed.execution_screen,'coordination_residual_v2':meta})
  else:chosen=replace(alt,execution_screen={**alt.execution_screen,'coordination_residual_v2':meta})
  result=replace(original,executed=chosen,selection_mode='native_residual_v2_'+meta['status'],evaluations=original.evaluations+(chosen,))
  self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return result

