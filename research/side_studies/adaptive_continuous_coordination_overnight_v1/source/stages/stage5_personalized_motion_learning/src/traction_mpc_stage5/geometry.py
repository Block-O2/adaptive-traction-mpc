"""Explicit W/B/H/E/C frame chain for provisional Stage-5 geometry."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.human import HumanV2Parameters

from .config import STAGE5_CONFIG
from .human import STAGE5_HUMAN


def _transform(record: dict[str, object]) -> RigidTransform:
    return RigidTransform(
        np.asarray(record["rotation"], dtype=float),
        np.asarray(record["translation_m"], dtype=float),
    )


@dataclass(frozen=True)
class Stage5Geometry:
    world_from_base: RigidTransform
    world_from_human: RigidTransform
    end_effector_from_cuff: RigidTransform
    cuff_bar_axis_in_cuff: np.ndarray
    terminal_stem_axis_in_end_effector: np.ndarray
    cuff_bar_length_m: float
    cuff_bar_radius_m: float

    def __post_init__(self) -> None:
        bar = np.asarray(self.cuff_bar_axis_in_cuff, dtype=float)
        stem = np.asarray(self.terminal_stem_axis_in_end_effector, dtype=float)
        if bar.shape != (3,) or stem.shape != (3,):
            raise ValueError("bar and stem axes must be three-vectors")
        if not np.isclose(np.linalg.norm(bar), 1.0, atol=1e-12):
            raise ValueError("cuff bar axis must be unit length")
        if not np.isclose(np.linalg.norm(stem), 1.0, atol=1e-12):
            raise ValueError("terminal stem axis must be unit length")
        stem_in_cuff = self.end_effector_from_cuff.rotation.T @ stem
        if not np.isclose(float(bar @ stem_in_cuff), 0.0, atol=1e-12):
            raise ValueError("cuff bar must be perpendicular to terminal stem")
        if self.cuff_bar_length_m <= 0.0 or self.cuff_bar_radius_m <= 0.0:
            raise ValueError("cuff bar dimensions must be positive")
        object.__setattr__(self, "cuff_bar_axis_in_cuff", bar.copy())
        object.__setattr__(self, "terminal_stem_axis_in_end_effector", stem.copy())

    def human_from_cuff(
        self, q_rad: np.ndarray, human: HumanV2Parameters = STAGE5_HUMAN
    ) -> RigidTransform:
        q1, q2 = np.asarray(q_rad, dtype=float)
        phi = q1 - q2
        position = np.array(
            [
                human.thigh_length_m * math.cos(q1)
                + human.sleeve_center_m * math.cos(phi),
                0.0,
                human.thigh_length_m * math.sin(q1)
                + human.sleeve_center_m * math.sin(phi),
            ]
        )
        angle = q2 - q1
        cosine, sine = math.cos(angle), math.sin(angle)
        rotation = np.array(
            [
                [cosine, 0.0, sine],
                [0.0, 1.0, 0.0],
                [-sine, 0.0, cosine],
            ]
        )
        return RigidTransform(rotation, position)

    def world_from_cuff(
        self, q_rad: np.ndarray, human: HumanV2Parameters = STAGE5_HUMAN
    ) -> RigidTransform:
        return self.world_from_human.compose(self.human_from_cuff(q_rad, human))

    def base_from_end_effector_target(
        self, q_rad: np.ndarray, human: HumanV2Parameters = STAGE5_HUMAN
    ) -> RigidTransform:
        world_from_end_effector = self.world_from_cuff(q_rad, human).compose(
            self.end_effector_from_cuff.inverse()
        )
        return self.world_from_base.inverse().compose(world_from_end_effector)

    def base_alignment_fraction_of_shank(
        self, human: HumanV2Parameters = STAGE5_HUMAN
    ) -> float:
        base_in_human = self.world_from_human.inverse().compose(self.world_from_base)
        return float(
            (base_in_human.translation[0] - human.thigh_length_m)
            / human.shank_length_m
        )


_frames = STAGE5_CONFIG["frames"]
_shape = STAGE5_CONFIG["geometry"]
STAGE5_GEOMETRY = Stage5Geometry(
    world_from_base=_transform(_frames["T_WB"]),
    world_from_human=_transform(_frames["T_WH"]),
    end_effector_from_cuff=_transform(_frames["T_EC"]),
    cuff_bar_axis_in_cuff=np.asarray(_shape["cuff_bar_axis_in_C"], dtype=float),
    terminal_stem_axis_in_end_effector=np.asarray(
        _shape["terminal_stem_axis_in_E"], dtype=float
    ),
    cuff_bar_length_m=float(_shape["cuff_bar_length_m"]),
    cuff_bar_radius_m=float(_shape["cuff_bar_radius_m"]),
)
