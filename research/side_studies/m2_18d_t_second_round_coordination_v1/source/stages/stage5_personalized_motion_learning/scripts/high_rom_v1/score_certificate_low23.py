"""Independent native and sampled scoring for the frozen candidate08 low23."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from score_variable_start import score_one
from summarize_phase_b import score

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_runtime_v1"
PLAN = DOC / "CANDIDATE08_LOW23_PLAN.json"
OUTPUT = STAGE / "results/high_rom_runtime_v1/candidate08_low23"


def main() -> None:
    plan = json.loads(PLAN.read_text())
    assert len(plan["rows"]) == plan["denominator"] == 23
    for relative, expected in plan["source_config_sha256"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"candidate source/config drift: {relative}")
    contract = json.loads((STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json").read_text())["scoring"]
    first = json.loads((OUTPUT / plan["rows"][0]["id"] / "HIGH_ROM_CASE_RESULT.json").read_text())
    frozen = {"runner_source_files_sha256": first["source_files_sha256"],
              "options_sha256": first["options_sha256"],
              "runtime_relative_path": "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py"}
    rows = []
    for index, entry in enumerate(plan["rows"]):
        case_path = ROOT / entry["case"]
        if hashlib.sha256(case_path.read_bytes()).hexdigest() != entry["case_sha256"]:
            raise RuntimeError(f"registered case drift: {entry['id']}")
        data = json.loads(case_path.read_text())
        case = {"case_key": entry["id"], "path": entry["case"],
                "sha256": entry["case_sha256"],
                "start_deg": data["task"]["start_deg"],
                "goal_deg": data["task"]["goal_deg"]}
        path = OUTPUT / entry["id"]
        row = score_one(case, path, contract, "original_low_rom_feedback", frozen)
        row.update(score(path, {**case, "physical_variant": "original_low_rom",
                                "candidate": "original_low_rom_feedback"},
                         contract, goal_deg=case["goal_deg"], start_deg=case["start_deg"]))
        launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
        snapshot = json.loads((path / "config_snapshot.json").read_text())
        row["plant_valid"] = (launch["plant_mode"] == "low_rom" and
                              snapshot["human_hard_rom_deg"] == [[0.0, 80.0], [0.0, 100.0]])
        row["case_valid"] = launch["case_sha256"] == entry["case_sha256"]
        native_valid = (row["native_arrival"] and row["native_valid_dwell_s"] >= .5
                        and row["native_return"] and row["native_count_valid"]
                        and row["native_load_count_valid"]
                        and row["native_contact_steps"] == 0
                        and row["native_rom_violation_steps"] == 0
                        and row["native_peak_force_n"] <= 200.
                        and row["native_peak_moment_nm"] <= 60.
                        and row["native_minimum_shank_clearance_m"] >= 0.
                        and row["native_phase_limit_violation_count"] == 0
                        and not row["stale_activation_ids"])
        row["confirmed"] = bool(row["same_frozen_candidate"] and row["pass"]
                                and native_valid and row["plant_valid"] and row["case_valid"])
        row["id"] = entry["id"]
        row["reused_same_source_gate"] = index in {int(k) for k in plan["reuse_from_same_source_gate"]}
        rows.append(row)
        print(json.dumps({"index": index, "id": entry["id"],
                          "confirmed": row["confirmed"]}), flush=True)
    result = {"schema": "high_rom_runtime_candidate08_low23_confirmation_v1",
              "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
              "denominator": 23, "executed": len(rows),
              "confirmed": sum(x["confirmed"] for x in rows),
              "reused_same_source_gate": sum(x["reused_same_source_gate"] for x in rows),
              "minimum_native_dwell_s": min(x["native_valid_dwell_s"] for x in rows),
              "minimum_native_clearance_m": min(x["native_minimum_shank_clearance_m"] for x in rows),
              "maximum_native_force_n": max(x["native_peak_force_n"] for x in rows),
              "maximum_native_moment_nm": max(x["native_peak_moment_nm"] for x in rows),
              "stale_activated": sum(len(x["stale_activation_ids"]) for x in rows),
              "rows": rows}
    (DOC / "CANDIDATE08_LOW23_RESULT.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: result[key] for key in (
        "denominator", "executed", "confirmed", "reused_same_source_gate",
        "minimum_native_dwell_s", "minimum_native_clearance_m",
        "maximum_native_force_n", "maximum_native_moment_nm", "stale_activated")}, indent=2))


if __name__ == "__main__":
    main()
