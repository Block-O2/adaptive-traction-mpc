"""Hash local DEV-D runtime dependency tree; does not claim clean-clone support."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

import mujoco
import numpy
import scipy


ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parents[1]
ROOTS = (
    ROOT / "stages/stage3_full3d/src",
    ROOT / "stages/stage4_adaptive_control/src",
    STAGE / "src",
    STAGE / "models",
    STAGE / "configs/full3d_adaptive_integration_v1",
)
EXTRA = (
    STAGE / "scripts/run_rigid_table_reference_development_v1.py",
    STAGE / "scripts/run_rigid_table_development_v1.py",
    STAGE / "scripts/diagnose_rigid_table_reference_v1.py",
    STAGE / "scripts/summarize_rigid_table_reference_development_v1.py",
    STAGE / "scripts/plot_rigid_table_reference_development_v1.py",
    STAGE / "scripts/profile_dev_d_geometry_v1.py",
    STAGE / "tests/full3d_adaptive_integration_v1/test_dev_d_rigid_table_reference.py",
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    files = set(EXTRA)
    for root in ROOTS:
        if root.exists():
            files.update(path for path in root.rglob("*") if path.is_file()
                         and "__pycache__" not in path.parts)
    tracked = set(git("ls-files").splitlines())
    entries = {}
    for path in sorted(files):
        rel = path.relative_to(ROOT).as_posix()
        entries[rel] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "tracked_at_head": rel in tracked}
    output = {
        "schema": "dev_d_local_dependency_snapshot_v1",
        "scope": "whole relevant source/model/config directories plus DEV-D entrypoints",
        "branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
        "clean_clone_reproducible": False,
        "reason": "current full-3D source/models/configs include uncommitted dependencies",
        "python": platform.python_version(), "mujoco": mujoco.__version__,
        "numpy": numpy.__version__, "scipy": scipy.__version__,
        "file_count": len(entries),
        "untracked_file_count_in_snapshot": sum(not item["tracked_at_head"] for item in entries.values()),
        "files": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: output[k] for k in (
        "branch", "head", "file_count", "untracked_file_count_in_snapshot",
        "python", "mujoco", "numpy", "scipy")}, indent=2))


if __name__ == "__main__":
    main()
