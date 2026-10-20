"""Exploration-only action adapter; existing planner, scheduler, and screens remain authoritative."""
from __future__ import annotations
from dataclasses import replace
import json, os, pickle
from copy import copy
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import TerminalSetHumanWaypointPlannerV1
from traction_mpc_stage5.task import TaskPhase

SPEC_ENV='SAFE_ACTION_HORIZON_EXPLORATION_SPEC_V1'
WEIGHTS={'H1':(.999999,), 'H2':(.65,1.0,.65), 'H3':(.5,.8,1.0,1.0,.8,.5), 'H4':(.5,.8,1.0,1.0,.8,.5)}
AMPLITUDE={'very_small':.125,'small':.25,'fine_low':.35,'medium':.5,'fine_mid':.65,'fine_high':.85,'large':1.0}

def factors(direction,scale):
    if direction=='slower': return np.array([1-.7*scale,1-.7*scale])
    if direction=='faster': return np.array([1+.8*scale,1+.8*scale])
    if direction=='hip_leading': return np.array([1+.8*scale,1-.8*scale])
    if direction=='knee_leading': return np.array([1-.8*scale,1+.8*scale])
    if direction=='hip_dominant': return np.array([1+scale,1-.95*scale])
    if direction=='knee_dominant': return np.array([1-.95*scale,1+scale])
    raise ValueError(f'unknown exploration direction {direction}')

class ExplorationTerminalSetPlannerV1(TerminalSetHumanWaypointPlannerV1):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        raw=os.environ.get(SPEC_ENV)
        if raw is None: raise RuntimeError('exploration planner has no frozen action specification')
        self.exploration_spec=json.loads(raw)
        spec=self.exploration_spec
        if spec['direction'] not in ('slower','faster','hip_leading','knee_leading','hip_dominant','knee_dominant') or spec['amplitude'] not in AMPLITUDE or spec['horizon'] not in WEIGHTS:
            raise ValueError('invalid exploration specification')

    def decide(self,**kwargs):
        baseline=super().decide(**kwargs)
        spec=self.exploration_spec
        phase=kwargs['phase']
        if phase is TaskPhase.HOLD or (phase is TaskPhase.RETURN and spec['horizon']!='H4'):
            return baseline
        index=getattr(self,"exploration_phase_index",sum(d.phase is phase for d in self.decisions)-1)
        weights=WEIGHTS[spec['horizon']]
        if index>=len(weights) or (phase is TaskPhase.OUTBOUND and spec['horizon'] in ('H1','H2') and index>=len(weights)):
            return baseline
        effective_scale=AMPLITUDE[spec['amplitude']]*weights[index]
        base=baseline.executed.proposed_delta_q_rad
        state=np.asarray(kwargs['current_deployable_state'],dtype=float)
        reference=np.asarray(kwargs['current_reference_state'],dtype=float)
        remaining=self.reference_phase_goal(phase)-state[:2]
        multipliers=factors(spec['direction'],effective_scale)
        # The 2x generator-step limit bounds this research grid only. It is not
        # a safety gate: the unchanged scheduler, clearance, mechanics, and
        # controller must still certify every proposed path.
        magnitude=np.minimum.reduce((np.abs(base)*multipliers,np.abs(remaining),
                         2*self.config.maximum_waypoint_step_fraction*self.span_rad))
        action=np.sign(base)*magnitude
        if np.allclose(action,base,rtol=0,atol=1e-12): return baseline
        alternative=self._evaluate(label=f"explore_{spec['direction']}_{spec['amplitude']}_{spec['horizon']}_{phase.value.lower()}_{index:02d}",state=state,reference_state=reference,phase=phase,phase_elapsed_s=kwargs['phase_elapsed_s'],phase_remaining_s=kwargs['phase_remaining_s'],action=action,execution_feasibility_checker=kwargs.get('execution_feasibility_checker'),value_state_or_belief=kwargs.get('value_state_or_belief'),candidate_value_evaluator=kwargs.get('candidate_value_evaluator'))
        if not alternative.feasible:
            raise ValueError('EXPLORATION_ACTION_INFEASIBLE:'+str(alternative.rejection_reason))
        chosen=replace(baseline,executed=alternative,selection_mode='safe_action_horizon_counterfactual',evaluations=baseline.evaluations+(alternative,))
        self.decisions[-1]=chosen
        self.previous_executed_delta_q_rad=action.copy()
        return chosen


def snapshot_exploration_task_call(adaptive_planner, arguments):
    """Preserve only a phase-local index; never serialize growing decision history."""
    snapshot=copy(adaptive_planner)
    snapshot.planner=copy(adaptive_planner.planner)
    snapshot.planner.exploration_phase_index=sum(
        decision.phase is arguments['phase'] for decision in adaptive_planner.planner.decisions)
    snapshot.planner.decisions=[]
    snapshot.belief_sequences_used=[]
    return pickle.dumps((snapshot,arguments),protocol=pickle.HIGHEST_PROTOCOL)
