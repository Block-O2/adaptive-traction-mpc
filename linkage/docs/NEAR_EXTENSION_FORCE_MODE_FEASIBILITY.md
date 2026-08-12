# Near-Extension Force-Mode Feasibility

## Scope

This is an offline quasistatic mechanics/feasibility study, not a final
controller. It does not implement NMPC, a safety supervisor, closed-loop
tracking, a bed-contact model, or a second contact. No GIF is generated.

The study leaves Human Model V2, its passive model, the distal contact
location, the force map, the current V2 reference, and the frozen atlas
conclusions unchanged. The 80 N, 120 N, and 200 N component bounds are
engineering diagnostic bounds, not medical or clinical safety thresholds.

At every posture,

\[
\dot q=0,\quad \ddot q=0,\quad
\tau_{hold}=G(q)+\tau_{passive,left}(q,0),\quad
A(q)\begin{bmatrix}F_{parallel}\\F_{perp}\end{bmatrix}=\tau_{hold}.
\]

## Posture scan and objectives

The scan uses `q1=0:1:80 deg` and `q2=1:1:30 deg`. The `q2=0` row is
evaluated separately as rank deficient and no finite exact force is reported.
For each positive `q2`, two independent grid searches retain:

1. the posture minimizing `abs(F_parallel)`;
2. the posture minimizing total force norm.

The two objectives happen to select the same grid posture at every sampled
`q2` in this run, but they remain separate in code and output.

The representative posture follows the current V2 shared-progress
coordination line for `q2=10..30 deg`. For `q2=1..9 deg`, where the current
reference has no samples, the same line is only a diagnostic extrapolation.

| q2 (deg) | Representative q1 (deg) | Representative Fparallel / norm (N) | Minimum-|Fparallel| q1 (deg) | Optimum Fparallel / norm (N) | sigma_min / cond |
|---:|---:|---:|---:|---:|---:|
| 30 | 15.811 | -151.605 / 151.987 | 0 | -34.031 / 35.098 | 0.09316 / 9.079 |
| 20 | 10.405 | -191.799 / 192.461 | 0 | -18.656 / 23.926 | 0.06251 / 13.792 |
| 15 | 7.703 | -232.626 / 233.360 | 0 | -4.323 / 18.466 | 0.04699 / 18.470 |
| 10 | 5.000 | -315.030 / 315.730 | 0 | 22.992 / 30.985 | 0.03138 / 27.791 |
| 5 | 2.297 | -460.215 / 460.814 | 0 | 101.842 / 104.502 | 0.01570 / 55.685 |
| 2 | 0.676 | 530.892 / 532.391 | 2 | -189.492 / 193.654 | 0.00628 / 139.285 |
| 1 | 0.135 | 4170.479 / 4170.925 | 79 | 218.476 / 222.908 | 0.00314 / 278.590 |

At the current `[5,10] deg` start/end posture, the study reproduces the frozen
`315.7298 N` static force. Allowing the scanned hip posture to move to
`q1=0 deg` lowers `abs(F_parallel)` from `315.030 N` to `22.992 N`, a 92.7%
reduction, and lowers total force to `30.985 N`.

This improvement is not a general near-extension solution. The selected hip
posture lies at or near a ROM/soft-limit boundary for most of the scan, and at
`q2=1 deg` it jumps to `q1=79 deg`. The required hip deviation from the
representative coordination is 5 degrees at `q2=10 deg`, 2.30 degrees at
`q2=5 deg`, 1.32 degrees at `q2=2 deg`, and 78.86 degrees at `q2=1 deg`.
Thus this grid optimum is a mechanical upper-bound diagnostic, not a smooth
force-mode reference or a deployable policy.

As `q2` approaches zero, conditioning deteriorates and even the posture
optimum rises: minimum `abs(F_parallel)` is `101.84 N` at 5 degrees,
`189.49 N` at 2 degrees, and `218.48 N` at 1 degree. At exactly zero degrees,
the suspended single-contact map is rank deficient and no finite exact
two-torque solution exists.

## Current V2 return branch

The actual return branch is evaluated in time order from `[45,84] deg` to
`[5,10] deg`. Threshold crossings are diagnostic only.

| Bound | First abs(Fparallel) crossing | First force-norm crossing |
|---:|---|---|
| 80 N | `[45.000,84.000] deg` | `[45.000,84.000] deg` |
| 120 N | `[26.889,50.495] deg` | `[26.889,50.495] deg` |
| 200 N | `[9.711,18.716] deg` | `[9.767,18.819] deg` |

Compared with the current V2 coordination, posture adjustment substantially
reduces axial force over much of `q2=5..30 deg`, but it does so by moving the
hip toward the ROM boundary. It does not prevent the low-flexion force growth
or the exact rank loss at full extension.

## Abstract external-support residual

For each component bound, the retained deterministic two-dimensional solver
selects the robot force minimizing generalized-torque residual. The remaining
quantity is

\[
\tau_{support,required}=\tau_{hold}-A(q)F_{robot}.
\]

It only says how much generalized torque must be carried by some other load
transfer when the robot force is bounded. It is not a specific bed force and
assumes no bed, support point, or contact geometry.

| Robot component bound | V2 return: residual begins | V2 return peak residual | Peak dominant component | Minimum-|Fparallel| curve: nonzero residual region | Curve peak residual |
|---:|---|---:|---|---|---:|
| +/-80 N | already at 84 deg | 7.398 N m | knee | q2=1..5 deg | 0.949 N m |
| +/-120 N | below q2=50.495 deg | 6.139 N m | knee | q2=1..4 deg | 0.572 N m |
| +/-200 N | below q2=18.716 deg | 3.621 N m | knee | q2=1 deg | 0.058 N m |

For the current V2 return, the peak residual occurs at the `[5,10] deg`
endpoint and is knee-dominated for all three bounds. The force-mode posture
curve reduces the residual strongly and eliminates it above 5 degrees under
80 N, above 4 degrees under 120 N, and above 1 degree under 200 N. It does not
eliminate the structural rank loss at `q2=0`.

## Decision boundary

Force-mode/posture adjustment can solve the large axial-force demand over a
meaningful positive-knee-flexion region if substantial deviation from the
nominal hip-knee coordination and use of ROM-boundary passive torque are
allowed. It is not sufficient arbitrarily close to extension: conditioning
still collapses, optimal axial force grows, and bounded-force residual remains.

Consequently, an explicit load-transfer model is not yet unconditionally the
next step. The project must first confirm the allowed operating envelope,
trajectory strictness, acceptable posture deviation, and permitted safety
intervention. If operation must include the residual-producing low-flexion
region under the selected robot force bound, then external support/load
transfer is mechanically necessary and the next model should introduce an
explicit support geometry. Otherwise, a force-mode operating envelope that
avoids that region remains mechanically plausible.

This study does not prove clinical safety or failure of the single-arm
architecture.

## Reproduction and artifacts

Headless command:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_near_extension_force_mode_feasibility"
```

Tracked runner, mechanics helpers, and tests are under
`linkage/matlab/runners/`, `linkage/matlab/src/near_extension_force_mode/`,
and `linkage/matlab/tests/near_extension_force_mode/`. MAT, CSV, PNG, and
summary artifacts remain ignored under
`linkage/results/local/near_extension_force_mode_feasibility/`.
