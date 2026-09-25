"""Write a read-only-hash manifest for the local, uncommitted study."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys

import mujoco
import numpy
import scipy


STAGE = Path(__file__).resolve().parents[1]
ROOT = STAGE.parents[1]
DOC = STAGE / "docs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
RESULT = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
PRIOR = STAGE / "docs/full3d_adaptive_integration_v1/integrated_recovery_v1/BASELINE_MANIFEST.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RESULT / "repro_v1/DEPENDENCY_MANIFEST.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    prior = json.loads(PRIOR.read_text())
    unchanged = prior["source_config_asset_sha256"]
    drift = [rel for rel, digest in unchanged.items()
             if not (ROOT / rel).is_file() or sha(ROOT / rel) != digest]
    if drift:
        raise RuntimeError(f"prior physical/controller dependencies changed: {drift}")
    new_runtime = [
        STAGE / "src/traction_mpc_stage5/rigid_table_assembly_v1/__init__.py",
        STAGE / "src/traction_mpc_stage5/rigid_table_assembly_v1/assembly.py",
        STAGE / "scripts/prepare_rigid_table_assembly_v1.py",
        STAGE / "scripts/run_rigid_table_prefix_v1.py",
        STAGE / "scripts/run_rigid_table_development_v1.py",
        STAGE / "scripts/audit_rigid_table_trajectory_geometry_v1.py",
        STAGE / "scripts/audit_rigid_table_pose_consistency_v1.py",
        STAGE / "scripts/summarize_rigid_table_development_v1.py",
        STAGE / "scripts/verify_rigid_table_artifacts_v1.py",
        STAGE / "scripts/prepare_rigid_table_envelope_extension_v2.py",
        STAGE / "scripts/run_rigid_table_envelope_supplement_v2.py",
        STAGE / "scripts/audit_rigid_table_supplement_v2.py",
        Path(__file__),
        STAGE / "configs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/nominal_reference_rigid_table_v1.json",
        STAGE / "tests/full3d_adaptive_integration_v1/test_rigid_table_assembly_v1.py",
    ]
    critical_results = [
        RESULT / "assembly_v1/OLD_TO_NEW_CASE_MAPPING.json",
        RESULT / "assembly_v1/STATIC_CONTACT_SWEEP.json",
        RESULT / "assembly_v1/ASSEMBLY_SUMMARY.json",
        RESULT / "prefix_v1/PREFIX_CONTACT_RESULTS.json",
        RESULT / "review_v1/DEVELOPMENT_SUMMARY.json",
        RESULT / "trajectory_geometry_broad_v1/SUMMARY.json",
        RESULT / "pose_consistency_v1/POSE_AUDIT.json",
        RESULT / "assembly_v2/OLD_TO_NEW_CASE_MAPPING.json",
        RESULT / "assembly_v2/ASSEMBLY_SUMMARY.json",
        RESULT / "trajectory_geometry_supplemental_v2.json",
    ]
    critical_results.extend(
        RESULT / "supplemental_v2/balanced_near_upper_current_rom_r02" / name
        for name in ("summary.json", "trace.npz", "contact_intervals.npz",
                     "contact_summary.json", "rigid_table_run_manifest.json")
    )
    for folder in (RESULT / "broad_old24_valid_v1").iterdir():
        if not folder.is_dir():
            continue
        critical_results.extend(folder / name for name in (
            "summary.json", "trace.npz", "contact_intervals.npz",
            "contact_summary.json", "rigid_table_run_manifest.json"))
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"],
                                     cwd=ROOT, text=True).splitlines()
    current = {
        "schema": "rigid_table_v1_local_dependency_manifest",
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "prior_607_dependency_snapshot_sha256": prior["archive_sha256"],
        "prior_607_dependency_count": len(unchanged),
        "prior_dependency_drift": drift,
        "new_runtime_source_config_sha256": {
            str(path.relative_to(ROOT)): sha(path) for path in new_runtime},
        "critical_result_sha256": {
            str(path.relative_to(ROOT)): sha(path) for path in critical_results},
        "study_document_sha256": {
            str(path.relative_to(ROOT)): sha(path) for path in sorted(DOC.glob("*.md"))
            if path.name not in {"STATUS.md", "AUDIT_REPORT.md", "FINAL_REPORT.md"}},
        "status_porcelain_v1_uall_at_finalization": status,
        "dirty_untracked_path_count": len(status),
        "python": sys.version,
        "platform": platform.platform(),
        "mujoco": mujoco.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "controller_flags": {"dev_a_recovery": True,
                             "dev_c_bumpless_transfer": False,
                             "qualification_arm": "continual_adaptive",
                             "simulate_planning_latency": True,
                             "formal_qualification": False},
        "clean_clone_reproducible": False,
        "git_mutations_performed": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"prior_dependency_count": len(unchanged),
                      "new_runtime_file_count": len(new_runtime),
                      "critical_result_file_count": len(critical_results),
                      "dirty_untracked_path_count": len(status),
                      "path": str(args.output)}))


if __name__ == "__main__":
    main()
