"""Mode-aware V2 baseline acceptance; scorer-v2 and runtime remain unchanged."""
from __future__ import annotations

import math

import numpy as np


SCIENTIFIC = "SCIENTIFIC_SIMULATION"


def assess(summary: dict, mode: dict, artifacts: dict, costs: dict,
           decisions: list[dict]) -> dict:
    """Evaluate existing mode-aware and raw-scorer results without rescoring.

    The caller must have run the unchanged evaluate_execution_mode.evaluate,
    which invokes the real historical scorer. This function checks cross-result
    consistency and adds the frozen baseline-specific lifecycle/accounting gate.
    """
    reasons: list[str] = []
    execution_mode = mode.get("execution_mode")
    if (execution_mode != SCIENTIFIC or summary.get("execution_mode") != SCIENTIFIC
            or artifacts.get("execution_mode") != SCIENTIFIC):
        reasons.append("execution_mode")
    raw = mode.get("raw_scorer_v2", {})
    conditions = raw.get("conditions", {})
    if (not isinstance(conditions, dict) or "plan_age" not in conditions
            or not conditions or any(type(v) is not bool for v in conditions.values())):
        reasons.append("raw_scorer_conditions_missing")
        common = {}
    else:
        common = {key: value for key, value in conditions.items() if key != "plan_age"}
        if not common or not all(common.values()):
            reasons.append("scorer_v2_physical_or_terminal")
        if raw.get("pass") is not all(conditions.values()):
            reasons.append("raw_scorer_consistency")
    physical = mode.get("physical_task_result", {})
    scientific = mode.get("scientific_validity", {})
    if physical.get("status") != "PASS":
        reasons.append("physical")
    if common and physical.get("scorer_v2_common_conditions") != common:
        reasons.append("physical_scorer_disagreement")
    if scientific.get("status") != "PASS":
        reasons.append("scientific")
    if scientific.get("reasons"):
        reasons.append("scientific_provenance")
    checks = scientific.get("request_checks")
    if not isinstance(checks, list) or not checks or any(x.get("reasons") for x in checks):
        reasons.append("scientific_request_provenance")
    if mode.get("overall_result_for_mode") != "PASS":
        reasons.append("mode_aware_overall")
    if summary.get("status") != "COMPLETE":
        reasons.append("not_complete")
    transitions = summary.get("task", {}).get("phase_transitions", [])
    if [x.get("to") for x in transitions] != ["HOLD", "RETURN", "COMPLETE"]:
        reasons.append("phase_sequence")
    if not math.isfinite(float(costs.get("J_F_n_s", float("nan")))):
        reasons.append("nonfinite_force_cost")
    elif not np.isclose(costs["J_F_n_s"], summary["task"]["force_integral_n_s"],
                        rtol=0, atol=1e-8):
        reasons.append("force_cost_disagrees_with_trace")
    if not summary.get("task", {}).get("boundary_interval_relation_holds"):
        reasons.append("boundary_interval_relation")
    if costs.get("interval_count") != summary.get("task", {}).get("integration_interval_count"):
        reasons.append("interval_count")
    if not decisions:
        reasons.append("no_waypoint_decisions")
    if any(d.get("learned_value") != 0 or d.get("RL") != "OFF" for d in decisions):
        reasons.append("zero_value_invariant")

    requests = artifacts.get("requests", [])
    wall = mode.get("wall_runtime_characterization", {})
    age = raw.get("maximum_plan_activation_age_ms")
    stale = age is None or not math.isfinite(float(age)) or age >= 100.0
    realtime_reasons = []
    if stale or conditions.get("plan_age") is not True:
        realtime_reasons.append("plan_age")
    if any(x.get("outcome") in ("ACTIVATION_DEADLINE_MISS", "EXPIRED") for x in requests):
        realtime_reasons.append("stale_or_deadline_miss")
    physics = artifacts.get("wall_physics", {})
    if physics.get("control_cycle_misses", 0):
        realtime_reasons.append("control_cycle_miss")
    if any(x.get("native_steps", 0) > 20 for x in physics.get("command_receipts", [])):
        realtime_reasons.append("command_gap")
    if any(x.get("event") == "FALLBACK_COMMITTED" and x.get("reason") == "HOST_LATENCY"
           for x in artifacts.get("safe_fallback_events", [])):
        realtime_reasons.append("host_lateness_fallback")
    characterization = {
        **wall,
        "raw_plan_age_condition": conditions.get("plan_age"),
        "max_wall_plan_age_ms": age,
        "counterfactual_realtime_validity": "FAIL" if realtime_reasons else "PASS",
        "counterfactual_realtime_reasons": realtime_reasons,
        "source_age_wall_ms": wall.get("maximum_plan_source_to_activation_age_ms"),
        "activation_latency_ms": wall.get("maximum_validation_to_activation_ms"),
        "control_cycle_misses": physics.get("control_cycle_misses", 0),
        "command_gap_count": sum(x.get("native_steps", 0) > 20
                                 for x in physics.get("command_receipts", [])),
    }
    return {
        "physical_task_validity": physical.get("status"),
        "scientific_validity": scientific.get("status"),
        "raw_scorer_v2_result": {
            "pass": raw.get("pass"), "conditions": conditions,
            "maximum_plan_activation_age_ms": age},
        "realtime_characterization": characterization,
        "overall_baseline_scientific_result": "PASS" if not reasons else "FAIL",
        "gate_reasons": reasons,
    }
