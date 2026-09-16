# Stage-5 Acceleration and Pacing Signal-Authority Audit

Evidence category: diagnostic-only, saved-trace audit. No rehabilitation
episode was run. No acceleration monitor, Human-ID, trust threshold, gamma
bound, registered limit, interface model, control model, or controller behavior
was changed.

The single-episode reduced Human-ID endpoint remains **R-C**. The confidence-
pacing/session endpoint remains **P-B**. The P-B files were checkpointed before
this audit at `11e1825` (`stage5: checkpoint confidence pacing human id study`).

## Current deployable acceleration authority

The online quantity is **model-based**, not a direct derivative of estimated
velocity and not a hybrid of the two.

```text
200 Hz robot cuff pose/twist + measured physical cuff wrench
  -> nominal controller Kelvin-Voigt inversion
  -> Human-side cuff pose/twist and interface state
  -> fixed registered geometry estimates q_hat,dq_hat
  -> measured Human-site cuff wrench mapped by virtual work to tau_measured
  -> fixed nominal Human model forward dynamics qdd_model(q_hat,dq_hat,tau_measured)
  -> trapezoidal causal mean over trailing min(history,20 ms)
  -> task_limit_violation([300,600] deg/s2)
  -> TASK_ACCELERATION_LIMIT -> GoalTaskState.ABORTED
```

Exact authority answers:

1. `CausalModelAccelerationMonitor` evaluates instantaneous forward dynamics
   from the deployable state and wrench, then averages those model accelerations.
   It does not differentiate `dq_hat`.
2. The model is `stage5_fixed_registered_human_v1`: registered geometry and
   fixed nominal Human beta from `FixedStage5Estimator`. Reduced shadow models
   are held by a separate service and never enter this path.
3. `InterfaceAwareHumanStateObserver` uses controller nominal Plant-v1
   Kelvin-Voigt parameters to infer Human cuff state from robot cuff pose/twist
   and measured wrench. No plant-truth interface state or parameter enters.
4. After startup, the monitor represents a trailing 20 ms trapezoidal mean of
   model `qdd` sampled every 5 ms. At 0/5/10/15 ms it uses the causally available
   0/5/10/15 ms interval; there is no startup exemption.
5. The gate is model-agnostic. `task_limit_violation` receives a two-vector and
   compares absolute values to the immutable task limits. All Human-model logic
   is upstream in the estimator/monitor.

The generalized Human input is reconstructed from the measured force and
moment about `human_sleeve_attach_site` through the nominal Human geometry.
The monitor's interval start is logged explicitly in each trace.

## Offline acceleration comparison

All calculations below use exact saved 5 ms samples. Motion-history candidates
are backward differences of deployable `dq_hat`; no interpolation, future
sample, MuJoCo state, or truth parameter is used. Each candidate is compared to
truth `dq` over the identical window. Vectors are `[q1,q2]` in deg, deg/s, or
deg/s2 as indicated. The registered limit is `[300,600] deg/s2`.

### Human-ID traces

In each acceleration cell, `signal | evaluation-only truth` is shown.

| trace/event | t; estimated q / dq | current model-mean | 5 ms history | 10 ms history | 15 ms history | 20 ms history |
|---|---|---|---|---|---|---|
| nominal near-limit | 3.400; `[19.51,36.08]` / `[0.75,-4.40]` | `[-152.86,-351.06] | [-162.12,-383.02]` | `[-141.41,-282.24] | [-155.58,-304.05]` | `[-146.43,-302.38] | [-159.89,-322.50]` | `[-147.05,-333.56] | [-168.39,-367.89]` | `[-162.41,-384.96] | [-162.12,-383.02]` |
| damping +20% near-limit | .280; `[5.83,11.72]` / `[5.65,11.39]` | `[133.28,354.63] | [97.67,221.52]` | `[76.75,112.32] | [91.03,135.39]` | `[81.77,136.16] | [95.27,157.71]` | `[81.76,164.41] | [99.72,194.46]` | `[101.30,231.21] | [97.67,221.52]` |
| stiffness +15% abort | 4.100; `[16.27,26.74]` / `[3.77,5.77]` | `[225.64,666.82] | [131.44,315.53]` **FP** | `[107.72,195.00] | [124.27,219.43]` | `[112.54,217.90] | [128.21,240.65]` | `[115.25,259.47] | [139.03,297.32]` | `[132.95,321.15] | [131.44,315.53]` |
| mass +8% abort | .320; `[4.40,9.95]` / `[-2.28,-3.58]` | `[197.33,766.49] | [-7.04,-280.75]` **FP** | `[27.55,-242.22] | [25.26,-237.34]` | `[7.46,-354.08] | [11.98,-348.40]` | `[-10.17,-351.49] | [-4.47,-356.12]` | `[-14.67,-284.17] | [-7.04,-280.75]` |
| mixed abort | .505; `[5.06,11.32]` / `[0.46,1.25]` | `[141.32,663.76] | [-37.19,-208.15]` **FP** | `[-35.56,-178.27] | [-29.28,-152.30]` | `[-37.73,-204.11] | [-34.00,-188.35]` | `[-43.68,-245.62] | [-40.01,-236.45]` | `[-39.72,-211.18] | [-37.19,-208.15]` |

Whole-trace synchronized classifications:

| trace | current FP/FN | 5 ms FP/FN | 10 ms FP/FN | 15 ms FP/FN | 20 ms FP/FN |
|---|---:|---:|---:|---:|---:|
| nominal | 0/0 | 2/0 | 0/0 | 0/0 | 0/0 |
| damping +20% | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| stiffness +15% | 1/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| mass +8% | 1/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| mixed | 1/0 | 0/0 | 0/0 | 0/0 | 0/0 |

Thus every tested history window removes the three Human-ID abort events, but
5 ms history introduces two nominal false positives elsewhere. This fact alone
cannot authorize a monitor replacement.

### Interface safety-regression stress traces

These traces are separate safety stress evidence and do not alter any interface
campaign conclusion.

| trace/event | t; estimated q / dq | current model-mean | 5 ms history | 10 ms history | 15 ms history | 20 ms history |
|---|---|---|---|---|---|---|
| `Kt x0.7`, first 20 ms truth violation | 2.960; `[10.40,12.92]` / `[-18.13,-40.48]` | `[216.35,490.33] | [265.39,656.34]` **FN** | `[234.89,452.37] | [249.10,479.41]` | `[256.98,527.46] | [264.91,549.58]` | `[262.34,589.30] | [274.61,626.06]` **FN** | `[296.75,700.47] | [265.39,656.34]` **TP** |
| `Kt x1.3`, current abort | .385; `[11.10,24.07]` / `[27.00,54.66]` | `[126.51,734.07] | [-50.20,-457.36]` **FP at 20 ms semantics** | `[-114.84,-1143.95] | [-138.69,-1165.55]` TP | `[-137.97,-992.42] | [-149.00,-1035.23]` TP | `[-71.37,-613.92] | [-85.34,-649.98]` TP | `[-32.09,-421.05] | [-50.20,-457.36]` TN |
| V2 `low_low_high`, first 5 ms truth violation | .005; `[5.19,10.43]` / `[0.20,1.39]` | `[157.12,504.41] | [185.82,633.71]` **FN** | `[39.09,277.97] | [185.82,633.71]` **FN** | unavailable | unavailable | unavailable |

Important timing details:

- `Kt x0.7`: current monitor never detects the retained 20 ms truth violation.
  The 20 ms history candidate first crosses at 2.955 s; truth crosses at
  2.960 s, a conservative 5 ms lead. Its whole trace has one FP and one TP.
- `Kt x1.3`: under 20 ms semantics the current abort is conservative, but the
  same trace contains real 5/10/15 ms truth exceedances. This illustrates that
  changing the interval changes the physical question; it is not evidence that
  one window is universally correct.
- V2 `low_low_high`: truth exceeds q2 at 5 ms. Current monitor is below at
  5 ms and crosses at 10 ms, when the same 10 ms truth interval is already
  below 600. It nevertheless detects a preceding real transient with 5 ms
  delay. The 5 ms motion-history candidate also misses; 10/15/20 ms candidates
  are below-limit or unavailable before the saved run terminates.

No existing history window both removes the Human-ID conservative aborts and
retains detection of both known types of real violation. In particular, the
otherwise promising 20 ms history signal detects `Kt x0.7` but cannot assess
the early 5 ms V2 event. Truth-compliant historical motion therefore is not
assumed safe to continue online.

## Confidence-to-gamma path

```text
reduced-ID clean-block information (diagnostic only)
  -> candidate fit (cannot raise gamma)
  -> embargoed future validation
  -> shadow publish/reject/pending (cannot directly raise gamma)
  -> current_nominal_model_trust_from_shadow_service()
  -> raw bool: is the fixed nominal model causally supported?
  -> 0.75 s first-order filter
  -> hysteresis: enter .75 / exit .25
  -> target gamma: 1.0 if high else .5
  -> rate limit: recovery .25/s, slowdown 1.0/s
  -> Goal-MPC planning velocity ceiling gamma*[15,25] deg/s
```

Gamma is driven only by evidence about the **current fixed nominal Human model
used by Goal-MPC**. It is not driven by generic rank/conditioning, the latest
candidate, or retained shadow incumbent. A shadow publication actively means
that another model predicted future blocks better while remaining unauthorized
for control; it cannot make nominal trustworthy.

| condition / time | information | challenger/publications | raw nominal support | filtered trust | gamma target / actual |
|---|---|---|---|---:|---:|
| nominal 0 | rank 0 | none / 0 | false: no comparison | 0 | .5/.5 |
| nominal 1.245 | rank 3, cond 4.581 | pending / 0 | false | 0 | .5/.5 |
| nominal 3.045 | rank 3, cond 3.140 | first shadow publication | false: challenger outperformed nominal | 0 | .5/.5 |
| nominal 5.645 | rank 3, cond 1.422 | rejected/inconclusive | false | 0 | .5/.5 |
| nominal 8.245 | rank 3, cond 1.341 | later rejected as worse | **true: supports nominal** | .0066 | .5/.5 |
| nominal 8.300 end | same | pending remains | true | .0769 | .5/.5 |
| stiffness 1.245 / 3.045 | rank 3, cond 3.630 -> 2.393 | pending -> publication | false throughout | 0 | .5/.5 |
| damping 1.245 / 3.045 / 5.645 / 7.445 | rank 3; cond 3.892 -> 1.389 | publish, inconclusive reject, publish | false throughout | 0 | .5/.5 |

Nominal remains at .5 because its first positive raw evidence appears only
55 ms before completion. The filter cannot reach .75, much less finish the
subsequent 2 s ramp at .25/s. Stiffness and damping remain at .5 because their
publications support different shadow models, not the nominal model still in
control. These three observed gamma trajectories are intended conservative
semantics, not a threshold or rate bug.

## Authority tests and one wiring gap

Focused tests establish that:

- full-rank fit/information alone cannot raise gamma;
- shadow publication cannot confer trust on a different control model;
- information quality and current-model trust are separate;
- explicit independent support for the current model passes through the
  filter, hysteresis, and rate limiter to recover gamma from .5 to 1.0.

One strict expected-failure test isolates a separate, not-yet-exercised gap.
The helper reconstructing nominal trust is stateless: if an older rejected
challenger supplied positive nominal support, a later *inconclusive* rejection
is treated as raw false and can eventually erase that support. An inconclusive
challenger should not automatically invalidate an already supported current
model. The core pacing class accepts persistent explicit support correctly;
the missing link is a model-versioned persistent current-control-model trust
state between the shadow service and pacing input.

This gap did not cause the saved gamma=.5 outcomes: stiffness/damping had no
nominal-support evidence, while nominal received support too late. No fix is
enabled here. The minimal future correction is to retain positive/negative
evidence keyed to the model actually in control and change it only on explicit
same-model validation/invalidation; challenger pending/inconclusive status
must remain diagnostic. Thresholds and rates need not change.

## Independent decisions

### A-MONITOR-UNRESOLVED

The current signal catches the early V2 transient with delay but misses the
`Kt x0.7` 20 ms violation and creates the three Human-ID conservative aborts.
The 20 ms history candidate removes those aborts and detects `Kt x0.7`, but is
unavailable for the early V2 event; shorter history candidates also miss that
event and introduce other false positives. Neither existing deployable signal
has demonstrated both required properties. Do not replace the monitor yet.

### P-TRUST-WIRING-GAP

The saved gamma=.5 trajectories are supported by the evidence. However, the
intended rule that inconclusive challengers do not invalidate an already valid
current model is not persistently represented at the service-to-pacing
boundary. This is a semantic connection gap, not an observed CEM/pacing defect
and not authorization to change thresholds.

## Smallest next online experiment design — not run

Because the acceleration decision is unresolved, no monitor A/B is authorized.
The next isolated experiment should address only the trust wiring while keeping
the current acceleration monitor unchanged:

- condition: nominal Human only, fixed nominal interface, same task, seed,
  Goal-MPC, limits, Human-ID, trust thresholds, gamma bounds, and Safety chain;
- arm A: present stateless service-to-pacing trust adapter;
- arm B: proposed model-versioned persistent current-model trust adapter;
- identified models remain shadow-only and never enter Goal-MPC;
- run at most two repetitions per arm, continuing after the first publication
  only to observe whether current-model support survives a later pending or
  inconclusive challenger;
- primary records: raw support evidence with model version, filtered trust,
  hysteresis state, gamma target/actual, and acceleration/safety events;
- if the required support-then-inconclusive sequence does not occur, report the
  comparison as uninformative rather than adding repetitions or changing
  thresholds.

Before any online run, the proposed adapter must first make the strict expected-
failure test pass and reproduce the existing nominal/stiffness/damping saved
gamma histories up to the point where the new persistence rule is actually
exercised. Monitor and pacing behavioral changes must not be combined.

## Reproducibility and limits

The read-only audit command is:

```bash
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/audit_stage5_acceleration_pacing_signals.py \
  --output-dir stages/stage5_personalized_motion_learning/results/acceleration_pacing_signal_audit_v1_attempt_02
```

The JSON diagnostic remains ignored/local. This audit makes no hardware-safety,
anatomical-recovery, simultaneous Human/interface-uncertainty, or 3--5-
repetition personalization claim. Interface EXIT C remains unchanged.
