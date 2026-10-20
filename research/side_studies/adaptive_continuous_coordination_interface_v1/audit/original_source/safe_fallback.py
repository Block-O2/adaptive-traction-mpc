"""Prevalidated zero-acceleration bridge fork; no planner or plant at commit.

The selected primary, ranking and candidate set are unchanged. An admission
certificate is attached in the worker before a moving endpoint can execute.
Certificates have the same deployable-model scope as the existing scheduler.
"""
from dataclasses import dataclass, fields, replace
import math
import numpy as np
from ..human_waypoint_scheduler import QuinticHumanWaypointSchedule
from ..architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from .activation_validation import clearance_geometry_signature


@dataclass(frozen=True)
class EscapeBundle:
    bridge: QuinticHumanWaypointSchedule
    stop: QuinticHumanWaypointSchedule
    commit_progress_s: float
    certificate: dict


@dataclass(frozen=True)
class PreparedWaypointSchedule(QuinticHumanWaypointSchedule):
    safe_escape: EscapeBundle | None = None


def braking_duration(velocity, acceleration_limits, grid_s):
    v, a = np.asarray(velocity), np.asarray(acceleration_limits)
    if v.shape != (2,) or a.shape != (2,) or not np.all(np.isfinite(np.r_[v,a,grid_s])) or np.any(a<=0) or grid_s<=0:
        raise ValueError('invalid braking limits')
    return max(grid_s, math.ceil((1.5*float(np.max(np.abs(v)/a))-1e-12)/grid_s)*grid_s)


def prepare_decision(decision, planner, belief):
    """Attach an escape to the already selected action; never rerank/search MPC."""
    primary = decision.executed.schedule
    endpoint = primary.sample(primary.duration_s)
    if not np.any(np.abs(endpoint.dq_rad_s)>1e-12):
        return decision
    if np.max(np.abs(endpoint.ddq_rad_s2))>1e-10:
        raise ValueError('SAFE_FALLBACK_NONZERO_ENDPOINT_ACCELERATION')
    scheduler = planner.scheduler
    dt = scheduler.reference_period_s
    bridge_duration = 8*dt  # Existing RSS bridge, unchanged.
    make = lambda label,q,v: replace(primary.candidate,label=label,q_waypoint_rad=q,dq_waypoint_rad_s=v)
    v = endpoint.dq_rad_s
    candidate = make('safe_fallback_bridge',endpoint.q_rad+bridge_duration*v,v)
    bridge = scheduler.plan_fixed_duration_reference_contract(
        current_q_hat_rad=endpoint.q_rad,current_dq_hat_rad_s=v,candidate=candidate,
        duration_s=bridge_duration,phase_elapsed_s=decision.phase_elapsed_s+primary.duration_s)
    screen = AdaptiveMechanicsScreenV22()
    bridge_check = screen.evaluate(belief,candidate,bridge)
    if not bridge_check['feasible']:
        raise ValueError('SAFE_FALLBACK_BRIDGE_MECHANICS')
    limits = np.asarray(scheduler.spec.task_joint_acceleration_limit_rad_s2)*scheduler.reference_acceleration_fraction
    duration = braking_duration(v,limits,dt)
    offset = np.asarray(decision.executed.execution_screen['causal_tracking_offset_clearance']['position_error_rad'])
    attempts=[]
    for index in range(7,-1,-1):
        commit = index*dt
        start = bridge.sample(commit)
        stop_candidate = make('safe_fallback_stop',start.q_rad+.5*duration*v,np.zeros(2))
        try:
            stop = scheduler.plan_fixed_duration_reference_contract(
                current_q_hat_rad=start.q_rad,current_dq_hat_rad_s=start.dq_rad_s,
                candidate=stop_candidate,duration_s=duration,
                phase_elapsed_s=decision.phase_elapsed_s+primary.duration_s+commit)
            mechanics=screen.evaluate(belief,stop_candidate,stop)
            shifted=stop.coefficients.copy();shifted[:,0]+=offset
            clearance=scheduler.clearance_evaluator
            lower=float(clearance.certified_minimum(shifted,duration))
            qbounds=np.asarray(scheduler.spec.q_bounds_rad)
            shifted_ends=np.vstack([start.q_rad+offset,stop_candidate.q_waypoint_rad+offset])
            hard=np.column_stack([scheduler.human_model.q_min_rad,scheduler.human_model.q_max_rad])
            rom=bool(np.all(shifted_ends>=qbounds[:,0]) and np.all(shifted_ends<=qbounds[:,1]) and np.all(shifted_ends>=hard[:,0]) and np.all(shifted_ends<=hard[:,1]))
            if not mechanics['feasible'] or lower<0 or not rom:
                raise ValueError('SAFE_FALLBACK_SHIFTED_PATH_OR_MECHANICS')
            certificate=dict(scope='existing deployable reference geometry and sampled mechanics; not physical invariance',
                belief_sequence=belief.sequence,geometry_signature=clearance_geometry_signature(clearance),
                bridge_mechanics=bridge_check,stop_mechanics=mechanics,shifted_lower_m=lower,
                shifted_rom_valid=rom,position_offset_rad=offset.tolist(),braking_duration_s=duration,
                commit_progress_s=commit,commit_rule='latest certified 5ms bridge grid node strictly before original endpoint',
                normal_bridge_duration_s=bridge_duration,truth_consumed=False,earlier_rejections=attempts)
            escape=EscapeBundle(bridge,stop,commit,certificate)
            prepared=PreparedWaypointSchedule(**{f.name:getattr(primary,f.name) for f in fields(QuinticHumanWaypointSchedule)},safe_escape=escape)
            executed=replace(decision.executed,schedule=prepared)
            return replace(decision,executed=executed,
                greedy=executed if decision.greedy is decision.executed else decision.greedy,
                evaluations=tuple(executed if x is decision.executed else x for x in decision.evaluations))
        except (ValueError,RuntimeError) as error:
            attempts.append(dict(commit_progress_s=commit,reason=str(error)))
    raise ValueError('SAFE_FALLBACK_ARCHITECTURE_NOT_JUSTIFIED:'+str(attempts))


class FallbackLatch:
    """One-way choice. Late output cannot turn BRAKING or HOLD into PRIMARY."""
    def __init__(self, bundle):
        self.bundle=bundle
        self.mode='ARMED'

    def cap(self, desired):
        return min(float(desired),self.bundle.commit_progress_s) if self.mode=='ARMED' else float(desired)

    def choose_primary(self, *, validated, age_ns):
        if self.mode!='ARMED' or not validated or not 0<=age_ns<100_000_000:
            return False
        self.mode='PRIMARY'
        return True

    def commit(self):
        if self.mode=='ARMED':self.mode='BRAKING'
        return self.mode=='BRAKING'

    def stopped(self):
        if self.mode!='BRAKING':raise RuntimeError('fallback stop out of order')
        self.mode='SAFE_FALLBACK_HOLD'

    def resume(self, *, fresh, validated, age_ns):
        if self.mode!='SAFE_FALLBACK_HOLD' or not fresh or not validated or not 0<=age_ns<100_000_000:
            return False
        self.mode='RESUMED'
        return True
