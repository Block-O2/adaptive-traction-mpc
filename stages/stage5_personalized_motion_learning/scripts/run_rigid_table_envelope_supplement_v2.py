"""Run only newly legal v2 envelope counterparts with the unchanged controller."""
from __future__ import annotations

import json
from pathlib import Path

from run_rigid_table_development_v1 import run_one, write_json


STAGE = Path(__file__).resolve().parents[1]
BASE = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
V2 = BASE / "assembly_v2"
OUT = BASE / "supplemental_v2"


def main() -> None:
    summary = json.loads((V2 / "ASSEMBLY_SUMMARY.json").read_text())
    newly_valid = summary["newly_valid_case_keys"]
    if newly_valid != ["balanced_near_upper_current_rom_r02"]:
        raise RuntimeError("unexpected v2 geometry-only promotion set")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key in newly_valid:
        output = OUT / key
        if (output / "rigid_table_run_manifest.json").exists():
            manifest = json.loads((output / "rigid_table_run_manifest.json").read_text())
            row = {"case_key": key, "status": manifest["summary_status"],
                   "resumed_existing_artifact": True}
        elif output.exists() and any(output.iterdir()):
            row = {"case_key": key,
                   "status": "INCOMPLETE_INTERRUPTED_ARTIFACT_PRESERVED",
                   "resumed_existing_artifact": True}
        else:
            row = run_one(V2 / "cases" / f"{key}.json", output)
            row["resumed_existing_artifact"] = False
        rows.append(row)
        write_json(OUT / "batch_status.json", {
            "schema": "rigid_table_v2_envelope_supplement_development",
            "evidence_category": "geometry_only_supplement_to_v1_not_fresh",
            "controller_unchanged": True,
            "rows": rows,
        })
        print(json.dumps(row, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
