"""Isolated RL candidate generator; all native scheduler/admission rules are inherited.

Action units are normalized progress per native planner event, not rad/s.
No B/H150 trajectory or candidate ranking is used to select the RL candidate.
"""
import numpy as np
from .terminal_reference import TerminalSetHumanWaypointPlannerV1
from ..task import TaskPhase


class NativeRateProposalPlanner(TerminalSetHumanWaypointPlannerV1):
    def set_rl_action(self, action, action_id, source_sample_s):
        a=np.asarray(action,dtype=float)
        if a.shape!=(2,) or not np.all(np.isfinite(a)) or np.any(np.abs(a)>1):
            raise ValueError('INVALID_RL_PROPOSAL_ACTION')
        self.rl_action=a.copy()
        self.rl_action_id=int(action_id)
        self.rl_source_sample_s=float(source_sample_s)

    def candidate_actions(self, current_q_rad, phase):
        current=np.asarray(current_q_rad,dtype=float)
        remaining=self.reference_phase_goal(phase)-current
        if phase is TaskPhase.HOLD:
            return (remaining.copy(),)  # Original mandatory HOLD; actor cannot skip it.
        fraction=(self.rl_action+1.)*.5
        permitted=self.span_rad*self.config.maximum_waypoint_step_fraction
        delta=np.sign(remaining)*np.minimum(np.abs(remaining),permitted*fraction)
        return (delta,)

    def _evaluate(self, **kwargs):
        kwargs['label']=f'rl_{self.rl_action_id:05d}_'+kwargs['label']
        return super()._evaluate(**kwargs)
