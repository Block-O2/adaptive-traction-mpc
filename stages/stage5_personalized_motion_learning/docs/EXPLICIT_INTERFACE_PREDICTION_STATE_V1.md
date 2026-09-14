# Stage-5 explicit interface prediction state v1

Evidence category: engineering diagnostic/smoke only. No CEM structure, cost,
constraint, action space, Plant-v1 parameter, HOLD rule, or learning component
is changed by this checkpoint.

## Hidden-state audit

The previous `NominalInterfaceHoldPredictor` retained two private history
objects: the previous `EstimatedInterfaceState` and previous executable wrench.
At every call it reconstructed additional horizon state as

```text
a_interface = (u_now - u_previous) / dt_measurement
alpha_interface = (omega_now - omega_previous) / dt_measurement
b_translation = M_interface a_interface + K x + D u
b_rotation = I_interface alpha_interface + Kr theta + Dr omega
```

The measured interface displacement `x`, velocity `u`, rotation `theta`, and
angular velocity `omega` were deployable. The two acceleration differences and
therefore both base-drive terms were hidden derived quantities. They were
recomputed from the latest 5 ms interval at the start of every solve, while an
accepted horizon propagated the earlier drive. A shifted action sequence was
therefore not initialized from the same dynamical state at the next solve.

## Explicit state definition

`ExplicitInterfacePredictionState` now contains:

- measurement timestamp and nominal-interface model version;
- Human-frame interface translation `x` and velocity `u`;
- Human-frame rotation error `theta` and angular velocity `omega`;
- current Human-to-WORLD rotation;
- WORLD-frame translational base drive `b_F`;
- WORLD-frame rotational base drive `b_M`;
- previous executable WORLD-frame cuff wrench;
- the registered transition assumption identifier.

All inputs come from the deployable robot/cuff pose, twist, and wrench boundary.
MuJoCo Human truth is not read by initialization, update, screening, or rollout.

### Initialization

Initialization occurs once from the measured nominal spring-damper state with
zero unknown inertial residual:

```text
b_F = R_WH (K (x-x0) + D u)
b_M = R_WH (Kr (theta-theta0) + Dr omega)
```

The executable wrench active at initialization is stored explicitly.

### Measurement transition

A new causal measurement replaces `x`, `u`, `theta`, `omega`, the Human frame,
and timestamp. `b_F`, `b_M`, and the previous executable wrench are carried
unchanged. The model does not recompute either drive from a short derivative.
A stale predictor timestamp causes an explicit runtime error rather than a
silent re-inference.

### Command transition

When an executable wrench changes from `w_prev` to `w_new`, the known increment
updates the explicit drive:

```text
b_F+ = b_F + F_new - F_prev
b_M+ = b_M + M_new - M_prev
w_prev+ = w_new
```

Between command changes the base drive uses zero-order hold. No first-order
decay is active in v1. The same state is consumed by first-action screening,
full Goal-MPC rollout, execution-command commit, and next-solve initialization.

## Saved feasibility-loss checkpoint

The old evidence at 0.440 s had zero feasible production candidates. Its
shifted objective-best plan became velocity-infeasible at prediction step 2
with margin -1.3414 rad/s. The old support, braking, and conservative-progress
checks had margins -1.5018, -0.9143, and -1.8696 respectively.

With explicit continuous state, the same initialized matched task was replayed
to the 0.440 s checkpoint in
`results/explicit_interface_state_v1/feasibility_replay_attempt_02/`:

| continuation/check | old margin | explicit-state margin | result |
|---|---:|---:|---|
| shifted previous selected | -1.3414 rad/s | +0.2226 | feasible |
| shifted previous safest | -1.5127 rad/s | +0.2226 | feasible |
| support only | -1.5018 rad/s | +0.2219 | feasible |
| model-based braking | -0.9143 rad/s | +0.2212 | feasible |
| conservative goal progress | -1.8696 rad/s2 | +0.2214 | feasible |
| production CEM | `NO_SAFE_ACTION`, 0 feasible | `SAFE_ACTION`, 44 feasible evaluations | accepted |

The previous-solve predicted versus next measured Human-state error at the new
checkpoint was `[-2.31e-4, -4.48e-4, -1.52e-2, -2.01e-2]` in
`[q1 rad, q2 rad, dq1 rad/s, dq2 rad/s]`. Interface-coordinate prediction error
remains real, including up to 0.0966 mm translation, 0.00408 m/s translation
velocity, 0.0404 deg rotation, and 0.0777 rad/s angular velocity.

The important state-continuity result is that the base-drive differences are
now exactly the differences between the predicted held executable wrench and
the actual 5 ms-refreshed executable wrench: `[+0.435, -0.158, -0.992]` N and
`[-0.0173, -0.6516, +0.0279]` Nm. They are explicit command/prediction error,
not a hidden derivative reset. The former feasibility collapse is removed.

## Matched complete episode

One matched engineering episode was retained at
`results/explicit_interface_state_v1/matched_attempt_01/`.

- phases: OUTBOUND 0--2.150 s, HOLD 2.150--2.875 s, RETURN 2.875--4.810 s,
  then COMPLETE;
- true continuous goal-set interval: 0.730 s;
- MPC: 202/202 `SAFE_ACTION`;
- peak estimated/truth velocity: `[25.70, 59.98]` / `[25.77, 60.08]` deg/s;
- peak deployable/truth interval acceleration: `[189.07, 458.69]` /
  `[193.49, 481.89]` deg/s2;
- peak/cumulative physical force: 130.43 N / 452.76 Ns;
- peak moment: 19.57 Nm;
- peak interface translation/rotation: 5.107 mm / 3.422 deg;
- q estimation RMSE: `[0.00192, 0.00423]` deg;
- dq estimation RMSE: `[0.08435, 0.15799]` deg/s;
- physical-force norm prediction RMSE/p95/max: 1.362/2.617/5.329 N;
- MPC runtime mean/p95/max: 25.22/27.28/28.59 ms;
- HOLD stabilizer plus safety runtime mean/p95/max:
  0.647/0.693/0.982 ms;
- no force gate, BRAKE, Safety Filter intervention, structural event, or
  MuJoCo warning.

Path freedom remains: there is no full prescribed q reference, ratio, or
corridor, and the maximum observed normalized q1/q2 progress difference is
0.2580.

## Remaining boundary

The 5 ms low-level executable command is refreshed during a 20 ms Human action
hold, whereas the selected first horizon step predicts the command available at
the solve instant as held. Its resulting wrench difference is now explicit and
auditable, but it remains a genuine prediction approximation. MPC runtime also
remains above the prior 20 ms throughput target. Neither issue was changed in
this checkpoint.
