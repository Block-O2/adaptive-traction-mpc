"""Prepare old24 DEVELOPMENT counterparts and evaluate rigid-table assembly.

No controller outcome is read by this script.  Historical case files are read
only and all output paths are new/versioned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys

import mujoco
import numpy as np
import scipy

from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.rigid_table_assembly_v1 import (
    MIN_PROXIMAL_GAP_M, assess_assembly, repaired_counterpart,
)


STAGE = Path(__file__).resolve().parents[1]
ROOT = STAGE.parents[1]
OLD = STAGE / "results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases"
DEFAULT_OUT = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v1"
PRIOR = STAGE / "docs/full3d_adaptive_integration_v1/integrated_recovery_v1/BASELINE_MANIFEST.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def static_contact_sweep(template: dict) -> list[dict]:
    """Pre-outcome solver contact check around fixed proximal tangency."""
    import copy

    rows = []
    for gap in (-0.001, 0.0, 0.00001, 0.00005, MIN_PROXIMAL_GAP_M, 0.0002):
        case = copy.deepcopy(template)
        case["physical"]["hip_translation_xz_m"][1] = gap
        human, geometry, spec, _ = hidden_plant(case)
        plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
        plant.reset(np.asarray(spec.start_return_target_rad))
        thigh = plant.model.geom("thigh_geom").id
        contacts = []
        for i in range(plant.data.ncon):
            c = plant.data.contact[i]
            if {int(c.geom1), int(c.geom2)} != {plant.bed_geom_id, thigh}:
                continue
            wrench = np.zeros(6)
            mujoco.mj_contactForce(plant.model, plant.data, i, wrench)
            contacts.append({"signed_distance_m": float(c.dist),
                             "normal_force_n": float(wrench[0])})
        rows.append({"installation_gap_m": gap,
                     "thigh_bed_contacts": contacts,
                     "ncon_all_pairs": int(plant.data.ncon)})
    return rows


def dependency_manifest() -> dict:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    required = prior["source_config_asset_sha256"]
    changed = []
    missing = []
    for rel, expected in required.items():
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
        elif sha256(path) != expected:
            changed.append(rel)
    if missing or changed:
        raise RuntimeError(f"prior 607 dependency snapshot drift: missing={missing}, changed={changed}")
    result = subprocess.run(["git", "status", "--porcelain=v1", "-uall"],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    additional = [Path(__file__),
                  STAGE / "src/traction_mpc_stage5/rigid_table_assembly_v1/assembly.py",
                  STAGE / "src/traction_mpc_stage5/rigid_table_assembly_v1/__init__.py"]
    return {
        "schema": "rigid_table_assembly_v1_dependency_manifest",
        "git_branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "baseline_verified_dependency_count": len(required),
        "baseline_dependency_archive": prior["archive"],
        "baseline_dependency_archive_sha256": prior["archive_sha256"],
        "new_source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in additional},
        "prior_dependency_changed": changed,
        "prior_dependency_missing": missing,
        "python": sys.version,
        "platform": platform.platform(),
        "mujoco": mujoco.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "git_status_porcelain_v1_uall_at_prepare": result.stdout.splitlines(),
        "clean_clone_reproducible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output}")
    files = sorted(OLD.glob("*.json"))
    if len(files) != 24:
        raise RuntimeError(f"expected original 24 frozen cases, found {len(files)}")
    manifest = dependency_manifest()
    cases_dir = args.output / "cases"
    cases_dir.mkdir(parents=True)
    mapping = []
    for file in files:
        old = json.loads(file.read_text(encoding="utf-8"))
        revised, change = repaired_counterpart(old)
        original_check = assess_assembly(old, verify_robot=False)
        revised_check = assess_assembly(revised)
        output_case = cases_dir / file.name
        write_json(output_case, revised)
        row = {
            "case_key": old["case_key"],
            "original_case_path": str(file.relative_to(ROOT)),
            "original_case_sha256": sha256(file),
            "original_geometry": old["physical"]["hip_translation_xz_m"],
            "original_validity_under_new_contract": original_check,
            "revised_case_path": str(output_case.relative_to(ROOT)),
            "revised_case_sha256": sha256(output_case),
            "revised_geometry": revised["physical"]["hip_translation_xz_m"],
            "exact_required_assembly_changes": change,
            "revised_validity": revised_check,
        }
        mapping.append(row)
        print(json.dumps({"case_key": old["case_key"], "old_gap_m": change["old_proximal_gap_m"],
                          "new_gap_m": change["new_proximal_gap_m"],
                          "valid": revised_check["valid"],
                          "category": revised_check["category"]}), flush=True)
    write_json(args.output / "OLD_TO_NEW_CASE_MAPPING.json", mapping)
    write_json(args.output / "STATIC_CONTACT_SWEEP.json", static_contact_sweep(
        json.loads(files[0].read_text(encoding="utf-8"))))
    write_json(args.output / "DEPENDENCY_MANIFEST.json", manifest)
    write_json(args.output / "ASSEMBLY_SUMMARY.json", {
        "schema": "rigid_table_assembly_v1_development_mapping",
        "historical_case_count": len(files),
        "historically_fixed_negative_gap_count": sum(
            row["exact_required_assembly_changes"]["old_proximal_gap_m"] < -1e-9 for row in mapping),
        "revised_full_assembly_valid_count": sum(row["revised_validity"]["valid"] for row in mapping),
        "revised_categories": {category: sum(row["revised_validity"]["category"] == category
                                    for row in mapping)
                               for category in sorted({row["revised_validity"]["category"] for row in mapping})},
        "not_fresh_qualification": True,
        "controller_unchanged": True,
        "dev_a_recovery": True,
        "dev_c_bumpless_transfer": False,
    })


if __name__ == "__main__":
    main()
