"""Geometry-only v2 extension: minimally clear an initial sleeve/table overlap.

This consumes v1 *assembly diagnostics only*, never any controller outcome.
v1 case files and results are preserved.  It cannot exceed the registered
+6 mm upward installation bound or change any non-hip-z patient/task field.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from traction_mpc_stage5.rigid_table_assembly_v1 import (
    MIN_PROXIMAL_GAP_M, assess_assembly,
)


STAGE = Path(__file__).resolve().parents[1]
ROOT = STAGE.parents[1]
BASE = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
V1 = BASE / "assembly_v1"
V2 = BASE / "assembly_v2"
MAX_UPWARD_INSTALLATION_SHIFT_M = 0.006


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if V2.exists():
        raise FileExistsError(f"refusing to overwrite {V2}")
    V2.mkdir(parents=True)
    (V2 / "cases").mkdir()
    prior = json.loads((V1 / "OLD_TO_NEW_CASE_MAPPING.json").read_text())
    rows = []
    for item in prior:
        key = item["case_key"]
        source = V1 / "cases" / f"{key}.json"
        case = json.loads(source.read_text())
        v1 = item["revised_validity"]
        extension = {"rule": "unchanged_from_v1", "added_upward_shift_m": 0.0}
        if (not v1["valid"] and v1["category"] == "INVALID_FIXED_GEOMETRY"
                and v1["reason"] == "MuJoCo reset overlap: sleeve"):
            sleeve_gap = float(v1["initial"]["distances"]["sleeve"]["minimum_signed_distance_m"])
            needed = MIN_PROXIMAL_GAP_M - sleeve_gap
            current = float(case["physical"]["hip_translation_xz_m"][1])
            proposed = current + needed
            extension = {"rule": "minimum_positive_sleeve_table_installation_clearance",
                         "v1_initial_sleeve_gap_m": sleeve_gap,
                         "required_added_upward_shift_m": needed,
                         "proposed_hidden_hip_shift_z_m": proposed,
                         "maximum_legal_hidden_hip_shift_z_m": MAX_UPWARD_INSTALLATION_SHIFT_M}
            if proposed <= MAX_UPWARD_INSTALLATION_SHIFT_M + 1e-9:
                case = deepcopy(case)
                case["physical"]["hip_translation_xz_m"][1] = proposed
                extension["added_upward_shift_m"] = needed
                extension["within_registered_installation_range"] = True
            else:
                extension["added_upward_shift_m"] = 0.0
                extension["within_registered_installation_range"] = False
                extension["no_legal_placement_found_by_this_minimal_vertical_rule"] = True
        revised_check = assess_assembly(case)
        output = V2 / "cases" / f"{key}.json"
        output.write_text(json.dumps(case, indent=2, sort_keys=True, allow_nan=False) + "\n",
                          encoding="utf-8")
        rows.append({"case_key": key,
                     "historical_original_case_path": item["original_case_path"],
                     "historical_original_case_sha256": item["original_case_sha256"],
                     "v1_case_path": item["revised_case_path"],
                     "v1_case_sha256": item["revised_case_sha256"],
                     "v1_validity": v1,
                     "v2_case_path": str(output.relative_to(ROOT)),
                     "v2_case_sha256": digest(output),
                     "v2_validity": revised_check,
                     "envelope_extension": extension})
        print(json.dumps({"case_key": key, "v1_valid": v1["valid"],
                          "v2_valid": revised_check["valid"],
                          "extension": extension["rule"]}), flush=True)
    (V2 / "OLD_TO_NEW_CASE_MAPPING.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    summary = {"schema": "rigid_table_assembly_v2_geometry_only_envelope_extension",
               "historical_case_count": len(rows),
               "v1_valid_count": sum(row["v1_validity"]["valid"] for row in rows),
               "v2_valid_count": sum(row["v2_validity"]["valid"] for row in rows),
               "newly_valid_case_keys": [row["case_key"] for row in rows
                                         if not row["v1_validity"]["valid"] and row["v2_validity"]["valid"]],
               "still_invalid_case_keys": [row["case_key"] for row in rows
                                           if not row["v2_validity"]["valid"]],
               "controller_outcomes_read": False,
               "controller_changed": False,
               "historical_v1_artifacts_untouched": True}
    (V2 / "ASSEMBLY_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
