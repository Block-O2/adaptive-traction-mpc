# adaptive-traction-mpc

## Project overview

This repository is the research archive for adaptive model-predictive control
of a compliant single-link Spring2D traction task. It contains the dynamics,
controllers, state estimators, online identifiers, experiment runners, tests,
and curated empirical evidence used to compare fixed, oracle, and adaptive
control.

The evidence is simulation-only. No formal safety, stability, robustness, or
identifiability guarantee is claimed.

## Current status: single-link phase closed

The single-link Spring2D phase is **closed after professor review**. The final
diagnosis is:

- known-state/known-parameter MPC and a long-horizon planner plus
  short-horizon tracker can complete the tested task;
- the current estimated-state Windowed NLS path is not reliable enough to
  support strong adaptive-control claims;
- affine finite-difference identification introduces structured point bias on
  the retained replay;
- the exact discrete transition closes that replay and retains local
  true-state parameter information;
- exact-discrete parameter recovery remains untested.

Stage 11H is cancelled. See the
[scientific closeout](docs/research/SINGLE_LINK_CLOSEOUT.md) and
[final research state](docs/research/CURRENT_STATE.md).

## System definition

```text
x = [theta, omega, r, r_dot]
u = [F_tan, F_rad]
delta_r = r - L0
alpha_k = (omega[k+1] - omega[k]) / dt
```

The task crosses only when the true simulated angle satisfies
`theta >= theta_target`; a near-target tolerance is not substituted for this
criterion.

The adaptive physical parameters are `[m, k, b_r]`, with later identification
audits expressed in
`[lambda, kappa, beta] = [1/m, k/m, b_r/m]`. The compact fixed-MPC
configuration tests force, radial-deformation, angular-velocity, and
angular-acceleration limits. These constraints are empirical controller
requirements, not a formal safety certificate.

## Control and estimation architecture

The final researched architecture combines:

- a one-shot long-horizon crossing planner;
- a short-horizon multiple-shooting NMPC reference tracker;
- a bias-aware UKF state estimator;
- a filtered Windowed NLS / affine parameter identifier.

Parameters remain frozen inside each planner or tracker solve and may be
updated only between control steps. The repository also retains fixed/oracle
ablations, MHE variants, information diagnostics, and exact-discrete replay
audits needed to reproduce positive, negative, and mixed findings.

## Repository structure

```text
assets/          MuJoCo and robot assets retained from supporting work
configs/         Spring2D, MPC, estimator, and experiment configurations
docs/reports/    Historical consolidation and audit reports
docs/research/   Workflow, experiment specs, live/final state, and closeout
legacy/          Preserved early prototypes and historical material
results/         Curated reports, summaries, replay, and artifact policy
scripts/         Demo, experiment, and diagnostic entry points
src/             Dynamics, environments, estimation, identification, and MPC
tests/           Dynamics, environment, controller, estimator, and audit tests
```

## Environment setup

Python 3.10 or newer is required. The retained runs used a conda environment
named `mpc_learn`.

```bash
conda create -n mpc_learn python=3.10
conda activate mpc_learn
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
```

CasADi is required by the constrained NMPC research runners. MuJoCo is an
installed project dependency but is not required by the canonical Spring2D
demo below.

## Canonical minimal demo

Run the existing fixed-model MPC baseline:

```bash
conda run -n mpc_learn python scripts/run_spring2d_fixed_mpc.py --config configs/spring2d_fixed_mpc.yaml
```

The command writes a CSV, GIF, and summary plot to ignored generated-output
paths. It is a compact mechanical demonstration of the Spring2D environment and
MPC interface; it is not a reproduction of the reviewed planner/tracker study.
During closeout validation it exited normally at `max_time` with final angle
89.97 degrees and maximum true alpha 42.175 rad/s². It therefore must not be
treated as a successful crossing or constraint-validation result.

## Tests

```bash
conda run -n mpc_learn python -m pytest -q
```

An import/bytecode check is also available:

```bash
conda run -n mpc_learn python -m compileall -q src scripts tests
```

## Key reviewed findings

- Oracle scaled NMPC works in the tested nominal and mismatch conditions.
- The long-horizon planner plus short-horizon tracker restores the
  initial-angle-offset crossing under oracle state and parameters.
- In the Stage 9J decomposition, parameter error is the largest measured
  contributor to the adaptive-oracle true-alpha gap; the interaction residual
  is diagnostic rather than causal proof.
- Robust Windowed NLS losses and the tested fixed-weight online MHE routes did
  not pass their declared gates.
- Passive information level, information gating, and a stable passive
  parameter subspace did not provide a reliable replacement identifier.
- Block-aware calibration did not repair lambda coverage.
- Across 24 runs and 710 windows, the exact discrete transition closes the
  replay exactly and the exact-discrete local Jacobian has rank-3 fraction 1.0.
  Its median exact/affine conditional-lambda-information ratio is 689.197, but
  that number is not an estimator-accuracy multiplier.

Negative and mixed results are part of the retained scientific record.

## Key limitations

- Single-link, simulation-only validation.
- Passive trajectories and one dominant saved replay.
- Estimated-state EIV and biased/overconfident parameter estimates.
- True-state exact-discrete diagnostics do not establish estimator recovery
  under noise.
- No exact-discrete parameter fit, online test, or closed-loop adaptive test.
- No formal safety/stability proof, hardware validation, or linkage model.
- Some historical Stage 9 generating revisions were not recorded.

## Curated result locations

| Topic | Primary record |
|---|---|
| Planner/tracker feasibility | [Stage 9H report](results/stage9h_planner_tracker/stage9h_report.md) |
| Adaptive-oracle gap decomposition | [Stage 9J report](results/stage9j_gap_decomposition/stage9j_report.md) |
| Identifier diagnosis | [Stage 9K report](results/stage9k_identifier_ablation/stage9k_report.md) |
| Closed MHE route | [Stage 10F report](results/stage10f_mhe_divergence_audit/stage10f_report.md) |
| Paired state source through exact-discrete information | [Stage 11C–11G index](results/README.md#single-link-closeout-evidence) |
| Final synthesis | [Single-link closeout](docs/research/SINGLE_LINK_CLOSEOUT.md) |

The complete artifact rules and retained-file map are in
[results/README.md](results/README.md) and
[results/reproducibility_manifest.md](results/reproducibility_manifest.md).

## Reproducibility policy

Each curated experiment retains a report, aggregate summary, and enough
command/config/manifest provenance to interpret or reproduce it. Irreplaceable
replay data may be retained when downstream comparisons depend on it. Raw
trajectories, window-level tables, solver output, videos, repeated figures,
caches, and smoke outputs remain local unless the artifact policy explicitly
designates them as evidence.

Formal experiment commands can be expensive and may overwrite files at their
selected output root. Reproduction or mechanical checks should use a separate
ignored `results/local/` output unless the approved experiment contract says
otherwise.

## Historical experiment policy

Old Stage-numbered scripts are not the recommended onboarding path, but they
remain intentionally: many are the only implementations behind reviewed
negative results, ablations, or diagnosis. Do not delete, rerun, or reinterpret
them solely because a branch failed. Use
[the research workflow](docs/research/WORKFLOW.md) and the matching experiment
spec before touching historical scientific code or evidence.

## Linkage phase

The linkage phase is maintained under [`linkage/`](linkage/) in this
repository. The Spring2D portion remains a frozen research archive. Intake
begins from a professor-supplied MATLAB reference whose original source remains
local and is not committed while publishing permission is unresolved.
