# Stage-4 measurement-to-prediction oracle audit

## Scope and evidence boundary

The five registered sensor-realism trajectories were reused without a new
controller rollout. Their deterministic measurement frontends were replayed
offline and the current minimal integral 11-base estimator was run on those
measurements. Oracle state, geometry, and registered parameters were used only
after each online-style estimator step for evaluation.

The bias/drift and 100 Hz source trajectories were originally generated with
the earlier instantaneous estimator. Therefore the dynamics results below are
offline current-estimator replays on the saved closed-loop trajectories, not
new claims about what a current-estimator closed loop would have done.

## Measurement versus oracle

| case | age mean/max (ms) | effective q lag (ms) | q RMSE (deg) | dq RMSE (deg/s) | pose RMSE (mm/deg) | F RMSE (N) | M RMSE (Nm) |
|---|---:|---:|---:|---:|---:|---:|---:|
| ideal 200 Hz | 0/0 | 0 | 0.061 | 0.166 | 0/0 | 0 | 0 |
| noise 200 Hz | 0/0 | 15 | 0.181 | 1.564 | 0.792/0.050 | 1.266 | 0.245 |
| noise+bias+drift 200 Hz | 0/0 | 15 | 0.181 | 1.564 | 0.792/0.050 | 1.952 | 0.248 |
| noise+bias+delay 200 Hz | 9.99/10 | 25 | 0.219 | 4.976 | 1.368/0.103 | 4.739 | 0.811 |
| combined 100 Hz ZOH | 12.49/15 | 25 | 0.227 | 4.623 | 1.381/0.104 | 4.563 | 0.849 |

The table uses arrival-aligned errors, i.e. the error actually presented to a
controller at that time. The 200 Hz delayed case has sample-aligned q/dq RMSE
0.135 deg / 4.098 deg/s; arrival alignment increases these to 0.219 deg /
4.976 deg/s. Force RMSE similarly grows from 3.190 N to 4.739 N.

For the bias/drift case, aligned wrench biases are
`[1.948, -1.345, 0.966] N` and
`[0.0401, -0.0437, 0.0216] Nm`. The observed error trend contains both the
injected drift and causal-filter lag, so it must not be interpreted as a direct
drift estimate.

The registered noise case also enables the 8 Hz low-pass and 120 ms derivative
frontend. Its 15 ms effective q lag and large transient wrench peaks therefore
represent noise plus registered preprocessing, not random noise alone.

## Estimator versus oracle

| case | geometry q/dq RMSE, sample-aligned | geometry final errors (hip mm / thigh % / cuff % / axis deg) | dynamics A/R | active-bound attempts | prior -> final beta distance/span |
|---|---:|---:|---:|---:|---:|
| ideal | 0.224 deg / 0.135 deg/s | 0.437 / -0.069 / -0.031 / 0.003 | 12/27 | 26/39 | 0.460 -> 0.287 |
| noise | 0.242 deg / 1.579 deg/s | 1.162 / -0.119 / -0.152 / 0.057 | 8/31 | 31/39 | 0.460 -> 0.359 |
| bias+drift | 0.242 deg / 1.579 deg/s | 1.162 / -0.119 / -0.152 / 0.057 | 1/38 | 38/39 | 0.460 -> 0.441 |
| delayed 200 Hz | 0.484 deg / 4.130 deg/s | 2.578 / -0.258 / -0.379 / 0.066 | 5/15 | 15/20 | 0.460 -> 0.288 |
| combined 100 Hz | 0.719 deg / 3.652 deg/s | 0.354 / -0.172 / +0.268 / 0.069 | 0/18 | 18/18 | 0.460 -> 0.460 |

All 12 ideal accepted updates move the last-valid beta toward registered truth.
Noise has six toward-truth and two away-from-truth accepted updates, although
the two away-moving updates still reduce oracle torque error. Bias/drift has
only one accepted update; delayed 200 Hz has five, all toward truth; 100 Hz has
none.

The worst final span-normalized parameter errors are `a` -20.4% (ideal), `a`
-26.8% (noise), `a` -25.3% (bias/drift), `b` -16.1% (delayed 200 Hz), and the
unchanged-prior `a` -22.3% (100 Hz). All 55 final parameter values and every
candidate's constrained/unconstrained beta and active bounds are retained in
the CSV artifacts.

## Measured versus oracle torque prediction

| case | E_meas prior -> final (Nm) | E_oracle prior -> final (Nm) | final parameter-only error | true-beta state/geometry error | measured target -> oracle |
|---|---:|---:|---:|---:|---:|
| ideal | 4.140 -> 1.476 | 4.323 -> 1.326 | 1.308 | 0.227 | 1.045 |
| noise | 4.347 -> 2.292 | 4.438 -> 2.225 | 2.038 | 1.092 | 1.137 |
| bias+drift | 4.618 -> 4.256 | 4.438 -> 4.066 | 3.968 | 1.092 | 1.180 |
| delayed 200 Hz | 4.715 -> 3.339 | 5.447 -> 4.211 | 2.617 | 3.447 | 2.126 |
| combined 100 Hz | 5.104 -> 5.104 | 5.185 -> 5.185 | 4.508 | 2.879 | 2.120 |

No individual candidate in these replays satisfies the strict pattern
“measurement fit improves relative to the retained model while oracle error
worsens.” However, the delayed 200 Hz final model has a materially more
optimistic measurement error (3.339 Nm) than oracle error (4.211 Nm). Across
the registered bias/drift versus delayed cases, measured error decreases while
oracle error slightly increases, but those trajectories and durations differ;
this is a warning sign, not a matched-state causal claim.

Even under ideal sensing, true-geometry oracle wrench versus the 11-base oracle
dynamics differs by 0.897 Nm. This is an upper bound on unmodelled/numerical
closure error because saved traces do not include exact MuJoCo Human qacc or
all generalized constraint forces; finite-difference acceleration is included.
It must not be labelled pure model-structure mismatch.

## Error attribution

- **Ideal and noise:** final error is primarily parameter estimation. Random
  noise plus preprocessing increases state/geometry-only error from 0.227 to
  1.092 Nm and final oracle error from 1.326 to 2.225 Nm.
- **Systematic F/T bias/drift:** pose/state accuracy is unchanged from noise,
  but accepted dynamics updates collapse from 8 to 1 and parameter-only error
  rises from 2.038 to 3.968 Nm. The dominant mechanism is biased wrench target
  driving boundary pressure/rejection and leaving a prior-like model.
- **Delay:** timestamp age and frontend lag dominate. State/geometry-only error
  is 3.447 Nm, larger than the 2.617 Nm parameter-only error. Delay also makes
  measured-target error understate oracle error.
- **100 Hz ZOH combined case:** every dynamics candidate hits a bound, no update
  is accepted, and the prior remains. Both timing/state error (2.879 Nm) and
  prior parameter error (4.508 Nm) are material. Different early termination
  prevents claiming that 100 Hz improves wrench RMSE over 200 Hz.
- **Model structure:** not separately identifiable from the saved traces. The
  0.897--1.269 Nm true-wrench closure residual is a conservative combined
  numerical/constraint/model-structure remainder.

## Trust-rule implications

Rank, in-sample integral residual, and a raw bound-distance test are not enough.
The redesigned rule should keep the physical bounds and estimator unchanged,
but evaluate trust using separate evidence channels:

1. measurement/timestamp validity, including age, ZOH freshness, persistent
   wrench bias/drift evidence, and causal-filter lag;
2. geometry/state validity;
3. active-set/tangent-space identifiability and statistically material
   unconstrained boundary pressure;
4. causal held-out prediction stability at correct timestamps;
5. separate model confidence from information/parameter confidence.

A small measured residual cannot by itself establish model trust in delayed or
biased data. Conversely, an active bound should reduce parameter/information
confidence but should reject model confidence only after measurement validity
and causal predictive evidence are considered. No production trust semantics
were changed by this audit.
