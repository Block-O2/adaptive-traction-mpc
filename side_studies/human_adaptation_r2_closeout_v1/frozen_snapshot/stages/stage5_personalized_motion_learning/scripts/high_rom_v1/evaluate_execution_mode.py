"""Add mode validity to an unchanged Stage-B scorer-v2 result."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from summarize_phase_b import ROOT, DOC, score

MODES = {"REALTIME_CHARACTERIZATION", "SCIENTIFIC_SIMULATION"}
VERSION_FIELDS = ("episode_epoch", "state_version", "physics_step", "sim_time_s",
                  "phase_version", "human_model_version", "reference_version")


def evaluate(path: Path, case: dict, scoring: dict, *, goal_deg=(120., 120.),
             start_deg=(5., 10.)) -> dict:
    launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
    summary = json.loads((path / "summary.json").read_text())
    artifacts = json.loads((path / "runtime_artifacts.json").read_text())
    modes = [launch.get("execution_mode"), summary.get("execution_mode"),
             artifacts.get("execution_mode")]
    if modes[0] not in MODES or modes != [modes[0]] * 3:
        raise ValueError(f"execution_mode absent, unknown or inconsistent: {modes}")
    mode = modes[0]
    raw = score(path, case, scoring, goal_deg=goal_deg, start_deg=start_deg)
    conditions = raw.get("conditions", {})
    common = {key: value for key, value in conditions.items() if key != "plan_age"}
    if not common or "plan_age" not in conditions:
        raise ValueError("incomplete scorer-v2 conditions")
    trace = np.load(path / "trace.npz")
    finite_keys = ("time_s", "evaluation_only_human_state_rad_rad_s",
                   "estimated_human_state_rad_rad_s", "cr12_q_rad", "cr12_dq_rad_s")
    finite_trace = all(np.all(np.isfinite(trace[key])) for key in finite_keys)
    native = artifacts["wall_physics"]["native_states_evaluation_only"]
    finite_native = all(np.all(np.isfinite(row[key])) for row in native
                        for key in ("qpos_evaluation_only", "qvel_evaluation_only", "command_torque_nm"))
    validations = artifacts["activation_validations"]
    certificates = all(row.get("feasible") is True and row.get("reference_continuity") is True
                       and row.get("truth_consumed") is False for row in validations)
    c2 = summary["timing"].get("all_reference_boundaries_q_dq_ddq_continuous") is True
    physical_reasons = [key for key, value in common.items() if not value]
    if launch.get("status") != "COMPLETE" or summary.get("status") != "COMPLETE":
        physical_reasons.append("not_complete")
    if not finite_trace or not finite_native:
        physical_reasons.append("nonfinite_physical_state")
    if not certificates:
        physical_reasons.append("activation_certificate_or_C2")
    if not c2:
        physical_reasons.append("reference_boundary_C2")
    physical = {"status": "PASS" if not physical_reasons else "FAIL",
                "reasons": physical_reasons, "scorer_v2_common_conditions": common,
                "finite_trace": bool(finite_trace), "finite_native": bool(finite_native),
                "activation_certificates_valid": bool(certificates),
                "reference_boundary_C2": bool(c2)}
    requests = summary["timing"]["requests"]
    if requests != artifacts["requests"]:
        raise ValueError("summary/runtime request record disagreement")
    wall_age = raw.get("maximum_plan_activation_age_ms")
    wall = {"maximum_plan_source_to_activation_age_ms": wall_age,
            "maximum_planner_compute_ms": max((r.get("compute_ms") or 0 for r in requests), default=None),
            "maximum_validation_to_activation_ms": max((r.get("validation_to_activation_ms") or 0 for r in requests), default=None),
            "injected_host_delay_ms": launch.get("scientific_host_delay_ms"),
            "host_elapsed_s": launch.get("elapsed_host_s"),
            "realtime_stale_counterfactual": wall_age is None or wall_age >= scoring["plan_max_activation_age_ms"]}
    scientific = {"status": "N/A", "reasons": [], "request_checks": []}
    realtime = {"status": "N/A", "reasons": [], "wall_age_ms": wall_age,
                "strict_age_limit_ms": scoring["plan_max_activation_age_ms"]}
    if mode == "SCIENTIFIC_SIMULATION":
        scientific["status"] = "PASS"
        if not requests:
            scientific["reasons"].append("no_requests")
        for row in requests:
            reasons = []
            source = row.get("source_simulation_version")
            receipt = row.get("receipt_simulation_version")
            activation = row.get("activation_simulation_version")
            if not source or not receipt or not activation or any(
                    key not in version for version in (source, receipt, activation)
                    for key in VERSION_FIELDS):
                reasons.append("missing_version_vector")
            else:
                if source != receipt:
                    reasons.append("source_receipt_version_changed")
                if source["episode_epoch"] != activation["episode_epoch"]:
                    reasons.append("activation_epoch_changed")
                if source["phase_version"] != activation["phase_version"]:
                    reasons.append("activation_phase_changed")
                if source["human_model_version"] != activation["human_model_version"] and not any(
                        str(v.get("request_model_sequence")) == source["human_model_version"]
                        and str(v.get("activation_model_sequence")) == activation["human_model_version"]
                        and v.get("feasible") is True for v in validations):
                    reasons.append("changed_model_without_fresh_validation")
                if activation["physics_step"] < source["physics_step"]:
                    reasons.append("physics_step_reversed")
                if not 0 <= activation["sim_time_s"] - source["sim_time_s"] < .100 - 1e-12:
                    reasons.append("simulated_source_age_stale")
            if row.get("outcome") != "ACTIVATED":
                reasons.append("request_not_activated")
            if row.get("execution_mode") != mode:
                reasons.append("request_mode_mismatch")
            scientific["request_checks"].append({"request_id": row["request_id"], "reasons": reasons,
                                                 "source": source, "receipt": receipt,
                                                 "activation": activation})
            scientific["reasons"].extend(f"request_{row['request_id']}:{reason}" for reason in reasons)
        if not certificates:
            scientific["reasons"].append("activation_certificate_or_C2")
        if any(event.get("native_steps") != 0 for event in artifacts["wall_physics"]["catchup_intervals"]):
            scientific["reasons"].append("physics_advanced_during_host_catchup")
        if scientific["reasons"]:
            scientific["status"] = "FAIL"
    else:
        if not conditions["plan_age"]:
            realtime["reasons"].append("plan_age")
        if any(row.get("outcome") in ("ACTIVATION_DEADLINE_MISS", "EXPIRED") for row in requests):
            realtime["reasons"].append("stale_or_deadline_miss")
        physics = artifacts["wall_physics"]
        if physics.get("control_cycle_misses", 0):
            realtime["reasons"].append("control_cycle_miss")
        if any(row.get("native_steps", 0) > 20 for row in physics["command_receipts"]):
            realtime["reasons"].append("command_gap")
        if any(row.get("event") == "FALLBACK_COMMITTED" and row.get("reason") == "HOST_LATENCY"
               for row in artifacts["safe_fallback_events"]):
            realtime["reasons"].append("host_lateness_fallback")
        realtime["status"] = "PASS" if not realtime["reasons"] else "FAIL"
    overall = physical["status"] == "PASS" and (
        scientific["status"] == "PASS" if mode == "SCIENTIFIC_SIMULATION"
        else realtime["status"] == "PASS")
    return {"schema": "mode_aware_execution_result_v1", "execution_mode": mode,
            "physical_task_result": physical, "scientific_validity": scientific,
            "realtime_execution_validity": realtime,
            "wall_runtime_characterization": wall,
            "overall_result_for_mode": "PASS" if overall else "FAIL",
            "raw_scorer_v2": raw,
            "historical_runtime_status": "RSS_RUNTIME_QUALIFICATION_NOT_MET"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case-key")
    group.add_argument("--case", type=Path)
    args = parser.parse_args()
    matrix = json.loads((DOC / "PHASE_B_MATRIX.json").read_text())
    if args.case is None:
        case = next(c for c in matrix["cases"] if c["case_key"] == args.case_key)
        goal, start = matrix["goal_deg"], (5., 10.)
    else:
        source = args.case.resolve()
        data = json.loads(source.read_text())
        case = dict(case_key=data["case_key"], physical_variant=data["cell"]["family"],
                    candidate=data.get("coordination_candidate", "low_rom_registered"),
                    path=str(source.relative_to(ROOT)), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        goal, start = data["task"]["goal_deg"], data["task"]["start_deg"]
    result = evaluate(args.run, case, matrix["scoring"], goal_deg=goal, start_deg=start)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"mode": result["execution_mode"], "result": result["overall_result_for_mode"],
                      "physical": result["physical_task_result"]["status"],
                      "scientific": result["scientific_validity"]["status"],
                      "realtime": result["realtime_execution_validity"]["status"]}))


if __name__ == "__main__":
    main()
