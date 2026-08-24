# Stage 4 integral dynamics identification and state-UKF comparison

## Frozen comparison boundary

This is a six-run engineering comparison: two estimator architectures under
three registered sensing cases. The perturbed Human/UR10e plant, population
prior, geometry identifier, Adaptive MPC, high-flexion trajectory, low-level
controller, gains, ROM, robot limits, contacts, and 200 N translational-force
gate are identical. Both architectures receive the same deterministic sensor
noise seed (`44104`) and the same measurement preprocessing.

- **A, minimal:** measurement preprocessing, geometry identification,
  integral 11-base-parameter identification, Adaptive MPC.
- **B, UKF-assisted:** the same chain with one state-only UKF before the same
  integral identifier. The UKF state is exactly `[q1,q2,dq1,dq2]`; geometry
  and dynamic parameters are never UKF states.

MuJoCo Human state and parameters are God-view evaluation only. The existing
bed/soft-limit contamination interface is retained. Under the strict current
sensor boundary there is no real bed-contact measurement, so the bed flag is
not replaced by MuJoCo truth; the estimated-state soft-limit gate remains
active. Integral windows containing an observable contamination flag are
excluded in their entirety.

## Causal integral regression

For the frozen linear inverse-dynamics model

```text
tau(t) = Y(q, dq, ddq) beta,
```

the new identifier forms, over each trailing interval `[a,b]`,

```text
integral(tau dt) = Phi_integral(q, dq) beta.
```

All acceleration columns are eliminated analytically. Important terms are:

```text
integral(ddq1 dt) = dq1(b) - dq1(a)
integral(ddq2 dt) = dq2(b) - dq2(a)

integral(2 cos(q2) ddq1 - cos(q2) ddq2
         + sin(q2)(-2 dq1 dq2 + dq2^2) dt)
  = [2 cos(q2) dq1 - cos(q2) dq2]_a^b

integral(-cos(q2) ddq1 + sin(q2) dq1^2 dt)
  = [-cos(q2) dq1]_a^b
    + integral(sin(q2) dq1 (dq1-dq2) dt).
```

Gravity, stiffness, and measured generalized input are integrated with causal
trapezoidal quadrature. Viscous columns use the exact position boundary
differences. No instantaneous `qdd` enters the implementation.

The registered identifier uses a 0.50 s trailing integration interval, a
five-measurement block stride, at least 20 clean integral blocks, and the same
population prior, bounds, 0.10 smoothing, 0.03 span step limit, `1e5`
condition limit, bounded least squares, positive-definite mass-matrix check,
and last-valid fallback. Each candidate must have full rank under both
column-normalized SVD and pivoted QR. Residual RMS is reported in `N m s`.

## State-only UKF

The UKF uses the current last-valid base-parameter Human model as the process
model and the measured cuff wrench mapped through the last-valid geometry as
the generalized input. Fixed settings for every B case are:

- unscented parameters: `alpha=0.70`, `beta=2`, `kappa=0`;
- process standard deviations per nominal 20 ms update:
  `[0.03 deg, 0.03 deg, 0.50 deg/s, 0.50 deg/s]`;
- measurement standard deviations:
  `[0.30 deg, 0.30 deg, 2.0 deg/s, 2.0 deg/s]`;
- initial standard deviations:
  `[0.50 deg, 0.50 deg, 3.0 deg/s, 3.0 deg/s]`.

These are fixed engineering assumptions, not hardware-calibrated Q/R. No UKF
state contains a geometry or dynamic parameter, and no architecture-specific
tuning was performed after observing results.

## Ideal frontend transparency

`frontend_transparency.json` records zero difference for every ideal
controller-facing measurement and `9.99e-16 N m` maximum difference between
the original and measurement-boundary low-level torque laws.

The full strict-boundary ideal run has `0.7186 deg` tracking RMSE versus the
frozen Stage-4 result's `0.6111 deg`, and three versus eleven accepted legacy
dynamic updates. This meaningful discrepancy is traced to removing the
MuJoCo bed-contact truth flag from the estimator, not to the ideal measurement
frontend. A and B both use that same strict boundary.

## Registered results

| arch | sensing | completed | dynamics first trusted | updates A/R | final SVD/RRQR rank | condition | residual RMS | base L2 error | God-view torque prediction RMSE | tracking RMSE; max hip/knee | peak cuff force | torque fraction; max speed |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | ideal | 23.000 s | 4.32 s | 4/35 | 11/11 | 346.9 | 0.131 N m s | 9.09% | 2.97 N m | 0.701 deg; 0.984/1.486 deg | 117.29 N | 0.456; 15.91 deg/s |
| B | ideal | 23.000 s | 4.02 s | 2/36 | 11/11 | 291.1 | 0.151 N m s | 11.63% | 3.61 N m | 1.661 deg; 1.861/2.993 deg | 118.15 N | 0.445; 15.99 deg/s |
| A | noise | 23.000 s | 3.80 s | 6/33 | 11/11 | 328.8 | 0.142 N m s | 8.60% | 2.53 N m | 0.671 deg; 0.887/1.511 deg | 118.91 N | 0.473; 16.43 deg/s |
| B | noise | 23.000 s | none | 0/38 | 11/11 | 266.8 | 0.158 N m s | 13.73% | 4.34 N m | 1.543 deg; 2.131/3.645 deg | 120.32 N | 0.455; 16.36 deg/s |
| A | noise + 10 ms | force gate at 13.545 s | 5.27 s | 3/16 | 11/11 | 386.2 | 0.090 N m s | 11.81% | 3.60 N m | 0.869 deg; 1.731/1.729 deg | 153.47 N | 0.657; 50.49 deg/s |
| B | noise + 10 ms | force gate at 14.705 s | none | 0/22 | 11/11 | 358.2 | 0.119 N m s | 13.73% | 4.39 N m | 1.510 deg; 2.359/3.328 deg | 167.72 N | 0.672; 59.60 deg/s |

Final geometry errors remained small in the completed ideal/noise cases. Hip
pivot errors were `0.44/1.15 mm` for A and `0.49/1.25 mm` for B; corresponding
thigh-length errors remained within `0.13%` and cuff-distance errors within
`0.17%`.

Every full or partial run had zero ROM samples, torque saturations, robot joint
limit samples, unintended collisions, MPC failures, and MuJoCo warnings. Each
delayed run recorded one unchanged commanded-force-gate event.

Estimator mean compute time was approximately `1.49-1.51 ms` for full A runs
and `1.97-2.00 ms` for full B runs. End-to-end 23 s rollout wall time was
`82.96-85.43 s` for A and `83.64-86.30 s` for B on the recorded machine. MPC
mean solve time remained about `66 ms` and dominated total offline runtime.

## Decision

The state UKF is not justified. Architecture A is better in both ideal and
noisy sensing: it accepts more dynamic updates, produces lower base-parameter
and torque-prediction error, and tracks substantially better with lower
estimator cost. B does not rescue the delayed case. The recommended final
architecture therefore excludes the UKF; its implementation and results are
retained only as uncommitted comparison evidence.

The dominant remaining failure is the uncompensated common 10 ms measurement
delay in the unchanged low-level Cartesian loop. Both architectures retain
full-rank, well-conditioned integral regressors, yet both reach the existing
commanded cuff-force gate during high flexion. Per the registered scope, no
delay compensation, gain change, or safety change was attempted.

## Reproduction

From `stages/stage3_full3d/`:

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_integral_ukf_comparison.py \
  --output-dir results/stage4_integral_ukf_comparison_engineering \
  --architecture all --case all
```
