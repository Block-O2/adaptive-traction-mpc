"""One preregistered local terminal-reference factor, inside original checks."""
from dataclasses import replace
import numpy as np
from rich_planner import RichFreePlanner
from traction_mpc_stage5.task import TaskPhase

class FixedTerminalScheduler:
    def __init__(self, original, factor=1.5):
        self.original=original; self.factor=factor; self.record=None
    def __getattr__(self,name):return getattr(self.original,name)
    def plan_reference_contract(self,**kwargs):
        old=self.original.plan_reference_contract(**kwargs)
        dt=self.original.reference_period_s
        duration=np.ceil((old.duration_s*self.factor)/dt-1e-10)*dt
        new=self.original.plan_fixed_duration_reference_contract(**kwargs,duration_s=float(duration))
        self.record=dict(factor=self.factor,original_duration_s=old.duration_s,proposed_duration_s=new.duration_s,target_unchanged=bool(np.array_equal(old.candidate.q_waypoint_rad,new.candidate.q_waypoint_rad)),pass_velocity_unchanged=bool(np.array_equal(old.candidate.dq_waypoint_rad_s,new.candidate.dq_waypoint_rad_s)),source='original fixed-duration reference contract')
        return new

class TerminalRepairPlanner(RichFreePlanner):
    def decide(self,**kwargs):
        previous=self.previous_executed_delta_q_rad.copy()
        original=super().decide(**kwargs)
        if kwargs['phase'] is not TaskPhase.OUTBOUND:return original
        target=np.asarray(original.executed.target_q_rad)
        if np.max(abs(target-self.reference_phase_goal(kwargs['phase'])))>1e-10:return original
        native_scheduler=self.scheduler
        proxy=FixedTerminalScheduler(native_scheduler)
        self.previous_executed_delta_q_rad=previous
        self.scheduler=proxy
        try:
            alt=self._evaluate(label='terminal_duration_factor_1p5',state=np.asarray(kwargs['current_deployable_state']),reference_state=np.asarray(kwargs['current_reference_state']),phase=kwargs['phase'],phase_elapsed_s=kwargs['phase_elapsed_s'],phase_remaining_s=kwargs['phase_remaining_s'],action=target-np.asarray(kwargs['current_deployable_state'])[:2],execution_feasibility_checker=kwargs.get('execution_feasibility_checker'),value_state_or_belief=kwargs.get('value_state_or_belief'),candidate_value_evaluator=kwargs.get('candidate_value_evaluator'))
        finally:self.scheduler=native_scheduler
        meta=dict(status='ACCEPTED' if alt.feasible else 'REJECTED',reason=alt.rejection_reason,selected_original_label=original.executed.label,selected_original_target_rad=target,selected_original_duration_s=original.executed.schedule.duration_s,terminal_contract=proxy.record,truth_consumed=False)
        chosen=alt if alt.feasible else original.executed
        chosen=replace(chosen,execution_screen={**chosen.execution_screen,'terminal_duration_intervention':meta})
        self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
        return replace(original,executed=chosen,selection_mode='terminal_duration_'+meta['status'],evaluations=original.evaluations+(chosen,))
