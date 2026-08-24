# Stage 3: full-3D UR10e surrogate

The `stage3b-ur10e-robot-core` tag preserves the independent robot-only torque
plant. The current Stage 3C work couples that core to an explicit port of frozen
Human V2 through a six-constraint rigid cuff. Stage 3 remains an independent
package and never imports either frozen `traction_mpc` package at runtime.

## Setup and validation

Run from this directory in the recorded `mpc_learn` environment:

```bash
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
conda run -n mpc_learn pytest -q
conda run -n mpc_learn python scripts/run_robot_core_validation.py --samples 301
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage3c_nominal_smoke.py \
  --output-dir results/engineering_stage3c
```

The Stage 3C script runs the bounded `[5 deg, 10 deg]` hold and 3-degree
departure gates before the single 15-second frozen nominal smoke. It preserves
JSON and compressed traces under the requested output directory. These are
engineering validation artifacts, not formal or authoritative evidence.

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

At the Stage 3B tag the adapter is only a robot-side frame definition; no Human
V2 weld or contact is present there.

## Stage 3C coupling contract

The coupled model adds only the frozen planar two-joint Human V2, its unilateral
bed contact, and an equality weld between `attachment_site` and
`sleeve_attach_site`. The provisional adapter stays explicitly identity. Robot
self-collision remains active. Collision bit domains isolate it from the Human
and bed so model composition does not introduce robot--Human or robot--bed
contacts; the Human--bed contact parameters are unchanged from Stage 2.

The nominal controller is a direct semantic port of Stage 2:

1. frozen Human reference and inverse dynamics;
2. minimum-translational-force cuff allocation with unbounded sagittal moment;
3. full 6D pose/wrench command;
4. `J_robot.T @ wrench`, bias torque, and the retained nullspace term;
5. explicit gear-1 torque motors with modeled UR10e limits.

The 200 N cuff gate applies only to translational force. No cuff moment limit or
moment clipping is introduced. Physical cuff wrench is reconstructed through
virtual work from the weld generalized force; raw rotational equality
multipliers are never interpreted as N m.

## Real-robot-facing software boundary

The post-Stage-3C interface work is deliberately hardware-independent and does
not command a real robot. See:

- [`docs/REAL_ROBOT_INTERFACE_CONTRACT.md`](docs/REAL_ROBOT_INTERFACE_CONTRACT.md)
- [`docs/CR12_LOCAL_HARDWARE_AUDIT.md`](docs/CR12_LOCAL_HARDWARE_AUDIT.md)
- [`docs/REAL_ROBOT_COMMISSIONING_PLAN.md`](docs/REAL_ROBOT_COMMISSIONING_PLAN.md)

`Stage3SimulationBackend` implements the contract using the validated MuJoCo
plant. `CR12DryRunBackend` contains no network or SDK transport and always
rejects transmission. In particular, the laboratory CR12 torque-control
capability remains unknown until confirmed by the exact controller and its
matching manufacturer API documentation.
