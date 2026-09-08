# Phase-3A Robot Control Velocity Path A/B Spec

Status: **FROZEN_USER_AUTHORIZED_EXPLORATORY_40_40_40_80_ONLY**  
Evidence: exploratory diagnostic only. This does not replace any prior formal or authoritative evidence.

## Single variable

Only the robot low-level translational velocity-feedback measurement source changes:

- OLD: `140 * (v_target_world_at_cuff_center - v_processed_pose_history_world)`
- NEW: `140 * (v_target_world_at_cuff_center - J_cuff_center_world(q_robot_raw) * dq_robot_raw)`

The NEW signal is sampled and held at the existing 200 Hz / 5 ms control boundary. It is not recomputed at each 0.25 ms physics step. The 140 mm cuff-center offset is applied exactly once by the existing rigid-offset Jacobian. Missing, nonfinite, future-dated, or older-than-one-control-period joint snapshots raise an error; there is no fallback. Rotational velocity feedback remains on the original processed pose-history path.

## Frozen conditions

The de23ea3 controller stack, suspended High-ROM scenario, nominal High-ROM Human, robot, 140 mm geometry, frozen control geometry, Fixed MPC, Reference Manager, Safety Filter, BRAKE, force policies, 0.25 ms physics step, 5 ms control period, solver, timing law, seed 44104, and formal 0.06896926724078867 deg completion tolerance are unchanged.

Implementation checkpoint: `ce72ddfc8867f6fc021bdcdf6bbc22aa8c6d5dd0`.

## Ordered executions

1. rigid 40/40 OLD
2. rigid 40/40 NEW
3. rigid 40/80 OLD
4. rigid 40/80 NEW

Each `--run-next` invocation executes exactly one case in a fresh process. No 90/120 or 120/120 run is admitted. Poor results are retained; no gain or threshold tuning is allowed.

## Evidence and stopping

The report preserves formal classification and separately records actual outbound/return progress, residual errors, tracking, velocity/position feedback, Human-level allocator demand, executable/physical force, Safety Filter/BRAKE events, force slew, the OLD/NEW velocity signals, and the exact equivalent force caused by the history estimator difference. Numerical warnings, nonfinite state, structural/ROM termination, hard physical termination, or incomplete evidence stop the campaign. Precision-only incompletion does not.
