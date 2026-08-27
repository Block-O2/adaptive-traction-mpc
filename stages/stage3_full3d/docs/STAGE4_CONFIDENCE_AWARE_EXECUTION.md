# Stage 4 confidence-aware execution layer

> Historical first design and comparison. Its candidate-acceptance speed logic
> is superseded by `STAGE4_SPLIT_CONFIDENCE_EXECUTION.md`; preserved here as the
> negative baseline that motivated the split-confidence redesign.

## Scope

This engineering implementation changes only reference timing. The existing
integral estimator, Human-space MPC, rigid-cuff resultant-wrench boundary,
low-level controller, plant, sensing, gains, ROM, robot limits, and 200 N cuff
force gate are unchanged. The current cylindrical surface model remains
resultant-wrench-equivalent evaluation postprocessing; no patch load is exposed
to the estimator, MPC, or execution layer. Tube MPC is not implemented.

## Module

`ReferenceExecutionLayer` wraps the existing reference callable with a causal
phase clock:

```text
d phase_time / d wall_time = speed_scale
0.50 <= speed_scale <= 1.00
```

The registered comparison settings were fixed before execution:

- minimum speed scale: `0.50`;
- nominal speed scale: `1.00`;
- recovery rate: `0.25 /s`;
- slowdown rate: `1.00 /s`.

The wrapper scales reference velocity by `speed_scale` and reference
acceleration by `speed_scale^2`. It never exceeds nominal speed. MPC and the
low-level cuff controller receive the same time-warped reference, preserving
their existing interface.

The execution layer reconstructs the existing estimator confidence payload
outside the estimator from its retained regression data. Rank, condition
number, residual, covariance, and standard deviation are logged. A subsystem
is high-confidence only when its latest estimator candidate was accepted, its
data matrix is full rank and finite-conditioned, and residual/covariance are
finite. Combined confidence is the minimum of geometry and dynamics
confidence. Fixed-speed mode logs the same confidence but ignores it.

Logged trace fields include:

- geometry, dynamics, and combined confidence;
- reference phase time and speed scale;
- joint tracking error;
- local six-axis cuff wrench;
- the pre-existing measurement, state, estimator, MPC, robot, and event logs.

## Tests

The tests verify low-confidence slowdown, rate-limited nominal-speed recovery,
reference derivative scaling, fixed-speed invariance, and finite rollout logs
for confidence, speed, tracking error, and cuff wrench.

```bash
PYTHONPATH=src conda run -n mpc_learn pytest -q
```

Observed mechanical result: `82 passed`.

## Single comparison rollout

Command:

```bash
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_confidence_aware_execution.py \
  --output-dir results/stage4_confidence_aware_execution_engineering
```

Both arms used ideal 200 Hz sensing, the unchanged `integral_minimal`
estimator, the unchanged Adaptive MPC, and the same high-flexion reference.
Fixed speed used the original 23 s wall duration. Confidence-aware speed used
a pre-registered 32 s wall-time allowance so slowdown would not automatically
truncate at 23 s.

| metric | fixed speed | confidence-aware speed |
|---|---:|---:|
| wall duration completed | 23.0 s | 32.0 s |
| reference phase reached | 23.0 s | 18.0393 s |
| complete 23 s reference | yes | **no** |
| mean / min / max speed scale | 1.000 / 1.000 / 1.000 | 0.564 / 0.500 / 1.000 |
| combined-confidence-high fraction | not used for speed | 0.250 |
| nominal-speed fraction | 1.000 | 0.0475 |
| tracking combined RMSE | 0.701 deg | 0.541 deg |
| peak translational cuff force | 117.29 N | 113.69 N |
| peak sagittal cuff moment | 27.10 N m | 26.14 N m |
| accepted geometry / dynamics updates | 38 / 4 | 53 / 16 |
| force-gate / ROM / MPC-failure events | 0 / 0 / 0 | 0 / 0 / 0 |

The confidence-aware arm reached high confidence first at `5.681 s`, but
repeated rejected dynamic candidates later returned combined confidence low.
It spent about `70.1%` of samples at minimum speed and did not complete the
reference within the registered allowance. The latest dynamic rejection was a
bound hit plus non-positive-definite candidate mass matrix; the unchanged
estimator correctly retained its last-valid model.

The lower tracking RMSE and peak wrench in the confidence-aware arm are not an
end-to-end improvement claim because that arm covered only 18.04 of the 23
reference seconds and therefore did not execute the full staged return. The
mechanical comparison outcome is **PARTIAL**: slowdown/recovery and logging are
present, safety settings were unchanged, but full-path confidence-aware
execution was not demonstrated. Per repository policy, no thresholds, rates,
estimator gates, or duration were retuned after observing this result.

Machine-readable evidence is in
`results/stage4_confidence_aware_execution_engineering/comparison_summary.json`,
with per-arm JSON and NPZ traces in the same directory. This is engineering
evidence, not formal or authoritative evidence.
