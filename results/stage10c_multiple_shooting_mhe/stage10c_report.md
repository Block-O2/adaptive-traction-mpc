# Stage 10C: True Multiple-Shooting Joint MHE Validation

## Protocol

- Reused saved Stage 9J replay plus the saved Stage 10B UKF+NLS and single-shooting inverse-mass MHE rows. No old method was rerun.
- The sole new method is inverse-mass multiple shooting. Every state in the 70-transition window and lambda are decision variables; the objective contains raw-measurement residuals, explicit process residuals, arrival cost, and lambda prior.
- `k` and `b_r` remain nominal. UKF states enter only as arrival/warm-start values, never as exact measurements.
- Process scaling is fixed from the pre-existing UKF-bias state process-noise diagonal. No controller, dynamics, horizon, or cost change was made.

## Gate

Gate: **FAIL**. Checks: `{'alpha_mean_clearly_better_than_baseline': False, 'alpha_mean_clearly_better_than_single': False, 'alpha_consistent': False, 'state_not_materially_worse': False, 'failure_rate_acceptable': False, 'solve_time_usable': False}`.
Overall full alpha RMSE: baseline=1.81465, single=1.65371, multiple=11.2992; clear improvement in 0/8 conditions.

| method | alpha RMSE | state RMSE | mean relative mass error | p95 solve time (s) |
|---|---:|---:|---:|---:|
| ukf_nls_current | 1.81465 | 0.0282008 | 0.043082 | nan |
| single_shooting_mhe_inverse_m | 1.65371 | 0.0902514 | 0.0710919 | 0.21083 |
| multiple_shooting_mhe_inverse_m | 11.2992 | 3.9439 | 0.0602182 | 2.34165 |

## Required conclusions

1. **Did multiple shooting fix Stage 10B state-estimation degradation?** No: state RMSE still violated the no-material-regression gate.
2. **Did it improve alpha prediction and parameter estimation?** No: it did not clearly beat both the UKF+NLS and single-shooting comparators.
3. **Is computational cost acceptable?** No: mean per-run p95 update time is 2.34165 s against the 0.20 s usability criterion.
4. **Does the MHE route remain viable?** Not under the tested fixed weighting and replay conditions.
5. **What exact method should be tested next?** Close this fixed-weight MHE branch and move to a state/parameter smoother or EM-style offline diagnosis; do not introduce uncertainty-aware control from this evidence.

## Failure interpretation

The failure establishes a computational-cost limitation directly: the multiple-shooting solve-time criterion failed in every condition. It also establishes that this fixed objective did not cure the state/alpha degradation, despite small fitted process residuals. That pattern is compatible with unresolved observability, measurement/model mismatch, or the fixed relative weighting of arrival, measurement, and process terms; this replay study cannot identify one as the cause. No broad weight tuning was performed.

## Closed loop

No closed-loop run or GIF was produced because the offline gate failed. The outcome distinguishes structural multiple shooting from the remaining issues only empirically; do not tune weights broadly in this stage.
