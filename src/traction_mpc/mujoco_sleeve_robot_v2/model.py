"""MJCF builder for the CR12-like sleeve/robot plant V2."""

from __future__ import annotations

import math

from .config import HumanV2Parameters, PlantV2Config, RobotV2Parameters
from .kinematics import coordinated_posture


def build_plant_xml(
    human: HumanV2Parameters,
    robot: RobotV2Parameters,
    config: PlantV2Config,
    fixture_q2_deg: float | None = None,
) -> str:
    """Return a primitive-geometry plant with no unverified CR12 mesh use."""

    i1_half = 0.51 * human.thigh_inertia_kg_m2
    i2_half = 0.51 * human.shank_inertia_kg_m2
    sc = human.sleeve_center_m
    half = config.sleeve_half_length_m
    base_x, base_y, base_z = robot.base_position_m
    l2, l3, l4, l5, l6 = robot.link_lengths_m
    masses = robot.link_masses_kg
    ranges = [tuple(math.radians(value) for value in limits) for limits in robot.joint_ranges_deg]
    fixture_xml = ""
    if fixture_q2_deg is not None:
        fixture_q = coordinated_posture(math.radians(fixture_q2_deg))
        fixture_xml = f"""
    <joint name="fixture_hip" joint1="hip_joint" polycoef="{fixture_q[0]:.12g} 0 0 0 0" solref="-20000 -400"/>
    <joint name="fixture_knee" joint1="knee_joint" polycoef="{fixture_q[1]:.12g} 0 0 0 0" solref="-20000 -400"/>"""

    actuator_xml = "\n".join(
        f'    <motor name="robot_motor_{index + 1}" joint="robot_joint_{index + 1}" '
        f'ctrlrange="-{limit:.9g} {limit:.9g}"/>'
        for index, limit in enumerate(robot.joint_torque_limits_nm)
    )
    return f"""<mujoco model="cr12_like_sleeve_robot_v2">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="{config.simulation_dt_s:.9g}" gravity="0 0 -{human.gravity_m_s2:.9g}" integrator="implicitfast" cone="elliptic" iterations="100"/>
  <default>
    <geom friction="{config.bed_friction:.9g} 0.01 0.001" solref="{config.bed_solref_timeconst_s:.9g} {config.bed_solref_dampratio:.9g}" solimp="0.90 0.98 {config.bed_solimp_width_m:.9g}"/>
    <joint armature="0.003"/>
  </default>
  <worldbody>
    <light pos="0 -1 2" dir="0 0 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="bed" type="plane" pos="0 0 {config.bed_height_m:.9g}" size="1.6 1.0 0.05" rgba="0.55 0.70 0.82 1" contype="1" conaffinity="1"/>
    <body name="hip" pos="0 0 {config.hip_height_m:.9g}">
      <joint name="hip_joint" type="hinge" axis="0 -1 0" range="{human.q_min_rad[0]:.12g} {human.q_max_rad[0]:.12g}" stiffness="{human.passive_stiffness_nm_rad[0]:.9g}" damping="{human.passive_damping_nms_rad[0]:.9g}" springref="{human.q_rest_rad[0]:.12g}"/>
      <inertial pos="{human.thigh_com_m:.12g} 0 0" mass="{human.thigh_mass_kg:.12g}" diaginertia="{i1_half:.12g} {human.thigh_inertia_kg_m2:.12g} {i1_half:.12g}"/>
      <geom name="thigh_geom" type="capsule" fromto="0 0 0 {human.thigh_length_m:.12g} 0 0" size="{config.thigh_radius_m:.9g}" rgba="0.24 0.48 0.82 1" contype="1" conaffinity="1"/>
      <body name="shank" pos="{human.thigh_length_m:.12g} 0 0">
        <joint name="knee_joint" type="hinge" axis="0 1 0" range="{human.q_min_rad[1]:.12g} {human.q_max_rad[1]:.12g}" stiffness="{human.passive_stiffness_nm_rad[1]:.9g}" damping="{human.passive_damping_nms_rad[1]:.9g}" springref="{human.q_rest_rad[1]:.12g}"/>
        <inertial pos="{human.shank_com_m:.12g} 0 0" mass="{human.shank_mass_kg:.12g}" diaginertia="{i2_half:.12g} {human.shank_inertia_kg_m2:.12g} {i2_half:.12g}"/>
        <geom name="shank_geom" type="capsule" fromto="0 0 0 {human.shank_length_m:.12g} 0 0" size="{config.shank_radius_m:.9g}" rgba="0.90 0.48 0.18 1" contype="1" conaffinity="1"/>
        <geom name="sleeve_geom" type="cylinder" fromto="{sc - half:.12g} 0 0 {sc + half:.12g} 0 0" size="{config.sleeve_outer_radius_m:.9g}" rgba="0.62 0.22 0.80 0.75" contype="0" conaffinity="0"/>
        <site name="sleeve_attach_site" pos="{sc:.12g} 0 0" size="0.014" rgba="0.90 0.10 0.75 1"/>
      </body>
    </body>

    <body name="robot_base" pos="{base_x:.9g} {base_y:.9g} {base_z:.9g}">
      <geom name="robot_base_geom" type="cylinder" pos="0 0 0.10" size="0.14 0.10" rgba="0.12 0.20 0.32 1" contype="0" conaffinity="0"/>
      <body name="robot_link_1">
        <joint name="robot_joint_1" type="hinge" axis="0 0 1" range="{ranges[0][0]:.12g} {ranges[0][1]:.12g}" damping="{robot.joint_damping_nms_rad[0]:.9g}"/>
        <inertial pos="0 0 {robot.base_column_height_m / 2:.9g}" mass="{masses[0]:.9g}" diaginertia="0.08 0.08 0.03"/>
        <geom type="capsule" fromto="0 0 0 0 0 {robot.base_column_height_m:.9g}" size="0.075" rgba="0.20 0.32 0.56 1" contype="0" conaffinity="0"/>
        <body name="robot_link_2" pos="0 0 {robot.base_column_height_m:.9g}">
          <joint name="robot_joint_2" type="hinge" axis="0 1 0" range="{ranges[1][0]:.12g} {ranges[1][1]:.12g}" damping="{robot.joint_damping_nms_rad[1]:.9g}"/>
          <inertial pos="{l2 / 2:.9g} 0 0" mass="{masses[1]:.9g}" diaginertia="0.025 0.16 0.16"/>
          <geom type="capsule" fromto="0 0 0 {l2:.9g} 0 0" size="0.065" rgba="0.30 0.48 0.78 1" contype="0" conaffinity="0"/>
          <body name="robot_link_3" pos="{l2:.9g} 0 0">
            <joint name="robot_joint_3" type="hinge" axis="0 1 0" range="{ranges[2][0]:.12g} {ranges[2][1]:.12g}" damping="{robot.joint_damping_nms_rad[2]:.9g}"/>
            <inertial pos="{l3 / 2:.9g} 0 0" mass="{masses[2]:.9g}" diaginertia="0.018 0.11 0.11"/>
            <geom type="capsule" fromto="0 0 0 {l3:.9g} 0 0" size="0.055" rgba="0.24 0.40 0.70 1" contype="0" conaffinity="0"/>
            <body name="robot_link_4" pos="{l3:.9g} 0 0">
              <joint name="robot_joint_4" type="hinge" axis="1 0 0" range="{ranges[3][0]:.12g} {ranges[3][1]:.12g}" damping="{robot.joint_damping_nms_rad[3]:.9g}"/>
              <inertial pos="{l4 / 2:.9g} 0 0" mass="{masses[3]:.9g}" diaginertia="0.008 0.025 0.025"/>
              <geom type="capsule" fromto="0 0 0 {l4:.9g} 0 0" size="0.045" rgba="0.18 0.34 0.62 1" contype="0" conaffinity="0"/>
              <body name="robot_link_5" pos="{l4:.9g} 0 0">
                <joint name="robot_joint_5" type="hinge" axis="0 1 0" range="{ranges[4][0]:.12g} {ranges[4][1]:.12g}" damping="{robot.joint_damping_nms_rad[4]:.9g}"/>
                <inertial pos="{l5 / 2:.9g} 0 0" mass="{masses[4]:.9g}" diaginertia="0.005 0.014 0.014"/>
                <geom type="capsule" fromto="0 0 0 {l5:.9g} 0 0" size="0.038" rgba="0.34 0.52 0.80 1" contype="0" conaffinity="0"/>
                <body name="robot_link_6" pos="{l5:.9g} 0 0">
                  <joint name="robot_joint_6" type="hinge" axis="1 0 0" range="{ranges[5][0]:.12g} {ranges[5][1]:.12g}" damping="{robot.joint_damping_nms_rad[5]:.9g}"/>
                  <inertial pos="{l6 / 2:.9g} 0 0" mass="{masses[5]:.9g}" diaginertia="0.003 0.007 0.007"/>
                  <geom type="capsule" fromto="0 0 0 {l6:.9g} 0 0" size="0.032" rgba="0.15 0.28 0.50 1" contype="0" conaffinity="0"/>
                  <site name="robot_ee_site" pos="{l6:.9g} 0 0" size="0.018" rgba="0.10 0.90 0.30 1"/>
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>

  <equality>
    <connect name="sleeve_connection" site1="robot_ee_site" site2="sleeve_attach_site" solref="-{config.sleeve_stiffness_n_m:.9g} -{config.sleeve_damping_ns_m:.9g}" solimp="{config.sleeve_solimp_min:.9g} {config.sleeve_solimp_max:.9g} {config.sleeve_solimp_width_m:.9g}"/>{fixture_xml}
  </equality>
  <actuator>
{actuator_xml}
  </actuator>
  <sensor>
    <jointpos name="measured_q1" joint="hip_joint"/>
    <jointpos name="measured_q2" joint="knee_joint"/>
    <jointvel name="measured_dq1" joint="hip_joint"/>
    <jointvel name="measured_dq2" joint="knee_joint"/>
    <framepos name="robot_ee_position" objtype="site" objname="robot_ee_site"/>
    <framelinvel name="robot_ee_velocity" objtype="site" objname="robot_ee_site"/>
  </sensor>
</mujoco>"""
