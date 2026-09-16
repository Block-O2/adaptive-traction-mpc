# Stage-5 one-step Human-model closed-loop A/B v1

## Frozen question and boundary

This engineering A/B tests one fact only: whether the first causally qualified,
bounded reduced Human-model successor can replace the nominal model cleanly in
the existing deterministic Goal-MPC chain.  The plant Human condition is
`theta_truth=[1,1,1.2]` (damping +20%) for evaluation only.  Both arms start
from `theta_k=[1,1,1]`; gamma is exactly 0.5 throughout.  Interface, CEM seed
and settings, task, support/HOLD architecture, acceleration monitor, physical
limits, Safety Filter, BRAKE and the 200 N gate are unchanged.  Truth is passed
only to the MuJoCo plant factory and is absent from the estimator/identifier,
qualification, transition callback and controller payload.

Arm A keeps the nominal model in control while the frozen identifier runs in
shadow.  Arm B permits the first qualified bounded publication to enter the
control-model authority once, then rejects all later control updates.  This is
not progressive personalization.

## Causal qualification and bounded transition

Both independently seeded arms reproduced the same causal result:

- fit end: 1.245 s;
- eight-block future-validation decision: 3.045 s;
- `theta_candidate=[1.000584391,1.010424687,1.193479803]`;
- `theta_k+1=[1.000058439,1.001042469,1.019347980]`;
- smoothing alpha 0.10; maximum component step 0.03; bounds [0.5,1.5];
- only the smoothing rule was active.

The historical expected value was not supplied to the online authority.  It
emerged from the actual deployable measurements and unchanged fit/embargo/
future-validation lifecycle.  Arm A recorded the qualification but applied
zero transitions.  Arm B changed from
`stage5_fixed_registered_human_v1` to
`stage5_control_human_scale3_v1` exactly once.

## Transition continuity audit

At 3.045 s Arm B was in OUTBOUND at estimated state
`[0.293346,0.545188,0.046187,0.077078]` rad/rad/s.  The estimator, explicit
interface state, task phase and loaded support were preserved.  The old
model-dependent CEM sequence and safest-plan diagnostic were invalidated; the
increment slew state was reconstructed from the command actually being held
under the successor model.

| quantity | before | after / change |
|---|---:|---:|
| total Human action [Nm] | [41.20037,-3.13912] | identical; jump 0 |
| support action [Nm] | [41.31143,-3.27507] | [41.32033,-3.26418]; norm change 0.0141 |
| executable force command step | — | 0.8661 N |
| executable moment command step | — | 0.2801 Nm |
| physical wrench after first 5 ms | — | force change 0.3942 N; moment change 0.0880 Nm |

There was no zero command.  At the same timestamp Arm A's ordinary command
steps were 0.8756 N / 0.2841 Nm, so the Arm-B step was not an update-induced
bookkeeping discontinuity.  The interface estimate before/after the authority
change was bit-for-bit identical.  No predecessor warm start was reused under
the successor version.

## Genuinely later model feedback

The first post-update block begins at 3.050 s, strictly after the transition.
No training or qualification sample is reused.  Each row evaluates the
rollback predecessor and active successor on exactly the same deployable
integral-dynamics block.

| interval [s] | phase | predecessor loss | successor loss | successor - predecessor |
|---|---|---:|---:|---:|
| 3.050–3.250 | OUTBOUND | 5.241278e-4 | 4.245630e-4 | -9.956485e-5 |
| 3.250–3.450 | OUTBOUND | 7.436786e-4 | 5.986333e-4 | -1.450453e-4 |
| 3.450–3.650 | OUTBOUND | 4.509946e-4 | 3.605141e-4 | -9.048050e-5 |
| 3.650–3.850 | OUTBOUND | 7.851298e-5 | 5.304796e-5 | -2.546502e-5 |
| 3.850–4.050 | MIXED | 2.648173e-5 | 1.943322e-5 | -7.048510e-6 |
| 4.050–4.250 | HOLD | 3.595403e-5 | 2.726975e-5 | -8.684281e-6 |
| 4.250–4.450 | HOLD | 7.822575e-9 | 9.881725e-7 | +9.803499e-7 |
| 4.450–4.650 | HOLD | 6.047286e-8 | 1.300573e-6 | +1.240100e-6 |
| 4.650–4.850 | MIXED | 4.707995e-5 | 5.248635e-5 | +5.406409e-6 |
| 4.850–5.050 | RETURN | 3.255205e-4 | 2.999164e-4 | -2.560407e-5 |
| 5.050–5.250 | RETURN | 5.209793e-4 | 4.709265e-4 | -5.005275e-5 |
| 5.250–5.445 | RETURN | 6.371755e-4 | 5.804364e-4 | -5.673909e-5 |
| 5.450–5.645 | RETURN | 5.220642e-4 | 4.689022e-4 | -5.316197e-5 |
| 5.650–5.845 | RETURN | 4.177330e-4 | 3.705569e-4 | -4.717612e-5 |
| 5.850–6.045 | RETURN | 6.738442e-4 | 6.060154e-4 | -6.782884e-5 |
| 6.050–6.245 | RETURN | 4.328489e-4 | 3.883591e-4 | -4.448975e-5 |
| 6.250–6.445 | RETURN | 5.606070e-4 | 5.026173e-4 | -5.798969e-5 |
| 6.450–6.645 | RETURN | 3.620239e-4 | 3.220357e-4 | -3.998820e-5 |
| 6.650–6.845 | RETURN | 3.751375e-4 | 3.300819e-4 | -4.505559e-5 |
| 6.850–7.045 | RETURN | 4.006222e-4 | 3.519643e-4 | -4.865790e-5 |
| 7.050–7.245 | RETURN | 5.733538e-4 | 4.929875e-4 | -8.036628e-5 |
| 7.250–7.445 | RETURN | 5.400173e-4 | 4.714835e-4 | -6.853382e-5 |
| 7.450–7.645 | RETURN | 4.555267e-4 | 3.931622e-4 | -6.236452e-5 |
| 7.650–7.845 | RETURN | 5.782007e-4 | 4.978069e-4 | -8.039378e-5 |
| 7.850–8.045 | RETURN | 4.917206e-4 | 4.165616e-4 | -7.515903e-5 |
| 8.050–8.245 | RETURN | 6.676824e-4 | 5.773061e-4 | -9.037625e-5 |
| 8.250–8.445 | RETURN | 1.707039e-4 | 1.453016e-4 | -2.540232e-5 |
| 8.450–8.645 | RETURN | 9.283203e-5 | 9.069356e-5 | -2.138469e-6 |
| 8.650–8.845 | RETURN | 1.637537e-5 | 1.623153e-5 | -1.438326e-7 |

Twenty-six of 29 blocks favor the successor.  Mean loss changes from
3.69720e-4 to 3.21779e-4 Nms² (12.97% descriptively lower).  OUTBOUND and
RETURN mean losses are 20.06% and 11.59% lower respectively.  Nevertheless,
the unchanged HAC scheduled looks at 8/10/12 blocks all cross zero.  At 12
blocks the mean paired difference is -4.17548e-5 Nms² with bounds
[-1.03098e-4,+1.95884e-5].  The formal result is therefore **NEUTRAL**, not
POSITIVE.

## Closed-loop comparison

| metric | Arm A fixed | Arm B one-step |
|---|---:|---:|
| status | COMPLETE | COMPLETE |
| OUTBOUND→HOLD | 4.075 s | 4.025 s |
| HOLD→RETURN | 4.735 s | 4.715 s |
| COMPLETE | 8.860 s | 8.955 s |
| continuous goal-set HOLD | 0.665 s | 0.695 s |
| peak estimated velocity q1/q2 | 5.780 / 11.389 deg/s | 5.780 / 11.389 deg/s |
| peak deployable acceleration q1/q2 | 133.28 / 354.63 deg/s² | 133.28 / 354.63 deg/s² |
| peak truth interval acceleration q1/q2 | 110.09 / 279.98 deg/s² | 97.67 / 221.52 deg/s² |
| peak physical force | 111.437 N | 111.754 N |
| cumulative physical force | 838.373 Ns | 841.347 Ns |
| peak moment | 15.027 Nm | 15.027 Nm |
| Goal-MPC SAFE_ACTION | 407/407 | 411/411 |
| Goal-MPC mean / p95 / max | 77.04 / 91.01 / 105.07 ms | 74.33 / 90.85 / 101.43 ms |
| >20 ms deadline misses | 407/407 | 411/411 |

Both arms satisfy estimated/truth velocity and registered 20 ms acceleration
envelopes.  Both have zero NO_SAFE_ACTION, gate, BRAKE, Safety Filter
intervention, structural event and MuJoCo warning.  Terminal estimated errors
are [0.243,-0.079] deg / [-0.931,0.398] deg/s for Arm A and
[0.046,-0.055] deg / [-0.526,0.452] deg/s for Arm B.  Path freedom remains:
the formulation still contains no trajectory, coordination ratio or corridor.

Because gamma is fixed, these small differences cannot come from confidence-
driven pacing.  They are classified descriptively as approximately unchanged,
not as statistical evidence for the model update.  The 74–77 ms mean and
90–91 ms p95 runtime remains a separate deployment blocker and was not
optimized here.

## Decision

**C-B — MECHANISM WORKS, EVIDENCE INSUFFICIENT.**

The bounded successor entered control causally once, model-version and
warm-start semantics were clean, later prediction was directionally favorable,
and no closed-loop or safety regression appeared.  The frozen statistical
standard is still NEUTRAL, so neither task completion nor the descriptive 26/29
sign count justifies C-A.  Do not increase model authority or begin progressive
updates.

The smallest justified follow-up is additional predeclared, matched
post-update evidence for this same one-step successor and damping condition,
with the same HAC rule and no second update.  It should establish whether the
later prediction advantage repeats across independent repetitions before any
`theta_0→theta_1→theta_2` experiment is authorized.  Trust-driven gamma remains
off.

Raw traces remain local under
`results/human_model_one_step_ab_v1_attempt_01/`; the compact tracked summary is
`HUMAN_MODEL_ONE_STEP_AB_V1_SUMMARY.json`.
