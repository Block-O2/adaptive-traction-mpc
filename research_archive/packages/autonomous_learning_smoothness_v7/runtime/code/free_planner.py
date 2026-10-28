"""Isolated richer waypoint intent; unchanged scheduler, plant and certification."""
from dataclasses import replace
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.coordination_residual_v2 import NativeResidualPlannerV2
from traction_mpc_stage5.task import TaskPhase

class FreePlanner(NativeResidualPlannerV2):
    def _waypoint_terminal_velocity(self, *, phase, reference_state, target_q_rad):
        native=super()._waypoint_terminal_velocity(phase=phase,reference_state=reference_state,target_q_rad=target_q_rad)
        x=np.asarray(getattr(self,'free_parameters',np.zeros(10)))
        if phase is TaskPhase.HOLD or not np.any(x):return native
        j=0 if phase is TaskPhase.OUTBOUND else 5
        goal=self.reference_phase_goal(phase)
        if np.all(abs(target_q_rad-goal)<=np.asarray(self.spec.joint_angle_completion_tolerance_rad)):return native
        start=np.asarray(self.spec.start_return_target_rad if phase is TaskPhase.OUTBOUND else self.spec.outbound_goal_target_rad)
        span=np.asarray(self.spec.outbound_goal_target_rad)-np.asarray(self.spec.start_return_target_rad)
        if phase is TaskPhase.RETURN:span=-span
        m=float(np.mean((target_q_rad-start)/span));e=np.sin(np.pi*np.clip(m,0,1))**2
        return native*(1+e*np.array([x[j+3]+x[j+4],x[j+3]-x[j+4]]))

    def decide(self,**kwargs):
        previous=self.previous_executed_delta_q_rad.copy()
        original=super().decide(**kwargs)
        x=np.asarray(getattr(self,'free_parameters',np.zeros(10)))
        phase=kwargs['phase']
        if phase is TaskPhase.HOLD or not np.any(x):return original
        target=np.asarray(original.executed.target_q_rad)
        if np.max(abs(target-self.reference_phase_goal(phase)))<=1e-10:return original
        start=np.asarray(self.spec.start_return_target_rad);span=np.asarray(self.spec.outbound_goal_target_rad)-start
        if phase is TaskPhase.RETURN:start,span=start+span,-span
        progress=(target-start)/span;m=float(progress.mean());e=np.sin(np.pi*np.clip(m,0,1))**2;j=0 if phase is TaskPhase.OUTBOUND else 5
        c=e*x[j];d=e*(x[j+1]+x[j+2]*(2*m-1));modified=progress+np.array([c+d,c-d])
        # Do not silently clip an infeasible proposal; retain native certified continuation.
        if np.any(modified<0) or np.any(modified>1):
            return replace(original,executed=replace(original.executed,execution_screen={**original.executed.execution_screen,'free_trajectory':dict(status='REJECTED',reason='NORMALIZED_TARGET_OUT_OF_RANGE',parameters=x)}))
        self.previous_executed_delta_q_rad=previous
        alt=self._evaluate(label='isolated_free_waypoint',state=np.asarray(kwargs['current_deployable_state']),reference_state=np.asarray(kwargs['current_reference_state']),phase=phase,phase_elapsed_s=kwargs['phase_elapsed_s'],phase_remaining_s=kwargs['phase_remaining_s'],action=start+span*modified-np.asarray(kwargs['current_deployable_state'])[:2],execution_feasibility_checker=kwargs.get('execution_feasibility_checker'),value_state_or_belief=kwargs.get('value_state_or_belief'),candidate_value_evaluator=kwargs.get('candidate_value_evaluator'))
        meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,parameters=x,original_target=target,proposed_target=start+span*modified,common_shift=c,differential_shift=d,continuous_realization='original certified quintic with independent boundary velocities',native_B_interface=False)
        chosen=alt if alt.feasible else original.executed
        chosen=replace(chosen,execution_screen={**chosen.execution_screen,'free_trajectory':meta})
        self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
        return replace(original,executed=chosen,selection_mode='isolated_free_waypoint_'+meta['status'],evaluations=original.evaluations+(chosen,))
