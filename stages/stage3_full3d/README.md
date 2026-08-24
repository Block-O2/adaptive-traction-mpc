# Stage 3B: independent full-3D UR10e robot core

This stage establishes a robot-only MuJoCo execution plant. It does not import,
modify, or couple either frozen `traction_mpc` package, Human V2, the cuff weld,
the rehabilitation controller, or adaptive control.

## Setup and validation

Run from this directory in the recorded `mpc_learn` environment:

```bash
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
conda run -n mpc_learn pytest -q
conda run -n mpc_learn python scripts/run_robot_core_validation.py --samples 301
```

The validation script prints robot-only diagnostic JSON and does not promote a
formal or authoritative result.

## Model boundary

The byte-preserved Menagerie UR10e source is under
`vendor/mujoco_menagerie/universal_robots_ur10e/`. Its geometry, inertias,
joint axes, joint limits, and documentation are unchanged. See
[`vendor/PROVENANCE.md`](vendor/PROVENANCE.md).

`models/ur10e_torque.xml` is the Stage-3 execution variant. It changes only the
asset path and actuator contract:

- the Menagerie position servos are removed;
- each joint has one gear-1 torque motor;
- `ctrl[i]` is joint torque in N m and maps one-to-one to the corresponding
  `qfrc_actuator` entry;
- the Menagerie force ranges remain the modeled torque limits
  `[330, 330, 150, 56, 56, 56] N m`;
- the home keyframe torque command is zero;
- vendor joint damping and armature remain passive model properties.

These are surrogate model limits, not real UR10e, CR12, treatment, or clinical
limits. Menagerie also states that the original UR10e actuator gains, damping,
and armature were not carefully tuned; the Stage-3 torque interface therefore
does not reuse its position-servo gains.

## Frames

Transform names use `PARENT_FROM_CHILD`.

| Frame | Definition |
|---|---|
| `WORLD` | Existing Stage-2 world convention. |
| `BASE` | UR10e model frame, translated to `(1.10, -0.62, 0.04) m` with axes aligned to `WORLD`. |
| `wrist_3_link` | Final serial-link body from the unchanged vendor kinematic tree. |
| `ATTACHMENT` | Vendor `attachment_site`: position `(0, 0.1, 0) m` and normalized quaternion `(-0.7071, 0.7071, 0, 0)` in `wrist_3_link`. |
| `CUFF` | Frozen Stage-2 cuff pose reference frame. |

The provisional rigid adapter is explicitly
`ATTACHMENT_FROM_CUFF = identity`. Therefore IK makes `ATTACHMENT` coincident
with `CUFF`; no orientation correction is hidden in IK or controller code.
The chain is

```text
WORLD_FROM_CUFF
  = WORLD_FROM_BASE
  * BASE_FROM_ATTACHMENT(q)
  * ATTACHMENT_FROM_CUFF
```

The adapter remains a robot-only frame definition in this stage. No Human V2
weld or contact is present.
