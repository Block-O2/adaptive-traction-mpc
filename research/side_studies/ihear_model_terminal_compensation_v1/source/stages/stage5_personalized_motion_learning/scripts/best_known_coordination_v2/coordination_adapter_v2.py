"""Exploration-only phase-path deformation through the unchanged planner screens."""
from __future__ import annotations

from copy import copy
from dataclasses import replace
import json
import math
import os
import pickle

import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import TerminalSetHumanWaypointPlannerV1
from traction_mpc_stage5.task import TaskPhase

SPEC_ENV = "BEST_KNOWN_COORDINATION_SPEC_V2"


def shape(s: float, peak: float) -> float:
    """Smooth endpoint-zero lead/catch-up bump, normalized to one at peak."""
    if not 0.0 < peak < 1.0:
        raise ValueError("peak must be interior")
    s = min(1.0, max(0.0, s))
    a, b = 2.0 * (1.0 - peak), 2.0 * peak
    return (s / peak) ** a * ((1.0 - s) / (1.0 - peak)) ** b


class CoordinationSearchPlannerV2(TerminalSetHumanWaypointPlannerV1):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = os.environ.get(SPEC_ENV)
        if not raw:
            raise RuntimeError("missing frozen coordination specification")
        self.coordination_spec = json.loads(raw)
        spec = self.coordination_spec
        from coordination_space import parameters
        parameters(spec)
        if spec['arm'] not in ('NATIVE','MATCHED'):
            raise ValueError('invalid search arm')
        self.coordination_phase_index = 0

    def decide(self, **kwargs):
        original = super().decide(**kwargs)
        spec = self.coordination_spec
        phase = kwargs["phase"]
        if phase is TaskPhase.HOLD:
            return original
        index = getattr(self, "coordination_phase_index", sum(d.phase is phase for d in self.decisions) - 1)
        from coordination_space import parameters, phase_active, deformation
        p = parameters(spec)
        if spec['arm'] == 'NATIVE' and not phase_active(p, phase.value):
            return original
        source = spec['baseline_waypoints'].get(phase.value, [])
        if index >= len(source):
            raise ValueError('COORDINATION_INFEASIBLE:baseline waypoint count exhausted')
        item = source[index]
        start = self.start_rad if phase is TaskPhase.OUTBOUND else self.goal_rad
        goal = self.goal_rad if phase is TaskPhase.OUTBOUND else self.start_rad
        span = goal - start
        base = np.asarray(item['target_q_rad'], dtype=float)
        progress = (base-start)/span
        s = float(np.mean(progress))
        target = base if index == len(source)-1 else base+span*deformation(s,phase.value,spec)
        if np.allclose(target,original.executed.target_q_rad,atol=1e-12,rtol=0.) and spec['arm']=='NATIVE':
            return original
        state = np.asarray(kwargs["current_deployable_state"], dtype=float)
        reference = np.asarray(kwargs["current_reference_state"], dtype=float)
        alternative = self._evaluate(
            label=f"coord_{phase.value.lower()}_{index:02d}", state=state,
            reference_state=reference, phase=phase,
            phase_elapsed_s=kwargs["phase_elapsed_s"],
            phase_remaining_s=kwargs["phase_remaining_s"],
            action=target - state[:2],
            execution_feasibility_checker=kwargs.get("execution_feasibility_checker"),
            value_state_or_belief=kwargs.get("value_state_or_belief"),
            candidate_value_evaluator=kwargs.get("candidate_value_evaluator"),
        )
        if not alternative.feasible:
            raise ValueError("COORDINATION_INFEASIBLE:" + str(alternative.rejection_reason))
        if spec["arm"] == "MATCHED":
            period = self.scheduler.reference_period_s
            duration = round(float(item["duration_s"]) * float(spec.get("matched_duration_factor", 1.0)) / period) * period
            try:
                fixed = self.scheduler.plan_fixed_duration_reference_contract(
                    current_q_hat_rad=reference[:2], current_dq_hat_rad_s=reference[2:],
                    candidate=alternative.schedule.candidate, duration_s=duration,
                    phase_elapsed_s=kwargs["phase_elapsed_s"],
                )
            except ValueError as exc:
                raise ValueError("MATCHED_PACING_INFEASIBLE:" + str(exc)) from exc
            checker = kwargs.get("execution_feasibility_checker")
            screen = {"evaluated": False, "feasible": True} if checker is None else dict(checker(fixed.candidate, fixed))
            if not screen.get("feasible", True):
                raise ValueError("MATCHED_PACING_INFEASIBLE:" + str(screen.get("rejection_reason")))
            # Preserve TerminalSetHumanWaypointPlannerV1._evaluate's causal
            # receipt-owned offset clearance on the *replacement* polynomial.
            # Reusing its earlier shortest-schedule certificate would be wrong.
            if getattr(self, "causal_tracking_offset_clearance", False):
                snapshot = self.tracking_reference_snapshot
                if not np.array_equal(state, np.asarray(snapshot["source_state_rad_rad_s"])):
                    raise ValueError("tracking-reference snapshot state mismatch")
                offset = state[:2] - np.asarray(snapshot["q_ref_rad"])
                velocity_error = state[2:] - np.asarray(snapshot["dq_ref_rad_s"])
                shifted = fixed.coefficients.copy()
                shifted[:, 0] += offset
                certificate = fixed.continuous_clearance_certificate
                lowers = certificate.get("combined_body_lowers_m") if isinstance(certificate, dict) else None
                nominal_lower = (float(min(lowers.values())) if lowers else
                    float(self.scheduler.clearance_evaluator.certified_minimum(fixed.coefficients, fixed.duration_s)))
                lower = float(self.scheduler.clearance_evaluator.certified_minimum(shifted, fixed.duration_s))
                if not np.all(np.isfinite(offset)) or not np.isfinite(lower):
                    raise ValueError("nonfinite causal tracking-offset clearance")
                causal = {"source": "immutable request q estimate minus actual receipt-owned q reference at same sensor timestamp",
                    "reference_snapshot": snapshot, "position_error_rad": offset.copy(),
                    "velocity_error_rad_s": velocity_error.copy(),
                    "schedule_origin_q_rad": fixed.coefficients[:, 0].copy(),
                    "nominal_continuous_model_clearance_lower_m": nominal_lower,
                    "prediction": "constant observed position error added to full candidate reference path",
                    "future_error_bound_proven": False,
                    "continuous_model_clearance_lower_m": lower,
                    "required_lower_m": 0.0, "feasible": lower >= 0.0}
                screen = {**screen, "causal_tracking_offset_clearance": causal}
                if not causal["feasible"]:
                    raise ValueError("MATCHED_PACING_INFEASIBLE:CAUSAL_TRACKING_OFFSET_CLEARANCE")
            alternative = replace(alternative, schedule=fixed, execution_screen=screen)
        chosen = replace(original, executed=alternative,
                         selection_mode="coordination_pacing_counterfactual",
                         evaluations=original.evaluations + (alternative,))
        self.decisions[-1] = chosen
        self.previous_executed_delta_q_rad = alternative.proposed_delta_q_rad.copy()
        return chosen


def snapshot_search_task_call(adaptive_planner, arguments):
    snapshot = copy(adaptive_planner)
    snapshot.planner = copy(adaptive_planner.planner)
    snapshot.planner.coordination_phase_index = sum(
        d.phase is arguments["phase"] for d in adaptive_planner.planner.decisions)
    snapshot.planner.decisions = []
    snapshot.belief_sequences_used = []
    return pickle.dumps((snapshot, arguments), protocol=pickle.HIGHEST_PROTOCOL)
