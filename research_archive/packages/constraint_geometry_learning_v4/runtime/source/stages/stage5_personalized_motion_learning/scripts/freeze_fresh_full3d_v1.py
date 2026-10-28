"""Seal the pre-outcome source/config/assets contract; never overwrite."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess

import mujoco
import numpy
import scipy


REPO = Path(__file__).resolve().parents[3]
STAGE5 = REPO / "stages/stage5_personalized_motion_learning"
DOC = STAGE5 / "docs/full3d_adaptive_integration_v1/fresh_qualification_v1"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True)


def dependency_paths() -> list[Path]:
    paths: set[Path] = set()
    for stage in ("stage3_full3d", "stage4_adaptive_control",
                  "stage5_personalized_motion_learning"):
        stage_root = REPO / "stages" / stage
        for directory, pattern in (("src", "*"), ("configs", "*.json"),
                                   ("models", "*"), ("vendor", "*")):
            root = stage_root / directory
            if root.exists():
                paths.update(path for path in root.rglob(pattern) if path.is_file()
                             and "__pycache__" not in path.parts)
        if (stage_root / "pyproject.toml").exists():
            paths.add(stage_root / "pyproject.toml")
    for name in ("run_fresh_full3d_case_v1.py", "generate_fresh_full3d_cases_v1.py",
                 "freeze_fresh_full3d_v1.py", "run_fresh_full3d_batch_v1.py",
                 "analyze_fresh_full3d_v1.py", "test_fresh_full3d_watchdog_v1.py"):
        path = STAGE5 / "scripts" / name
        if not path.exists():
            raise FileNotFoundError(path)
        paths.add(path)
    paths.add(DOC / "PREREGISTRATION.md")
    return sorted(paths)


def main() -> None:
    manifest_path = DOC / "FREEZE_MANIFEST.json"
    status_path = DOC / "FREEZE_GIT_STATUS.txt"
    if manifest_path.exists() or status_path.exists():
        raise FileExistsError("freeze artifacts already exist; do not overwrite")
    paths = dependency_paths()
    hashes = {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in paths}
    status = _git("status", "--short", "--untracked-files=all")
    status_path.write_text(status, encoding="utf-8")
    record = {
        "schema": "fresh_full3d_qualification_v1_preoutcome_freeze",
        "branch": _git("branch", "--show-current").strip(),
        "head": _git("rev-parse", "HEAD").strip(),
        "source_config_asset_sha256": hashes,
        "file_count": len(hashes),
        "git_status_snapshot_sha256": hashlib.sha256(status.encode()).hexdigest(),
        "python": platform.python_version(), "numpy": numpy.__version__,
        "scipy": scipy.__version__, "mujoco": mujoco.__version__,
        "qualification_cases_generated": False,
        "formal_episodes_executed": False,
    }
    manifest_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps({"freeze_manifest": str(manifest_path),
                      "files": len(hashes), "branch": record["branch"],
                      "head": record["head"]}, sort_keys=True))


if __name__ == "__main__":
    main()
