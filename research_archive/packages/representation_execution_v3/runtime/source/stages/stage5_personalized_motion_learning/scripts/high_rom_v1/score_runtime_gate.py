"""Score the frozen eight development timing cases from original native evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from score_variable_start import score_one
from summarize_phase_b import score

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_runtime_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=("06", "07", "08"), required=True)
    args = parser.parse_args()
    freeze = json.loads((DOC / f"CANDIDATE{args.candidate}_FREEZE.json").read_text())
    for relative, expected in freeze["source_config_sha256"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"candidate source/config drift: {relative}")
    spec = json.loads((DOC / "BENCHMARK_SPEC.json").read_text())
    contract = json.loads((STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json").read_text())["scoring"]
    run_root = STAGE / f"results/high_rom_runtime_v1/candidate{args.candidate}_gate"
    first = json.loads((run_root / spec["cases"][0]["id"] / "HIGH_ROM_CASE_RESULT.json").read_text())
    frozen = {"runner_source_files_sha256": first["source_files_sha256"],
              "options_sha256": first["options_sha256"],
              "runtime_relative_path": "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py"}
    rows = []
    for entry in spec["cases"]:
        case_path = STAGE / entry["case"]
        case_data = json.loads(case_path.read_text())
        case = {"case_key": entry["id"], "path": str(case_path.relative_to(ROOT)),
                "sha256": freeze["benchmark_case_sha256"][entry["id"]],
                "start_deg": case_data["task"]["start_deg"],
                "goal_deg": case_data["task"]["goal_deg"]}
        if hashlib.sha256(case_path.read_bytes()).hexdigest() != case["sha256"]:
            raise RuntimeError(f"benchmark case drift: {entry['id']}")
        path = run_root / entry["id"]
        row = score_one(case, path, contract,
                        case_data.get("candidate", entry["plant"]), frozen)
        # The retained variable-start helper uses 120/120 as its sampled
        # default. Restore each registered goal for the sampled task scorer;
        # its native-node scorer above already used the per-case goal.
        row.update(score(path, {**case,
                                "physical_variant": ("original_low_rom" if entry["plant"] == "low_rom"
                                                     else "registered_interpolated"),
                                "candidate": case_data.get("candidate", entry["plant"])},
                         contract, goal_deg=case["goal_deg"], start_deg=case["start_deg"]))
        launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
        snapshot = json.loads((path / "config_snapshot.json").read_text())
        plant_ok = (launch["plant_mode"] == entry["plant"] and
                    snapshot["human_hard_rom_deg"] == (
                        [[0.0, 80.0], [0.0, 100.0]] if entry["plant"] == "low_rom"
                        else [[0.0, 125.0], [0.0, 125.0]]))
        row["plant_valid"] = plant_ok
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
                                and native_valid and plant_ok)
        row["id"] = entry["id"]
        rows.append(row)
        print(json.dumps({"id": entry["id"], "confirmed": row["confirmed"]}), flush=True)
    result = {"schema": "high_rom_runtime_eight_case_function_scoring_v1",
              "candidate": args.candidate, "denominator": len(rows),
              "confirmed": sum(row["confirmed"] for row in rows),
              "minimum_native_dwell_s": min(row["native_valid_dwell_s"] for row in rows),
              "minimum_native_clearance_m": min(row["native_minimum_shank_clearance_m"] for row in rows),
              "maximum_native_force_n": max(row["native_peak_force_n"] for row in rows),
              "maximum_native_moment_nm": max(row["native_peak_moment_nm"] for row in rows),
              "stale_activated": sum(len(row["stale_activation_ids"]) for row in rows),
              "rows": rows}
    (DOC / f"CANDIDATE{args.candidate}_FUNCTION.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: result[key] for key in ("denominator", "confirmed",
        "minimum_native_dwell_s", "minimum_native_clearance_m", "maximum_native_force_n",
        "maximum_native_moment_nm", "stale_activated")}, indent=2))


if __name__ == "__main__":
    main()
