# adaptive-traction-mpc

Stage 2 retains a planar Human V2 MuJoCo validation plant with a rigid
robot-to-cuff weld, physical cuff-wrench reconstruction, and a nominal
inverse-dynamics cuff controller with 6D pose feedback. The 200 N cuff
translational-force gate, robot joint-torque limits, Human V2 ROM/passive
dynamics/cubic soft limit, and the registered 15 s rehab reference remain
frozen.

This is simulation-only engineering evidence. It is not hardware, clinical,
or formal safety validation. Stage 3 robot-surrogate work is intentionally not
included on this cleanup branch.

## Setup

Python 3.10 or newer is required. The retained environment is named
`mpc_learn` in the recorded commands.

```bash
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
```

## Retained commands

Run the rigid-cuff posture validation:

```bash
conda run -n mpc_learn python scripts/run_mujoco_sleeve_robot_v2.py \
  --output-dir linkage/results/local/rigid_cuff_postures
```

Run the nominal 3-degree full rehab cycle:

```bash
conda run -n mpc_learn python scripts/run_mujoco_sleeve_robot_v2.py \
  --dynamic-baseline --lower-q2-deg 3 \
  --output-dir linkage/results/local/nominal_q2_3
```

Run the registered fixed-model mismatch matrix with a nominal controller:

```bash
conda run -n mpc_learn python scripts/run_mujoco_sleeve_robot_v2.py \
  --fixed-model-mismatch \
  --output-dir linkage/results/local/fixed_model_mismatch_q2_3
```

Run all retained Python regressions:

```bash
conda run -n mpc_learn pytest -q
```

The final Stage-2 conclusions and compact evidence index are in
[`linkage/docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md`](linkage/docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md).
