# Stage-5 Interface Robustness v1 closeout checkpoint

## Status and scope

This checkpoint changes the interface branch's engineering objective. Online
recovery of physical `Kt`, `Kr`, `Dt`, and `Dr` is no longer an acceptance
target. The control authority is the fixed nominal low-order Kelvin--Voigt
model, existing deployable observer, unified loaded execution, path-free
Goal-MPC, and local HOLD stabilizer. Interface ID, the finite uncertainty bank,
Human adaptation, terminal-value learning, and RL are inactive.

The reason is evidential: the retained identification reports show that the
measurement-prediction objective can prefer effective parameters that compensate
predictor model-form error. A numerical `K/D` fit therefore cannot currently be
interpreted as recovered cuff mechanics. Those negative results remain
historical evidence and are not relabeled.

This is an engineering simulation checkpoint, not clinical validation, a
hardware safety validation, or a continuous robustness proof.

## Acceptance contract

The machine-readable contract is
`configs/stage5_interface_robustness_v1.json`. The task remains start/return
`[5,10] deg`, outbound goal `[20,35] deg`, with no full time trajectory,
coordination ratio, or path corridor.

Evaluation-only truth acceptance is:

- absolute terminal angle error at each declared arrival no more than
  `[3,3] deg`, and truth speed no more than `[5,5] deg/s`;
- the outbound terminal set is continuously occupied for at least `0.5 s`;
- one dedicated `5 s` HOLD, with last-`2 s` truth angle peak-to-peak no more
  than `[2,2] deg`;
- normal duration no more than `25 s`, long-HOLD duration no more than `30 s`.

State-estimation budgets are q RMSE `[2,2] deg`, q error p95 `[3,3] deg`, q
error max `[5,5] deg`, and completion-window q/dq max errors `[2,2] deg` and
`[2,2] deg/s`. Existing online completion remains the controller-only
conservative subset (`0.95/0.90 deg`, `1.25/0.50 deg/s`) of the existing
`GoalTaskSpec`; it uses no MuJoCo truth and is already stricter than the new
truth acceptance.

The 20 ms prediction contract compares predicted mean transmitted wrench with
mean time-aligned physical wrench, in the world frame and at the Human-cuff
reference point. Force-vector RMSE/p95 must be at most `10/15 N`;
moment-vector RMSE/p95 at most `1/2 Nm`; maximum action-hold peak-force
underprediction at most `20 N`.

Registered Human ROM, velocity `[45,75] deg/s`, 20 ms acceleration
`[300,600] deg/s2`, robot torque screening, the 200 N physical gate, Safety
Filter, and BRAKE are unchanged. No cuff-moment hard limit is invented.

## Saved-trace re-score

Historical files were read only. `PASS` below means the available recorded
evidence satisfies the new engineering contract. The frozen checkpoint did not
record selected 20 ms wrench horizons, so its complete task/state/safety
re-score is valid but its total contract score is `N/A`; the deterministically
equivalent Mismatch-v1 nominal trace supplies that metric.

| trace | online | truth task | classification | truth peak ddq q1/q2 (deg/s2) | force RMSE/p95 (N) | moment RMSE/p95 (Nm) |
|---|---|---|---|---:|---:|---:|
| frozen nominal checkpoint | COMPLETE | COMPLETE | task/state/safety pass; prediction N/A | 193.49 / 481.89 | N/A | N/A |
| Mismatch nominal | COMPLETE | COMPLETE | task/state/mean-wrench pass; peak metric N/A | 193.49 / 481.89 | 2.38 / 4.34 | 0.37 / 0.80 |
| Kt x0.7 | COMPLETE | COMPLETE | real false-negative acceleration violation | 265.39 / **656.34** | 2.78 / 5.11 | 0.41 / 0.90 |
| Kt x1.3 | ABORT | not completed | false-positive acceleration abort | 223.27 / 504.37 | 4.71 / 7.38 | 0.73 / 1.00 |
| Kr x0.7 | ABORT at start | not started | settled-start reconstruction rejection | 0 / 0 | N/A | N/A |
| Kr x1.3 | COMPLETE | COMPLETE | task/state/mean-wrench pass; peak metric N/A | 198.46 / 459.46 | 4.57 / 6.63 | 0.39 / 0.76 |
| D x0.7 | COMPLETE | COMPLETE | task/state/mean-wrench pass; peak metric N/A | 189.92 / 482.75 | 2.42 / 4.95 | 0.38 / 0.78 |
| D x1.3 | COMPLETE | COMPLETE | task/state/mean-wrench pass; peak metric N/A | 198.80 / 487.73 | 2.22 / 4.02 | 0.37 / 0.79 |

Every historically completed cell also passed the former strict truth-arrival
check (`1 deg`, `2 deg/s`). None is rescued solely by relaxing an old 1-degree
reporting threshold. Kt x0.7 is a real registered-envelope violation, Kt x1.3
is a real conservative false abort, and Kr x0.7 is a real initialization
usability failure. The full re-score is in
`results/interface_robustness_closeout_v1/saved_trace_rescore_final.json`.

## Interface Robustness v1 implementation

V1 makes two general, explicit MPC-planning changes while retaining the same
architecture, action space, objective weights, horizon, CEM population and
iterations, loaded execution, HOLD gains, and execution safety chain:

1. Predicted physical force is screened at `180 N`, leaving a `20 N` planning
   reserve below the unchanged `200 N` physical gate. Executable robot-force
   screening and plant supervision remain at `200 N`.
2. Predicted Human velocity is constrained inside MPC to `[15,25] deg/s` by
   joint. This is an internal conservative pace, not a changed registered
   physical envelope. It remains path-free and imposes no q1/q2 ratio.

The 180 N reserve did not bind in development: the largest selected predicted
action-hold peak was `127.90 N`, leaving at least `52.10 N` to the ceiling. It
did not destroy nominal usability, but these runs do not establish its benefit
near the force gate. The pacing constraint is the operative low-complexity
change supported by the prior Kt acceleration discrepancy.

## Six-episode development result

The predeclared six-episode budget is exhausted. No V2 or per-cell tuning was
performed.

| case | phases O/H/R/C (s) | online / truth | truth peak dq (deg/s) | truth peak ddq (deg/s2) | peak/cumulative force | peak moment | result |
|---|---|---|---:|---:|---:|---:|---|
| nominal | 0 / 2.110 / 2.610 / 4.890 | COMPLETE / COMPLETE | 13.59 / 25.60 | 180.47 / 458.66 | 120.54 N / 455.94 Ns | 16.50 Nm | PASS |
| nominal, 5 s HOLD | 0 / 2.110 / 7.110 / 9.415 | COMPLETE / COMPLETE | 13.59 / 25.60 | 180.47 / 458.66 | 120.54 N / 921.04 Ns | 16.50 Nm | PASS |
| Kt x0.7 | 0 / 2.020 / 2.785 / 5.055 | COMPLETE / COMPLETE | 12.09 / 25.21 | 196.82 / 523.44 | 115.42 N / 470.65 Ns | 16.25 Nm | PASS |
| Kt x1.3 | 0 / 2.370 / 2.960 / 5.215 | COMPLETE / COMPLETE | 12.63 / 24.50 | 184.05 / 439.62 | 118.93 N / 493.86 Ns | 16.24 Nm | PASS |
| Kr x0.7 | abort at 0 | ABORT / not started | 0 / 0 | 0 / 0 | 79.30 N / 0 Ns | 12.61 Nm | conservative boundary rejection |
| Kr x1.3 | 0 / 4.400 / 5.170 / 7.270 | COMPLETE / COMPLETE | 13.68 / 29.66 | 156.79 / 404.53 | 116.38 N / 691.52 Ns | 16.22 Nm | PASS |

The five executable episodes had no false completion, silent registered-limit
violation, 200 N gate, BRAKE, Safety Filter intervention, MuJoCo warning, or
`NO_SAFE_ACTION`. Their 20 ms force RMSE/p95 ranges were `1.91--4.31 N` and
`3.48--5.83 N`; moment RMSE/p95 ranges were `0.224--0.245 Nm` and
`0.395--0.437 Nm`. Peak-force underprediction was `1.11--3.69 N`. All are
inside the contract.

All q RMSE values were below `0.70 deg`; q max error was at most `1.051 deg`.
Completion-window q and dq errors were at most `0.563 deg` and `0.134 deg/s`.
The 5 s HOLD had `0/0 deg` last-2-second truth peak-to-peak angle. Path freedom
remained: no full reference, ratio, or corridor; maximum normalized q1/q2
progress difference was `0.159--0.213` in nominal/Kt cells and `0.183` for
Kr x1.3.

MPC mean/p95 was `18.09/19.10 ms` nominal; across executable cells mean was
`18.09--18.27 ms`, p95 `19.10--19.41 ms`. There were `0--2` samples over 20 ms
per episode and maxima up to `32.89 ms`; this is not a WCET claim.

Kr x0.7 remains an explicit boundary limitation. Plant truth was the settled
`[5,10] deg` start, but nominal inversion returned `[5.627,11.595] deg`. The q2
error `1.595 deg` cannot be admitted while preserving a conservative online
subset consistent with the `2 deg` completion-window estimator budget and
`3 deg` truth target. The controller rejects rather than silently declaring a
safe start. No further margin was added.

## Development gate and preregistered final campaign

The development gate is mechanically complete: nominal and executable Kt/Kr
representative conditions are useful and compliant, while the severe Kr-low
boundary is detected conservatively. This supports freezing V1 for final
verification; it is not final authorization or interface closeout.

`configs/stage5_interface_robustness_final_campaign_v1.json` preregisters:

- core box: nominal plus eight corners of alpha_t/r `[0.9,1.1]` and alpha_d
  `[0.8,1.2]`, fixed seeds `20260824--20260826`, 27 episodes;
- boundaries: Kt x0.7, Kt x1.3, Kr x0.7, and one progressive spring with 10%
  higher radial tangent stiffness at nominal peak deformation;
- a continuous-process 30-episode session, with episodes 1 and 30 using 5 s
  HOLD and the specified drift/trend checks.

The status is **PREREGISTERED_NOT_AUTHORIZED**. It must not be run without a new
explicit user instruction. Its runner is intentionally not implemented here.

## Exit rules

- **EXIT A:** final campaign passes: close interface identification and proceed
  to Human identification, then value learning.
- **EXIT B:** core box works but boundary cases have known/detectable limits:
  freeze that limited operating scope explicitly.
- **EXIT C:** after at most V2 the core still false-completes, silently violates,
  or is unusable: stop interface iteration and make a research/mechanical
  decision; do not automatically add another filter or ID layer.

Current status is pre-final: V1 passed the development gate, Kr x0.7 is a known
conservative boundary rejection, and the final campaign awaits authorization.

## Reproduction record

Saved-trace re-score (zero new MuJoCo episodes):

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_interface_robustness_closeout.py \
  --output-dir stages/stage5_personalized_motion_learning/results/interface_robustness_closeout_v1/new_rescore
```

The exhausted six-episode development command was:

```bash
MPLCONFIGDIR=/tmp/stage5_interface_robustness_mpl \
XDG_CACHE_HOME=/tmp/stage5_interface_robustness_cache \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
  conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_interface_robustness_v1.py \
  --output-dir stages/stage5_personalized_motion_learning/results/interface_robustness_v1_development
```

Raw per-episode traces remain local engineering evidence. The compact aggregate
is `results/interface_robustness_v1_development/development_summary.json`.
The formal/final campaign command is deliberately reserved: no runner was
created and no final episode was executed.
