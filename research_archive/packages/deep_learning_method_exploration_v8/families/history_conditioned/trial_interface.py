"""Pure causal complete-Trial interface for the v8 orchestrator.

This module never imports a plant, reads native truth, trains a model, writes a
file, or starts physics. The orchestrator owns live objects and all accounting.
Recipe descriptors describe signed nominal reference changes, not torques.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

SCHEMA = "v8_causal_complete_trial_v1"
PHASES = ("OUTBOUND", "HOLD", "RETURN")
ROW_FIELDS = frozenset({
    "time_s", "phase", "estimated_q_dq", "reference_q_dq", "measured_force",
    "measured_moment", "source_sample_time_s", "reference_progress", "truth_used",
})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _norm(values):
    return math.sqrt(sum(float(v) ** 2 for v in values))


def capture_boundary(b):
    """Read the same causal allowlist as v7 Study.boundary; no native access."""
    ref = b["reference"]
    sample = float(b["observation"].sample_timestamp_s)
    return dict(time_s=float(b["physical_now"]), phase=b["task_state"].phase.value,
                estimated_q_dq=[float(v) for v in b["observation"].as_array()[:4]],
                reference_q_dq=[float(v) for v in ref.q_rad] + [float(v) for v in ref.dq_rad_s],
                measured_force=[float(v) for v in b["interface"].measured_force_world_n],
                measured_moment=[float(v) for v in b["interface"].measured_moment_world_nm],
                source_sample_time_s=sample, truth_used=False)


def summarize(rows, *, trial_id, patient_id, trial_number, actual_action_tag,
              task_start_s, task_end_s, complete, identity, public_phase_targets):
    """Summarize an observed complete Trial, with a terminal causal boundary.

    public_phase_targets maps moving phase to [start_q_rad, goal_q_rad]. Its
    source is the frozen public task specification, never native human state.
    Every interval belongs to its left boundary's actual phase. Missing final
    samples are rejected rather than extrapolated into a complete cost label.
    """
    if complete is not True:
        raise ValueError("PARTIAL_TRIAL_HAS_NO_COMPLETE_COST_LABEL")
    if len(rows) < 3:
        raise ValueError("INSUFFICIENT_CAUSAL_HISTORY")
    clean = []
    for index, row in enumerate(rows):
        unknown = set(row) - ROW_FIELDS
        if unknown:
            raise ValueError("NON_ALLOWLISTED_HISTORY_FIELDS:" + ",".join(sorted(unknown)))
        if row.get("truth_used") is not False:
            raise ValueError("TRUTH_FIREWALL")
        r = copy.deepcopy(row)
        for name, length in [("estimated_q_dq", 4), ("reference_q_dq", 4),
                             ("measured_force", 3), ("measured_moment", 3)]:
            if len(r[name]) != length or not all(math.isfinite(float(v)) for v in r[name]):
                raise ValueError("INVALID_CAUSAL_VECTOR:" + name)
        if r["phase"] not in PHASES and not (index == len(rows)-1 and r["phase"] == "COMPLETE"):
            raise ValueError("INVALID_PHASE")
        if not math.isfinite(float(r["time_s"])) or not math.isfinite(float(r["source_sample_time_s"])):
            raise ValueError("INVALID_TIMESTAMP")
        age = r["time_s"] - r["source_sample_time_s"]
        if age < -1e-9:
            raise ValueError("FUTURE_OBSERVATION")
        clean.append(r)
    if abs(clean[0]["time_s"] - task_start_s) > 1e-8:
        raise ValueError("MISSING_TASK_START_BOUNDARY")
    if abs(clean[-1]["time_s"] - task_end_s) > 1e-8:
        raise ValueError("MISSING_TERMINAL_CAUSAL_BOUNDARY")
    stats = {p: dict(duration_s=0., JF_N_s=0., JM_Nm_s=0.,
                     tracking_squared_deg2_s=[0., 0.], windows=[]) for p in PHASES}
    windows = {(p, k): dict(duration_s=0., force_integral_N_s=0.,
                            error_integral_deg_s=[0., 0.])
               for p in ("OUTBOUND", "RETURN") for k in range(5)}
    rad_to_deg = 180. / math.pi
    for r, nxt in zip(clean[:-1], clean[1:]):
        dt = nxt["time_s"] - r["time_s"]
        if not 0. < dt <= .006:
            raise ValueError("HISTORY_GAP_OR_NONMONOTONIC_TIME")
        p = r["phase"]; s = stats[p]
        force = _norm(r["measured_force"]); moment = _norm(r["measured_moment"])
        error = [(r["estimated_q_dq"][j] - r["reference_q_dq"][j]) * rad_to_deg
                 for j in (0, 1)]
        s["duration_s"] += dt; s["JF_N_s"] += force * dt; s["JM_Nm_s"] += moment * dt
        for j in (0, 1):
            s["tracking_squared_deg2_s"][j] += error[j] ** 2 * dt
        if p in ("OUTBOUND", "RETURN"):
            if "reference_progress" in r:
                progress = float(r["reference_progress"])
            else:
                start, goal = public_phase_targets[p]
                relevant = [j for j in (0, 1) if abs(goal[j] - start[j]) > 1e-12]
                if not relevant:
                    raise ValueError("NO_PUBLIC_MOVEMENT_PROGRESS_AXIS")
                progress = sum((r["reference_q_dq"][j] - start[j]) / (goal[j] - start[j])
                               for j in relevant) / len(relevant)
            if not math.isfinite(progress) or not -.05 <= progress <= 1.05:
                raise ValueError("REFERENCE_PROGRESS_OUTSIDE_TASK")
            k = min(4, max(0, int(progress * 5)))
            w = windows[p, k]; w["duration_s"] += dt; w["force_integral_N_s"] += force * dt
            for j in (0, 1):
                w["error_integral_deg_s"][j] += error[j] * dt
    for p, s in stats.items():
        if s["duration_s"] <= 0.:
            raise ValueError("MISSING_REQUIRED_PHASE:" + p)
        s["tracking_rms_deg"] = [math.sqrt(v / s["duration_s"])
                                 for v in s.pop("tracking_squared_deg2_s")]
        if p in ("OUTBOUND", "RETURN"):
            for k in range(5):
                w = windows[p, k]; duration = w["duration_s"]
                s["windows"].append(dict(progress=[k / 5., (k + 1) / 5.], **w,
                    mean_force_N=w["force_integral_N_s"] / duration if duration else None,
                    mean_tracking_error_deg=[e / duration for e in w["error_integral_deg_s"]]
                    if duration else None))
    local = {}
    for p in ("OUTBOUND", "RETURN"):
        ws = [windows[p, k] for k in (1, 2)]; duration = sum(w["duration_s"] for w in ws)
        if duration <= 0.:
            raise ValueError("MISSING_MIDDLE_REFERENCE_WINDOW:" + p)
        local[p] = dict(duration_s=duration,
                        mean_force_N=sum(w["force_integral_N_s"] for w in ws) / duration,
                        mean_tracking_error_deg=[sum(w["error_integral_deg_s"][j] for w in ws) / duration
                                                 for j in (0, 1)])
    result = dict(schema=SCHEMA, trial_id=trial_id, patient_id=patient_id,
                  trial_number=trial_number, actual_action_tag=actual_action_tag,
                  complete=True, task_start_s=task_start_s, task_end_s=task_end_s,
                  identity=copy.deepcopy(identity), phases=stats, local=local,
                  JF_N_s=sum(s["JF_N_s"] for s in stats.values()),
                  JM_Nm_s=sum(s["JM_Nm_s"] for s in stats.values()),
                  raw_history_sha256=digest(clean), sample_count=len(clean), truth_used=False,
                  native_motion_is_input=False, future_trial_outcomes_consumed=False)
    result["history_sha256"] = digest(result)
    return result


def feature_vector(history):
    """Phase-local measured burden and estimated tracking; no future labels."""
    if history.get("schema") != SCHEMA or history.get("complete") is not True or history.get("truth_used") is not False:
        raise ValueError("INVALID_CAUSAL_HISTORY")
    names = ["prior_measured_JF", "prior_measured_JM"]
    values = [history["JF_N_s"], history["JM_Nm_s"]]
    for p in ("OUTBOUND", "RETURN"):
        names += [p + "_mid_force", p + "_mid_hip_lag_deg", p + "_mid_knee_lag_deg"]
        values += [history["local"][p]["mean_force_N"], *history["local"][p]["mean_tracking_error_deg"]]
    return names, values


def ilc_target(history, *, gain=.25, cumulative=None, maximum_deg=.3,
               window="largest_force", joint="knee"):
    """A transparent prior-error update, not a learned force gradient.

    `all_phases` differs mechanistically from historical largest-force gating;
    it retains both local error signals. It still needs physical falsification.
    """
    feature_vector(history)
    if not 0. <= gain <= 1. or not 0. < maximum_deg <= .3:
        raise ValueError("ILC_CONTRACT_DOMAIN")
    phases = [max(("OUTBOUND", "RETURN"), key=lambda p: history["local"][p]["mean_force_N"])]
    if window == "all_phases":
        phases = ["OUTBOUND", "RETURN"]
    elif window != "largest_force":
        raise ValueError("UNKNOWN_WINDOW_RULE")
    if joint not in ("knee", "both"):
        raise ValueError("UNKNOWN_JOINT_RULE")
    cumulative = cumulative or {}
    target = {}
    for p in phases:
        previous = cumulative.get(p, [0., 0.])
        target[p] = [max(-maximum_deg, min(maximum_deg, float(previous[j]) + gain * history["local"][p]["mean_tracking_error_deg"][j]))
                     if joint == "both" or j == 1 else 0. for j in (0, 1)]
    return dict(reference_delta_target_deg=target, gain=gain, window=window, joint=joint,
                history_sha256=history["history_sha256"], learning_type="prior_error_update",
                force_gradient_identified=False)


def project_to_menu(target, descriptors, *, menu_sha256):
    """Project to declared recipe effects; never manufacture a new action.

    A descriptor is {tag, nominal_reference_delta_deg:{phase:[hip,knee]}}.
    Descriptors must be supplied by the orchestrator from the exact frozen
    reference recipe. A modal coordinate is not a direct knee displacement.
    Projection does not certify admission, activation, or task qualification.
    """
    if not descriptors or not menu_sha256:
        raise ValueError("MISSING_FROZEN_MENU")
    wanted = target["reference_delta_target_deg"]
    ranked = []
    for d in descriptors:
        effects = d["nominal_reference_delta_deg"]
        distance = sum((effects.get(p, [0., 0.])[j] - wanted.get(p, [0., 0.])[j]) ** 2
                       for p in ("OUTBOUND", "RETURN") for j in (0, 1))
        ranked.append((distance, d["tag"]))
    ranked.sort()
    return dict(selected_tag=ranked[0][1], menu_sha256=menu_sha256,
                projection_distance_deg2=ranked[0][0], ranked=ranked,
                history_sha256=target["history_sha256"], new_continuous_action_created=False,
                task_or_motion_qualification_inferred=False)


def verify_trial2_inputs(history, *, patient_id, trial_number, frozen_at_s,
                         source_trial_completed_at_s, expected_identity):
    """Causal lifecycle checks independent of any particular algorithm."""
    feature_vector(history)
    if history["patient_id"] != patient_id or history["trial_number"] != trial_number - 1:
        raise ValueError("WRONG_PATIENT_OR_PREVIOUS_TRIAL")
    if source_trial_completed_at_s > frozen_at_s:
        raise ValueError("FUTURE_TRIAL_INFORMATION")
    if history["identity"] != expected_identity:
        raise ValueError("TASK_SOURCE_SCORER_MENU_IDENTITY_CHANGED")
    return dict(status="INPUT_CAUSALITY_CHECKED", history_sha256=history["history_sha256"],
                physical_continuity_verified=False,
                note="live parent and same-branch continuation remain orchestrator duties")
