"""Score the fixed 23 original-ROM cases on the Stage-B source revision."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from summarize_phase_b import DOC, OUT, ROOT, STAGE, score


def main() -> None:
    manifest_path = DOC / "PHASE_B_LOW_ROM_REGRESSION.json"
    manifest = json.loads(manifest_path.read_text())
    contract = json.loads((DOC / "PHASE_B_MATRIX.json").read_text())["scoring"]
    output_root = STAGE / "results/high_rom_v1/low_rom_regression"
    rows = []
    high_rom_results = json.loads((DOC / "PHASE_B_RESULTS.json").read_text())
    high_source = high_rom_results["rows"][0]["output"]
    high_source_hashes = json.loads((Path(high_source) / "HIGH_ROM_CASE_RESULT.json").read_text())["source_files_sha256"]
    for entry in manifest["cases"]:
        key = entry["case_key"]
        case_path = ROOT / entry["local_path"]
        case_data = json.loads(case_path.read_text())
        case = dict(case_key=key, path=entry["local_path"], sha256=entry["sha256"],
                    physical_variant=case_data["cell"]["family"] + ":" + case_data["cell"]["range"],
                    candidate="original_low_rom_feedback")
        path = output_root / f"{key}_attempt_01"
        row = score(path, case, contract, case_data["task"]["goal_deg"], case_data["task"]["start_deg"])
        row["source_copy_sha256_valid"] = (hashlib.sha256(case_path.read_bytes()).hexdigest() == entry["sha256"])
        if (path / "HIGH_ROM_CASE_RESULT.json").exists() and (path / "config_snapshot.json").exists():
            launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
            snapshot = json.loads((path / "config_snapshot.json").read_text())
            requests = json.loads((path / "summary.json").read_text())["timing"]["requests"]
            ages = [r["activation_age_ms"] for r in requests if r.get("activation_age_ms") is not None]
            # The two plant configs are intentionally distinct. Compare only executable source.
            source_keys = {name for name in high_source_hashes if "/src/" in name}
            row["source_same_as_high_rom"] = all(
                launch["source_files_sha256"].get(name) == high_source_hashes[name]
                for name in source_keys)
            row["options_hash_valid"] = launch["options_sha256"] == manifest["controller_options_sha256"]
            row["runtime_loaded_from_worktree"] = launch["runtime_path"].startswith(str(ROOT) + "/")
            row["original_plant_rom_valid"] = snapshot["human_hard_rom_deg"] == [[0.0, 80.0], [0.0, 100.0]]
            row["low_rom_mode_valid"] = launch["plant_mode"] == "low_rom" and "--plant-mode" in launch["command"]
            row["maximum_all_stage_plan_activation_age_ms"] = max(ages, default=None)
            row["all_stage_plan_age_valid"] = bool(ages) and max(ages) < contract["plan_max_activation_age_ms"]
        else:
            for name in ("source_same_as_high_rom", "options_hash_valid", "runtime_loaded_from_worktree",
                         "original_plant_rom_valid", "low_rom_mode_valid", "all_stage_plan_age_valid"):
                row[name] = False
        row["pass"] = bool(row.get("pass")) and all(row[k] for k in (
            "source_copy_sha256_valid", "source_same_as_high_rom", "options_hash_valid",
            "runtime_loaded_from_worktree", "original_plant_rom_valid", "low_rom_mode_valid",
            "all_stage_plan_age_valid"))
        rows.append(row)
    result = dict(schema="high_rom_v1_phase_b_low_rom_same_source_regression_results",
                  manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  source_fingerprint=high_source_hashes, total=len(rows),
                  completed_count=sum(r["status"] == "COMPLETE" for r in rows),
                  passed_count=sum(r["pass"] for r in rows),
                  failed_or_incomplete_count=sum(not r["pass"] for r in rows), rows=rows)
    target = DOC / "PHASE_B_LOW_ROM_RESULTS.json"
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("total", "completed_count", "passed_count", "failed_or_incomplete_count")}))


if __name__ == "__main__":
    main()
