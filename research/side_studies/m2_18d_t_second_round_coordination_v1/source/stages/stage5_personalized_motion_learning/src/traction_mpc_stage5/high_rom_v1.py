"""Versioned engineering High-ROM task/model prior. Never reads hidden plant truth."""
from __future__ import annotations

from dataclasses import replace
import json
from .config import STAGE5_ROOT
from .human import STAGE5_HUMAN

CONFIG_PATH = STAGE5_ROOT / "configs/high_rom_v1/stage5_goal_task_120_v1.json"

def contract():
    record = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (record.get("research_schema") != "high_rom_120_model_and_task_v1"
            or record["human_model"]["hard_rom_deg"] != [[0.0, 125.0], [0.0, 125.0]]
            or record["human_model"]["soft_limit_margin_deg"] != 5.0
            or record["human_model"]["passive_stiffness_nm_rad"] != [10.0, 10.0]
            or record["human_model"]["passive_damping_nms_rad"] != [5.0, 5.0]):
        raise ValueError("High-ROM v1 engineering model contract changed")
    return record

def deployable_prior():
    # ROM is an explicitly configured structural hypothesis, never a plant read.
    import numpy as np
    record = contract()
    bounds = record["human_model"]["hard_rom_deg"]
    return replace(STAGE5_HUMAN,
                   q_min_rad=tuple(np.radians([row[0] for row in bounds])),
                   q_max_rad=tuple(np.radians([row[1] for row in bounds])))
