"""Separated Stage-4 P1 and Stage-5 interface parameter sets."""

from __future__ import annotations

import json

from traction_mpc_stage3.spring_damper_interface import InterfaceParameters

from .config import STAGE5_CONFIG, STAGE5_ROOT


def _interface(record: dict[str, object]) -> InterfaceParameters:
    return InterfaceParameters(
        translation_stiffness_n_m=tuple(record["translation_stiffness_n_m"]),
        translation_damping_ns_m=tuple(record["translation_damping_ns_m"]),
        rotation_stiffness_nm_rad=float(record["rotation_stiffness_nm_rad"]),
        rotation_damping_nms_rad=float(record["rotation_damping_nms_rad"]),
    )


_mechanics = STAGE5_CONFIG["mechanics"]
STAGE4_P1_INTERFACE = _interface(_mechanics["stage4_p1_reference"])
STAGE5_STIFF_INTERFACE = _interface(_mechanics["stage5_stiff_surrogate"])
_v2 = json.loads(
    (STAGE5_ROOT / "configs" / "stage5_geometry_mechanics_v2.json").read_text(
        encoding="utf-8"
    )
)
if _v2.get("schema") != "stage5_geometry_mechanics_v2":
    raise ValueError("unexpected Stage-5 geometry/mechanics v2 schema")
STAGE5_RIGID_INTERFACE = _interface(_v2["selected_interface"])
NOMINAL_PHYSICS_DT_S = float(_mechanics["nominal_physics_dt_s"])
TIMESTEP_PROBE_S = tuple(float(value) for value in _mechanics["timestep_probe_s"])
