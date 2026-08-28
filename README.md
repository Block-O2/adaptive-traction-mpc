# Adaptive Traction MPC

This repository studies adaptive model-predictive control for robot-assisted
lower-limb motion. The central question is whether natural rehabilitation
motion contains enough information to improve control when the patient's
effective dynamics differ from a population prior, while preserving a causal,
auditable fallback to the prior model.

The current result is a **simulation-qualified research controller**. It is
not hardware-qualified, clinically validated, or production-ready.

## Project evolution

1. **Stage 1 — point-force mechanics.** A planar Spring2D model exposed the
   near-extension transmission problem and established fixed/adaptive MPC and
   identification baselines.
2. **Stage 2 — rigid-cuff mechanics.** Human V2 replaced the idealized point
   force with an explicit rigid cuff and preserved the key mechanics and
   model-mismatch questions in MuJoCo.
3. **Stage 3 — full 3D coupled simulation.** A torque-actuated 3D UR10e
   surrogate was coupled to Human V2 through a six-constraint rigid cuff, with
   explicit frame, actuator, wrench, and real-robot interface boundaries.
4. **Stage 4 — prior-informed, trust-gated adaptive MPC.** A causal accumulated
   integral estimator learns an 11-parameter control-effective Human model
   from robot/cuff measurements. A single incumbent/challenger trust lifecycle
   decides when a candidate may enter control. Natural task motion supplies the
   excitation; no hidden calibration motion or active-excitation policy is
   used in the authoritative crossed study.

## Current architecture

The plant is the Stage-3 torque-actuated UR10e surrogate plus Human V2 and the
rigid cuff. The Stage-4 loop reconstructs Human state and cuff wrench from the
robot-facing measurement boundary, updates the constrained 11-base integral
identifier, validates at most one challenger against a fixed incumbent on
future embargoed blocks, and exposes only a trusted retained model to the
controller. Confidence pacing advances the reference conservatively until the
retained geometry and dynamics models qualify.

The controller uses a frozen 1:1 cuff-aware sagittal allocator and feasible-
first CEM Human-space MPC: horizon 15, 32 candidates, two iterations, six
elites, and seed 20260824. Batched evaluation is the default; the scalar path
is retained as the regression/fallback reference. Interaction-aware objective
terms are implemented and have engineering evidence, but the authoritative
formal A/B and crossed replication keep those interaction weights at zero.

## Main simulation findings

- The original registered adaptive A/B reduced tracking RMSE from 0.7655° to
  0.7131° (6.85%) and torque-prediction RMSE from 4.4244 to 3.9687 Nm (10.30%).
  It did not materially reduce cuff interaction.
- The patient/model-mismatch suite promoted in 13/13 cases. Tracking RMSE
  improved in 13/13 and torque-prediction RMSE in 9/13; three pairs shared an
  incomplete reference because first qualification was late.
- The five-seed nominal sensor study promoted in 0/5 ideal, 2/5 noise-only,
  and 5/5 noise+bias+drift cases. Every promoted nominal model improved the
  measured trust target while degrading clean-oracle model prediction. This is
  why beta is interpreted as a control-effective measured-channel model, not
  recovered anatomy or physical parameter truth.
- The trajectory study found promotion in 5/6 cases. Full rank was not enough
  for timely or useful adaptation; the practically ill-conditioned two-cycle
  trajectory promoted later, while one knee-dominant case hit the same force
  gate in both arms before any challenger formed.
- The final patient × trajectory × measurement replication contains 18 paired
  cases / 36 arms (16 new, two read-only bridges): 18/18 promotion, completion,
  tracking-RMSE improvement, and torque-prediction-RMSE improvement, with no
  recorded safety event. Two cases improved RMSE while worsening maximum
  tracking error. H1, H2, and H5 were supported; H3 and H4 were conditionally
  supported within the preregistered design.

These are controlled simulation findings, not patient-population guarantees.

## Realtime status

Saved-trace desktop replay measured 9.422 ms mean MPC time and 16.524 ms mean
full-cycle time for the batched implementation (about 60.5 Hz), with recorded
optimized samples below 20 ms. This supports the project's >30 Hz desktop
replay target. It is not a hard-realtime guarantee: target hardware, drivers,
I/O, scheduling jitter, and worst-case deadlines have not been validated.

## Repository structure

- [`stages/stage1/`](stages/stage1/) — frozen point-force/Spring2D mechanics,
  identification, and MPC evidence.
- [`stages/stage2_linkage/`](stages/stage2_linkage/) — frozen Human V2 rigid-
  cuff linkage baseline.
- [`stages/stage3_full3d/`](stages/stage3_full3d/) — full 3D robot-Human plant
  and the Stage-4 adaptive controller, tests, protocols, and evidence.
- [`stages/stage3_full3d/docs/research/CURRENT_STATE.md`](stages/stage3_full3d/docs/research/CURRENT_STATE.md)
  — authoritative technical entry point.
- [`stages/stage3_full3d/docs/research/STAGE4_EVIDENCE_MAP.md`](stages/stage3_full3d/docs/research/STAGE4_EVIDENCE_MAP.md)
  — canonical evidence inventory, hashes, findings, and limitations.

Each stage is an independent Python package. Do not combine their packages or
retroactively modify frozen Stage 1-3 scientific code.

## Reproducing canonical Stage-4 evidence

Run from `stages/stage3_full3d` in the recorded `mpc_learn` environment. Formal
experiments are user-run only and must write to a new directory; never
overwrite a canonical result directory.

```bash
PYTHONPATH=src:. conda run -n mpc_learn pytest -q

PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_single_challenger_closed_loop_ab.py \
  --output-dir results/stage4_single_challenger_closed_loop_ab_reproduction

PYTHONPATH=src conda run -n mpc_learn python \
  scripts/run_stage4_crossed_excitation_replication.py \
  --matrix-config configs/stage4_crossed_excitation_replication.json \
  --case-id <preregistered-case-id> \
  --output-dir results/stage4_crossed_excitation_replication_reproduction
```

The exact commands for the patient, sensor, trajectory, crossed-summary, and
realtime artifacts are listed in the corresponding Experiment Specs and the
evidence map. Repository validation does not rerun formal experiments.

## Limits and next phase

- The identified 11-base beta is control-effective and identifiable within the
  frozen model/measurement setup; it is not anatomical truth.
- The cylindrical cuff surface quantity is a minimum-norm mathematical proxy,
  not tissue pressure, comfort, or injury risk.
- The UR10e model is a simulation surrogate, not proof for the laboratory CR12.
- Desktop replay timing is not hardware hard-real-time evidence.
- No clinical safety, efficacy, certification, or production claim is made.

The next branch may prepare professor-facing comparisons of PD, PD+feedforward,
fixed-model MPC, and adaptive MPC, together with representative patient and
trajectory GIF/video visualizations. Hardware work must first validate the
actual CR12 command interface, timing, sensing, calibration, cuff/contact
mechanics, supervisory safety, and emergency-stop behavior. A separately
preregistered model-inadequacy study remains optional.
