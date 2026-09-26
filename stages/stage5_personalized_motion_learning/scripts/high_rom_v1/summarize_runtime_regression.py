"""Score the frozen 49-case runtime regression from retained raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_variable_start import score_one
from summarize_phase_b import score

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_runtime_v1"
PLAN = DOC / "CANDIDATE03_REGRESSION_PLAN.json"
OUTPUT = STAGE / "results/high_rom_runtime_v1/candidate03_regression"


def main() -> None:
    plan = json.loads(PLAN.read_text())
    for relative, expected in plan["source_config_sha256"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"candidate source/config drift: {relative}")
    contract = json.loads((STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json").read_text())["scoring"]
    first = json.loads((OUTPUT / plan["rows"][0]["id"] / "HIGH_ROM_CASE_RESULT.json").read_text())
    runtime_relative_path = "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py"
    frozen = {"runner_source_files_sha256": first["source_files_sha256"],
              "options_sha256": first["options_sha256"],
              "runtime_relative_path": runtime_relative_path}
    rows = []
    for entry in plan["rows"]:
        case_path = ROOT / entry["case"]
        data = json.loads(case_path.read_text())
        case = {"case_key": entry["id"], "path": entry["case"],
                "sha256": entry["case_sha256"],
                "start_deg": data["task"]["start_deg"],
                "goal_deg": data["task"]["goal_deg"]}
        row = score_one(case, OUTPUT / entry["id"], contract,
                        data.get("candidate", entry["plant"]), frozen)
        if entry["plant"] == "low_rom":
            # The retained variable-start helper calls its sampled scorer
            # with the High-ROM 120-degree default. Restore the registered
            # per-case low-ROM goal without changing that historical helper.
            sampled = score(OUTPUT / entry["id"],
                            {**case, "physical_variant": "original_low_rom",
                             "candidate": "original_low_rom_feedback"},
                            contract, goal_deg=case["goal_deg"],
                            start_deg=case["start_deg"])
            row.update(sampled)
        launch = json.loads((OUTPUT / entry["id"] / "HIGH_ROM_CASE_RESULT.json").read_text())
        snapshot = json.loads((OUTPUT / entry["id"] / "config_snapshot.json").read_text())
        row["plant_mode_valid"] = launch["plant_mode"] == entry["plant"]
        row["full_case_hash_valid"] = launch["case_sha256"] == entry["case_sha256"]
        row["runner_source_same"] = launch["source_files_sha256"] == frozen["runner_source_files_sha256"]
        row["plant_hard_rom_deg"] = snapshot["human_hard_rom_deg"]
        row["plant_rom_valid"] = snapshot["human_hard_rom_deg"] == (
            [[0.0, 80.0], [0.0, 100.0]] if entry["plant"] == "low_rom"
            else [[0.0, 125.0], [0.0, 125.0]])
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
        row["confirmed"] = bool(row["pass"] and row["same_frozen_candidate"]
                                and native_valid and row["plant_mode_valid"]
                                and row["full_case_hash_valid"] and row["runner_source_same"]
                                and row["plant_rom_valid"])
        rows.append(row)
        print(json.dumps({"id": entry["id"], "confirmed": row["confirmed"]}), flush=True)
    result = {"schema": "high_rom_runtime_candidate03_regression_v1",
              "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
              "denominator": plan["denominator"], "executed": len(rows),
              "confirmed": sum(r["confirmed"] for r in rows),
              "low_rom": {"total": 23, "confirmed": sum(r["confirmed"] for r in rows[:23])},
              "high_rom_fixed": {"total": 10, "confirmed": sum(r["confirmed"] for r in rows[23:33])},
              "high_rom_variable": {"total": 16, "confirmed": sum(r["confirmed"] for r in rows[33:])},
              "minimum_native_dwell_s": min(r["native_valid_dwell_s"] for r in rows),
              "minimum_native_clearance_m": min(r["native_minimum_shank_clearance_m"] for r in rows),
              "minimum_sampled_sleeve_gap_m": min(r["minimum_measured_sleeve_gap_m"] for r in rows),
              "maximum_native_force_n": max(r["native_peak_force_n"] for r in rows),
              "maximum_native_moment_nm": max(r["native_peak_moment_nm"] for r in rows),
              "maximum_activation_age_ms": max(r["maximum_all_stage_plan_activation_age_ms"]
                                               if r.get("maximum_all_stage_plan_activation_age_ms") is not None
                                               else r["maximum_plan_activation_age_ms"] for r in rows),
              "stale_activated": sum(len(r["stale_activation_ids"]) for r in rows),
              "rows": rows}
    path = DOC / "CANDIDATE03_REGRESSION.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("denominator", "confirmed", "low_rom",
                       "high_rom_fixed", "high_rom_variable", "minimum_native_dwell_s",
                       "minimum_native_clearance_m", "minimum_sampled_sleeve_gap_m",
                       "maximum_native_force_n", "maximum_native_moment_nm",
                       "maximum_activation_age_ms", "stale_activated")}, indent=2))


if __name__ == "__main__":
    main()
