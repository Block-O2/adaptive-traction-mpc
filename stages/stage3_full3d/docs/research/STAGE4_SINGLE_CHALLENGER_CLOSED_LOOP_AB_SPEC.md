# Stage-4 Single-Challenger Closed-Loop A/B Experiment Spec

Status: preregistered implementation, awaiting user-run formal execution and
review. This spec is not evidence and does not make the trust rule production
default.

## Question

Does a statistically qualified patient-specific 11-base Human dynamics model
provide meaningful closed-loop benefit over population-prior control during
the existing short 23 s reference trajectory, after accounting for the late
qualification time imposed by causal validation?

## Single scientific variable

`apply_statistically_qualified_dynamics_model_to_control`

- A, `prior_only`: false. The same trust lifecycle runs causally so pacing and
  diagnostics retain the same contract, but qualified dynamics parameters are
  never applied to the control model. The control dynamics remain exactly the
  population prior.
- B, `trusted_adaptive`: true. A qualified challenger becomes the control
  incumbent at its causal L4 decision time.

Before the first B promotion the arms must have identical control-model
dynamics, registered random seeds, and settings. Pre/post reporting uses B's
first control-promotion wall time as one shared split for both arms.

## Frozen shared configuration

- Human: `registered_cold_start_perturbed_human`.
- Reference: existing continuous high-flexion trajectory, 23 s reference phase.
- Wall-time limit: 32 s, already used for the existing confidence-paced
  continuous execution so the slowed 23 s phase has an opportunity to finish.
- Sensor case: `noise_bias_drift_200hz`.
- Measurement random seed: 44104.
- MPC random seed: 20260824.
- Geometry estimator: unchanged accumulated cuff geometry estimator.
- Dynamics estimator: unchanged constrained 11-base integral identifier and
  physical bounds.
- L1/L2/L3: unchanged hierarchical-trust semantics and diagnostics.
- L4: one incumbent, at most one challenger; 0.5 s embargo; clean non-overlap
  0.5 s validation blocks; looks at 8/12/16 blocks; lag-2 HAC bounds; anytime
  `alpha_j=0.05/[j(j+1)]`, split across two references and three looks.
- MPC/CEM: current production configuration, unchanged.
- Allocator: frozen 1:1 cuff-aware engineering allocator.
- Confidence pacing: existing low-pass/hysteretic model-confidence execution
  layer, unchanged.
- Plant, gains, trajectory, solver, force gate, ROM, robot limits, and all
  safety settings: unchanged.
- UKF/Kalman, hybrid optimizer, corridor/tube, and new excitation: absent.

The 32 s wall limit is a completion observation window, not a change to the
23 s task trajectory. If either arm terminates or fails to reach phase 23 s,
that result is retained without rerun or tuning.

## Required outputs

For each arm, retain raw JSON/NPZ plus:

- challenger creation, decision, qualification/promotion wall times and
  reference phases;
- remaining reference-phase duration after each promotion;
- termination, wall duration, reference-completion time, final phase/progress;
- tracking RMSE and maximum error;
- cuff force and moment peak/RMS;
- cylindrical minimum-norm surface-load proxy peak/RMS, explicitly not pressure
  or comfort;
- robot torque and velocity peak/RMS;
- causal confidence-pacing and speed-scale signals;
- control-model generalized-torque oracle error, appended only after rollout;
- safety, contact, torque saturation, MPC failure, and MuJoCo warning events;
- the same metrics before B's first promotion, after it, and over the full
  available task phase.

## Decision interpretation

No numerical benefit threshold is introduced after observing results. Report
continuous A-minus-B differences and effect sizes. A late statistically valid
improvement may be measurable but practically small. No promotion, incomplete
task, safety termination, or worse adaptive result remains valid evidence and
must not trigger tuning in this experiment.

The trust subsystem can be recommended for freeze only if the single-
challenger invariants hold, no oracle enters online decisions, fallback remains
safe, and the observed post-promotion benefit is practically relevant relative
to the small remaining trajectory. Otherwise report adaptation latency or lack
of benefit as the blocking finding.

## Formal user command

From `stages/stage3_full3d`:

```bash
PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_single_challenger_closed_loop_ab.py \
  --output-dir results/stage4_single_challenger_closed_loop_ab_formal
```

The output directory must not already exist. Do not rerun with changed settings
after inspecting results.
