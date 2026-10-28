"""Load and validate the single provisional Stage-5 parameter record."""

from __future__ import annotations

import json
from pathlib import Path


STAGE5_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_geometry_mechanics_v1.json"


def load_stage5_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_geometry_mechanics_v1":
        raise ValueError("unexpected Stage-5 geometry/mechanics schema")
    if payload.get("provisional_not_measured") is not True:
        raise ValueError("Stage-5 v1 geometry must remain labeled provisional")
    return payload


STAGE5_CONFIG = load_stage5_config()
