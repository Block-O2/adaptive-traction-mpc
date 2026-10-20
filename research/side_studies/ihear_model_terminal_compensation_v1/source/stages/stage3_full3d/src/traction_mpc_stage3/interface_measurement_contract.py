"""Explicit soft-interface sensor boundary; world axes, robot-site reference.

Physical plant truth and robot-facing ideal sensor truth are separate objects.
The latter is the only soft-interface input accepted by CausalMeasurementLayer.
No Human pose, deformation, state, or parameters cross this boundary.
"""
from dataclasses import dataclass

import numpy as np

from .spring_damper_interface import SpringDamperCoupledUR10eHumanV2


@dataclass(frozen=True)
class RobotInterfaceSensorTruth:
    """Ideal sensor channels before sampling/noise/filtering/delay.

    Wrench is robot-to-interface transmitted load ABOUT adapter_cuff_site in
    WORLD axes, i.e. the negative of the physical reaction acting on the robot.
    This preserves the existing positive transmitted-load convention.
    """
    time_s: float
    robot_q_rad: np.ndarray
    robot_dq_rad_s: np.ndarray
    attachment_position_m: np.ndarray
    attachment_rotation_matrix: np.ndarray
    attachment_velocity_m_s: np.ndarray
    attachment_angular_velocity_rad_s: np.ndarray
    cuff_force_vector_n: np.ndarray
    cuff_moment_vector_nm: np.ndarray
    cuff_wrench_reference_point: str = 'adapter_cuff_site'
    controller_measurement_requires_adapter: bool = False


def transport_world_wrench(wrench: np.ndarray, from_point_m: np.ndarray,
                           to_point_m: np.ndarray) -> np.ndarray:
    """Same physical load, same world axes, different moment reference point."""
    force, moment = np.asarray(wrench)[:3], np.asarray(wrench)[3:]
    return np.r_[force, moment + np.cross(np.asarray(from_point_m)-to_point_m, force)]


def robot_interface_sensor_truth(plant: SpringDamperCoupledUR10eHumanV2) -> RobotInterfaceSensorTruth:
    interface, robot, _ = plant.interface_diagnostics()
    transmitted_at_robot = -interface.robot_wrench_world
    return RobotInterfaceSensorTruth(
        float(plant.data.time), plant.data.qpos[plant.robot_qpos_indices].copy(),
        plant.data.qvel[plant.robot_dof_indices].copy(), robot.position_world_m,
        robot.rotation_world, robot.velocity_world_m_s, robot.angular_velocity_world_rad_s,
        transmitted_at_robot[:3].copy(), transmitted_at_robot[3:].copy(),
    )
