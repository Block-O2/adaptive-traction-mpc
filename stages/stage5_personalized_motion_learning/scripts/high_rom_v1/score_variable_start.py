"""Independent, evaluation-only scoring for the registered variable-start 16."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from summarize_phase_b import score
from verify_existing_native import valid, longest_valid_run


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_v1"
SPEC = DOC / "HIGH_ROM_FUNCTION_FRESH16_SPEC.json"
MATRIX = DOC / "PHASE_B_MATRIX.json"
NATIVE_DT = .00025


def score_one(case: dict, path: Path, contract: dict, candidate: str, frozen: dict) -> dict:
    row = score(path, {**case, "physical_variant": "registered_interpolated",
                       "candidate": candidate}, contract, start_deg=case["start_deg"])
    row["registered_start_deg"] = case["start_deg"]
    row["registered_goal_deg"] = case["goal_deg"]
    if row["status"] == "NOT_RUN" or not (path / "runtime_artifacts.json").is_file():
        row["confirmed"] = False
        return row
    launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
    row["same_frozen_candidate"] = (
        launch.get("source_files_sha256") == frozen["runner_source_files_sha256"]
        and launch.get("options_sha256") == frozen["options_sha256"]
        and launch.get("case_sha256") == case["sha256"]
        and launch.get("runtime_path") == str((ROOT / frozen["runtime_relative_path"]).resolve())
    )
    summary = json.loads((path / "summary.json").read_text())
    artifacts = json.loads((path / "runtime_artifacts.json").read_text())
    wall = artifacts["wall_physics"]
    nodes = wall["native_states_evaluation_only"]
    transitions = summary["task"]["phase_transitions"]
    at = lambda phase: next((x["time_s"] for x in transitions if x["to"] == phase), None)
    hold, returning, complete = at("HOLD"), at("RETURN"), at("COMPLETE")
    def boundary(time_s):
        if time_s is None:
            return None
        matches = [x for x in nodes if abs(x["time_s"] - time_s) <= NATIVE_DT / 2 + 1e-9]
        return matches[0] if len(matches) == 1 else None
    goal = tuple(map(math.radians, case["goal_deg"]))
    start = tuple(map(math.radians, case["start_deg"]))
    arrival = boundary(hold)
    returned = boundary(complete)
    dwell = (longest_valid_run(nodes, hold, returning, goal)[0]
             if hold is not None and returning is not None else 0.)
    monitor = summary["qualification"]["true_physics"]
    stages = monitor["step_count"]
    native_count_valid = (wall["native_dt_s"] == NATIVE_DT
                          and len(nodes) == sum(stages.values()))
    load_count_valid = all(
        monitor["missing_interface_load_observation_count"][stage] == 0
        and monitor["interface_load_observation_count"][stage]
            == stages[stage] + monitor["boundary_observation_count"][stage]
        for stage in stages)
    contact_count = sum(monitor["shank_bed_contact_steps"].values())
    rom_count = sum(monitor["rom_violation_steps"].values())
    force = max(monitor["maximum_interface_force_n"].values())
    moment = max(monitor["maximum_interface_moment_nm"].values())
    clearance = min(monitor["minimum_clearance_m"].values())
    activated = [x for x in summary["timing"]["requests"] if x.get("outcome") == "ACTIVATED"]
    stale = [x.get("request_id") for x in activated
             if x.get("activation_age_ms") is None or x["activation_age_ms"] >= 100.]
    row.update(native_arrival=arrival is not None and valid(arrival, goal),
               native_valid_dwell_s=dwell,
               native_return=returned is not None and valid(returned, start),
               native_state_count=len(nodes), native_monitor_count=sum(stages.values()),
               native_count_valid=native_count_valid, native_load_count_valid=load_count_valid,
               native_contact_steps=contact_count, native_rom_violation_steps=rom_count,
               native_minimum_shank_clearance_m=clearance,
               native_peak_force_n=force, native_peak_moment_nm=moment,
               native_phase_limit_violation_count=len(wall["phase_limit_violations"]),
               activated_plan_count=len(activated), stale_activation_ids=stale,
               native_evidence_kind="0.25ms raw q/dq nodes plus monitor cumulative per-step extrema; 5ms sampled sleeve/kinematics in original score")
    row["confirmed"] = bool(
        row["same_frozen_candidate"] and row["pass"] and row["native_arrival"]
        and dwell >= .5 and row["native_return"] and native_count_valid
        and load_count_valid and contact_count == 0 and rom_count == 0
        and force <= 200. and moment <= 60. and clearance >= 0.
        and not wall["phase_limit_violations"] and not stale)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text())
    contract = json.loads(MATRIX.read_text())["scoring"]
    frozen = json.loads((DOC / "VARIABLE_START_FROZEN_CANDIDATE.json").read_text())
    run_root = STAGE / "results/high_rom_v1/variable_start_v1"
    rows = []
    for index, case in enumerate(spec["cases"], start=1):
        name = f"trial_fresh_{index:02d}" if index <= 2 else f"case_{index:02d}"
        rows.append(score_one(case, run_root / name, contract, spec["candidate"], frozen))
        print(json.dumps({"case": index, "status": rows[-1]["status"],
                          "confirmed": rows[-1]["confirmed"]}), flush=True)
    result = {"schema": "high_rom_variable_start_confirmation_v1",
              "preregistration_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
              "frozen_candidate_sha256": hashlib.sha256((DOC / "VARIABLE_START_FROZEN_CANDIDATE.json").read_bytes()).hexdigest(),
              "denominator": 16,
              "executed": sum(x["status"] != "NOT_RUN" for x in rows),
              "confirmed_count": sum(x["confirmed"] for x in rows),
              "rows": rows}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
