"""Opt-in references inside the unchanged task completion set.

These routines select controller references; they never replace the registered
task goal, completion test, original-goal cost, or deployable clearance model.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import product
from functools import lru_cache
from typing import Any

import numpy as np
from scipy.optimize import minimize

from ..human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCV1, HumanWaypointFeedbackDecisionV1
from ..human_waypoint_scheduler import _quintic_coefficients
from ..task import TaskPhase
from traction_mpc_stage3.coupled import SLEEVE_OUTER_RADIUS_M, SLEEVE_HALF_LENGTH_M
from ..geometry import STAGE5_GEOMETRY


@lru_cache(maxsize=4)
def _rest_progress(sample_count: int) -> np.ndarray:
    s = np.linspace(0.0, 1.0, sample_count)
    u = 10*s**3-15*s**4+6*s**5
    u.setflags(write=False)
    return u


def rest_to_rest_clearance_lower(clearance: Any, origin: np.ndarray, target: np.ndarray,
                                 *, endpoint_only: bool = False) -> float:
    """Same 1201-node support/Lipschitz certificate with analytic quintic extrema.

    Rest-to-rest q=q0+(q1-q0)*u; max |du/ds| is exactly 15/8. This
    removes repeated polynomial solves, roots and sample-grid allocation.
    Every selected endpoint is also rechecked by the original general method.
    """
    if not hasattr(clearance, "envelope"):
        c = _quintic_coefficients(origin,np.zeros(2),target,np.zeros(2),1.0)
        return float(clearance.certified_minimum(c,1.0))
    env = clearance.envelope
    g = env.geometry
    delta = np.asarray(target)-origin
    progress = np.array([0., 1.]) if endpoint_only else _rest_progress(env.sample_count)
    q = np.asarray(origin)[None,:]+progress[:,None]*delta
    margins = env.margins(q)
    half = 0.5/(env.sample_count-1)
    thigh_bound = half*g.thigh_length_m*1.875*abs(delta[0])
    limb_bound = thigh_bound + half*(env.shank_length_upper_m+SLEEVE_OUTER_RADIUS_M)*1.875*abs(delta[0]-delta[1])
    if (min(origin[0],target[0]) >= 0 and max(origin[0],target[0]) <= np.pi
            and abs(float(g.plane_x_world[2])) < 1e-9 and g.plane_z_world[2] > 0):
        thigh_bound = 0.0
    else:
        knee_above_hip = g.thigh_length_m*(np.cos(q[:,0])*g.plane_x_world[2]+np.sin(q[:,0])*g.plane_z_world[2])
        if float(np.min(knee_above_hip))-thigh_bound >= 0:
            thigh_bound = 0.0
    lower = {k:float(np.min(v))-(thigh_bound if k=="proximal_thigh_m" else limb_bound)
             for k,v in margins.items()}
    if getattr(clearance, "use_monotonic_certificate", False):
        from .monotonic_clearance import monotonic_component_lowers
        c = np.asarray(delta)[:,None]*np.array([0.,0.,0.,10.,-15.,6.])
        c[:,0] = origin
        improved = monotonic_component_lowers(env,c)
        lower = {k:max(v,improved.get(k,-np.inf)) for k,v in lower.items()}
    return min(lower.values())


def _terminal_cache_key(clearance: Any, goal: np.ndarray, spec: Any) -> bytes | None:
    if not hasattr(clearance, "envelope"):
        return None
    env, g = clearance.envelope, clearance.envelope.geometry
    return np.concatenate([np.asarray(goal), np.asarray(spec.start_return_target_rad),
        np.asarray(spec.joint_angle_completion_tolerance_rad), np.asarray(spec.q_bounds_rad).ravel(),
        g.origin_world_m, g.plane_x_world, g.plane_z_world, g.hip_plane_m,
        env.cuff_reference_translation_world_m,
        [g.thigh_length_m,g.cuff_distance_m,env.shank_length_upper_m,env.existing_shank_margin_m,
         env.registered_proximal_installation_gap_lower_m,env.sample_count]]).astype(float).tobytes()


def in_original_terminal_box(spec: Any, q: np.ndarray, goal: np.ndarray) -> bool:
    return bool(np.all(np.abs(np.asarray(q) - goal)
                       <= np.asarray(spec.joint_angle_completion_tolerance_rad)))


def select_terminal_reference(*, spec: Any, goal: np.ndarray, clearance: Any,
                              origin: np.ndarray | None = None,
                              _full_path_search: bool = False) -> dict[str, Any]:
    """Numerically minimize squared angular displacement in the original box.

    Deterministic grid starts and multiple bounded local searches are retained.
    A failed search means no point was found, not a proof of nonrecoverability.
    If an origin is supplied, the same continuous quintic geometry certificate
    as the existing scheduler is included (not an arbitrary extra margin).
    """
    goal = np.asarray(goal, dtype=float)
    tolerance = np.asarray(spec.joint_angle_completion_tolerance_rad, dtype=float)
    rom = np.asarray(spec.q_bounds_rad, dtype=float)
    lower = np.maximum(-np.ones(2), (rom[:, 0] - goal) / tolerance)
    upper = np.minimum(np.ones(2), (rom[:, 1] - goal) / tolerance)
    if goal.shape != (2,) or not np.all(np.isfinite(goal)) or np.any(lower > upper):
        raise ValueError("invalid original terminal set")
    # Preserve the scheduler's original endpoint floor, including the zero
    # hard-table floor. It still refers to the original task endpoints.
    floor = max(0.0, float(np.min(clearance.evaluate(np.vstack(
        [spec.start_return_target_rad, goal])))))

    margin_cache = {}
    counters = {"margin_requests": 0, "unique_path_evaluations": 0, "cache_hits": 0, "final_general_certificates": 0, "near_boundary_general_certificates": 0}

    def margins(x):
        counters["margin_requests"] += 1
        key = np.asarray(x, dtype=float).tobytes()
        if key in margin_cache:
            counters["cache_hits"] += 1
            return margin_cache[key]
        counters["unique_path_evaluations"] += 1
        q = goal + tolerance * np.asarray(x)
        values = [float(clearance.evaluate(q)) - floor]
        if origin is not None:
            lower = rest_to_rest_clearance_lower(clearance, np.asarray(origin), q,
                                                  endpoint_only=not _full_path_search)
            # Near a binding boundary the original polynomial solve/root
            # arithmetic defines the numerical decision. Reuse it exactly
            # for stable optimizer finite differences; this is not a margin
            # or acceptance tolerance and does not admit negative clearance.
            if _full_path_search and abs(lower-floor) <= 1e-8:
                c = _quintic_coefficients(np.asarray(origin),np.zeros(2),q,np.zeros(2),1.0)
                lower = float(clearance.certified_minimum(c,1.0))
                counters["near_boundary_general_certificates"] += 1
            # Optimization arithmetic gets a 128-ulp positive numerical guard
            # (2.85e-14 m at unit scale), never an acceptance relaxation. This
            # avoids returning a mathematically active endpoint just below
            # zero after the general polynomial arithmetic is reapplied.
            # A positive floor can be the exactly constant proximal bound.
            # Asking that bound to exceed itself rejects every safe point.
            # Use the optimizer-only guard at the zero penetration boundary;
            # positive floors retain their exact original >= floor check.
            numerical_guard = 128*np.finfo(float).eps if floor == 0.0 else 0.0
            values.append(lower-floor-numerical_guard)
        result = np.asarray(values)
        margin_cache[key] = result
        return result

    def valid(x):
        q = goal + tolerance * np.asarray(x)
        return (bool(np.all(np.asarray(x) >= lower) and np.all(np.asarray(x) <= upper))
                and in_original_terminal_box(spec, q, goal) and bool(np.min(margins(x)) >= 0.0))

    def objective(x):
        offset = tolerance * np.asarray(x)
        return float(offset @ offset / np.min(tolerance)**2)

    attempts = []
    grid_records = []
    center = np.clip(np.zeros(2), lower, upper)
    if valid(center):
        feasible = [center]
        selected = center
    else:
        grid = [np.asarray(x) for x in product(*[np.linspace(a, b, 5) for a, b in zip(lower, upper)])]
        grid_records = [{"normalized_offset": x.copy(), "margins_m": margins(x),
                         "feasible": valid(x)} for x in grid]
        feasible = [x for x in grid if valid(x)]
        ranked = sorted(grid, key=lambda x: (max(0.0, -float(np.min(margins(x)))), objective(x)))
        starts = [center, *ranked[:3]]
        for start in starts:
            fit = minimize(objective, start, method="SLSQP", bounds=list(zip(lower, upper)),
                           constraints={"type": "ineq", "fun": lambda x: 1000.0 * margins(x)},
                           options={"maxiter": 45, "ftol": 1e-11})
            x = np.clip(fit.x, lower, upper)
            accepted = valid(x)
            attempts.append({"start_normalized_offset": start.copy(), "success": bool(fit.success),
                             "message": str(fit.message), "iterations": int(fit.nit),
                             "offset_rad": tolerance * x, "margins_m": margins(x),
                             "independently_feasible": accepted})
            if accepted:
                feasible.append(x)
        selected = min(feasible, key=objective) if feasible else None
    # Never substitute the optimization approximation for the original final
    # acceptance. Try candidates in objective order; retain every rejection.
    final_checks = []
    if selected is not None and origin is not None:
        selected = None
        for x in sorted(feasible, key=objective):
            q = goal+tolerance*x
            c = _quintic_coefficients(np.asarray(origin),np.zeros(2),q,np.zeros(2),1.0)
            lower_general = float(clearance.certified_minimum(c,1.0))
            counters["final_general_certificates"] += 1
            final_checks.append({"target_rad": q, "general_certificate_m": lower_general,
                                 "feasible": lower_general >= floor})
            if lower_general >= floor and valid(x):
                selected = x
                break
    if selected is None and origin is not None and not _full_path_search:
        # Endpoints are necessary, not sufficient: an interior valley must
        # fall back to the full-path search, never be accepted on endpoints.
        fallback = select_terminal_reference(spec=spec,goal=goal,clearance=clearance,
                                              origin=origin,_full_path_search=True)
        fallback["endpoint_first_attempt"] = {"attempts": attempts,"grid_evaluations": grid_records,
            "final_general_certificate_checks": final_checks,"computation_counters": counters}
        return fallback
    result = {"policy": "minimum_squared_displacement_inside_original_terminal_box",
              "original_goal_rad": goal.copy(), "original_tolerance_rad": tolerance.copy(),
              "floor_m": floor, "continuous_path_from_origin_checked": origin is not None,
              "search_mode": "full_path_fallback" if _full_path_search else "endpoint_first_with_general_final_certificate",
              "attempts": attempts, "grid_evaluations": grid_records,
              "computation_counters": counters, "final_general_certificate_checks": final_checks,
              "global_optimality_proven": False,
              "feasible": selected is not None,
              "status": "SELECTED" if selected is not None else "NO_FEASIBLE_POINT_FOUND",
              "physical_nonrecoverability_proven": False}
    if selected is not None:
        result.update(reference_target_rad=goal + tolerance * selected,
                      signed_offset_rad=tolerance * selected,
                      displacement_norm_rad=float(np.linalg.norm(tolerance * selected)),
                      verified_margins_m=margins(selected))
    return result



def select_robust_terminal_reference(*, spec, goal, clearance, origin):
    """Choose the largest certified local error ball in the original goal box.

    A deterministic 9x9 endpoint set replaces repeated nonlinear searches for
    this opt-in controller policy. No global optimality or physical invariance
    is asserted. Safety/task thresholds and original-goal MPC costs are intact.
    """
    goal, origin = np.asarray(goal), np.asarray(origin)
    tol = np.asarray(spec.joint_angle_completion_tolerance_rad)
    rom = np.asarray(spec.q_bounds_rad)
    lower = np.maximum(goal-tol, rom[:,0]); upper = np.minimum(goal+tol, rom[:,1])
    points = np.asarray(list(product(*[np.linspace(a,b,9) for a,b in zip(lower,upper)])))
    points = np.vstack([goal, points])
    env, g = clearance.envelope, clearance.envelope.geometry
    # Excluding the constant proximal component from the radius ranking is
    # valid only if this entire original goal box retains that same branch.
    if not (np.array_equal(g.plane_x_world,[1.,0.,0.]) and np.array_equal(g.plane_z_world,[0.,0.,1.])
            and lower[0]>=0. and upper[0]<=np.pi):
        return select_terminal_reference(spec=spec,goal=goal,clearance=clearance,origin=origin)
    margins = env.margins(points)
    floor = max(0.,float(np.min(clearance.evaluate(np.vstack([spec.start_return_target_rad,goal])))))
    radii = {
        'distal_shank_m':env.shank_length_upper_m,
        'sleeve_m':g.cuff_distance_m+np.hypot(SLEEVE_HALF_LENGTH_M,SLEEVE_OUTER_RADIUS_M),
        'cuff_bar_m':g.cuff_distance_m+np.hypot(.5*STAGE5_GEOMETRY.cuff_bar_length_m,STAGE5_GEOMETRY.cuff_bar_radius_m),
        'cuff_adapter_m':g.cuff_distance_m+np.linalg.norm(STAGE5_GEOMETRY.end_effector_from_cuff.translation)+.018}
    angular = np.min(np.minimum(points-lower,upper-points),axis=1)
    robust = angular.copy()
    for name,radius in radii.items():
        robust = np.minimum(robust,(margins[name]-floor)/(g.thigh_length_m+2*radius))
    endpoint_valid = np.all(np.stack(list(margins.values())) >= floor,axis=0)
    ranked = sorted(range(len(points)), key=lambda i:(-robust[i],float(np.sum((points[i]-goal)**2)),i))
    checks = []
    selected = None
    for i in ranked:
        if not endpoint_valid[i] or robust[i] < 0.:
            continue
        c = _quintic_coefficients(origin,np.zeros(2),points[i],np.zeros(2),1.)
        path_lower = float(clearance.certified_minimum(c,1.))
        checks.append({'point_index':i,'continuous_lower_m':path_lower,'feasible':path_lower>=floor})
        if path_lower >= floor:
            selected = i
            break
    record = {'policy':'maximum_certified_endpoint_error_ball_on_original_terminal_box_grid',
        'original_goal_rad':goal.copy(),'original_tolerance_rad':tol.copy(),'floor_m':floor,
        'radius_scope':'nominal endpoint q-position Linfinity ranking; no velocity, estimation-error, or closed-loop invariance guarantee',
        'proximal_constant_branch_covers_entire_goal_box':True,
        'endpoint_candidates':points,'endpoint_margins_m':margins,'endpoint_error_ball_rad':robust,
        'continuous_path_checks':checks,'continuous_path_from_origin_checked':True,
        'global_optimality_proven':False,'physical_invariance_proven':False,
        'feasible':selected is not None,'status':'SELECTED' if selected is not None else 'NO_FEASIBLE_GRID_POINT'}
    if selected is not None:
        target = points[selected]
        record.update(reference_target_rad=target.copy(),signed_offset_rad=target-goal,
            model_endpoint_position_error_ball_rad=float(robust[selected]),
            displacement_norm_rad=float(np.linalg.norm(target-goal)))
    return record

@dataclass(frozen=True)
class TerminalSetDecisionV1(HumanWaypointFeedbackDecisionV1):
    terminal_reference_selection: dict[str, Any] = field(default_factory=dict)

    def record(self) -> dict[str, Any]:
        return {**super().record(), "terminal_reference_selection": self.terminal_reference_selection}


def receipt_reference_at_sample(receipts, sample_time_s):
    """Recover the actual half-open ZOH owner at the immutable sensor source."""
    if not np.isfinite(sample_time_s):
        raise ValueError("nonfinite tracking reference source")
    for index in range(len(receipts)-1, -1, -1):
        receipt = receipts[index]
        if not receipt.get("applied") or receipt["start_physics_s"] > sample_time_s+1e-12:
            continue
        if receipt.get("mode") != "TRACK":
            raise ValueError("tracking error has no TRACK reference at sensor source")
        q, dq = np.asarray(receipt["q_ref_rad"]), np.asarray(receipt["dq_ref_rad_s"])
        if q.shape != (2,) or dq.shape != (2,) or not np.all(np.isfinite(np.r_[q, dq])):
            raise ValueError("invalid receipt-owned tracking reference")
        return {"receipt_index": index, "source_sample_time_s": float(sample_time_s),
            "reference_effective_physics_s": float(receipt["start_physics_s"]),
            "reference_apply_ns": int(receipt["apply_ns"]),
            "q_ref_rad": q.copy(), "dq_ref_rad_s": dq.copy()}
    raise ValueError("missing receipt-owned reference at tracking source")


class TerminalSetHumanWaypointPlannerV1(HumanWaypointFeedbackMPCV1):
    def _evaluate(self, **kwargs: Any):
        evaluated = super()._evaluate(**kwargs)
        if not getattr(self, "causal_tracking_offset_clearance", False) or not evaluated.feasible:
            return evaluated
        # The emitted reference and deployable state are from one immutable
        # request snapshot. Persisting their current position error is only an
        # internal prediction hypothesis, not a bound on future tracking error.
        snapshot = self.tracking_reference_snapshot
        state = np.asarray(kwargs["state"])
        if not np.array_equal(state, np.asarray(snapshot["source_state_rad_rad_s"])):
            raise ValueError("tracking-reference snapshot state mismatch")
        error = state[:2]-np.asarray(snapshot["q_ref_rad"])
        velocity_error = state[2:]-np.asarray(snapshot["dq_ref_rad_s"])
        coefficients = evaluated.schedule.coefficients.copy()
        coefficients[:, 0] += error
        # The scheduler has already certified these exact unshifted
        # coefficients. Reuse its saved per-body lower bounds; retain the
        # original calculation for other clearance implementations.
        certificate = evaluated.schedule.continuous_clearance_certificate
        body_lowers = (certificate.get("combined_body_lowers_m")
                       if isinstance(certificate, dict) else None)
        nominal_lower = (float(min(body_lowers.values()))
                         if body_lowers else float(self.scheduler.clearance_evaluator.certified_minimum(
                             evaluated.schedule.coefficients, evaluated.schedule.duration_s)))
        lower = float(self.scheduler.clearance_evaluator.certified_minimum(
            coefficients, evaluated.schedule.duration_s))
        if not np.all(np.isfinite(error)) or not np.isfinite(lower):
            raise ValueError("nonfinite causal tracking-offset clearance")
        accepted = lower >= 0.0
        record = {
            "source": "immutable request q estimate minus actual receipt-owned q reference at same sensor timestamp",
            "reference_snapshot": snapshot,
            "position_error_rad": error.copy(),
            "velocity_error_rad_s": velocity_error.copy(),
            "schedule_origin_q_rad": evaluated.schedule.coefficients[:, 0].copy(),
            "nominal_continuous_model_clearance_lower_m": nominal_lower,
            "prediction": "constant observed position error added to full candidate reference path",
            "future_error_bound_proven": False,
            "continuous_model_clearance_lower_m": lower,
            "required_lower_m": 0.0,
            "feasible": accepted,
        }
        return replace(evaluated, feasible=accepted,
            total_cost=evaluated.total_cost if accepted else None,
            rejection_reason=None if accepted else "CAUSAL_TRACKING_OFFSET_CLEARANCE",
            execution_screen={**evaluated.execution_screen, "causal_tracking_offset_clearance": record})

    def reference_phase_goal(self, phase: TaskPhase) -> np.ndarray:
        return self.internal_reference_target_rad.copy()

    def note_accepted_decision(self, decision: TerminalSetDecisionV1) -> None:
        # The task worker uses an isolated serialized snapshot; explicitly copy
        # back only this deployable endpoint cache after accepting its decision.
        if decision.phase is not TaskPhase.HOLD:
            record = decision.terminal_reference_selection
            key = _terminal_cache_key(self.scheduler.clearance_evaluator, self.phase_goal(decision.phase), self.spec)
            if key is not None and record.get("feasible"):
                self.terminal_reference_cache = {**getattr(self,"terminal_reference_cache",{}), key: record}

    def decide(self, **kwargs: Any) -> TerminalSetDecisionV1:
        phase = kwargs["phase"]
        original = self.phase_goal(phase)
        reference = np.asarray(kwargs["current_reference_state"])
        clearance = self.scheduler.clearance_evaluator
        if phase is TaskPhase.HOLD and not getattr(self,"robust_hold_reference",False):
            # The accepted OUTBOUND endpoint is the HOLD reference, preserving
            # the C2 boundary instead of jumping back to the exact goal center.
            target = reference[:2].copy()
            selection = {"policy": "retain_accepted_outbound_reference_for_hold",
                         "original_goal_rad": original, "reference_target_rad": target,
                         "signed_offset_rad": target-original,
                         "feasible": in_original_terminal_box(self.spec, target, original)
                             and float(clearance.evaluate(target)) >= 0.0}
        else:
            key = _terminal_cache_key(clearance, original, self.spec)
            cached = getattr(self, "terminal_reference_cache", {}).get(key) if key is not None else None
            selection = None
            if cached is not None:
                target = np.asarray(cached["reference_target_rad"])
                c = _quintic_coefficients(reference[:2],np.zeros(2),target,np.zeros(2),1.0)
                lower = float(clearance.certified_minimum(c,1.0))
                floor = max(0.0,float(np.min(clearance.evaluate(np.vstack([self.spec.start_return_target_rad,original])))))
                if in_original_terminal_box(self.spec,target,original) and float(clearance.evaluate(target)) >= floor and lower >= floor:
                    selection = {**cached, "cache_status": "FIXED_GEOMETRY_PHASE_TARGET_REVALIDATED",
                                 "current_origin_general_certificate_m": lower}
            if selection is None:
                selector = (select_robust_terminal_reference if getattr(self, "robust_terminal_center", False)
                            else select_terminal_reference)
                selection = selector(spec=self.spec, goal=original,
                                     clearance=clearance, origin=reference[:2])
                selection["cache_status"] = "MISS_OR_REVALIDATION_FAILED"
            if selection["feasible"] and key is not None:
                self.terminal_reference_cache = {**getattr(self,"terminal_reference_cache",{}), key: selection}
        self.last_terminal_reference_selection = selection
        if not selection["feasible"]:
            # The exception carries complete search evidence across the worker.
            error = ValueError("TERMINAL_REFERENCE_SEARCH_NO_FEASIBLE_POINT_FOUND")
            error.terminal_reference_selection = selection
            raise error
        self.internal_reference_target_rad = np.asarray(selection["reference_target_rad"]).copy()
        # A new HOLD target must travel through the same constrained quintic
        # path as other waypoints; the legacy constant HOLD would jump at t=0.
        self.scheduler.continuous_hold_reference = bool(getattr(self, "robust_hold_reference", False))
        decision = super().decide(**kwargs)
        return TerminalSetDecisionV1(**decision.__dict__, terminal_reference_selection=selection)
