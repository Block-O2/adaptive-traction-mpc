# Stage-5 Human-ID Confidence Pacing V1

## Scope and frozen predecessor

This is a small multi-repetition engineering feasibility study, not a formal
personalization campaign. The prior single-episode result remains **R-C — HUMAN
ID NOT USEFUL ENOUGH** and is not relabelled. Its reduced three-scale shadow
implementation was checkpointed locally at `b621e0c` with no model entering
control.

This study retains the same joint control-effective parameterization

`theta_H = [alpha_M, alpha_K, alpha_D]`

and the same fit, embargo, future-validation, challenger, and smoothed shadow
publication rules. Goal-MPC always uses the fixed nominal Human model. Plant-v1
and the controller nominal interface are fixed; Human truth scales are
evaluation-only. No interface identification, value learning, RL, or closed-loop
Human-model publication is active.

## Stage-4 execution audit

The audit used the actual `confidence_execution.py` implementation rather than
its historical result labels.

| Stage-4 component | Stage-5 classification | V1 treatment |
|---|---|---|
| Retained/current-model validity distinct from information confidence | directly reusable | current-model trust alone may raise pacing |
| One retained incumbent, one challenger, embargoed future evidence | directly reusable | unchanged reduced shadow lifecycle |
| `prior_only` versus trusted adaptive authority | directly reusable in meaning | fixed nominal remains the control incumbent; every challenger is shadow-only |
| First-order confidence filter and enter/exit hysteresis | directly reusable | unchanged historical defaults |
| Minimum/nominal scale and rate-limited slowdown/recovery | reusable after semantic adaptation | scale a Goal-MPC planning-velocity ceiling, not a trajectory clock |
| Reference phase clock and time-warp kinematics | not appropriate | no phase clock, full `q(t)`, or reference derivatives exist |
| Safety-Filter intervention magnitude as `alpha_force` | not reused | Stage-5 Safety Filter/BRAKE and hard gates retain their existing authority |

The historical default mapping is defensible because the Stage-5 quantity is a
soft, independent-joint planning ceiling already separate from registered hard
velocity/acceleration constraints. The first and only V1 settings are:

| Parameter | Value |
|---|---:|
| `gamma_min`, `gamma_nominal` | 0.50, 1.00 |
| recovery, slowdown | 0.25/s, 1.00/s |
| confidence filter time constant | 0.75 s |
| high-confidence enter, exit | 0.75, 0.25 |

These are unchanged Stage-4 `ConfidenceAwareExecutionConfig` defaults, not
Stage-5 outcome tuning.

## Exact Stage-5 pacing semantics

At each causal controller update,

`v_plan_ceiling(t) = gamma(t) * [15, 25] deg/s`, `gamma in [0.5, 1]`.

The two ceilings remain independent; this does not impose a `q1/q2` ratio,
path corridor, or full time reference. `gamma` does not scale inverse-dynamics
support, the loaded HOLD equilibrium, the registered `[45,75] deg/s` velocity
limits, the `[300,600] deg/s^2` 20 ms acceleration limits, force/moment gates,
Safety Filter, or BRAKE.

Three signals are explicit and non-substitutable:

1. identification information: whether data support fitting all three scales;
2. current control-model trust: whether causal future data support the nominal
   model actually used by MPC;
3. challenger publication: whether a shadow candidate beat its references.

A fit, full rank, low training residual, pending challenger, or shadow
publication cannot raise `gamma`. A published challenger instead means that the
nominal control model has been outperformed but cannot yet be replaced, so its
trust remains low. Only completed future evidence that a challenger is
statistically worse than nominal can support nominal-model trust. Rate limiting
and the confidence filter then still prevent an instantaneous recovery.

In this study `gamma` stayed exactly 0.5 in all episodes. Nominal obtained one
late nominal-supporting comparison, but filtered trust ended at 0.0769, below
the 0.75 enter threshold; all other final filtered trust values were zero.

## Session-persistent lifecycle

```text
same Human condition
    |
    v
Episode n: causal measurements -> episode-internal 0.2 s blocks
    |                                  |
    |                                  +-> fit/pending challenger
    |                                           |
physical reset (no transition/window crosses)  |
    |                                           v
    +-> Episode n+1 internal blocks ------> future validation
                                                |
                             publish / reject / remain pending
                                                |
                         retained shadow state and history persist
```

Global session timestamps and episode indices disambiguate evidence. Regression
and validation blocks are constructed separately within each episode; neither
dynamics transitions nor integration windows cross a reset. Later episode
blocks can validate an earlier challenger only after they arrive. Unit tests
cover this causal path. The observed study did not exercise cross-episode
publication: every published candidate matured within repetition 1, while the
two repeated-abort conditions never produced a candidate.

## Five-condition result

One fixed seed and one frozen pacing configuration were used. Stop occurred
after the first qualified shadow publication or after two consecutive
minimum-pacing aborts with fewer than 16 cumulative clean blocks.

| Human condition | Repetitions / result | task time; wall time | gamma min/mean/final; time at min | clean blocks by repetition | first fit / first publication | retained shadow scales |
|---|---|---|---|---|---|---|
| nominal `[1,1,1]` | 1; COMPLETE | 8.300 s; 48.764 s | .5/.5/.5; 8.305 s | 162 | 1.245 s / rep 1 at 3.045 s | `[1.00009,0.99996,1.00079]` |
| mass +8% `[1.08,1,1]` | 2; acceleration ABORT twice | .320+.320 s; 4.077 s | .5/.5/.5; .325 s each | 0, 0 | none / none | `[1,1,1]` |
| stiffness +15% `[1,1.15,1]` | 1; acceleration ABORT | 4.100 s; 25.385 s | .5/.5/.5; 4.105 s | 78 | 1.245 s / rep 1 at 3.045 s | `[1.00008,1.01466,1.00122]` |
| damping +20% `[1,1,1.2]` | 1; COMPLETE | 8.860 s; 52.442 s | .5/.5/.5; 8.865 s | 173 | 1.245 s / rep 1 at 3.045 s | `[1.00010,1.00086,1.03940]` |
| mixed `[1.04,1.10,1.10]` | 2; acceleration ABORT twice | .505+.505 s; 6.621 s | .5/.5/.5; .510 s each | 0, 0 | none / none | `[1,1,1]` |

Compared with the fixed-pacing single episodes, nominal duration rose from
4.935 to 8.300 s, stiffness from 1.335 to 4.100 s, damping from 5.060 to
8.860 s, and mass from .270 to .320 s. Mixed decreased from .550 to .505 s.
Thus slower planning has a real collection-time cost and does not uniformly
increase survivability.

### Motion and execution constraints

| Condition | peak estimated/truth velocity q1,q2 (deg/s) | peak deployable/truth acceleration q1,q2 (deg/s²) | peak force / moment | Safety result |
|---|---|---|---|---|
| nominal | `[6.34,12.48]` / `[6.36,12.43]` | `[152.86,351.06]` / `[162.12,383.02]` | 112.07 N / 14.50 Nm | no gate/BRAKE; all 1660 `SAFE_UNCHANGED` |
| mass +8% | `[3.04,3.85]` / `[3.05,3.87]` | `[209.05,766.49]` / `[123.99,280.75]` | 90.87 N / 14.41 Nm | deployable q2 monitor abort; no gate/BRAKE |
| stiffness +15% | `[5.00,10.57]` / `[5.00,10.56]` | `[225.64,666.82]` / `[131.44,315.53]` | 111.83 N / 14.49 Nm | deployable q2 monitor abort; no gate/BRAKE |
| damping +20% | `[5.78,11.39]` / `[5.79,11.25]` | `[133.28,354.63]` / `[110.09,279.98]` | 111.44 N / 15.03 Nm | no gate/BRAKE; all 1772 `SAFE_UNCHANGED` |
| mixed | `[1.77,7.05]` / `[1.82,6.92]` | `[180.98,663.76]` / `[113.81,323.44]` | 93.20 N / 14.60 Nm | deployable q2 monitor abort; no gate/BRAKE |

Repeated cells were deterministic and have the same peaks. No MuJoCo warning
was recorded. The evaluation-only truth accelerations remain below the hard
limits in the three aborting cells, so these are conservative deployable-
monitor aborts; the registered decision semantics were not weakened.

## Information and challenger evolution

| Condition | fixed-pacing blocks -> V1 clean blocks | final rank / condition / max corr | first raw candidate | lifecycle |
|---|---:|---|---|---|
| nominal | 95 -> 162 | 3 / 1.338 / .283 | `[1.00089,.99963,1.00789]` | 1 publish, 2 reject, 1 pending |
| mass +8% | 2 -> 0+0 | no clean matrix | none | no attempt |
| stiffness +15% | 23 -> 78 | 3 / 2.258 / .586 | `[1.00076,1.14659,1.01217]` | 1 publish, 1 pending |
| damping +20% | 98 -> 173 | 3 / 1.357 / .296 | `[1.00058,1.01043,1.19348]` | 2 publish, 1 reject, 1 pending |
| mixed | 8 -> 0+0 | no clean matrix | none | no attempt |

The prior counts and V1 clean-block counts are not perfectly identical
quantities: the session implementation excludes reset/transition-contaminated
windows explicitly. The comparison still answers the operational question:
stiffness, nominal, and damping collect substantially more usable internal
blocks; mass and mixed do not collect a single admissible fit block despite a
second repetition.

All published first decisions used eight non-overlapping, genuinely future
blocks after the 1.245 s fit and embargo, with decision time 3.045 s. Their
validation episode indices were all `0`, so no claim of observed cross-episode
maturation is made. The smoothed shadow publication step deliberately moves
only partway toward the raw candidate, explaining why retained stiffness and
damping scales are closer to nominal than their raw fits. No fit hit a bound or
showed the defined instability flag.

## Future prediction error

Integrated generalized-torque residual RMSE is shown in Nms. `O/H/R` denotes
OUTBOUND/HOLD/RETURN; `--` means the episode never entered that phase.

| Condition | nominal control model O/H/R | retained shadow O/H/R | latest challenger O/H/R |
|---|---|---|---|
| nominal | `.004996/.000016/.005900` | `.004511/.000496/.006299` | `.004462/.000445/.006161` |
| mass +8% | `.45872/--/--` | same | same; no challenger |
| stiffness +15% | `.05280/--/--` | `.04759/--/--` | `.04285/--/--` |
| damping +20% | `.02170/.00182/.02193` | `.01750/.00156/.01898` | `.01583/.00141/.01729` |
| mixed | `.23230/--/--` | same | same; no challenger |

Stiffness and damping keep the correct candidate direction and improve the
available OUTBOUND future prediction. Nominal is already near zero, and its
tiny HOLD/RETURN differences do not support a personalization claim.

## Required questions

**Q1. Did pacing prevent premature termination?** Partly. Stiffness survives
3.07 times longer and reaches fit plus publication. Mass survives only .05 s
longer and mixed slightly less; both repeatedly abort before useful blocks.

**Q2. More information or only longer episodes?** Both, condition-dependent.
Nominal, stiffness, and damping gain clean blocks and/or better separation;
mass and mixed merely consume a second short episode with zero clean blocks.

**Q3. Can validation mature across repetitions?** The implementation can do
so causally and reset-boundary tests pass, without weakening the trust rule.
This run does not demonstrate it empirically because publications occurred in
episode 1 and the repeated cases never generated a challenger.

**Q4. Is the reduced candidate stable across repetitions?** Within the long
first episodes, stiffness/damping candidate directions remain physically
consistent and no bound/instability flag appears. No multi-repetition candidate
exists, so stability *across* repetitions remains unresolved.

**Q5. Does a trustworthy shadow incumbent emerge within 3--5 repetitions?**
Not for the representative set. It appears in repetition 1 for nominal,
stiffness, and damping, but never for mass or mixed. This is not evidence of
general 3--5-repetition personalization.

## Decision

**P-B — PACING HELPS, TRUST STILL TOO SLOW.** The lower planning ceiling
materially helps stiffness and permits causal shadow publication, but the
representative mismatch set remains incomplete: mass and mixed still terminate
at minimum pacing with no useful information. A qualified shadow incumbent is
not a control-authorized personalized model, and no trusted Human-model A/B is
preregistered or run. P-A is unsupported; lowering trust thresholds or motion
limits is not justified.

The unresolved hardware interface uncertainty remains separate. This study
does not claim anatomical recovery, simultaneous unknown Human/cuff robustness,
hardware safety, or clinical validation.

## Reproducibility

The compact record is `HUMAN_ID_CONFIDENCE_PACING_V1_SUMMARY.json`. The raw
engineering traces remain ignored under
`results/human_id_confidence_pacing_v1_attempt_01/`; they were not committed or
promoted to authoritative evidence. The study command was:

```bash
MPLCONFIGDIR=/tmp/stage5_human_id_confidence_pacing_mpl \
PYTHONPATH=stages/stage3_full3d/src:stages/stage4_adaptive_control/src:stages/stage5_personalized_motion_learning/src \
conda run --no-capture-output -n mpc_learn python \
  stages/stage5_personalized_motion_learning/scripts/run_stage5_human_id_confidence_pacing_v1.py \
  --output-dir stages/stage5_personalized_motion_learning/results/human_id_confidence_pacing_v1_attempt_01
```
