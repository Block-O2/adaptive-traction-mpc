# Stage 1: single-link Spring2D adaptive traction MPC

## Research question and architecture

Stage 1 asked whether a compliant single-link traction task could be completed
by MPC while online state and Human-model parameter estimates supplied an
adaptive controller model. It separates control feasibility from state
estimation, parameter identification, and closed-loop robustness; all evidence
is simulation-only.

The retained stack contains the Spring2D dynamics/environment, fixed and
adaptive MPC, CEM and nonlinear MPC solvers, constraint and runtime-safety
machinery, UKF/noisy-observation estimation, Windowed LS/NLS and robust
identification variants, and the long-horizon planner plus short-horizon
tracker used by the final evaluations. The final researched online path is a
bias-aware UKF feeding filtered Windowed NLS/affine identification of
`[m, k, b_r]`; the oracle/fixed/state-error/parameter-error/full-adaptive modes
remain available for decomposition.

The final evidence supports control feasibility with accurate state and
parameters. In the retained Stage 9J primary matrix, full adaptive crossed in
24/24 runs and matched fixed nominal crossed in 0/24, but adaptive control had
larger true-alpha tails. Later audits found estimated-state errors-in-variables
and affine finite-difference formulation bias; exact discrete replay closed and
retained local parameter information, but no fitted exact-discrete estimator
or recovery claim was established.

## Authoritative evidence

`results/final/` is the tracked, curated evidence snapshot recovered from the
pre-Linkage closeout. It includes the Stage 9 planner/tracker and gap/identifier
evaluations, Stage 10 estimator audits, Stage 11C--11G closeout evidence, and
the earlier compact reports. The larger CSV files retained there are
authoritative audit inputs/outputs, including the Stage 9J replay consumed by
later identification work; ignored local result trees, caches, duplicate GIFs,
and prototype binaries were not recovered.

The detailed scientific closeout is
[`docs/research/SINGLE_LINK_CLOSEOUT.md`](docs/research/SINGLE_LINK_CLOSEOUT.md),
and [`docs/research/CURRENT_STATE.md`](docs/research/CURRENT_STATE.md) records
the frozen workflow state. Historical command files may show their original
`results/<experiment>` paths; the recovered evidence is namespaced under
`results/final/` and must not be overwritten by smoke runs.

## Setup and tests

Run from this directory:

```bash
cd stages/stage1
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
conda run -n mpc_learn pytest -q
```

Representative interfaces, without changing the recorded configurations:

```bash
conda run -n mpc_learn python scripts/run_spring2d_fixed_mpc.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9h_planner_tracker.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9k_identifier_ablation.py --help
```

Formal experiment execution remains governed by the approved specs in
`docs/research/experiment_specs/`; this structural recovery does not rerun or
promote scientific experiments.

## Transition to Stage 2

The professor closed the single-link phase after the audits isolated the
identifier limitation and showed that exact-discrete recovery remained future
work. The project then moved to the mechanically distinct Human V2 linkage and
robot-cuff transmission question. Stage 2 therefore lives in a separate
snapshot rather than importing or rewriting Stage 1.
