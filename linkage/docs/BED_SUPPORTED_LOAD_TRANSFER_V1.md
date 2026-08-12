# Bed-Supported Load Transfer V1

## Status and coordinate correction

This stage adds an engineering horizontal-support abstraction around the
unchanged Human Model V2. The mathematical coordinate definition was already
correct: +x is horizontal to the right, +y is upward, q1 is measured from +x,
and the shank absolute angle is `phi=q1-q2`. Thus q1=0 degrees is a horizontal
thigh and `[q1,q2]=[5,10] deg` is a nearly horizontal supine posture. The
vertical appearance of the first Hybrid Tube V1 GIF came from swapped sine and
cosine terms in drawing code only; the tracked dynamics and force calculations
were not rotated or changed.

PR #13 remains the unsupported, fully suspended initialization negative
baseline. It shows that directly assigning the robot the `[5,10] deg` hold is
infeasible under the 80/120/200 N engineering component boxes. It does not
establish that a tube-based task is infeasible after an explicit support and
load-transfer phase.

The new implementation and tests are present. The full dynamic matrix remains
reserved for user execution under repository policy; no formal cycle outcome
or GIF is promoted in this report.

## World geometry and support candidates

The hip remains the origin of the existing local V2 kinematics. World points
are formed as

\[
p_{world}=p_{local}+[0,h_{hip}]^T,
\]

and the bed is the horizontal plane `y=0`. Hip and bed are therefore not
incorrectly colocated.

The minimal V1 surface abstraction uses four uniformly spaced candidates on
each segment at fractions `[0.2,0.4,0.6,0.8]`. They represent regularly
sampled lower limb surfaces, not point bones. Fixed vertical centerline-to-
surface offsets are 0.100 m for the thigh and 0.075 m for the shank. These are
engineering geometry assumptions and are not fitted per case.

At each point,

\[
\delta_i=\max(-y_i,0),\qquad
F_{bed,i}=\begin{cases}
\max(0,k_{bed}\delta_i+c_{bed}\max(-\dot y_i,0)),&\delta_i>0,\\
0,&\delta_i=0.
\end{cases}
\]

Only a world-up normal force is present. V1 has no tensile support and no
tangential friction. Its generalized torque is computed explicitly as

\[
\tau_{bed}=\sum_i J_i^T[0,F_{bed,i}]^T.
\]

The nominal/softer/stiffer engineering pairs are `(3000 N/m,55 Ns/m)`,
`(1500,35)`, and `(6000,80)`. They are not clinical mattress parameters.

## Fixed initial calibration

One deterministic nominal-bed search over `h_hip=0.04..0.16 m` selects the
height minimizing normalized robot holding force, whole-leg vertical support
mismatch, and penetration, subject to maximum penetration `0.03 m`. The same
calibrated geometry is retained for all three bed-stiffness sensitivities so
stiffness remains the only changed bed variable.

For the nominal adult at `[5,10] deg`, the calibration gives:

- `h_hip = 0.06825 m`;
- eight initial gaps, thigh then shank:
  `[-0.024135,-0.016519,-0.008904,-0.001289,0.024341,0.017355,0.010369,0.003384] m`;
- four active thigh forces:
  `[72.404,49.558,26.712,3.866] N`, totaling `152.540 N`;
- initial bed generalized torque `[23.251,0] N m`;
- total static holding torque `[40.518,-7.578] N m`;
- residual robot force `[F_parallel,F_perp]=[-8.543,21.011] N`, norm
  `22.681 N`;
- generalized-torque balance residual `0` at printed precision.

The bed force exceeds the two modeled links' weight because the hip is a fixed
constraint and can carry an unreported reaction; bed force is therefore not a
standalone body-weight percentage. Robot and bed forces and torques are kept
separate throughout.

## Dynamics and bed-off identity

The extended equation is

\[
M\ddot q+h+G+\tau_{passive}
=A_{robot}F_{robot}+\tau_{bed}.
\]

No gravity-compensation hack or passive-sign change is added. With
`bed_enabled=false`, bed force and torque are exactly zero and tests compare
the full state derivative against the retained suspended endpoint dynamics to
machine precision.

The controller retains the existing equilibrium feedback and deterministic
bounded two-dimensional solver. It subtracts the current bed generalized
torque from the total requested generalized torque before solving for robot
force. Component-force and slew constraints remain explicit; dynamics and
controller residuals are logged separately.

## Hybrid sequence and guards

The implementation records these modes:

1. `BED_SUPPORT`;
2. `SUPPORTED_PREPOSITION`;
3. `LOAD_TAKEOVER`;
4. `LIFTOFF`;
5. `SUSPENDED_MOTION`;
6. `RECONTACT`;
7. `LOAD_RETURN`;
8. `RELEASE`.

`SUPPORTED_PREPOSITION` is a bed-supported, pre-liftoff configuration
adjustment. Formal rehabilitation progress remains exactly `s=0`. A
deterministic enumeration searches only the initial 5 or 10 degree tube and
rejects ROM violations, active soft limits, inadequate force margin, excessive
bounded residual, or loss of bed support. Its normalized objective includes
nominal-posture deviation, predicted robot-only axial and total force, force
change, and soft/ROM clearance. PR #12's low-force posture is mechanics
evidence only and is not hard-coded as a target.

At every candidate, robot-only feasibility is evaluated independently from
the current bed-supported balance using

\[
A(q)F_{robot}=G(q)+\tau_{passive}(q,0).
\]

The witness force, component margin, bounded residual, mapping conditioning,
and ROM/soft-limit margins are logged. Only a continuously reached robust
witness can enter `LOAD_TAKEOVER`. This is not hidden pre-positioning: the
plant begins at `[5,10] deg`, follows a quintic reference while visibly
supported by the bed, and formal task progress has not begun.

Load takeover continuously reduces the bed generalized-torque credit used by
the robot controller from one to zero; robot force remains subject to the
retained slew box. If robot-only feasibility is lost, the sequence returns to
supported preposition once, then reports `PREPOSITION_INFEASIBLE` rather than
forcing liftoff. Entry to suspended motion requires both bed
normal force below the contact threshold and an exact robot-only holding
solution within the configured force bound. Re-contact is contact-driven on
the return portion, not a fixed-time declaration. Release is accepted only
after bed support has remained active for the configured stable interval.

Terminal classifications are `TASK_COMPLETE`, `INITIAL_SUPPORT_REQUIRED`,
`PREPOSITION_INFEASIBLE`, `LIFTOFF_INFEASIBLE`, `SUSPENDED_INFEASIBLE`, `RECONTACT_FAILED`,
`LOAD_RETURN_FAILED`, and `ABORTED`. A failed handoff is never represented as
a successful transfer.

## Validation boundary and smoke observation

Twenty bed-stage tests cover the requested coordinate convention, bed-off identity,
unilateral force, zero force without contact, Jacobian torque accumulation,
calibrated equilibrium, force-slew continuity, robot-only liftoff guard,
re-contact force restoration, stable external support before release, and
total dynamics balance. The added preposition checks cover `s=0`, tube and ROM
containment, bed-supported versus robot-only feasibility, takeover blocking,
failure classification, feasibility loss during takeover, liftoff guards, and
reference/force continuity.

A six-case nominal-bed smoke used the fixed 80/120/200 N bounds and 5/10 degree
tubes. No case entered `LIFTOFF`, so the formal matrix was not run and no
parameter was tuned. Five cases contained no robust robot-only target and
stopped from `BED_SUPPORT` as `PREPOSITION_INFEASIBLE`. The 200 N/10 degree
case found the enumerated target `[7,20] deg`, reached
`SUPPORTED_PREPOSITION`, and entered `LOAD_TAKEOVER`. Near the end of takeover,
the actual posture `[7.057,19.292] deg` required the robot-only witness
`[-195.030,16.116] N`; its remaining component margin fell to `4.970 N`, just
below the fixed `5 N` guard. The sequence did not continue to liftoff and
reported `PREPOSITION_INFEASIBLE`. There was no soft-limit activation, ROM
violation, or boundary-seeking in this smoke. This is mechanical smoke
evidence, not a formal scientific conclusion.

The representative ignored smoke GIF and metrics are under
`linkage/results/local/bed_supported_load_transfer_v1/smoke_preposition/`.
They explicitly display the mode, bed and actual robot forces, robot-only
witness, bounded residual, nominal/governed/tube joint signals, and `s=0`.

Within the present tube and support abstraction, the smoke does not justify
running the formal matrix. A viable next attempt would require explicitly
approved wider task freedom, a different support/load-transfer strategy, or an
architecture change rather than hidden weight tuning.

## Formal matrix and outputs

The formal runner covers tube caps 5/10 degrees, force-component bounds
80/120/200 N, and softer/nominal/stiffer bed sensitivities. The force bounds
are engineering diagnostics, not clinical safety thresholds. It generates
MAT/CSV/text, load-share and contact-event figures, and one nominal-bed GIF
for each force bound under:

```text
linkage/results/local/bed_supported_load_transfer_v1/
```

Formal command reserved for the user:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_bed_supported_load_transfer_v1"
```

The GIF uses equal world axes and explicitly labels +x right, +y up, q1 from
+x, `y=0` bed, hip height, active support candidates, bed load, robot force,
progress, and hybrid mode.

This V1 does not claim q2=0 fully suspended holding or clinical safety. More
realistic mattress deformation, straps, limb radii, pressure distribution,
soft tissue, hip motion, or tangential contact require a separate contact-
model upgrade.
