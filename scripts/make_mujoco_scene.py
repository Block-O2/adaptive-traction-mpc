"""
build scene_rod.xml: elastic rod + UR5e, direct torque control.
Rod: rigid rod + radial slide spring (k=5000, d=100).
Arm: UR5e on pedestal at z=0.3, motor actuators.
nq: [hinge_slide(0), rod_rotate(1), rod_radial(2), arm(3..8)]
"""
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UR5E_DIR = PROJECT_ROOT / 'third_party' / 'mujoco_menagerie' / 'universal_robots_ur5e'
OUT = PROJECT_ROOT / 'assets' / 'mujoco' / 'scene_rod.xml'

OUT.parent.mkdir(parents=True, exist_ok=True)
src = (UR5E_DIR / 'ur5e.xml').read_text()
src = src.replace('meshdir="assets"', f'meshdir="{UR5E_DIR / "assets"}"')
src = src.replace('<option integrator="implicitfast"/>',
                  '<option integrator="implicitfast" gravity="0 0 -9.81"/>')
src = re.sub(r'<actuator>.*?</actuator>', '', src, flags=re.DOTALL)

ROD = """
    <geom name="floor" type="plane"
          pos="0 0 -0.01" size="2 2 0.1"
          rgba="0.25 0.35 0.45 1" contype="0" conaffinity="0"/>

    <!-- Arm base plate flush with floor -->
    <geom name="pedestal" type="box"
          pos="0 0.4 -0.005" size="0.1 0.1 0.005"
          rgba="0.35 0.40 0.50 1" contype="0" conaffinity="0"/>

    <body name="hinge" pos="-0.5 0 0">
      <joint name="hinge_slide" type="slide" axis="1 0 0"
             range="-0.05 0.05" stiffness="200" damping="10"/>
      <geom type="sphere" size="0.018" rgba="0.85 0.45 0.85 1" mass="0.1"/>
      <body name="rod_pivot" pos="0 0 0">
        <joint name="rod_rotate" type="hinge" axis="0 -1 0"
               stiffness="0" damping="2.0" range="-0.1 3.3"/>
        <geom name="rod_geom" type="capsule"
              fromto="0 0 0  0.35 0 0"
              size="0.008" rgba="0.3 0.7 0.9 1" mass="1.5"/>
        <body name="rod_tip" pos="0.315 0 0.005">
          <joint name="rod_radial" type="slide" axis="1 0 0"
                 range="-0.03 0.03" stiffness="5000" damping="100"/>
          <geom type="sphere" size="0.014" rgba="1.0 0.55 0.1 1" mass="0.05"/>
          <site name="contact_site" pos="0 0 0" size="0.012" rgba="1 0.5 0 1"/>
        </body>
      </body>
    </body>"""

src = src.replace('<worldbody>', f'<worldbody>{ROD}', 1)

# Arm on pedestal at z=0.3
src = src.replace(
    '<body name="base"',
    '<body name="ur5e_mount" pos="0 0.4 0">\n      <body name="base"', 1)
src = src.replace('  </worldbody>', '    </body>\n  </worldbody>', 1)

EXTRA = """
  <actuator>
    <motor name="shoulder_pan_motor"  joint="shoulder_pan_joint"  ctrlrange="-150 150"/>
    <motor name="shoulder_lift_motor" joint="shoulder_lift_joint" ctrlrange="-150 150"/>
    <motor name="elbow_motor"         joint="elbow_joint"         ctrlrange="-150 150"/>
    <motor name="wrist_1_motor"       joint="wrist_1_joint"       ctrlrange="-28 28"/>
    <motor name="wrist_2_motor"       joint="wrist_2_joint"       ctrlrange="-28 28"/>
    <motor name="wrist_3_motor"       joint="wrist_3_joint"       ctrlrange="-28 28"/>
  </actuator>
  <equality>
    <connect site1="attachment_site" site2="contact_site"
             solimp="0.95 0.99 0.0001" solref="0.003 1"/>
  </equality>
  <sensor>
    <framepos    name="ee_pos"      objtype="site" objname="attachment_site"/>
    <framelinvel name="ee_vel"      objtype="site" objname="attachment_site"/>
    <framepos    name="contact_pos" objtype="site" objname="contact_site"/>
    <jointpos    name="rod_angle"   joint="rod_rotate"/>
    <jointpos    name="rod_stretch" joint="rod_radial"/>
    <jointvel    name="rod_stretch_vel" joint="rod_radial"/>
  </sensor>"""

src = src.replace('</mujoco>', EXTRA + '\n</mujoco>', 1)
OUT.write_text(src)
print(f"Written: {OUT}  ({len(src)} chars)")

try:
    import mujoco
    m = mujoco.MjModel.from_xml_path(str(OUT))
    print(f"MuJoCo OK: nq={m.nq} nv={m.nv} nu={m.nu}")
except Exception as e:
    print(f"ERROR: {e}")
