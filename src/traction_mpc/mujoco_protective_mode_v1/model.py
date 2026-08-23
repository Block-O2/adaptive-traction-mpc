"""MJCF construction for the minimal Human V2 / bed / cuff / robot model."""

from __future__ import annotations

from .config import HumanV2Parameters, ProtectiveModeConfig


def build_mjcf(
    parameters: HumanV2Parameters,
    config: ProtectiveModeConfig,
    cuff_interface: str = "tension_only",
) -> str:
    """Build a self-contained model with no external mesh dependency.

    ``bilateral_point`` is an M1.5 simulation hypothesis, not a hardware
    contract.  It uses the same nominal stiffness/damping numbers as the V1
    tendon, but applies them through a bilateral MuJoCo point connection.
    """

    if cuff_interface not in {"tension_only", "bilateral_point"}:
        raise ValueError(f"unsupported cuff interface: {cuff_interface}")

    p, c = parameters, config
    # MuJoCo requires a physically valid 3-D inertia tensor. The validated
    # planar y-axis values stay exact; unused x/z entries are 51% of Iyy.
    i1_half = p.thigh_inertia_kg_m2 * 0.51
    i2_half = p.shank_inertia_kg_m2 * 0.51
    tendon_stiffness = c.cuff_stiffness_n_m if cuff_interface == "tension_only" else 0.0
    tendon_damping = c.cuff_damping_ns_m if cuff_interface == "tension_only" else 0.0
    equality = ""
    if cuff_interface == "bilateral_point":
        equality = f"""  <equality>
    <connect name="cuff_bilateral_connection" site1="robot_cuff_attach_site" site2="cuff_site"
      solref="-{c.cuff_stiffness_n_m:.9g} -{c.cuff_damping_ns_m:.9g}"
      solimp="0.95 0.99 0.001"/>
  </equality>
"""
    return f"""<mujoco model="human_v2_protective_mode_v1">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="{c.simulation_dt_s:.9g}" gravity="0 0 -{p.gravity_m_s2:.9g}" integrator="implicitfast" cone="elliptic" iterations="80"/>
  <default>
    <geom condim="4" friction="{c.bed_friction:.9g} 0.01 0.001" solref="{c.bed_solref_timeconst_s:.9g} {c.bed_solref_dampratio:.9g}" solimp="0.90 0.98 {c.bed_solimp_width_m:.9g}"/>
    <joint armature="0.002"/>
  </default>
  <worldbody>
    <light pos="0 -1 2" dir="0 0 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="bed" type="plane" pos="0 0 {c.bed_height_m:.9g}" size="1.5 0.5 0.05" rgba="0.55 0.70 0.82 1" contype="1" conaffinity="1"/>
    <body name="hip" pos="0 0 {c.hip_height_m:.9g}">
      <joint name="hip_joint" type="hinge" axis="0 -1 0" range="{p.q_min_rad[0]:.12g} {p.q_max_rad[0]:.12g}" stiffness="{p.passive_stiffness_nm_rad[0]:.9g}" damping="{p.passive_damping_nms_rad[0]:.9g}" springref="{p.q_rest_rad[0]:.12g}"/>
      <inertial pos="{p.thigh_com_m:.12g} 0 0" mass="{p.thigh_mass_kg:.12g}" diaginertia="{i1_half:.12g} {p.thigh_inertia_kg_m2:.12g} {i1_half:.12g}"/>
      <geom name="thigh_geom" type="capsule" fromto="0 0 0 {p.thigh_length_m:.12g} 0 0" size="{c.thigh_radius_m:.9g}" rgba="0.24 0.48 0.82 1" contype="1" conaffinity="1"/>
      <body name="shank" pos="{p.thigh_length_m:.12g} 0 0">
        <joint name="knee_joint" type="hinge" axis="0 1 0" range="{p.q_min_rad[1]:.12g} {p.q_max_rad[1]:.12g}" stiffness="{p.passive_stiffness_nm_rad[1]:.9g}" damping="{p.passive_damping_nms_rad[1]:.9g}" springref="{p.q_rest_rad[1]:.12g}"/>
        <inertial pos="{p.shank_com_m:.12g} 0 0" mass="{p.shank_mass_kg:.12g}" diaginertia="{i2_half:.12g} {p.shank_inertia_kg_m2:.12g} {i2_half:.12g}"/>
        <geom name="shank_geom" type="capsule" fromto="0 0 0 {p.shank_length_m:.12g} 0 0" size="{c.shank_radius_m:.9g}" rgba="0.90 0.48 0.18 1" contype="1" conaffinity="1"/>
        <site name="cuff_site" pos="{p.cuff_location_m:.12g} 0 0" size="0.012" rgba="0.95 0.15 0.10 1"/>
      </body>
    </body>
    <body name="robot_x" pos="0 0 0">
      <joint name="robot_x_joint" type="slide" axis="1 0 0" range="-0.2 1.2" damping="0.5"/>
      <inertial pos="0 0 0" mass="0.01" diaginertia="0.00001 0.00001 0.00001"/>
      <body name="robot_ee">
        <joint name="robot_z_joint" type="slide" axis="0 0 1" range="-0.2 1.2" damping="0.5"/>
        <inertial pos="0 0 0" mass="0.5" diaginertia="0.001 0.001 0.001"/>
        <geom name="robot_ee_geom" type="sphere" size="0.025" rgba="0.18 0.72 0.28 1" contype="0" conaffinity="0"/>
        <site name="robot_site" size="0.012" rgba="0.10 0.80 0.20 1"/>
        <site name="robot_cuff_attach_site" pos="0 0 -{c.cuff_rest_length_m:.9g}" size="0.009" rgba="0.65 0.20 0.85 1"/>
      </body>
    </body>
  </worldbody>
  <tendon>
    <spatial name="cuff_tendon" stiffness="{tendon_stiffness:.9g}" damping="{tendon_damping:.9g}" springlength="{c.cuff_rest_length_m:.9g}" width="0.006" rgba="0.15 0.75 0.20 1">
      <site site="robot_site"/><site site="cuff_site"/>
    </spatial>
  </tendon>
{equality}  <actuator>
    <motor name="robot_x_motor" joint="robot_x_joint" gear="1" ctrlrange="-{c.actuator_force_limit_n:.9g} {c.actuator_force_limit_n:.9g}"/>
    <motor name="robot_z_motor" joint="robot_z_joint" gear="1" ctrlrange="-{c.actuator_force_limit_n:.9g} {c.actuator_force_limit_n:.9g}"/>
  </actuator>
  <sensor>
    <jointpos name="measured_q1" joint="hip_joint"/>
    <jointpos name="measured_q2" joint="knee_joint"/>
    <jointvel name="measured_dq1" joint="hip_joint"/>
    <jointvel name="measured_dq2" joint="knee_joint"/>
    <tendonpos name="cuff_length" tendon="cuff_tendon"/>
    <tendonvel name="cuff_velocity" tendon="cuff_tendon"/>
  </sensor>
</mujoco>"""
