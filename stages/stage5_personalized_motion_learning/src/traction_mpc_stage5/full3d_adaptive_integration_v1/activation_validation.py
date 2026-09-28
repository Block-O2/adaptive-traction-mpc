"""Current deployable-model certificate reuse and sensor-supported dwell."""
from dataclasses import replace
import hashlib
import numpy as np
from ..architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from ..human_waypoint_scheduler import _quintic_coefficients
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


def clearance_geometry_signature(clearance):
    """Complete numeric input key for the frozen combined path certificate."""
    envelope = clearance.envelope
    shank = clearance.shank_contract
    geometry = envelope.geometry
    numeric = [
        *np.asarray(geometry.origin_world_m).ravel(),
        *np.asarray(geometry.plane_x_world).ravel(),
        *np.asarray(geometry.joint_axis_world).ravel(),
        *np.asarray(geometry.plane_z_world).ravel(),
        *np.asarray(geometry.hip_plane_m).ravel(),
        geometry.thigh_length_m,
        *np.asarray(geometry.knee_to_cuff_in_cuff_m).ravel(),
        envelope.shank_length_upper_m, envelope.existing_shank_margin_m,
        envelope.registered_proximal_installation_gap_lower_m,
        envelope.sample_count,
        *np.asarray(envelope.cuff_reference_translation_world_m).ravel(),
        shank.shank_length_upper_m, shank.margin_m,
        float(clearance.use_monotonic_certificate),
    ]
    digest = hashlib.sha256(b"combined_rigid_table_clearance_v1/monotonic_v2")
    digest.update(np.asarray(numeric, dtype="<f8").tobytes())
    return digest.hexdigest()


def certified_original_schedule_lower(schedule, clearance, request_geometry_signature):
    """Reuse only the certificate bound to this immutable schedule and geometry.

    The scheduler constructs coefficients and certificate together. Rebuilding
    coefficients verifies that no schedule state was changed after selection.
    A different geometry or missing proof takes the original computation path.
    """
    proof = schedule.continuous_clearance_certificate
    if (request_geometry_signature is not None and proof is not None
            and clearance_geometry_signature(clearance) == request_geometry_signature
            and schedule.candidate.phase is not TaskPhase.HOLD):
        rebuilt = _quintic_coefficients(
            schedule.start_q_rad, schedule.start_dq_rad_s,
            schedule.candidate.q_waypoint_rad,
            schedule.candidate.dq_waypoint_rad_s,
            schedule.duration_s)
        lowers = proof.get("combined_body_lowers_m")
        if (np.array_equal(rebuilt, schedule.coefficients)
                and isinstance(lowers, dict) and lowers
                and all(np.isfinite(v) for v in lowers.values())):
            return float(min(lowers.values())), proof, True
    lower = float(clearance.certified_minimum(schedule.coefficients, schedule.duration_s))
    return lower, getattr(clearance, "last_certificate", None), False


def validate_activation(*, belief, request_sequence, schedule, clearance,
                        phase, request_phase, remaining_s, reference_state, now_physics_s=0.,
                        future_handoff=None, certificate_geometry_at_request=None):
    first = schedule.sample(0.)
    continuity = bool(np.max(np.abs(np.r_[first.q_rad, first.dq_rad_s]-reference_state)) <= 1e-10
                      and np.max(np.abs(first.ddq_rad_s2)) <= 1e-10)
    mechanics = AdaptiveMechanicsScreenV22().evaluate(belief, schedule.candidate, schedule)
    lower, original_certificate, reused_certificate = certified_original_schedule_lower(
        schedule, clearance, certificate_geometry_at_request)
    record = {"request_model_sequence": request_sequence, "activation_model_sequence": belief.sequence,
              "request_phase": request_phase.value, "activation_phase": phase.value,
              "phase_deadline_physics_s": now_physics_s+remaining_s,
              "remaining_phase_time_s": remaining_s, "schedule_duration_s": schedule.duration_s,
              "reference_continuity": continuity, "current_model_mechanics": mechanics,
              "current_geometry_continuous_lower_m": lower,
              "current_geometry_certificate":original_certificate,
              "original_geometry_certificate_reused":reused_certificate,
              "truth_consumed": False}
    record["feasible"] = bool(phase is request_phase and schedule.duration_s <= remaining_s+1e-12
                              and continuity and mechanics["feasible"] and lower >= 0.)
    escape = getattr(schedule, "safe_escape", None)
    if escape is not None:
        bridge_mechanics = AdaptiveMechanicsScreenV22().evaluate(belief, escape.bridge.candidate, escape.bridge)
        stop_mechanics = AdaptiveMechanicsScreenV22().evaluate(belief, escape.stop.candidate, escape.stop)
        geometry_valid = clearance_geometry_signature(clearance) == escape.certificate["geometry_signature"]
        reserve = schedule.duration_s + escape.commit_progress_s + escape.stop.duration_s
        escape_valid = bool(geometry_valid and bridge_mechanics["feasible"] and stop_mechanics["feasible"]
                            and reserve <= remaining_s+1e-12)
        record["safe_escape"] = dict(feasible=escape_valid, geometry_valid=geometry_valid,
            bridge_mechanics=bridge_mechanics, stop_mechanics=stop_mechanics, stop_horizon_s=reserve)
        record["feasible"] = record["feasible"] and escape_valid
    if future_handoff is not None:
        # Revalidate a speculative endpoint plan against a *new* deployable
        # observation. Neither the original request capture nor its age is
        # replaced by the revalidation sample in PlanLifecycle.
        spec = future_handoff["spec"]
        observed = np.asarray(future_handoff["estimated_state"], dtype=float)
        observed_ddq = np.asarray(future_handoff["estimated_acceleration"], dtype=float)
        reference_ddq = np.asarray(future_handoff["reference_acceleration"], dtype=float)
        now_ns = int(future_handoff["now_ns"])
        original_ns = int(future_handoff["original_capture_ns"])
        revalidation_ns = int(future_handoff["revalidation_capture_ns"])
        finite = bool(observed.shape == (4,) and observed_ddq.shape == (2,)
                      and reference_ddq.shape == (2,)
                      and np.all(np.isfinite(np.r_[observed, observed_ddq, reference_ddq])))
        observed_reference = np.asarray(
            future_handoff.get("observed_reference_state", reference_state), dtype=float)
        finite = bool(finite and observed_reference.shape == (4,)
                      and np.all(np.isfinite(observed_reference)))
        q_error = observed[:2]-observed_reference[:2] if finite else np.full(2, np.nan)
        dq_error = observed[2:]-observed_reference[2:] if finite else np.full(2, np.nan)
        model = belief.human_model()
        q_bounds = np.asarray(spec.q_bounds_rad)
        hard_bounds = np.column_stack([model.q_min_rad, model.q_max_rad])
        velocity_limit = np.asarray(spec.task_joint_velocity_limit_rad_s)
        acceleration_limit = np.asarray(spec.task_joint_acceleration_limit_rad_s2)
        state_rom = bool(finite and np.all(observed[:2] >= q_bounds[:, 0])
                         and np.all(observed[:2] <= q_bounds[:, 1])
                         and np.all(observed[:2] >= hard_bounds[:, 0])
                         and np.all(observed[:2] <= hard_bounds[:, 1]))
        state_motion = bool(finite and future_handoff["acceleration_valid"]
                            and np.all(np.abs(observed[2:]) <= velocity_limit+1e-12)
                            and np.all(np.abs(observed_ddq) <= acceleration_limit+1e-12)
                            and np.all(schedule.maximum_reference_velocity_rad_s+np.abs(dq_error)
                                       <= velocity_limit+1e-12)
                            and np.all(schedule.maximum_reference_acceleration_rad_s2
                                       +np.abs(observed_ddq-reference_ddq)
                                       <= acceleration_limit+1e-12))
        live_c2 = bool(continuity and np.max(np.abs(first.ddq_rad_s2-reference_ddq)) <= 1e-10)
        shifted_lower = float("-inf")
        shifted_rom = False
        current_clearance = float("-inf")
        if finite:
            shifted = schedule.coefficients.copy()
            shifted[:, 0] += q_error
            steps = max(1, int(round(schedule.duration_s/schedule.reference_period_s)))
            u = np.linspace(0., 1., steps+1)
            q_path = np.stack([u**power for power in range(6)], axis=1) @ shifted.T
            shifted_rom = bool(np.all(q_path >= q_bounds[:, 0])
                               and np.all(q_path <= q_bounds[:, 1])
                               and np.all(q_path >= hard_bounds[:, 0])
                               and np.all(q_path <= hard_bounds[:, 1]))
            current_clearance = float(clearance.evaluate(observed[:2]))
            if shifted_rom and current_clearance >= 0.:
                shifted_lower = float(clearance.certified_minimum(shifted, schedule.duration_s))
        original_age_ms = (now_ns-original_ns)/1e6
        revalidation_age_ms = (now_ns-revalidation_ns)/1e6
        version_valid = bool(schedule.version == future_handoff["request_plan_version"]
                             and belief.sequence >= request_sequence)
        expected_goal = (spec.start_return_target_rad if phase is TaskPhase.RETURN
                         else spec.outbound_goal_target_rad)
        goal_valid = bool(np.allclose(schedule.candidate.phase_goal_rad,
                                      expected_goal, atol=1e-12, rtol=0.0))
        ages_valid = bool(0 <= original_age_ms < 100. and 0 <= revalidation_age_ms < 100.)
        record["future_handoff_revalidation"] = {
            "original_request_sample_s": future_handoff["original_sample_s"],
            "original_request_capture_ns": original_ns,
            "original_request_age_ms": original_age_ms,
            "revalidation_sample_s": future_handoff["revalidation_sample_s"],
            "revalidation_capture_ns": revalidation_ns,
            "revalidation_sample_age_ms": revalidation_age_ms,
            "request_model_sequence": request_sequence,
            "current_model_sequence": belief.sequence,
            "request_plan_version": future_handoff["request_plan_version"],
            "current_plan_version": schedule.version,
            "model_changed_and_rescreened": belief.sequence != request_sequence,
            "q_deviation_rad": q_error,
            "dq_deviation_rad_s": dq_error,
            "observation_reference_state_rad_rad_s": observed_reference,
            "state_rom_valid": state_rom,
            "state_and_shifted_path_motion_valid": state_motion,
            "shifted_path_rom_valid": shifted_rom,
            "current_clearance_m": current_clearance,
            "shifted_continuous_clearance_lower_m": shifted_lower,
            "live_reference_c2": live_c2,
            "version_valid": version_valid,
            "task_goal_valid": goal_valid,
            "both_ages_valid": ages_valid,
            "current_model_force_moment_feasible": mechanics["feasible"],
        }
        record["feasible"] = bool(record["feasible"] and live_c2 and state_rom
                                  and state_motion and shifted_rom and current_clearance >= 0.
                                  and shifted_lower >= 0. and version_valid and ages_valid)
        record["feasible"] = bool(record["feasible"] and goal_valid)
    return record


def validate_rolling_composite(*, composite, belief, request_sequence, clearance,
                               spec, phase, request_phase, remaining_s,
                               current_reference_state, current_reference_acceleration,
                               future_handoff, now_physics_s,
                               certificate_geometry_at_request=None):
    """Recertify the unchanged active prefix and selected suffix at activation."""
    suffix_origin = composite.suffix.sample(0.0)
    suffix_state = np.r_[suffix_origin.q_rad, suffix_origin.dq_rad_s]
    suffix_validation = validate_activation(
        belief=belief, request_sequence=request_sequence,
        schedule=composite.suffix, clearance=clearance,
        phase=phase, request_phase=request_phase,
        remaining_s=remaining_s-composite.splice_elapsed_s,
        reference_state=suffix_state, now_physics_s=now_physics_s,
        certificate_geometry_at_request=certificate_geometry_at_request,
        future_handoff={**future_handoff,
                        "observed_reference_state": current_reference_state,
                        "reference_acceleration": suffix_origin.ddq_rad_s2})
    current = composite.sample(0.0)
    prefix_c2 = bool(all(np.max(np.abs(a-b)) <= 1e-10 for a, b in (
        (current.q_rad, current_reference_state[:2]),
        (current.dq_rad_s, current_reference_state[2:]),
        (current.ddq_rad_s2, current_reference_acceleration))))
    model = belief.human_model()
    q_bounds = np.asarray(spec.q_bounds_rad, dtype=float)
    hard_bounds = np.column_stack([model.q_min_rad, model.q_max_rad])
    observed = np.asarray(future_handoff["estimated_state"], dtype=float)
    q_offset = observed[:2]-current_reference_state[:2]
    shifted = composite.prefix.coefficients.copy()
    shifted[:, 0] += q_offset
    count = max(1, int(round(composite.splice_elapsed_s/composite.prefix.reference_period_s)))
    remaining_times = np.linspace(composite.prefix_start_s,
                                  composite.prefix.duration_s, count+1)
    u = remaining_times/composite.prefix.duration_s
    path = np.stack([u**power for power in range(6)], axis=1) @ shifted.T
    prefix_rom = bool(np.all(path >= q_bounds[:, 0]) and np.all(path <= q_bounds[:, 1])
                      and np.all(path >= hard_bounds[:, 0])
                      and np.all(path <= hard_bounds[:, 1]))
    prefix_clearance = (float(clearance.certified_minimum(
        shifted, composite.prefix.duration_s)) if prefix_rom else float("-inf"))
    prefix_mechanics = AdaptiveMechanicsScreenV22().evaluate(
        belief, composite.prefix.candidate, composite.prefix)
    motion_limit = bool(
        np.all(composite.prefix.maximum_reference_velocity_rad_s
               <= np.asarray(spec.task_joint_velocity_limit_rad_s)+1e-12)
        and np.all(composite.prefix.maximum_reference_acceleration_rad_s2
                   <= np.asarray(spec.task_joint_acceleration_limit_rad_s2)+1e-12))
    prefix_valid = bool(prefix_c2 and prefix_rom and prefix_clearance >= 0.
                        and prefix_mechanics["feasible"] and motion_limit)
    suffix_validation["rolling_composite"] = dict(
        prefix_c2=prefix_c2, prefix_shifted_rom_valid=prefix_rom,
        prefix_shifted_continuous_clearance_m=prefix_clearance,
        prefix_current_model_mechanics=prefix_mechanics,
        prefix_motion_limit_valid=motion_limit,
        prefix_duration_remaining_s=composite.splice_elapsed_s,
        composite_duration_s=composite.duration_s,
        suffix_boundary_c2=True,
        composite_version=composite.version,
        request_id=composite.request_id)
    suffix_validation["schedule_duration_s"] = composite.duration_s
    suffix_validation["feasible"] = bool(
        suffix_validation["feasible"] and prefix_valid
        and composite.duration_s <= remaining_s+1e-12)
    return suffix_validation


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
