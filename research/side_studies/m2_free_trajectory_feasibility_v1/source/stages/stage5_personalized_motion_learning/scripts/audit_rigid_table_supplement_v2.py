"""Evaluation-only executed geometry audit for the one v2 supplemental run."""
from __future__ import annotations

import json
from pathlib import Path

from audit_rigid_table_trajectory_geometry_v1 import audit_one


STAGE = Path(__file__).resolve().parents[1]
BASE = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
KEY = "balanced_near_upper_current_rom_r02"
OUT = BASE / "trajectory_geometry_supplemental_v2.json"


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    result = audit_one(BASE / "assembly_v2/cases" / f"{KEY}.json",
                       BASE / "supplemental_v2" / KEY)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
                   encoding="utf-8")
    print(json.dumps({"case_key": KEY,
                      "minima": {k: v["distance_m"]
                                 for k, v in result["minimum_signed_distances"].items()}},
                     sort_keys=True))


if __name__ == "__main__":
    main()
