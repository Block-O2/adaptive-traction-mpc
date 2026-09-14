# Goal-MPC v1.2 phase-aware objective engineering report

Evidence category: **engineering smoke only**. No formal or robustness claim
is made.

## Phase-aware cost

OUTBOUND and RETURN retain the v1.1 goal-directed objective, with the current
phase target and no time trajectory, coordination ratio, or path corridor.
HOLD adds, over every predicted horizon state,

`wq_hold * sum ||(q_k-q_goal)/q_scale||^2 + wv_hold * sum ||dq_k/dq_scale||^2`.

Terminal position and velocity terms remain unchanged. The retained weights
are:

- `wq_hold = 4.0`;
- `wv_hold = 0.25`;
- inherited `q_scale = 2 deg`, `dq_scale = 8 deg/s`.

The first narrow attempt used `wq_hold=1.0`, `wv_hold=0.25`. It reduced HOLD
velocity RMS but increased positional offset. The single follow-up set
`wq_hold=4.0=(2 deg / 1 deg completion tolerance)^2`, leaving the velocity
weight unchanged. No further tuning was performed.

## Retained matched-model result

Primary output:
`results/goal_mpc_v12/hold_wq4_wv025_attempt02/`.

The episode entered HOLD at 1.945 s, then terminated at 11.95 s with
`TIMEOUT_HOLD`; RETURN and COMPLETE were not reached. The longest continuous
period satisfying both angle and velocity predicates was 0.010 s, not the
required 0.5 s. Across HOLD, angle-only, velocity-only, and combined predicate
satisfaction were 1.55%, 18.09%, and 0.15%.

| Quantity | Observed value |
|---|---:|
| Peak / cumulative physical cuff force | 166.005 N / 1266.098 N s |
| Peak physical cuff moment | 24.693 Nm |
| q estimation RMSE | 0.0076 / 0.0155 deg |
| dq estimation RMSE | 0.3720 / 0.6298 deg/s |
| physical-force vector prediction RMSE / p95 / max | 5.291 / 11.055 / 36.991 N |
| physical-force norm prediction RMSE / p95 / max | 4.165 / 8.607 / 29.534 N |
| MPC runtime mean / p95 / max | 16.650 / 18.277 / 25.671 ms |
| maximum normalized q1/q2 progress difference | 0.244 |

All 599 MPC solves returned `SAFE_ACTION`. There was no 200 N force-gate
event, BRAKE, Safety-Filter intervention, structural/nonfinite event, or
MuJoCo warning.

## Interpretation

The running velocity term is active and reduces HOLD velocity RMS relative to
v1.1, but a position/velocity trade remains under the fixed 15-step, 32-candidate
CEM and first-step-only interface transmission model. Increasing the position
weight from 1 to 4 partially recovered position accuracy but did not create a
continuous hold. This is no longer evidence for simply increasing one weight;
the next change needs a separately reviewed design for completion-aligned HOLD
cost/constraint treatment and/or more consistent multi-step transmitted-input
prediction.

Because matched completion was not obtained, no plant K/D mismatch case was
run. Goal-MPC is not ready for interface-mismatch testing or value/RL learning.
