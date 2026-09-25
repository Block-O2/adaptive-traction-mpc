"""Generation/evaluation-side hidden Human V2 and placement parameters.

Nothing in this module is imported into online estimation or action selection.
The parameterization changes the physical MuJoCo plant, not Human V2 laws.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

import numpy as np

from traction_mpc_stage3.frames import RigidTransform
from ..geometry import STAGE5_GEOMETRY, Stage5Geometry
from ..human import STAGE5_HUMAN, Stage5HumanParameters
from ..task import GoalTaskSpec, PROVISIONAL_LOW_MODERATE_GOAL_TASK


@dataclass(frozen=True)
class HiddenHumanV2(Stage5HumanParameters):
    """Same Human V2 mechanics with independently varying physical coefficients."""

    thigh_length_scale: float = 1.0
    shank_length_scale: float = 1.0
    thigh_mass_scale: float = 1.0
    shank_mass_scale: float = 1.0
    thigh_com_fraction: float = 0.433
    shank_com_fraction: float = 0.430
    thigh_inertia_radius_fraction: float = 0.30
    shank_inertia_radius_fraction: float = 0.30

    def __post_init__(self):
        super().__post_init__()
        for value in (self.thigh_length_scale,self.shank_length_scale,
                      self.thigh_mass_scale,self.shank_mass_scale,
                      self.thigh_inertia_radius_fraction,self.shank_inertia_radius_fraction):
            if not math.isfinite(value) or value <= 0:raise ValueError('physical scales must be finite positive')
        for value in (self.thigh_com_fraction,self.shank_com_fraction):
            if not 0 < value < 1:raise ValueError('COM fractions must be internal to each segment')

    @property
    def thigh_length_m(self):return 0.254*self.height_m*self.thigh_length_scale
    @property
    def shank_length_m(self):return 0.233*self.height_m*self.shank_length_scale
    @property
    def thigh_mass_kg(self):return 0.099*self.body_mass_kg*self.thigh_mass_scale
    @property
    def shank_mass_kg(self):return (0.046+0.014)*self.body_mass_kg*self.shank_mass_scale
    @property
    def thigh_com_m(self):return self.thigh_com_fraction*self.thigh_length_m
    @property
    def shank_com_m(self):return self.shank_com_fraction*self.shank_length_m
    @property
    def thigh_inertia_kg_m2(self):return self.thigh_mass_kg*(self.thigh_inertia_radius_fraction*self.thigh_length_m)**2
    @property
    def shank_inertia_kg_m2(self):return self.shank_mass_kg*(self.shank_inertia_radius_fraction*self.shank_length_m)**2


def hidden_plant(case: Mapping[str,Any]) -> tuple[HiddenHumanV2,Stage5Geometry,GoalTaskSpec,np.ndarray]:
    """Construct physical truth and registered task before the controller exists."""
    physical=case['physical']; task=case['task']
    human=HiddenHumanV2(
        height_m=float(physical['height_m']),body_mass_kg=float(physical['body_mass_kg']),
        q_rest_rad=tuple(np.radians(physical['q_rest_deg'])),
        passive_stiffness_nm_rad=tuple(physical['passive_stiffness_nm_rad']),
        passive_damping_nms_rad=tuple(physical['passive_damping_nms_rad']),
        cuff_fraction_of_shank=float(physical['cuff_fraction_of_shank']),
        thigh_length_scale=float(physical['thigh_length_scale']),
        shank_length_scale=float(physical['shank_length_scale']),
        thigh_mass_scale=float(physical['thigh_mass_scale']),
        shank_mass_scale=float(physical['shank_mass_scale']),
        thigh_com_fraction=float(physical['thigh_com_fraction']),
        shank_com_fraction=float(physical['shank_com_fraction']),
        thigh_inertia_radius_fraction=float(physical['thigh_inertia_radius_fraction']),
        shank_inertia_radius_fraction=float(physical['shank_inertia_radius_fraction']),
    )
    translation=STAGE5_GEOMETRY.world_from_human.translation.copy()
    translation[[0,2]]+=np.asarray(physical['hip_translation_xz_m'],dtype=float)
    geometry=replace(STAGE5_GEOMETRY,world_from_human=RigidTransform(
        STAGE5_GEOMETRY.world_from_human.rotation.copy(),translation))
    spec=replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        name='fresh_qualification_'+str(case['case_key']),
        start_return_target_rad=tuple(np.radians(task['start_deg'])),
        outbound_goal_target_rad=tuple(np.radians(task['goal_deg'])))
    commissioning=np.radians(np.asarray(task['commissioning_waypoints_deg'],dtype=float))
    if commissioning.shape!=(5,2) or not np.allclose(commissioning[[0,-1]],spec.start_return_target_rad):
        raise ValueError('commissioning must start and end at registered task start')
    return human,geometry,spec,commissioning
