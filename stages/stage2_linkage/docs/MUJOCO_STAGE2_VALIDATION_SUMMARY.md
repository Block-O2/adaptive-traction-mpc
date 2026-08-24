# MuJoCo Stage-2 validation closeout

## Retained baseline

Stage 2 closes on the planar Human V2 MuJoCo plant with rigid robot-cuff-shank
pose transmission. The cuff is a weld constraint, reset/IK is pose-consistent,
and the controller combines nominal Human V2 inverse-dynamics cuff-wrench
feedforward with the existing 6D pose feedback. The physical cuff wrench is
reconstructed from the constraint Jacobian rather than interpreting raw weld
rotational multipliers as moments.

This rigid-cuff model supersedes the former point-force/tendon research branch
for active development. Those earlier models and their dedicated diagnostics
are retained only in Git history and are not alternative live plant options.

The Human V2 ROM, passive dynamics, cubic soft limit, and zero Human-joint
armature are frozen. Robot joints retain armature `0.003`, their original
torque limits, and the translational cuff-force gate remains 200 N. Sagittal
moment `My` is reported without inventing a moment limit. No adaptive,
protective, recovery, or Stage-3 robot logic is present.

The retained six-axis arm is explicitly a **CR12-like engineering surrogate**,
not a validated CR12 model: its geometry, inertias, actuators, and control
contract are not hardware specifications. Real-robot and full-3D surrogate
validation remain outside Stage 2.

## Static rigid-cuff checks

All six validation postures had Human V2 mass-matrix residuals below
`2e-13`, negligible rigid-pose constraint residual, and no robot-torque-limit
violation.

| q2 (deg) | cuff force (N) | My (N m) | peak robot torque (N m) |
|---:|---:|---:|---:|
| 0 | 60.00 | -55.99 | 45.55 |
| 2 | 21.38 | -6.70 | 33.77 |
| 3 | 42.90 | 5.03 | 41.08 |
| 5 | 63.51 | 14.35 | 47.74 |
| 10 | 75.40 | 19.20 | 51.61 |
| 20 | 80.59 | 21.56 | 53.64 |

At 3 degrees, admitting the physical cuff moment reduced the required
translational force from the previous point-force estimate of about 348 N to
42.90 N.

## Nominal dynamic results

The original 15 s Human V2 rehabilitation reference,
`[5 deg, 10 deg] -> [45 deg, 84 deg] -> [5 deg, 10 deg]`, completed with the
nominal inverse-dynamics cuff controller after its required one-second initial
hold. It respected the 200 N cuff-force gate and robot torque limits and had no
solver or rigid-cuff instability. This established the normal-range dynamic
baseline before extending the same reference machinery toward extension.

The lower endpoint was then extended to q2 = 3 degrees without changing the
plant, controller gains, bed, ROM, force gate, robot limits, or trajectory
construction. The 15 s
`[1.216 deg, 3 deg] -> [45 deg, 84 deg] -> [1.216 deg, 3 deg]`
reference completed. Joint RMSE was `[0.081, 0.195] deg`, maximum absolute
error was `[0.212, 0.489] deg`, peak cuff force was `109.81 N`, peak `|My|`
was `27.19 N m`, and peak robot torque ratio was `60.47%`. Peak cuff relative
pose error was `0.0214 mm` and `0.3597 deg`. There were no ROM, 200 N,
robot-torque, nonfinite-state, or solver-warning violations. Cubic soft-limit
activity near the retained 3-degree floor is expected model behavior.

The 3-degree endpoint is an engineering reference used to probe
near-extension mechanics. It is not a hard safety boundary, anatomical limit,
clinical threshold, or treatment recommendation. Direct departure from and
return to 3 degrees required no separate recovery primitive in the nominal
smoke, but that result is not evidence of safety under unvalidated patients,
hardware, disturbances, or contact conditions.

Bed-contact closeout: using a 2 N reporting threshold, force-bearing contact
lasted `0.281 s` (`1.873%` duty), with `33.0815 N s` total normal impulse,
`0.19308 J` absolute contact work, and `1.15785 N m s` integrated generalized
Human-joint torque. These represented only `0.336%` of absolute system work
and `0.204%` of absolute generalized-torque impulse. The 800+ switches were
therefore classified as negligible boundary/solver chatter (case A); no bed
parameter was tuned.

## Fixed nominal-controller mismatch baseline

Only the true Human V2 plant was perturbed; the controller model stayed
nominal. All cases ran the full 15 s and respected ROM, the 200 N cuff-force
gate, and robot torque limits, with no solver failure. The existing mechanical
completion gate additionally checks terminal tracking tolerance, so moderate
and adverse are marked incomplete despite reaching 15 s.

| true plant | completion gate | q RMSE (deg) | max error (deg) | peak F (N) | peak \|My\| (N m) | peak torque ratio | first 2x-nominal degradation |
|---|---|---:|---:|---:|---:|---:|---|
| nominal | complete | 0.081 / 0.195 | 0.212 / 0.489 | 109.81 | 27.19 | 60.47% | none |
| mild | complete | 0.360 / 0.724 | 0.652 / 1.361 | 114.98 | 28.42 | 61.56% | 0.320 s, lower hold |
| moderate | terminal tolerance not met | 0.420 / 0.789 | 0.773 / 1.695 | 120.45 | 27.51 | 61.50% | 0.195 s, lower hold |
| adverse | terminal tolerance not met | 0.925 / 1.348 | 1.220 / 2.676 | 130.57 | 26.72 | 61.58% | 0.115 s, lower hold |

Registered cases are preserved in the current validation code: mild uses
`mass x1.05` and `q_rest -2 deg`; moderate additionally uses
`lc1 x1.05`, `lc2 x0.95`, passive stiffness `x1.10`, and sleeve center
`x1.02`; adverse uses mass/lc1/lc2/stiffness/sleeve-center scales
`1.10/1.10/0.90/1.20/1.05` with `q_rest -2 deg`.

## Final evidence

- `results/final/nominal_full_cycle.gif`
- `results/final/nominal_timeseries.png`
- `results/final/fixed_model_mismatch_summary.json`

These are engineering-validation smoke artifacts, not formal safety or
clinical evidence.

## Stage-3 boundary

Online identification/adaptive control, uncertainty-aware protection, and
validation with a selected full-3D or real robot remain future work. The
current fixed-model mismatch baseline measures the robustness available before
adaptation; it does not implement adaptation. No Stage-3 result or robot claim
is implied by this closeout.

A later read-only CR12 CAD feasibility audit was **NO-GO**: constructing a
credible articulated model would require substantial manual reconstruction or
guessing of joint geometry/dynamics. Stage 3 will therefore use a complete
six-DoF MuJoCo Menagerie surrogate; no Stage-3 implementation is included here.
