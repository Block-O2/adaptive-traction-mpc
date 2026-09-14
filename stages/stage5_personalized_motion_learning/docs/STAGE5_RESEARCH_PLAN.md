# Stage-5 Research Plan

## Status and boundary

`Stage-5 Plant v1` is frozen. Its geometry and cuff mechanics remain the
provisional simulation plant until a separately approved hardware-calibration
phase replaces them. This plan does not change the current controller, start
RL/value training, define clinical limits, or modify Stage 3/4.

Stage 5 studies a repetitive rehabilitation session of approximately 30
outbound--hold--return repetitions. The research target is rapid
personalization within approximately the first 3--5 repetitions, followed by
stable exploitation for the rest of the session. “Personalization” must be
demonstrated by preregistered, causal, matched evidence; it is not inferred
from a training loss or a single favorable trajectory.

## Core research direction

The intended control architecture has three complementary parts:

1. **Online Human dynamics identification.** Retain causal identification of a
   control-effective Human model. It estimates how the Human state will evolve
   under a proposed generalized cuff action. The identified parameters need
   not be interpreted as anatomical truth.
2. **Goal-directed CEM-MPC.** Replace the prescribed full `q1/q2` time
   trajectory with an episode task: start state, goal state/region, phase, and
   explicit constraints. CEM-MPC remains the only module choosing the actual
   control action and continues to use short-horizon model prediction.
3. **Learned long-term state value.** Learn remaining task cost beyond the MPC
   horizon. The value module is not an actor and cannot directly command the
   plant. A candidate may learn continuously, but only a validated, immutable,
   published value version may enter MPC scoring.

The future planning objective is conceptually

`short-horizon predicted task cost + published terminal/remaining value`.

All explicit safety constraints and the executable-screening, Safety Filter,
and BRAKE path remain outside and authoritative over learning.

## Ordered research phases

### Phase 0: frozen plant and contracts

- Retain `Stage-5 Plant v1`, the 0.25 ms physics timestep, current Human
  mechanics, geometry, controller ancestry, and safety execution boundary.
- Freeze the episode/task contract and learning/control responsibility split.
- Define reproducible session, repetition, model-version, and value-version
  provenance.

This document set completes the contract definition only. It is not an
Experiment Spec and produces no scientific result.

### Phase 1: goal-directed model-based baseline

- Implement outbound--hold--return phase state and true task completion.
- Reuse the current two-dimensional Human generalized action, Human predictor,
  cuff allocator, CEM sampler, first-action screening, Safety Filter, and
  BRAKE.
- Replace time-indexed `q_ref/dq_ref/ddq_ref` arrays with goal/progress costs
  and explicit task constraints.
- Set terminal learned value identically to zero. This isolates and validates
  the goal-directed MPC change before any value learning.
- Compare against the frozen prescribed-trajectory sanity baseline only under
  a separately approved Experiment Spec.

### Phase 2: online Human-model personalization

- Restore the retained Stage-4-style causal control-effective Human
  identification behind its trust/publication boundary.
- Record the exact Human-model version used by every MPC solve and transition.
- Evaluate prediction and task performance separately; parameter proximity to
  simulator truth is evaluation-only and is not the promotion criterion.
- Target useful model personalization within approximately 3--5 repetitions,
  without assuming it will occur.

### Phase 3: value learner in shadow mode

- Train state remaining-cost estimates within episodes and across repetitions.
- Keep the candidate value out of control; log counterfactual terminal-value
  contributions and calibration errors.
- At episode end, use complete observed returns to correct online TD targets.
- Preserve aborted/failed episodes as costly or censored non-success outcomes,
  never zero-cost completions.

### Phase 4: published value in MPC

- Define a preregistered validation and publication rule.
- Publish immutable value versions only after future-data validation; retain a
  known-good incumbent and explicit rollback.
- Add the published terminal value to goal-directed CEM candidate scoring.
- Require exact logs showing which value version ranked each candidate and
  which action was ultimately executed after the safety stack.
- Test rapid improvement over the first 3--5 repetitions and stable
  exploitation over the remaining repetitions of an approximately 30-repeat
  session.

### Phase 5: later hardware validation

Before hardware or clinical interpretation, separately measure and validate:

- robot/table/Human/cuff frame registration and repeatability;
- cuff, strap, adapter, mount, and leg-surrogate stiffness/damping, including
  hysteresis, backlash, slip, and rate dependence;
- force/torque sensing axes, bias, drift, bandwidth, delay, saturation, and
  calibration uncertainty;
- actual Human/fixture ROM and task-specific start/goal regions;
- robot dynamics, latency, collision geometry, stopping, hold, retreat, and
  load-transfer feasibility;
- hardware operating limits and an independently approved safety protocol.

Simulation completion or the Stage-4 200 N engineering gate does not establish
hardware or clinical safety.

## Scientific comparisons to preregister later

The natural staged comparisons are:

1. prescribed-trajectory Stage-5 sanity baseline;
2. goal-directed MPC with fixed Human model and zero terminal value;
3. goal-directed MPC with trusted online Human model and zero terminal value;
4. the same MPC with a published learned terminal value.

Each comparison must keep plant, episode set, initial states, constraints,
measurement cases, safety stack, action definition, and evaluation metrics
matched. Failed and aborted repetitions remain in the analysis. No formal run
is authorized by this plan alone.

## Required evidence milestones

- contract/unit validation for task phase, cost, constraint, termination, and
  logging semantics;
- deterministic smoke replay with zero terminal value;
- matched goal-directed baseline under an approved Experiment Spec;
- causal Human-model publication evidence;
- value prediction calibration on future held-out transitions and complete
  episode returns;
- published-value control evaluation with rollback and safety invariance;
- only then, separately reviewed hardware validation.
