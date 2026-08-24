# Stage 2: Human V2 rigid-cuff linkage

Stage 2 is the frozen planar Human V2 MuJoCo baseline. The robot end effector
is weld-coupled to the cuff/shank, reset and IK are pose-consistent, and a
nominal Human V2 inverse-dynamics cuff wrench is combined with six-dimensional
pose feedback and mapped through the robot Jacobian. Physical cuff force and
sagittal moment are reconstructed from the constraint Jacobian.

The former point-force/tendon branch is superseded and is not live code. Human
V2 ROM, passive dynamics, cubic soft limit, zero Human-joint armature, the
200 N translational-force gate, robot torque limits, controller gains, and the
15 s rehabilitation reference remain frozen. `My` is logged without inventing
a moment limit.

The nominal original and 3-degree full cycles completed without force, ROM,
robot-torque, nonfinite-state, or solver violations. The 3-degree endpoint is
an engineering probe, not a hard, anatomical, clinical, or treatment limit.
Bed-contact switching was measured as negligible boundary/solver chatter with
little dynamic contribution. Registered fixed-model mismatch cases remain
executable; mild completed the terminal gate, while moderate/adverse reached
15 s but missed terminal tracking tolerance.

The CR12-like arm remains only an engineering surrogate. A later CAD audit
judged credible CR12 reconstruction **NO-GO** because it would require
substantial reconstruction or guessed joint geometry/dynamics. Stage 3 has not
started and will select a complete six-DoF model from MuJoCo Menagerie.

## Setup and retained validation

Run from this directory:

```bash
cd stages/stage2_linkage
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
conda run -n mpc_learn pytest -q
conda run -n mpc_learn python scripts/run_mujoco_sleeve_robot_v2.py \
  --dynamic-baseline --lower-q2-deg 3 \
  --output-dir results/local/nominal_q2_3
```

The full conclusions and numerical table are in
[`docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md`](docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md).
The compact final evidence is in `results/final/`: one nominal GIF, one
timeseries figure, and one fixed-model mismatch summary.
