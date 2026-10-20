"""Versioned 18D waypoint intents; unchanged mechanics, certification and actuation."""
from dataclasses import replace
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.coordination_residual_v2 import NativeResidualPlannerV2
from traction_mpc_stage5.task import TaskPhase

class RichFreePlanner(NativeResidualPlannerV2):
    def parameters(self):
        x=np.asarray(getattr(self,'free_parameters',np.zeros(18)),float)
        assert x.ndim==1 and len(x) in (10,18) and np.all(np.isfinite(x))
        return np.pad(x,(0,18-len(x)))

    def _waypoint_terminal_velocity(self, *, phase, reference_state, target_q_rad):
        native=super()._waypoint_terminal_velocity(phase=phase,reference_state=reference_state,target_q_rad=target_q_rad)
        x=self.parameters()
        if phase is TaskPhase.HOLD or not np.any(x): return native
        j=0 if phase is TaskPhase.OUTBOUND else 5; k=10 if j==0 else 14
        goal=self.reference_phase_goal(phase)
        if np.all(abs(target_q_rad-goal)<=np.asarray(self.spec.joint_angle_completion_tolerance_rad)): return native
        start=np.asarray(self.spec.start_return_target_rad if phase is TaskPhase.OUTBOUND else self.spec.outbound_goal_target_rad)
        span=np.asarray(self.spec.outbound_goal_target_rad)-np.asarray(self.spec.start_return_target_rad)
        if phase is TaskPhase.RETURN: span=-span
        m=float(np.mean((target_q_rad-start)/span)); e=np.sin(np.pi*np.clip(m,0,1))**2; u=2*m-1
        return native*(1+e*np.array([x[j+3]+x[j+4]+x[k+3]*u,x[j+3]-x[j+4]-x[k+3]*u]))

    def decide(self,**kwargs):
        previous=self.previous_executed_delta_q_rad.copy(); original=super().decide(**kwargs)
        x=self.parameters(); phase=kwargs['phase']
        if phase is TaskPhase.HOLD or not np.any(x): return original
        target=np.asarray(original.executed.target_q_rad)
        if np.max(abs(target-self.reference_phase_goal(phase)))<=1e-10: return original
        start=np.asarray(self.spec.start_return_target_rad); span=np.asarray(self.spec.outbound_goal_target_rad)-start
        if phase is TaskPhase.RETURN: start,span=start+span,-span
        progress=(target-start)/span; m=float(progress.mean()); e=np.sin(np.pi*np.clip(m,0,1))**2; u=2*m-1
        j=0 if phase is TaskPhase.OUTBOUND else 5; k=10 if j==0 else 14
        c=e*(x[j]+x[k]*u+x[k+1]*u*u); d=e*(x[j+1]+x[j+2]*u+x[k+2]*u*u)
        modified=progress+np.array([c+d,c-d])
        if np.any(modified<0) or np.any(modified>1):
            return replace(original,executed=replace(original.executed,execution_screen={**original.executed.execution_screen,'free_trajectory':dict(status='REJECTED',reason='NORMALIZED_TARGET_OUT_OF_RANGE',parameters=x)}))
        self.previous_executed_delta_q_rad=previous
        alt=self._evaluate(label='isolated_rich_waypoint',state=np.asarray(kwargs['current_deployable_state']),reference_state=np.asarray(kwargs['current_reference_state']),phase=phase,phase_elapsed_s=kwargs['phase_elapsed_s'],phase_remaining_s=kwargs['phase_remaining_s'],action=start+span*modified-np.asarray(kwargs['current_deployable_state'])[:2],execution_feasibility_checker=kwargs.get('execution_feasibility_checker'),value_state_or_belief=kwargs.get('value_state_or_belief'),candidate_value_evaluator=kwargs.get('candidate_value_evaluator'))
        meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,parameters=x,original_target=target,proposed_target=start+span*modified,common_shift=c,differential_shift=d,continuous_realization='unchanged certified quintic; polynomial spatial intent and velocity tilt',native_B_interface=False)
        chosen=alt if alt.feasible else original.executed
        chosen=replace(chosen,execution_screen={**chosen.execution_screen,'free_trajectory':meta})
        self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
        return replace(original,executed=chosen,selection_mode='isolated_rich_waypoint_'+meta['status'],evaluations=original.evaluations+(chosen,))
