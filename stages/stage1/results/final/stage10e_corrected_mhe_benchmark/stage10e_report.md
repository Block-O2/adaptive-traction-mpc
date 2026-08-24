# Stage 10E: Corrected Multiple-Shooting MHE Benchmark

## Protocol

- Reused saved Stage 10B UKF+NLS and single-shooting rows. Only the corrected multiple-shooting inverse-mass MHE was rerun.
- The only source change is the Stage 10D rolling-arrival index correction. Lambda-only estimation, nominal k/b_r, 70-transition window, 10-step cadence, weights, bounds, scaling, solver settings, replay, metrics, and gate are unchanged.
- No bias state was added. `noise_bias` is the bias/noise-bias group; all remaining conditions form the no-bias group.

## Offline gate

Gate: **FAIL**. Checks: `{'alpha_mean_clearly_better_than_baseline': False, 'alpha_mean_clearly_better_than_single': False, 'alpha_consistent': False, 'state_not_materially_worse': False, 'failure_rate_acceptable': False, 'solve_time_usable': False}`.
Overall alpha RMSE: UKF+NLS=1.81465, single=1.65371, corrected multiple=12.7072.
Overall state RMSE: UKF+NLS=0.0282008, single=0.0902514, corrected multiple=4.26802.
Overall mass relative error: UKF+NLS=0.043082, single=0.0710919, corrected multiple=0.0486443.

## Bias split

- Corrected MHE no-bias alpha/state RMSE: 12.6549 / 4.39324.
- Corrected MHE noise-bias alpha/state RMSE: 13.0729 / 3.3915.
- Missing bias model is not established as the dominant limitation by this split.

## Required conclusions

1. **How much of Stage 10C failure was caused by the arrival-index bug?** The pre-fix Stage 10C result is invalid as a performance comparison; Stage 10E is the corrected measurement. The corrected overall alpha RMSE is 12.7072 versus the pre-fix 11.2992.
2. **Does corrected MHE beat UKF+NLS?** No under the specified gate.
3. **Is bias mismatch now the main limitation?** No: the available no-bias versus noise-bias split does not establish it as dominant.
4. **Is solve time usable?** No: average per-run p95 update time is 2.35623 s against the 0.20 s gate.
5. **Should the next step be bias-aware MHE or branch closure?** Close the fixed-weight MHE branch unless a separate bias-aware formulation is explicitly authorized; this stage does not add one.

## Closed loop

No closed-loop run or GIF was created because the offline gate failed.
