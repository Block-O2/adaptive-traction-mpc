"""Causal completion transaction before non-control terminal bookkeeping."""
import numpy as np
from ..task import at_goal, task_limit_violation
from .activation_validation import return_finalization_reason


def terminal_sample_evidence(spec, observation, measurement, interface, split, *,
                             authority, clearance, force_limit, moment_limit,
                             robot_velocity_limits):
    """Apply original task/measurement limits to every new terminal-tail capture."""
    state = observation.as_array()
    decision = authority.evaluate(split)
    reason = decision.abort_reason if decision.violation else task_limit_violation(
        spec, state[:2], state[2:], split.human_motion_acceleration_rad_s2,
        acceleration_authority_valid=split.human_motion_valid)
    if reason is None and np.linalg.norm(interface.measured_force_world_n) > force_limit+1e-9:
        reason = "REALIZED_CUFF_FORCE_LIMIT"
    if reason is None and np.linalg.norm(interface.measured_moment_world_nm) > moment_limit+1e-9:
        reason = "REALIZED_CUFF_MOMENT_LIMIT"
    if reason is None and np.any(np.abs(measurement.robot_dq_rad_s) > robot_velocity_limits+1e-9):
        reason = "CR12_VELOCITY_LIMIT"
    gap = float(clearance.evaluate(state[:2]))
    if reason is None and gap < -1e-9:
        reason = "SESSION_CLEARANCE_LIMIT"
    return {"sample_time_s": float(observation.sample_timestamp_s),
            "model_version": observation.human_model_version,
            "estimated_state": state.copy(), "reason": reason,
            "session_clearance_m": gap,
            "return_set_valid": bool(at_goal(spec, state[:2], state[2:], spec.start_return_target_rad)),
            "truth_consumed": False}


def attempt_return_commit(wall, guard, *, phase_elapsed_at_boundary_s,
                          boundary_physics_s, phase_timeout_s,
                          task_start_s, task_timeout_s, inspect_sample):
    """A late proposal stays active in RETURN; only an actual commit ends epoch.

    All elapsed complete native intervals retain the old receipt owner. New
    causal captures can veto the proposal, but never refresh its source stamp.
    Post-commit logging does not belong to the already ended physical session.
    """
    runtime = wall.runtime
    if not wall.active:
        raise RuntimeError("terminal commit requires an active physical session")
    if runtime.get("terminal_capture_hook") is not None:
        raise RuntimeError("nested terminal capture hook")
    samples = []
    source_s, source_ns = guard["source_sample_time_s"], guard["source_capture_ns"]
    record = {"source_sample_time_s": source_s, "source_capture_ns": source_ns,
              "capture_anchored_horizon_s": guard["capture_anchored_horizon_s"],
              "truth_used_for_decision": False, "causal_tail_samples": samples,
              "attempt_entered_host_ns": wall.clock(), "action": "IN_PROGRESS"}
    # Register before any operation can fail. Runtime persistence must retain
    # interrupted proposals and partially inspected samples, not just successes.
    runtime.setdefault("return_commit_attempts", []).append(record)
    if source_s <= runtime.get("last_return_commit_source_s", -float('inf'))+1e-12:
        record.update(action="DEFER", accepted=False, reason="TERMINAL_COMMIT_REQUIRES_NEW_CAPTURE")
        return record
    runtime["last_return_commit_source_s"] = source_s
    def hook(observation, measurement, interface, split):
        sample = {"sample_time_s": float(observation.sample_timestamp_s),
                  "inspection_complete": False}
        samples.append(sample)
        try:
            sample.update(inspect_sample(observation, measurement, interface, split))
            sample["inspection_complete"] = True
        except BaseException as error:
            sample["exception"] = f"{type(error).__name__}:{error}"
            raise
    runtime["terminal_capture_hook"] = hook
    try:
        for attempt in range(3):
            wall.catch_up("return_completion_commit" if attempt == 0 else "return_completion_check_tail")
            native_s = float(wall.plant.data.time)
            return_elapsed = phase_elapsed_at_boundary_s + native_s-boundary_physics_s
            task_elapsed = native_s-task_start_s
            safety_reason = next((s["reason"] for s in samples if s["reason"] is not None), None)
            goal_contradiction = any(not s["return_set_valid"] for s in samples)
            checked_ns = wall.clock()
            reason = safety_reason or return_finalization_reason(
                physical_age=native_s-source_s, host_age=(checked_ns-source_ns)/1e9,
                horizon_s=guard["capture_anchored_horizon_s"],
                return_elapsed_s=return_elapsed, phase_timeout_s=phase_timeout_s,
                task_elapsed_s=task_elapsed, task_timeout_s=task_timeout_s)
            if reason is None and goal_contradiction:
                reason = "TERMINAL_NEW_CAPTURE_OUTSIDE_RETURN_SET"
            # Timestamp the actual commit attempt after necessary checks. Any
            # complete native interval consumed by those checks must catch up.
            commit_ns = wall.clock()
            residual_ns = commit_ns-wall.source_ns(native_s)
            if residual_ns >= wall.dt_ns and reason in (None,
                    "TERMINAL_RETURN_PROJECTION_HORIZON_EXCEEDED",
                    "TERMINAL_NEW_CAPTURE_OUTSIDE_RETURN_SET"):
                continue
            if reason is None and commit_ns-source_ns > round(guard["capture_anchored_horizon_s"]*1e9):
                reason = "TERMINAL_RETURN_PROJECTION_HORIZON_EXCEEDED"
            accepted = reason is None
            if accepted:
                wall.end_ns = commit_ns
                wall.active = False
            action = ("COMPLETE" if accepted else "DEFER" if reason in (
                "TERMINAL_RETURN_PROJECTION_HORIZON_EXCEEDED",
                "TERMINAL_NEW_CAPTURE_OUTSIDE_RETURN_SET") else "ABORT")
            record.update(final_native_time_s=native_s, final_host_ns=commit_ns,
                source_to_final_physical_s=native_s-source_s,
                source_to_final_host_s=(commit_ns-source_ns)/1e9,
                actual_return_elapsed_s=return_elapsed, original_phase_timeout_s=phase_timeout_s,
                actual_task_elapsed_s=task_elapsed, original_task_timeout_s=task_timeout_s,
                quantization_residual_ns=residual_ns, accepted=accepted, action=action,
                reason=reason, covered=max(native_s-source_s, (commit_ns-source_ns)/1e9)
                    <= guard["capture_anchored_horizon_s"]+1e-12)
            return record
        # Bounded transaction work only. The caller must acquire a strictly
        # newer sample; original phase and global clocks continue unchanged.
        record.update(accepted=False, action="DEFER", reason="TERMINAL_COMMIT_CHECK_BACKLOG",
                      last_attempt_host_ns=wall.clock(), last_attempt_native_s=float(wall.plant.data.time))
        return record
    except BaseException as error:
        record.update(accepted=False, action="EXCEPTION", exception=f"{type(error).__name__}:{error}",
                      last_attempt_host_ns=wall.clock(), last_attempt_native_s=float(wall.plant.data.time))
        raise
    finally:
        runtime.pop("terminal_capture_hook", None)


def attempt_scientific_return_commit(wall, guard, *, phase_elapsed_at_boundary_s,
                                     boundary_physics_s, phase_timeout_s,
                                     task_start_s, task_timeout_s, inspect_sample):
    """Commit COMPLETE at the current native state with no host catch-up."""
    if not wall.active:
        raise RuntimeError("terminal commit requires an active physical session")
    runtime = wall.runtime
    source_s = float(guard["source_sample_time_s"])
    source_ns = int(guard["source_capture_ns"])
    native_s = float(wall.plant.data.time)
    now_ns = wall.clock()
    physical_age = native_s-source_s
    host_age = (now_ns-source_ns)/1e9
    return_elapsed = phase_elapsed_at_boundary_s+native_s-boundary_physics_s
    task_elapsed = native_s-task_start_s
    record = {"source_sample_time_s": source_s, "source_capture_ns": source_ns,
              "capture_anchored_horizon_s": guard["capture_anchored_horizon_s"],
              "truth_used_for_decision": False, "causal_tail_samples": [],
              "attempt_entered_host_ns": now_ns, "final_native_time_s": native_s,
              "final_host_ns": now_ns, "source_to_final_physical_s": physical_age,
              "source_to_final_host_s": host_age,
              "actual_return_elapsed_s": return_elapsed,
              "original_phase_timeout_s": phase_timeout_s,
              "actual_task_elapsed_s": task_elapsed,
              "original_task_timeout_s": task_timeout_s,
              "quantization_residual_ns": 0,
              "scientific_validity_age_s": physical_age}
    runtime.setdefault("return_commit_attempts", []).append(record)
    if source_s <= runtime.get("last_return_commit_source_s", -float("inf"))+1e-12:
        record.update(action="DEFER", accepted=False,
                      reason="TERMINAL_COMMIT_REQUIRES_NEW_CAPTURE")
        return record
    runtime["last_return_commit_source_s"] = source_s
    reason = return_finalization_reason(
        physical_age=physical_age, host_age=physical_age,
        horizon_s=guard["capture_anchored_horizon_s"],
        return_elapsed_s=return_elapsed, phase_timeout_s=phase_timeout_s,
        task_elapsed_s=task_elapsed, task_timeout_s=task_timeout_s)
    if not guard.get("ready", False) and reason is None:
        reason = "TERMINAL_RETURN_PROJECTION_NOT_READY"
    accepted = reason is None
    action = ("COMPLETE" if accepted else "DEFER" if reason ==
              "TERMINAL_RETURN_PROJECTION_HORIZON_EXCEEDED" else "ABORT")
    record.update(accepted=accepted, action=action, reason=reason,
                  covered=physical_age <= guard["capture_anchored_horizon_s"]+1e-12)
    if accepted:
        wall.end_ns = now_ns
        wall.active = False
    return record
