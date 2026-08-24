# Stage 4 sensor-realism engineering check

## Scope

This check inserts a causal measurement boundary in front of the frozen Stage-4
one-shot estimator, Adaptive MPC, and unchanged Stage-3 low-level law. The
Human/robot plant, population prior, Estimator V2 gates, trajectory, gains,
limits, contacts, and 200 N translational cuff-force gate are unchanged.

The perturbations are deterministic engineering assumptions, not measured
CR12 sensor specifications or clinical thresholds. MuJoCo Human state,
parameters, bed force, contacts, and physical wrench remain God-view
evaluation quantities. They are absent from the controller measurement object.
In particular, the earlier MuJoCo bed-contact flag is not supplied to the
estimator in this check.

## Measurement ladder

The five cases are cumulative:

1. ideal pass-through at 200 Hz;
2. 200 Hz plus independent Gaussian robot joint, cuff pose, and cuff F/T noise;
3. case 2 plus constant and linearly drifting F/T bias;
4. case 3 plus a common aligned 10 ms timestamp delay;
5. case 4 at 100 Hz with zero-order hold at the unchanged 200 Hz control loop.

The registered noise standard deviations per sampled axis are:

- robot joint position: `0.02 deg`;
- robot joint velocity: `0.10 deg/s`;
- cuff position: `0.30 mm`;
- cuff orientation rotvec: `0.05 deg`;
- cuff force: `0.50 N`;
- cuff moment: `0.020 N m`.

The force bias starts at `[1.50, -1.00, 0.80] N` and drifts at
`[0.040, -0.030, 0.020] N/s`. The moment bias starts at
`[0.030, -0.020, 0.015] N m` and drifts at
`[0.0010, -0.0008, 0.0006] N m/s`. The deterministic random seed is `44104`.

All non-ideal cases share one causal preprocessing configuration: an 8 Hz
first-order low-pass on robot state, cuff pose, and cuff wrench, followed by a
120 ms trailing local-quadratic pose derivative for cuff twist. Pose/state and
wrench are sampled at one timestamp before the common delay. No F/T bias is
estimated or subtracted.

The initial 20 Hz/60 ms preprocessing diagnostic completed mechanically but
produced acceleration RMSE `[3.70, 6.64] rad/s^2` and no accepted dynamic
update. The single shared preprocessing revision above reduced that derivative
error. Its diagnostic evidence is retained under
`results/stage4_sensor_realism_engineering/diagnostic_preprocessing_v1/`.

## Observed results

| case | completed duration | geometry first trusted | final geometry error: hip / thigh / cuff | dynamics first trusted | dynamics accepted/rejected | base-vector relative L2 error | tracking RMSE | peak cuff force | peak torque fraction | maximum joint speed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal 200 Hz | 23.000 s | 2.82 s | 0.44 mm / -0.069% / -0.031% | 8.32 s | 3 / 37 | 9.94% | 0.719 deg | 117.66 N | 0.457 | 15.93 deg/s |
| noise 200 Hz | 23.000 s | 2.30 s | 1.16 mm / -0.119% / -0.152% | none | 0 / 40 | 13.73% | 0.840 deg | 119.03 N | 0.481 | 16.45 deg/s |
| noise+bias 200 Hz | 23.000 s | 2.30 s | 1.16 mm / -0.119% / -0.152% | none | 0 / 40 | 13.73% | 0.840 deg | 119.03 N | 0.481 | 16.45 deg/s |
| noise+bias+10 ms 200 Hz | terminated at 13.335 s by commanded-force gate | 2.27 s | 2.70 mm / -0.327% / -0.303% | none | 0 / 21 | 13.73% | 0.926 deg | 168.13 N | 0.668 | 59.87 deg/s |
| noise+bias+10 ms 100 Hz | terminated at 12.820 s by commanded-force gate | 2.25 s | 0.46 mm / -0.139% / +0.279% | none | 0 / 20 | 13.73% | 0.873 deg | 156.67 N | 0.633 | 47.81 deg/s |

All completed portions had zero ROM samples, torque saturations, robot joint
limit samples, unintended collisions, MPC solve failures, and MuJoCo warnings.
The two delayed cases each recorded one existing commanded cuff-force gate
event. Their state/pose/wrench timestamps were aligned; mean measurement age
was 9.99 ms at 200 Hz and 12.49 ms at 100 Hz due to delay plus sample hold.

The geometry fit tolerated the tested noise. Dynamic identification did not:
with strict measurement-only startup, the noisy acceleration estimates had
RMSE `[1.06, 1.59] rad/s^2`, and every dynamic candidate hit an existing
parameter bound. Adding F/T bias raised the final old/candidate residual RMS
from `4.29/0.568 N m` to `4.56/0.580 N m` and introduced an additional
stiffness-rest-combination bound hit. Because the noise-only case already had
zero accepted updates, the last-valid population-prior fallback made the
noise-only and bias case closed-loop trajectories identical.

The dominant mechanical failure is common sensing latency: the unchanged
high-gain Cartesian execution law reaches its existing total commanded-force
gate during high flexion. No gain, gate, estimator bound, or scientific
parameter was changed to hide this result.

## Reproduction

From `stages/stage3_full3d/`:

```bash
PYTHONPATH=src conda run -n mpc_learn python scripts/run_stage4_sensor_realism.py \
  --output-dir results/stage4_sensor_realism_engineering --case all
```

The output directory preserves each JSON configuration/summary, compressed
trace, the compact aggregate, and the preprocessing diagnostics.

## Most-needed hardware information

The next decision needs one synchronized real sensing capture, or equivalent
manufacturer specifications, covering robot joint state, cuff pose, cuff F/T,
and command timestamps. Highest priority is the measured end-to-end
pose/state-to-wrench latency and jitter together with the mounted F/T sensor's
per-axis zero bias, warm-up/temperature drift, noise density, bandwidth,
cross-axis calibration, and timestamp source. Without these values, the
simulation perturbations cannot be claimed to represent CR12 hardware and the
dynamic estimator cannot be qualified for migration.
