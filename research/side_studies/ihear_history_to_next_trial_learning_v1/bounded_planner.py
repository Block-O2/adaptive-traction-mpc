"""Isolated, bounded middle-knee intent on native B; original certification owns admission."""
from dataclasses import replace
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.coordination_residual_v2 import NativeResidualPlannerV2
from round_planner import FixedDuration

class HistoryPosturePlanner(NativeResidualPlannerV2):
    def _waypoint_terminal_velocity(self, **kw):
        forced=getattr(self,'history_forced_velocity',None)
        return forced.copy() if forced is not None else super()._waypoint_terminal_velocity(**kw)

    def decide(self, **kw):
        previous=self.previous_executed_delta_q_rad.copy()
        original=super().decide(**kw)
        intent=getattr(self,'history_posture_intent',None)
        if intent is None or float(intent['knee_delta_deg'])==0.: return original
        phase=kw['phase'].value
        assert (phase,int(intent['slot'])) in [('OUTBOUND',1),('RETURN',3)]
        delta=float(intent['knee_delta_deg'])
        assert np.isfinite(delta) and abs(delta)<=.3+1e-12
        target=np.asarray(original.executed.target_q_rad)
        old=original.executed.schedule
        meta=dict(schema='history_bounded_knee_v1',phase=phase,slot=int(intent['slot']),
            knee_delta_deg=delta,parent='native_B_current_selected_waypoint',
            original_target_rad=target,proposed_target_rad=target+np.radians([0.,delta]),
            original_duration_s=old.duration_s,unchanged_pass_velocity_rad_s=old.candidate.dq_waypoint_rad_s.copy(),
            history_sha256=intent.get('history_sha256'),action_hash=intent['action_hash'],truth_consumed=False)
        if np.max(abs(target-self.reference_phase_goal(kw['phase'])))<=1e-10:
            meta.update(status='REJECTED',reason='MIDDLE_ACTION_NOT_SUPPORTED_AT_ENDPOINT')
            chosen=replace(original.executed,execution_screen={**original.executed.execution_screen,'history_posture':meta})
            return replace(original,executed=chosen,selection_mode='history_posture_REJECTED')
        self.previous_executed_delta_q_rad=previous
        native=self.scheduler;self.scheduler=FixedDuration(native,old.duration_s)
        self.history_forced_velocity=old.candidate.dq_waypoint_rad_s.copy()
        try:
            alt=self._evaluate(label='history_bounded_knee_v1',state=np.asarray(kw['current_deployable_state']),
                reference_state=np.asarray(kw['current_reference_state']),phase=kw['phase'],
                phase_elapsed_s=kw['phase_elapsed_s'],phase_remaining_s=kw['phase_remaining_s'],
                action=target+np.radians([0.,delta])-np.asarray(kw['current_deployable_state'])[:2],
                execution_feasibility_checker=kw.get('execution_feasibility_checker'),
                value_state_or_belief=kw.get('value_state_or_belief'),candidate_value_evaluator=kw.get('candidate_value_evaluator'))
        finally:self.scheduler=native;self.history_forced_velocity=None
        chosen=alt if alt.feasible else original.executed
        meta.update(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason)
        if alt.feasible:
            assert abs(chosen.schedule.duration_s-old.duration_s)<1e-12
            assert np.max(abs(chosen.schedule.candidate.dq_waypoint_rad_s-old.candidate.dq_waypoint_rad_s))<1e-12
            assert abs(chosen.target_q_rad[0]-target[0])<1e-12
        chosen=replace(chosen,execution_screen={**chosen.execution_screen,'history_posture':meta})
        self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
        return replace(original,executed=chosen,selection_mode='history_posture_'+meta['status'],evaluations=original.evaluations+(chosen,))
