# Stage-5 progressive Human-model authority v1

## Scope and preserved stop result

The previous progressive task stopped before any longitudinal A/B session.
That stop was an implementation-semantic finding, not evidence against
progressive personalization.  The bounded rule already worked for an arbitrary
`theta_k`; the problem was that `OneStepHumanModelControlAuthority` could label
the predecessor as `theta_1` while keeping its actual scales and reduced-ID
incumbent at `[1,1,1]`.  The reduced service had no non-nominal initialization,
the successor id was hard-coded to v1, updates applied immediately within an
episode, and no post-update gate or multi-version lineage existed.

This change implements only model/authority state semantics.  It does not run
Goal-MPC, change Human-ID fitting, statistical thresholds, smoothing/bounds,
gamma, acceleration monitoring, task limits, interface behavior or runtime.

## Active-model API

`ActiveHumanModel` is an immutable record containing:

- deterministic `model_id`, session id and update index;
- `theta=[alpha_M,alpha_K,alpha_D]`;
- immediate predecessor and rollback predecessor ids;
- provenance and candidate evidence id;
- bounded transition delta and qualification repetition/time;
- activation repetition/time; and
- post-update evidence state/id/time.

The id has the form
`stage5-human:<session>:u<index>:<theta-sha256-prefix>`.  Construction validates
the id against the exact float64 theta bytes, so a version string cannot be
paired with different scales.  Progressive successor ids are deterministic and
unique by session/update index/theta.

## Authority separation

```text
population prior theta_prior=[1,1,1]
    |-- regularization reference
    |-- secondary prediction diagnostic
    `-- NO immediate transition authority

active current model theta_k
    |-- exact model used by future Goal-MPC integration
    |-- retained reduced-ID incumbent
    `-- immediate predecessor for the next transition

absolute Human-ID candidate theta_c
    `-- bounded rule around theta_k
        raw     = theta_c - theta_k
        smooth  = 0.10 * raw
        limited = clip(smooth, -0.03, +0.03)
        theta_k+1 = clip(theta_k + limited, 0.5, 1.5)
              |
              `-- qualified successor queued for next repetition
```

The existing prior-regularized absolute fit is unchanged.  Training residual
acceptance uses the retained active incumbent.  Future validation computes the
same frozen one-sided intervals for both active predecessor and population
prior.  The population-prior interval remains in the record, but only the
immediate-predecessor interval supplies `transition_authority_supported`.  The
per-reference alpha spending and thresholds are unchanged.

## Repetition-boundary queue

One repetition has exactly one fixed active model.  A causally qualified
proposal records its current predecessor id and is queued without changing the
active model.  At the immediately following valid repetition boundary the
authority verifies that the predecessor is still current, activates the queued
model once, aligns the reduced-ID incumbent atomically, retains the predecessor
as rollback provenance, and starts a new reset-isolated episode.  Wrong
repetition, stale predecessor, changed successor theta/id, duplicate evidence,
pending challenger or multiple queued updates fail explicitly.

The reduced service now accepts initial incumbent theta/version separately from
the fixed population prior.  Deferred-publication mode prevents the service
from fitting another challenger against a merely queued model.  Integral and
future-validation blocks continue carrying episode indices and cannot cross a
simulation reset.

## Post-update support gate

Transition qualification and post-update support are separate records.

| post-update evidence | active model | next correction authority |
|---|---|---|
| POSITIVE | retained | enabled for one later qualified successor |
| NEUTRAL | retained | blocked; collect more evidence |
| NEGATIVE | retained, rollback predecessor preserved | session progression blocked |

There is no automatic rollback.  NEGATIVE marks the session as a rollback
candidate and blocks progression.  No `theta_k+2` can be queued until the
actually active `theta_k+1` receives post-update POSITIVE evidence.

The independently replicated starting `theta_1` is initialized as supported.
All later activated models start NEUTRAL.

## Regularization audit

The identifier still solves an absolute three-scale candidate with its frozen
`1e-3` regularization toward `[1,1,1]`.  This prior remains separate from the
active incumbent.  It does not replace retained theta, determine the bounded
delta, or authorize a transition.

For the test-only candidate `[1,1,1.2]`, starting from
`theta_1=[1.0000584390985465,1.0010424686528112,1.0193479803467633]`, the
unchanged bounded rule gives:

`theta_2=[1.0000525951886918,1.00093822178753,1.037413182312087]`.

This is the update from `theta_1`, not the nominal-based
`[1,1,1.02]`.  The synthetic candidate exists only in tests.

## Focused state-machine validation

| requirement | focused evidence |
|---|---|
| non-nominal initialization | active id/theta and reduced-ID incumbent match theta1 |
| non-nominal bounded successor | exact theta1-relative theta2 result |
| immediate-predecessor authority | transition passes against theta1 even when prior diagnostic is unfavorable |
| queue without mid-repetition switch | active theta1 remains unchanged |
| next-boundary activation | theta2 activates exactly once in repetition 2 |
| lineage/rollback | theta2 points to theta1 |
| NEUTRAL | theta2 retained; theta3 blocked |
| POSITIVE | theta3 may queue and activate next repetition |
| NEGATIVE | progression blocked; theta1 rollback record preserved |
| one transition per repetition | duplicate queue/boundary rejected |
| stale candidate | old-predecessor candidate rejected |
| id/theta consistency | mismatched construction raises |
| reset isolation | validation blocks contain one episode only |
| prior separation | prior remains `[1,1,1]` and non-authoritative |
| truth isolation | no truth argument/API; unexpected truth field rejected |
| gamma | fixed status remains exactly 0.5; authority has no gamma authority |
| acceleration monitor | existing Goal-MPC path unchanged |
| deferred service proposal | matching service proposal queues/activates atomically |
| fixed arm | theta1 cannot change |

The deterministic unit-test harness exercises both the required
`theta1 ACTIVE -> theta2 QUEUED -> theta2 ACTIVE -> NEUTRAL -> HOLD` path and a
separate synthetic-evidence `theta2 ACTIVE -> POSITIVE -> theta3 authority`
path.  Saved scientific traces do not contain a deployed theta2 or its later
evidence, so they cannot provide a meaningful real-trace progressive replay;
no evidence was fabricated in a scientific report and no MuJoCo episode ran.

## Decision and next experiment design

**PA-A — PROGRESSIVE AUTHORITY READY**, subject to the regression results in
this checkpoint.  This is an implementation readiness result only.

The next longitudinal experiment is design-only:

- Arm A holds the independently supported theta1 for every repetition;
- Arm B starts theta1, queues at most one qualified update per repetition and
  activates it only at the next boundary;
- a later update requires post-update POSITIVE support for the current model;
- NEUTRAL holds and NEGATIVE blocks progression;
- up to five matched repetitions use preregistered controller-search seeds;
- gamma remains 0.5 and all controller/safety/monitor/runtime semantics remain
  frozen.

No longitudinal session was run in this task.
