# Linkage System Definition Draft

> **Archived / Superseded.** This source-only reconstruction is retained for
> historical context and is not the current model definition. Start from
> [CURRENT_STATE.md](CURRENT_STATE.md), then use
> [HUMAN_MODEL_V2.md](HUMAN_MODEL_V2.md) for the current human model and
> [SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY.md](SINGLE_ARM_TRAJECTORY_FEASIBILITY_STUDY.md)
> for the latest single-contact trajectory mechanics analysis.

This reconstruction uses only the preserved `singleArmDual.m` source. It is a
description of the code, not a validation or correction of the model.

## Coordinates and state

The source defines the generalized coordinates

```math
q =
\begin{bmatrix}
q_1 \\ q_2
\end{bmatrix}
=
\begin{bmatrix}
\theta_{\mathrm{hip}} \\ \theta_{\mathrm{knee,flex}}
\end{bmatrix},
\qquad
x =
\begin{bmatrix}
q_1 & q_2 & \dot q_1 & \dot q_2
\end{bmatrix}^{\mathsf T}.
```

The hip is fixed at the origin. `q1=0` places the thigh along the positive X
axis, and positive `q1` raises it toward positive Y. The shank absolute angle
used by kinematics is

```math
\phi_2 = q_1-q_2.
```

`TODO / needs professor confirmation`: confirm that positive knee flexion is
intended to subtract from the thigh absolute angle in every dynamics equation.

## Inputs

The script exposes no external input argument. Its generalized applied torque
is

```math
\tau_{\mathrm{total}}
= \tau_{\mathrm{ctrl}}
+ J_1^{\mathsf T}F_1
+ J_2^{\mathsf T}F_2
+ \tau_{\mathrm{safety}}.
```

For a reusable plant, a provisional input could be
`u=tau_total`, or a structured input could contain joint control torque and two
endpoint forces separately.

`TODO / needs professor confirmation`: define the intended control/input vector
for the next architecture, especially whether future robot joint commands or
endpoint poses replace the current internal force construction.

## Physical parameters

| Quantity | Source value | Meaning / unit |
|---|---:|---|
| `L1`, `L2` | 0.45, 0.40 | thigh/shank length, m |
| `m1`, `m2` | 8.5, 3.8 | thigh/shank mass, kg |
| `lc1`, `lc2` | `L1/2`, `L2/2` | COM distance, m |
| `I1`, `I2` | `m_i L_i^2/12` | COM inertia, kg·m² |
| `g` | 9.81 | gravitational acceleration, m/s² |
| `s_attach1`, `s_attach2` | `0.55 L1`, `0.50 L2` | attachment distance, m |
| `offset1`, `offset2` | 0.13, 0.12 | displayed normal endpoint offset, m |
| `k_arm1`, `k_arm2` | 350, 300 | equivalent normal stiffness, N/m |
| `c_arm1`, `c_arm2` | 25, 20 | equivalent normal damping, N·s/m |

`TODO / needs professor confirmation`: confirm whether the link inertias and
anthropometric values are subject-specific, representative, or placeholders.

## Kinematics

With

```math
d_1=[\cos q_1,\sin q_1]^{\mathsf T},\quad
d_2=[\cos\phi_2,\sin\phi_2]^{\mathsf T},
```

the joint positions are

```math
p_H=[0,0]^{\mathsf T},\quad
p_K=p_H+L_1d_1,\quad
p_A=p_K+L_2d_2.
```

The attachment points are

```math
p_{c1}=p_H+s_1d_1,\qquad
p_{c2}=p_K+s_2d_2.
```

The displayed end-effector positions are

```math
p_{e1}=p_{c1}+o_1n_1,\qquad
p_{e2}=p_{c2}+o_2n_2,
```

where each normal starts as `[-sin(phi), cos(phi)]^T` and is sign-flipped if
its Y component is negative.

The coded attachment Jacobians are

```math
J_1 =
\begin{bmatrix}
-s_1\sin q_1 & 0\\
 s_1\cos q_1 & 0
\end{bmatrix},
```

```math
J_2 =
\begin{bmatrix}
-L_1\sin q_1-s_2\sin\phi_2 & s_2\sin\phi_2\\
 L_1\cos q_1+s_2\cos\phi_2 &-s_2\cos\phi_2
\end{bmatrix}.
```

`TODO / needs professor confirmation`: decide whether subsequent work should
use attachment-point or displayed-endpoint velocity/Jacobian.

## Governing equations

The source uses

```math
M(q)\ddot q
=\tau_{\mathrm{total}}-C(q,\dot q)\dot q-\tau_g(q).
```

The coded inertia terms are

```math
M_{11}=I_1+I_2+m_1l_{c1}^2
+m_2(L_1^2+l_{c2}^2+2L_1l_{c2}\cos q_2),
```

```math
M_{12}=M_{21}=I_2+m_2(l_{c2}^2+L_1l_{c2}\cos q_2),
\qquad
M_{22}=I_2+m_2l_{c2}^2.
```

With `h=-m2 L1 lc2 sin(q2)`,

```math
C =
\begin{bmatrix}
h\dot q_2 & h(\dot q_1+\dot q_2)\\
-h\dot q_1 & 0
\end{bmatrix}.
```

The coded gravity vector is

```math
\tau_g =
\begin{bmatrix}
-m_1gl_{c1}\sin q_1
-m_2g(L_1\sin q_1+l_{c2}\sin(q_1-q_2))\\
-m_2gl_{c2}\sin(q_1-q_2)
\end{bmatrix}.
```

`TODO / needs professor confirmation`: verify `M`, `C`, and `tau_g` against the
intended `q2` sign and the source's X-horizontal/Y-up frame. In particular, the
coded gravity moment is zero at a horizontal limb.

## External and endpoint forces

For each arm, the source defines

```math
\delta_i=o_i-(p_{ei}-p_{ci})^{\mathsf T}n_i,\qquad
v_{ni}=n_i^{\mathsf T}J_i\dot q,
```

```math
F_i=
\operatorname{clip}(k_i\delta_i-c_iv_{ni},-F_{i,\max},F_{i,\max})n_i,
```

with force limits 500 N and 400 N.

Since the source constructs `p_e-p_c=o n`, the coded displacement error
`delta_i` is identically zero apart from floating-point roundoff.

`TODO / needs professor confirmation`: supply the intended arm endpoint
reference/measured position if stiffness is meant to produce a nonzero
interaction force.

No separate bed contact, patient voluntary force, disturbance, or passive
joint impedance appears in the source.

## Controller

The references are

```math
q_{r,i}(t)=q_{0,i}+a_i(1-\cos\omega t),
\quad
\dot q_{r,i}=a_i\omega\sin\omega t,
\quad
\ddot q_{r,i}=a_i\omega^2\cos\omega t,
```

where `freq=0.2 Hz`, hip range is 0–65 degrees, and knee range is 0–70
degrees.

The coded controller is

```math
e=q-q_r,\qquad \dot e=\dot q-\dot q_r,
```

```math
\tau_{\mathrm{ff}}=M\ddot q_r+C\dot q_r,\qquad
\tau_{\mathrm{fb}}=-K_pe-K_d\dot e,
```

```math
\tau_{\mathrm{ctrl}}=\tau_g+\tau_{\mathrm{ff}}+\tau_{\mathrm{fb}},
```

with `Kp=diag(500,400)` and `Kd=diag(25,20)`.

`TODO / needs professor confirmation`: confirm gain units, torque limits, and
whether this should be called computed-torque PD, impedance control, or a
different intended controller.

## Safety logic and constraints

- Hip hard range: -5 to 85 degrees.
- Knee hard range: -5 to 120 degrees.
- Hip/knee speed limits: 60/80 deg/s.
- Soft safety torque activates 3 degrees before joint limits.
- When hip is below 20 degrees, knee flexion is limited by
  `1.4*hip + 5 degrees`.
- When hip exceeds 40 degrees, knee flexion is encouraged to remain at least
  15 degrees.
- Velocity and angle values are hard-clipped after integration.

`TODO / needs professor confirmation`: distinguish clinical constraints,
controller safeguards, and numerical clipping in the intended architecture.

## Integration/update equation

At `dt=0.0005 s`, the source applies semi-implicit Euler:

```math
\dot q_{k+1}
=\operatorname{clip}_{\dot q}
  (\dot q_k+\ddot q_k\Delta t),
```

```math
q_{k+1}
=\operatorname{clip}_{q}
  (q_k+\dot q_{k+1}\Delta t).
```

Total simulated time is 12 s. There is no early simulation termination.

## Initial condition

```math
x_0=[0.02,\;0.02,\;0,\;0]^{\mathsf T}.
```

Angles are radians and angular velocities are rad/s.

## Task objective

The visible objective is periodic tracking of coordinated hip and knee
flexion for a supine rehabilitation animation, while activating kinematic
safety protection near declared limits.

`TODO / needs professor confirmation`: define the actual task-success
criterion, acceptable tracking error, force/torque limits, patient safety
criteria, and whether one or multiple cycles form the baseline.

## Outputs

The script produces console summaries, an interactive animation, joint-angle
and tracking-error plots, joint torques, arm force components/magnitudes,
endpoint paths, joint velocities, endpoint orientations, phase plots, safety
activation history, and hip-knee coordination visualization.

No output file is saved by the original source. A future non-invasive runner
may capture workspace arrays, MAT data, figures, and a log under
`linkage/results/local/`, but none is validated in this intake.
