# Dynamic Robust Load Transfer V1 Initialization Diagnosis

## Scope and retained history

The first formal run is retained at
`linkage/results/local/dynamic_robust_load_transfer_v1/20260815_154754`.
Its nominal case completed the full hybrid sequence in `22.442 s`. The mild,
moderate, and adverse cases terminated after `0.006`, `0.006`, and `0.004 s`
with `SOFT_LIMIT_VIOLATION`.

The first Stage 2 run terminated at initialization with
`SOFT_LIMIT_VIOLATION` and therefore was not treated as a valid robustness
rollout. It did not reach transfer planning, takeover, liftoff, suspension, or
recontact.

## Exact trigger and call path

The checked quantity was the true plant's joint-1 lower soft-limit physical
torque, not an estimator state, finite-difference acceleration, planner value,
or model-predicted joint trajectory. The path was:

```text
run_dynamic_robust_load_transfer_v1
-> registered combined-case plant override
-> simulate_dynamic_robust_load_transfer_v1
-> human_two_link_v2_passive_torque(q, dq, plant)
-> human_two_link_v2_soft_limit_rhs_torque
-> abs(soft_rhs) > 1e-8 Nm
-> dynamic_robust_v1_manager_step
-> SOFT_LIMIT_VIOLATION
```

The joint-1 lower soft zone starts at `5 deg`; its numerical activation point
is `4.99999994270422 deg`. The trigger samples from the retained result files
were:

| Case | Index | Time (s) | true q1 (deg) | q1 minus activation (deg) | true soft torque (Nm) | torque minus `1e-8` (Nm) |
|---|---:|---:|---:|---:|---:|---:|
| mild | 4 | 0.006 | 4.997122985798 | -0.002876956906 | 1.522713660449e-8 | 5.227136604486e-9 |
| moderate | 4 | 0.006 | 4.995297678799 | -0.004702263905 | 6.593047198189e-8 | 5.593047198189e-8 |
| adverse | 3 | 0.004 | 4.996543545841 | -0.003456396864 | 3.584315620866e-8 | 2.584315620866e-8 |

At `t=0`, every case used the same `q=[5,10] deg`, `dq=[0,0] deg/s`, nominal
calibration force `[-8.5426713728,21.0112404748] N`, and nominal controller
reference. The state was pointwise legal but had exactly zero joint-1 soft-zone
clearance. The nominal force exactly balanced the nominal plant. It did not
balance the registered mismatch plants. The first sampled joint accelerations,
estimated directly from the retained `0.002 s` state transition, were:

| Case | q1 acceleration (deg/s^2) | q2 acceleration (deg/s^2) |
|---|---:|---:|
| mild | -168.4851 | -432.4931 |
| moderate | -278.9745 | -894.5459 |
| adverse | -440.6299 | -1428.1182 |

Thus the true plant moved immediately into the lower soft zone while the
nominal reference remained at `[5,10] deg`. This is a scenario-definition
initialization bug: the initial actuator force was copied from the nominal
calibration even after the true plant parameters changed. It is not a
zero-history alpha artifact, solver failure, or a model-side-only limit
violation. The movement was a real response of the perturbed plant, but it was
caused by a mismatched pre-rollout equilibrium at a zero-clearance boundary, so
the old short cases are not interpreted as closed-loop robustness evidence.

## Minimal fix

`dynamic_robust_v1_initial_admissibility` now constructs the actuator force
already present at `t=0` from the selected true plant's static balance at the
same physical posture, zero velocity, fixed calibrated hip height, and real bed
contact. This initialization-only force is then passed as controller memory.
From the first controller call onward, the controller, predictor, robust
supervisor, reference, gains, limits, and safety checks still use the nominal
model exactly as before.

No safety threshold, force bound, tube, plant dynamics, mismatch severity,
controller gain, time step, or stopping rule changed. In particular, no initial
sample is ignored and soft-limit entry remains an immediate terminal failure.

The corrected required equilibrium forces are:

| Case | true equilibrium force `[parallel, perpendicular]` (N) | minimum component-bound margin (N) |
|---|---:|---:|
| mild | `[-38.98524772, 21.09401393]` | 161.01475228 |
| moderate | `[-58.42174377, 19.50406368]` | 141.57825623 |
| adverse | `[-95.98963920, 18.70455409]` | 104.01036080 |

All retain the shared initial posture, `152.54039465 N` physical bed support,
`[5,10] deg` lower ROM margins, `[75,90] deg` upper ROM margins, zero soft
torque, and the unchanged `+/-200 N` component bound. Joint-1 soft-zone
clearance is still exactly zero, so consistent force balance is essential and
is explicitly logged rather than assumed.

The formal runner now writes `initial_admissibility.csv` plus a per-case
`initial_admissibility.txt`. These include true and model equilibrium forces,
the first nominal-controller command, true and model first-command angular
accelerations, ROM margins, soft-zone thresholds and clearances, bed support,
force margins, and pass/fail. A failed report prevents the rollout from
starting.

## Validation and corrected formal result

An independent equation-level replay reproduced the old mild, moderate, and
adverse first four samples to printed precision. With the corrected initial
force, its first four samples moved joint 1 inward and kept soft-limit torque
at zero in all three mismatch cases. The retained MATLAB suite then completed
with `117 passed, 0 failed, 0 incomplete` in `34.5617 s`, including the
five-step startup check for every mismatch case.

The corrected user-run formal result is retained at
`linkage/results/local/dynamic_robust_load_transfer_v1/20260815_161905`.
All four initial-admissibility reports passed. The nominal regression reproduced
the earlier full `TASK_COMPLETE` trajectory in `22.442 s` with the same
`186.374756 N` peak robot-force norm and no soft-limit or ROM samples.

The mismatch cases did not fail the corrected initialization. Their true
equilibrium accelerations were numerically zero, their first nominal-controller
commands accelerated joint 1 inward, and their soft torque stayed zero through
the five-step startup test. The nominal controller then moved the commanded
parallel force toward its nominal-model demand at the unchanged `250 N/s` slew
limit. Joint 1 reversed, crossed the zero-clearance lower soft-zone boundary,
and produced the following terminal observations:

| Case | Terminal status | Time (s) | Final task s | Trigger q1 (deg) | Trigger soft torque (Nm) | Peak robot norm (N) | Peak bed force (N) | ROM samples |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| mild | `SOFT_LIMIT_VIOLATION` | 0.026 | 7.28e-7 | 4.996613281982 | 1.605853246043e-8 | 43.648914 | 153.127278 | 0 |
| moderate | `SOFT_LIMIT_VIOLATION` | 0.026 | 7.28e-7 | 4.996906435203 | 1.258256445497e-8 | 60.959682 | 153.097964 | 0 |
| adverse | `SOFT_LIMIT_VIOLATION` | 0.030 | 1.088e-6 | 4.996344473101 | 2.231563279665e-8 | 97.209449 | 153.268881 | 0 |

The maximum inward q1 positions occurred at `0.010`, `0.012`, and `0.016 s`;
q1 velocity then became negative at `0.012`, `0.012`, and `0.018 s`. This
separates the corrected failure from the old mismatched-equilibrium transient.
It is an observed physical safety termination after valid initialization: the
nominal controller does not preserve the perturbed plant's equilibrium at a
starting task with zero joint-1 soft-zone clearance. No optimizer failure,
force-bound violation, ROM violation, estimator, or parameter update was
involved. The cases never reached transfer planning or meaningful task
progress, so they do not establish robustness or non-robustness over the later
transfer path.

No parameter tuning, safety-limit change, controller change, or additional
experiment is made from this result. Any change to the starting-task margin,
controller handling of equilibrium mismatch, or mismatch protocol requires a
separate approved research step.

That separate controller-handover step is now R1 Safe Takeover. Its scope,
exact old force/state chain, implementation contract, non-formal startup smoke,
and reviewed user-run formal result are documented in
[DYNAMIC_ROBUST_LOAD_TRANSFER_V1_SAFE_TAKEOVER_R1.md](DYNAMIC_ROBUST_LOAD_TRANSFER_V1_SAFE_TAKEOVER_R1.md).
