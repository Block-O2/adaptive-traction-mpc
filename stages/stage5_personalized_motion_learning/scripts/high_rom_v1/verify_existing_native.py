"""Independently score the ten retained Stage-B cases at native 0.25 ms nodes.

Reads one large raw artifact at a time; writes only compact derived evidence.
This evaluation-only script never supplies controller inputs.
"""
from __future__ import annotations

import gc
import argparse
import json
import math
from pathlib import Path
from summarize_phase_b import score

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_v1"
GOAL = math.radians(120.)
POSITION_TOL = math.radians(1.)
SPEED_TOL = math.radians(2.)
NATIVE_DT = .00025


def valid(node: dict, target: tuple[float, float]) -> bool:
    q, dq = node["qpos_evaluation_only"][:2], node["qvel_evaluation_only"][:2]
    return all(abs(q[i] - target[i]) <= POSITION_TOL and abs(dq[i]) <= SPEED_TOL
               for i in range(2))


def longest_valid_run(nodes: list[dict], start_s: float, end_s: float,
                      target: tuple[float, float]) -> tuple[float, float | None, int, int]:
    first = previous = None
    longest = 0.
    max_gap = 0.
    resets = 0
    checked = 0
    for node in nodes:
        t = float(node["time_s"])
        if t < start_s - 1e-10 or t > end_s + 1e-10:
            continue
        checked += 1
        good = valid(node, target)
        contiguous = previous is not None and 0 < t - previous <= NATIVE_DT + 1e-9
        if not good or (first is not None and not contiguous):
            if first is not None:
                longest = max(longest, previous - first)
                resets += 1
            first = None
        if good:
            if first is None:
                first = t
            previous = t
        elif previous is not None:
            previous = None
    if first is not None and previous is not None:
        longest = max(longest, previous - first)
    return float(longest), (None if previous is None else float(previous)), resets, checked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instrumented-rerun-root", type=Path)
    args = parser.parse_args()
    matrix = json.loads((DOC / "PHASE_B_MATRIX.json").read_text())
    old = json.loads((DOC / "PHASE_B_RESULTS.json").read_text())
    cases = {x["case_key"]: x for x in matrix["cases"]}
    rows = []
    for prior in old["rows"]:
        short = prior["case_key"].removeprefix("high_rom_").removesuffix("_v1")
        path = (Path(prior["output"]) if args.instrumented_rerun_root is None
                else args.instrumented_rerun_root / f"{short}_attempt_01")
        summary = json.loads((path / "summary.json").read_text())
        artifact = json.loads((path / "runtime_artifacts.json").read_text())
        wall = artifact["wall_physics"]
        nodes = wall["native_states_evaluation_only"]
        phases = summary["task"]["phase_transitions"]
        outbound_hold = next(x["time_s"] for x in phases if x["to"] == "HOLD")
        hold_return = next(x["time_s"] for x in phases if x["to"] == "RETURN")
        return_complete = next(x["time_s"] for x in phases if x["to"] == "COMPLETE")
        task_start = next(x["start_physics_s"] for x in wall["phase_boundaries"] if x["phase"] == "TASK")
        goal_target = (GOAL, GOAL)
        arrival_nodes = [x for x in nodes if abs(x["time_s"] - outbound_hold) <= NATIVE_DT / 2 + 1e-9]
        arrival_true_valid = bool(len(arrival_nodes) == 1 and valid(arrival_nodes[0], goal_target))
        dwell, dwell_last, resets, checked = longest_valid_run(nodes, outbound_hold, hold_return, goal_target)
        return_nodes = [x for x in nodes if abs(x["time_s"] - return_complete) <= NATIVE_DT / 2 + 1e-9]
        return_true_valid = bool(len(return_nodes) == 1 and valid(return_nodes[0], tuple(map(math.radians, (5., 10.)))))
        monitor = summary["qualification"]["true_physics"]
        all_stage_steps = sum(monitor["step_count"].values())
        ledger = summary["timing"]["requests"]
        activated = [x for x in ledger if x.get("outcome") == "ACTIVATED"]
        stale_activation = [x.get("request_id") for x in activated
                            if x.get("activation_age_ms") is None or x["activation_age_ms"] >= 100.]
        phase_limit_events = wall["phase_limit_violations"]
        causal_dwell = artifact["sample_supported_dwell"]
        causal_credited = sum(float(x.get("credited_s", 0.)) for x in causal_dwell)
        native_load_available = all(k in monitor for k in (
            "maximum_interface_force_n", "maximum_interface_moment_nm",
            "interface_load_observation_count", "missing_interface_load_observation_count"))
        native_load_valid = (native_load_available
            and all(monitor["missing_interface_load_observation_count"][stage] == 0
                    and monitor["interface_load_observation_count"][stage]
                        == monitor["step_count"][stage] + monitor["boundary_observation_count"][stage]
                    for stage in monitor["step_count"])
            and all(monitor["maximum_interface_force_n"][stage] <= 200.
                    and monitor["maximum_interface_moment_nm"][stage] <= 60.
                    for stage in monitor["step_count"]))
        original_score = score(path, cases[prior["case_key"]], matrix["scoring"])
        evidence = dict(case_key=prior["case_key"], output=str(path),
                        native_dt_s=wall["native_dt_s"], native_state_count=len(nodes),
                        native_count_equals_physics_monitor=all_stage_steps == len(nodes),
                        task_start_s=task_start, outbound_to_hold_s=outbound_hold,
                        hold_to_return_s=hold_return, return_complete_s=return_complete,
                        true_arrival_at_hold_boundary=arrival_true_valid,
                        true_native_valid_dwell_s=dwell,
                        true_native_dwell_reset_count=resets,
                        native_dwell_checked_step_count=checked,
                        true_native_dwell_last_valid_s=dwell_last,
                        actual_return_at_completion_boundary=return_true_valid,
                        causal_sample_supported_dwell_entry_count=len(causal_dwell),
                        causal_sample_credited_total_s=causal_credited,
                        task_step_count=monitor["step_count"]["TASK"],
                        task_native_minimum_shank_clearance_m=monitor["minimum_clearance_m"]["TASK"],
                        task_native_shank_bed_contact_steps=monitor["shank_bed_contact_steps"]["TASK"],
                        task_native_rom_violation_steps=monitor["rom_violation_steps"]["TASK"],
                        physical_phase_limit_violation_count=len(phase_limit_events),
                        activated_plan_count=len(activated),
                        stale_or_missing_age_activation_ids=stale_activation,
                        maximum_activated_plan_age_ms=max((x["activation_age_ms"] for x in activated), default=None),
                        native_cuff_force_and_moment_extrema_present=native_load_available,
                        native_load_valid=native_load_valid,
                        native_peak_force_n=(monitor["maximum_interface_force_n"] if native_load_available else None),
                        native_peak_moment_nm=(monitor["maximum_interface_moment_nm"] if native_load_available else None),
                        original_scoring_pass=original_score["pass"],
                        original_scoring_conditions=original_score.get("conditions"))
        evidence["pass_existing_native_task_and_events"] = bool(
            arrival_true_valid and dwell >= .5 and return_true_valid
            and all_stage_steps == len(nodes)
            and monitor["shank_bed_contact_steps"]["TASK"] == 0
            and monitor["rom_violation_steps"]["TASK"] == 0
            and not phase_limit_events and not stale_activation
            and summary["status"] == "COMPLETE" and original_score["pass"]
            and (args.instrumented_rerun_root is None or native_load_valid))
        rows.append(evidence)
        print(json.dumps({k: evidence[k] for k in (
            "case_key", "true_arrival_at_hold_boundary", "true_native_valid_dwell_s",
            "actual_return_at_completion_boundary", "pass_existing_native_task_and_events")} ), flush=True)
        del artifact, wall, nodes
        gc.collect()
    result = dict(schema="high_rom_function_existing_native_evidence_v1",
                  source_matrix_sha256=__import__("hashlib").sha256((DOC / "PHASE_B_MATRIX.json").read_bytes()).hexdigest(),
                  native_step_s=NATIVE_DT, total=len(rows), passed=sum(x["pass_existing_native_task_and_events"] for x in rows),
                  missing_native_load_extrema=args.instrumented_rerun_root is None, rows=rows)
    target = ("HIGH_ROM_FUNCTION_EXISTING10_NATIVE.json" if args.instrumented_rerun_root is None
              else "HIGH_ROM_FUNCTION_RECHECK10_NATIVE.json")
    (DOC / target).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
