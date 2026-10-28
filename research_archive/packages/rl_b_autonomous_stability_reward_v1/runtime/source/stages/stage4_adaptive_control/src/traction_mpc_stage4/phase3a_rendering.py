"""Neutral frozen-state renderer support for the final Phase-3A report.

This module constructs the corrected High-ROM rigid plant used only to render
saved states.  It does not import an experiment runner, invoke MPC, or advance
a trajectory.
"""

from __future__ import annotations

from dataclasses import replace
import math

from traction_mpc_stage3.coupled import SUSPENDED_SEATED_LIKE_SCENARIO
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import HUMAN

from .sensor_realism import (
    ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY,
    SensorBoundaryStage4Plant,
)


HIGH_ROM_HUMAN = replace(
    HUMAN,
    q_min_rad=(0.0, 0.0),
    q_max_rad=(math.radians(125.0), math.radians(125.0)),
)
PHASE3A_PHYSICS_DT_S = 0.00025


def create_phase3a_rigid_render_plant() -> SensorBoundaryStage4Plant:
    """Create the frozen corrected rigid plant without running a trajectory."""

    plant = SensorBoundaryStage4Plant(
        HIGH_ROM_HUMAN,
        attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
        engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
        translational_velocity_feedback_source=(
            ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
        ),
    )
    plant.model.opt.timestep = PHASE3A_PHYSICS_DT_S
    return plant
