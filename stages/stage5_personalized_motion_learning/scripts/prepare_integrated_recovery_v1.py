"""Snapshot the local integrated-recovery baseline; no Git mutations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

import mujoco
import numpy
import scipy

STAGE = Path(__file__).resolve().parents[1]
REPO = STAGE.parents[1]
DOCS = STAGE / "docs/full3d_adaptive_integration_v1/integrated_recovery_v1"
OUT = STAGE / "results/full3d_adaptive_integration_v1/integrated_recovery_v1/baseline_v1"


def main():
    if OUT.exists():
        raise FileExistsError(f"baseline already recorded: {OUT}")
    OUT.mkdir(parents=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    old = json.loads((STAGE / "docs/full3d_adaptive_integration_v1/fresh_qualification_v1/FREEZE_MANIFEST.json").read_text())
    files = {REPO / p for p in old["source_config_asset_sha256"]}
    for stage in ("stage3_full3d", "stage4_adaptive_control", "stage5_personalized_motion_learning"):
        for directory in ("src", "configs", "scripts", "tests"):
            for p in (REPO / "stages" / stage / directory).rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc"}:
                    files.add(p)
    files.add(REPO / "AGENTS.md")
    missing = sorted(str(p.relative_to(REPO)) for p in files if not p.is_file())
    if missing:
        raise FileNotFoundError(missing)
    hashes = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(files)}
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=REPO, text=True)
    (OUT / "git_status_entry.txt").write_text(status)
    patch = subprocess.check_output(["git", "diff", "--binary"], cwd=REPO)
    (OUT / "tracked_baseline.patch").write_bytes(patch)
    archive = OUT / "local_dependency_snapshot.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(files):
            tar.add(p, arcname=str(p.relative_to(REPO)), recursive=False)
    manifest = {
        "schema": "integrated_recovery_v1_baseline",
        "baseline": "current local DEV-A lifecycle with DEV-C explicitly OFF",
        "runtime_options": {"dev_a_recovery": True, "dev_c_bumpless_transfer": False,
                            "simulate_planning_latency": True, "formal_qualification": False},
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "command": sys.argv, "platform": platform.platform(), "python": sys.version,
        "mujoco": mujoco.__version__, "numpy": numpy.__version__, "scipy": scipy.__version__,
        "entry_status_path_count": len(status.splitlines()), "file_count": len(hashes),
        "source_config_asset_sha256": hashes,
        "archive": str(archive.relative_to(REPO)),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "tracked_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "clean_clone_reproducible": False,
    }
    (DOCS / "BASELINE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"files": len(hashes), "snapshot": str(archive), "branch": manifest["branch"], "head": manifest["head"]}))


if __name__ == "__main__":
    main()
