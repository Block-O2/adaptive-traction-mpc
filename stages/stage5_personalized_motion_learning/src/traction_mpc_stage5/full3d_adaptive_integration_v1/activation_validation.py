"""Current deployable-model certificate reuse and sensor-supported dwell."""
from dataclasses import replace
import numpy as np
from ..architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from ..task import (TaskPhase, at_goal, abort_episode, transition_phase,
                    task_limit_violation, phase_timed_out)


def reference_safe_task_transition(spec, previous, proposed, physical_dt,
                                   reference_ready, *, continuous_hold=False):
    """Defer phase handoff without inventing dwell or extending its deadline."""
    if proposed.phase is TaskPhase.ABORTED:
        return proposed
    elapsed = previous.phase_elapsed_s + physical_dt
    if (continuous_hold and previous.phase is TaskPhase.HOLD
            and elapsed > spec.phase_timeout_s + 1e-12):
        return abort_episode(replace(previous, phase_elapsed_s=elapsed), "TIMEOUT_HOLD")
    guarded = previous.phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN) or (
        continuous_hold and previous.phase is TaskPhase.HOLD)
    if proposed.phase is previous.phase or not guarded or reference_ready:
        return proposed
    # RETURN is proposed only after the causal task clock proves the original
    # uninterrupted dwell. It clears its counter for RETURN; keep exactly the
    # proven threshold while awaiting a continuous stationary reference boundary.
    deferred = replace(previous, phase_elapsed_s=elapsed,
        hold_elapsed_s=(spec.hold_duration_s if previous.phase is TaskPhase.HOLD
                        and proposed.phase is TaskPhase.RETURN else 0.0))
    if phase_timed_out(spec, deferred):
        return abort_episode(deferred, "TIMEOUT_" + previous.phase.value)
    return deferred


def causal_return_projection(spec, state, fast_acceleration, slow_acceleration, *,
                             fast_valid, slow_valid, aligned, source_age_s,
                             horizon_s, target_rad=None):
    """Observed-acceleration return guard, not a certified physical bound.

    The triangle envelope covers every time in [0,h] IF future acceleration is
    bounded by the observed proxy. Source age consumes this same capture-anchored
    horizon; it is never added by renewing the observation timestamp.
    """
    x = np.asarray(state, dtype=float)
    target = np.asarray(spec.start_return_target_rad if target_rad is None else target_rad, dtype=float)
    fast, slow = np.asarray(fast_acceleration), np.asarray(slow_acceleration)
    finite = bool(x.shape == (4,) and fast.shape == slow.shape == target.shape == (2,)
                  and np.all(np.isfinite(np.r_[x, fast, slow, target])))
    valid = bool(finite and fast_valid and slow_valid and aligned
                 and np.isfinite(source_age_s) and 0 <= source_age_s <= horizon_s
                 and np.isfinite(horizon_s) and horizon_s > 0.)
    record = {"scope": "causal observed-acceleration proxy; no physical invariance guarantee",
        "fast_valid": bool(fast_valid), "slow_valid": bool(slow_valid),
        "aligned": bool(aligned), "finite": finite,
        "source_age_at_decision_s": float(source_age_s) if np.isfinite(source_age_s) else None,
        "capture_anchored_horizon_s": float(horizon_s) if np.isfinite(horizon_s) else None, "ready": False,
        "future_acceleration_bound_proven": False}
    if not valid:
        record["reason"] = "MISSING_OR_STALE_ALIGNED_CAUSAL_HISTORY"
        return record
    bound = np.maximum(np.abs(fast), np.abs(slow))
    excursion = np.abs(x[2:])*horizon_s + .5*bound*horizon_s**2
    position_error = np.abs(x[:2]-target) + excursion
    velocity = np.abs(x[2:]) + bound*horizon_s
    bounds = np.asarray(spec.q_bounds_rad)
    record.update(state=x.copy(), fast_acceleration_rad_s2=fast.copy(),
        slow_acceleration_rad_s2=slow.copy(), observed_acceleration_proxy_rad_s2=bound,
        predicted_position_error_bound_rad=position_error,
        predicted_absolute_velocity_bound_rad_s=velocity,
        ready=bool(np.all(position_error <= np.asarray(spec.joint_angle_completion_tolerance_rad))
                   and np.all(velocity <= np.asarray(spec.joint_velocity_completion_tolerance_rad_s))
                   and np.all(x[:2]-excursion >= bounds[:,0])
                   and np.all(x[:2]+excursion <= bounds[:,1])))
    record["reason"] = "PROJECTION_INSIDE_ORIGINAL_RETURN_SET" if record["ready"] else "CONTINUE_RETURN_SETTLING"
    return record


def return_finalization_reason(*, physical_age, host_age, horizon_s,
                               return_elapsed_s, phase_timeout_s,
                               task_elapsed_s, task_timeout_s):
    """Commit only within the capture horizon and original physical deadlines."""
    if not np.all(np.isfinite([physical_age, host_age, horizon_s, return_elapsed_s,
                               phase_timeout_s, task_elapsed_s, task_timeout_s])):
        return "INVALID_TERMINAL_RETURN_TIMING"
    if task_elapsed_s > task_timeout_s + 1e-12:
        return "GLOBAL_TASK_TIMEOUT"
    if return_elapsed_s > phase_timeout_s + 1e-12:
        return "TIMEOUT_RETURN"
    if min(physical_age, host_age) < 0 or max(physical_age, host_age) > horizon_s + 1e-12:
        return "TERMINAL_RETURN_PROJECTION_HORIZON_EXCEEDED"
    return None


def validate_activation(*, belief, request_sequence, schedule, clearance,
                        phase, request_phase, remaining_s, reference_state, now_physics_s=0.):
    first = schedule.sample(0.)
    continuity = bool(np.max(np.abs(np.r_[first.q_rad, first.dq_rad_s]-reference_state)) <= 1e-10
                      and np.max(np.abs(first.ddq_rad_s2)) <= 1e-10)
    mechanics = AdaptiveMechanicsScreenV22().evaluate(belief, schedule.candidate, schedule)
    lower = float(clearance.certified_minimum(schedule.coefficients, schedule.duration_s))
    record = {"request_model_sequence": request_sequence, "activation_model_sequence": belief.sequence,
              "request_phase": request_phase.value, "activation_phase": phase.value,
              "phase_deadline_physics_s": now_physics_s+remaining_s,
              "remaining_phase_time_s": remaining_s, "schedule_duration_s": schedule.duration_s,
              "reference_continuity": continuity, "current_model_mechanics": mechanics,
              "current_geometry_continuous_lower_m": lower,
              "current_geometry_certificate":getattr(clearance,"last_certificate",None), "truth_consumed": False}
    record["feasible"] = bool(phase is request_phase and schedule.duration_s <= remaining_s+1e-12
                              and continuity and mechanics["feasible"] and lower >= 0.)
    return record


def projected_dwell_sample(spec, row):
    """Stricter causal dwell admission; neither truth nor an error certificate."""
    x = np.asarray(row.get('estimated_state', []), dtype=float)
    original = bool(x.shape == (4,) and np.all(np.isfinite(x)) and
                    at_goal(spec, x[:2], x[2:], spec.outbound_goal_target_rad))
    stamp = row.get('sample_time_s', float('nan'))
    motion_stamp = row.get('motion_source_sample_s', float('nan'))
    proxy = causal_return_projection(spec, x,
        row.get('fast_motion_acceleration_rad_s2', [float('nan')]*2),
        row.get('human_motion_acceleration_rad_s2', [float('nan')]*2),
        fast_valid=row.get('fast_motion_valid', False),
        slow_valid=row.get('human_motion_valid', False),
        aligned=bool(np.isfinite(stamp) and np.isfinite(motion_stamp) and abs(stamp-motion_stamp)<=1e-12),
        source_age_s=0., horizon_s=.010, target_rad=spec.outbound_goal_target_rad)
    proxy['reason'] = 'DWELL_PROXY_INSIDE_ORIGINAL_OUTBOUND_SET' if proxy['ready'] else 'CONTINUE_HOLD_SETTLING'
    proxy['target_rad'] = np.asarray(spec.outbound_goal_target_rad).copy()
    return bool(original and proxy['ready']), {'original_at_goal': original, 'dwell_projection': proxy}


class SensorSupportedTaskClock:
    """Dwell uses two consecutive valid captured samples, never missed time.

    This supplies a sampling-level guarantee only. Inter-sample true-state and
    estimation-error acceptance remain independently scored, never truth-gated.
    """
    def __init__(self, projected_dwell=False):
        if not isinstance(projected_dwell, bool):
            raise ValueError('projected dwell must be boolean')
        self.projected_dwell = projected_dwell
        self.hold_entry_physics_s = None
        self.previous_sample_s = None
        self.previous_valid = False
        self.evidence = []
        self.arrival_evidence = []

    def transition(self, spec, state, q, dq, physical_dt, sample_time_s, captured_samples=None,
                   physical_time_s=None, **kwargs):
        valid = at_goal(spec, q, dq, spec.outbound_goal_target_rad)
        current_alignment = True
        arrival_admission = None
        if self.projected_dwell:
            if physical_time_s is None or not np.isfinite(physical_time_s) or physical_time_s < sample_time_s-1e-10:
                raise ValueError('projected dwell requires actual causal physical boundary')
            latest = [r for r in (captured_samples or []) if abs(r['sample_time_s']-sample_time_s)<=1e-12]
            current_alignment = bool(latest and np.array_equal(np.asarray(latest[-1]['estimated_state']), np.r_[q,dq]))
            valid, arrival_admission = (projected_dwell_sample(spec, latest[-1])
                                        if current_alignment else (False, None))
        delta = None if self.previous_sample_s is None else sample_time_s-self.previous_sample_s
        continuous = bool(self.previous_valid and valid and delta is not None and 0 < delta <= .005+1e-10)
        if delta is not None and delta < -1e-10:
            raise ValueError("sensor task clock moved backwards")
        if state.phase is TaskPhase.HOLD:
            if self.projected_dwell and self.hold_entry_physics_s is None:
                self.hold_entry_physics_s = physical_time_s-state.phase_elapsed_s
            violation = kwargs.get("abort_reason") or task_limit_violation(
                spec, q, dq, kwargs.get("ddq_rad_s2"),
                acceleration_authority_valid=kwargs.get("acceleration_authority_valid", True))
            if violation:
                result = abort_episode(state, violation)
            else:
                dwell = state.hold_elapsed_s
                rows = [] if captured_samples is None else [r for r in captured_samples
                    if (self.previous_sample_s is None or r["sample_time_s"] > self.previous_sample_s+1e-10)
                    and r["sample_time_s"] <= sample_time_s+1e-10]
                if self.projected_dwell and not current_alignment:
                    rows = []
                if rows:
                    for row in rows:
                        t = float(row["sample_time_s"])
                        x = np.asarray(row["estimated_state"])
                        row_valid = at_goal(spec, x[:2], x[2:], spec.outbound_goal_target_rad)
                        admission = {}
                        if self.projected_dwell:
                            row_valid, admission = projected_dwell_sample(spec, row)
                            row_valid = row_valid and t >= self.hold_entry_physics_s-1e-12
                        row_dt = None if self.previous_sample_s is None else t-self.previous_sample_s
                        row_contiguous = bool(self.previous_valid and row_valid and row_dt is not None
                                              and 0 < row_dt <= .005+1e-10)
                        credit = row_dt if row_contiguous else 0.
                        if self.projected_dwell and row_contiguous:
                            credit = max(0., t-max(self.previous_sample_s,self.hold_entry_physics_s))
                        dwell = dwell+credit if row_contiguous else 0.
                        self.evidence.append({"sample_time_s":t,"previous_sample_s":self.previous_sample_s,
                            "valid":row_valid,"two_valid_contiguous_samples":row_contiguous,
                            "credited_s":credit,"source":"actual fixed-grid causal capture",
                            **admission, 'hold_entry_physics_s':self.hold_entry_physics_s})
                        self.previous_sample_s, self.previous_valid = t, row_valid
                else:
                    dwell = dwell if delta == 0 and valid else (dwell+delta if continuous else 0.)
                    if self.projected_dwell:
                        self.evidence.append({'sample_time_s':sample_time_s,'previous_sample_s':self.previous_sample_s,
                            'valid':valid,'current_sample_alignment':current_alignment,
                            'two_valid_contiguous_samples':continuous,'credited_s':0.,
                            'reason':'DUPLICATE_CAPTURE' if delta==0 and valid else 'MISSING_OR_MISMATCHED_CAUSAL_CAPTURE',
                            'hold_entry_physics_s':self.hold_entry_physics_s})
                result = replace(state, phase_elapsed_s=state.phase_elapsed_s+physical_dt, hold_elapsed_s=dwell)
                if dwell+1e-12 >= spec.hold_duration_s:
                    result = replace(result, phase=TaskPhase.RETURN, phase_elapsed_s=0.,
                                     hold_elapsed_s=0., outbound_hold_completed=True)
                elif phase_timed_out(spec, result):
                    result = abort_episode(result, "TIMEOUT_HOLD")
            if not captured_samples:
                self.evidence.append({"sample_time_s": sample_time_s, "previous_sample_s": self.previous_sample_s,
                                  "valid": valid, "two_valid_contiguous_samples": continuous,
                                  "credited_s": delta if continuous else 0.})
        elif physical_dt > 0:
            result = transition_phase(spec, state, q, dq, physical_dt, **kwargs)
            if self.projected_dwell and state.phase is TaskPhase.OUTBOUND:
                original_arrival = result.phase is TaskPhase.HOLD
                if original_arrival and not valid:
                    # The existing causal 10 ms dwell projection also guards
                    # arrival. Keep the original task clock and timeout while
                    # waiting for a sensor-supported settled endpoint.
                    deferred = replace(state, phase_elapsed_s=state.phase_elapsed_s+physical_dt)
                    result = (abort_episode(deferred, "TIMEOUT_OUTBOUND")
                              if phase_timed_out(spec, deferred) else deferred)
                self.arrival_evidence.append({
                    'sample_time_s': sample_time_s,
                    'physical_time_s': physical_time_s,
                    'original_arrival': original_arrival,
                    'causal_arrival_ready': bool(valid),
                    'current_sample_alignment': current_alignment,
                    'clock_result_phase': result.phase.value,
                    'admission': arrival_admission,
                })
        elif kwargs.get("abort_reason"):
            result = abort_episode(state, kwargs["abort_reason"])
        else:
            result = state
        if delta != 0:
            self.previous_sample_s = sample_time_s
            self.previous_valid = valid
        elif self.projected_dwell and not valid:
            # Rejected duplicate evidence also invalidates this interval endpoint.
            self.previous_valid = False
        if self.projected_dwell and state.phase is not TaskPhase.HOLD and result.phase is TaskPhase.HOLD:
            self.hold_entry_physics_s = physical_time_s
            # Both credited endpoints must be captured after actual HOLD entry.
            self.previous_valid = False
        return result
