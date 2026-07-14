# adaptive-traction-mpc

## Project overview

This repository studies adaptive model-predictive control for a compliant traction task. It compares fixed-model control, online state/parameter estimation, adaptive control, and diagnostic robustness variants in reproducible Spring2D simulation.

The current evidence is empirical. No formal safety or stability guarantee is claimed.

## Problem definition

The main system is a Spring2D compliant single-link traction model. The task succeeds only when the true simulated angle satisfies:

```text
theta >= theta_target
```

Near-target tolerances are not substituted for this crossing criterion.

## State, action, and key constraints

```text
x = [theta, omega, r, r_dot]
u = [F_tan, F_rad]
delta_r = r - L0
alpha_k = (omega[k+1] - omega[k]) / dt
```

Experiments track force bounds, radial deformation, angular velocity, and angular acceleration. In the current scaled NMPC line, alpha is a high-priority soft path constraint with explicit slack. There is no separate gravity-compensation term.

## Current controller architecture

The validated Stage 9 architecture contains:

- a long-horizon crossing planner;
- a short-horizon multiple-shooting NMPC tracker;
- a UKF-bias state estimator;
- the current filtered Windowed NLS parameter baseline for `[m, k, b_r]`.

Planner/tracker comparisons distinguish true-state/true-parameter oracle modes, state-error-only and parameter-error-only ablations, fixed nominal control, and full adaptive control. Parameters are frozen within each solve and may update only between control steps.

## Repository structure

```text
assets/          MuJoCo and robot assets
configs/         Experiment and controller configurations
docs/reports/    Consolidation and historical reports
legacy/          Preserved early prototypes
results/         Curated evidence, archive, and reproducibility manifest
scripts/         Experiment and analysis entry points
src/             Dynamics, estimation, identification, MPC, and visualization
tests/           Core Spring2D and fixed-MPC regression tests
```

## Installation

Python 3.10 or newer is required. A local conda environment named `mpc_learn` was used for the retained Stage 9 runs.

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

The constrained Stage 9 scripts also require CasADi in the execution environment.

## Minimal execution example

Run the Spring2D open-loop example with the checked-in config:

```bash
conda run -n mpc_learn python scripts/run_spring2d_openloop.py --config configs/spring2d.yaml
```

Generated logs, figures, and videos use ignored local output directories.

## Core reproduction commands

Run regression tests and import/compile checks:

```bash
conda run -n mpc_learn python -m pytest tests
conda run -n mpc_learn python -m compileall -q src scripts tests
```

Reproduce the authoritative Stage 9 lines:

```bash
conda run -n mpc_learn python scripts/run_spring2d_stage9c_scaled_nmpc_validation.py --config configs/spring2d_safety_aware_cem.yaml --output-root results/stage9c_scaled_nmpc_validation
conda run -n mpc_learn python scripts/run_spring2d_stage9d_nmpc_stress_validation.py --config configs/spring2d_safety_aware_cem.yaml --output-root results/stage9d_nmpc_stress_validation
conda run -n mpc_learn python scripts/run_spring2d_stage9g_crossing_alpha_frontier.py --config configs/spring2d_safety_aware_cem.yaml --output-root results/stage9g_crossing_alpha_frontier
conda run -n mpc_learn python scripts/run_spring2d_stage9h_planner_tracker.py --config configs/spring2d_safety_aware_cem.yaml --output-root results/stage9h_planner_tracker
conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py --config configs/spring2d_safety_aware_cem.yaml --output-root results/stage9j_gap_decomposition
conda run -n mpc_learn python scripts/run_spring2d_stage9k_identifier_ablation.py --replay results/stage9j_gap_decomposition/stage9j_replay.csv --config configs/spring2d_safety_aware_cem.yaml --output-root results/stage9k_identifier_ablation
```

These experiment commands are expensive and overwrite files at the selected output root. Use a separate local output directory when validating changes.

## Results and reports index

- [Results index](results/README.md)
- [Reproducibility manifest](results/reproducibility_manifest.md)
- [Legacy Stage 1–8 archive](results/archive/legacy_stages/README.md)
- [Stage 9J report](results/stage9j_gap_decomposition/stage9j_report.md)
- [Stage 9K report](results/stage9k_identifier_ablation/stage9k_report.md)

## Current validated findings

- Scaled multiple-shooting NMPC works under oracle or nominally accurate models in the tested Spring2D conditions.
- A long-horizon planner plus short-horizon tracker restores crossing in the initial-angle-offset case.
- Stage 9J identifies parameter error as the dominant measured contribution to the adaptive–oracle true-alpha gap; its interaction residual is diagnostic, not causal proof.
- Stage 9K identifies errors-in-variables bias in the current UKF-to-NLS cascade.
- Huber and Cauchy Windowed NLS variants did not pass the offline improvement gate, so the Stage 9K closed-loop comparison was not run.

Negative and mixed results are retained rather than tuned away.

## Known limitations

- Validation is simulation-only and single-link.
- The current UKF-to-NLS cascade uses estimated state as regressor input and shows biased/overconfident parameter estimates.
- Initial long-horizon planning occurs before the current identifier has meaningful episode data.
- Stronger noise and model mismatch can amplify true alpha.
- Current uncertainty diagnostics do not justify formal confidence bounds, robust tightening, or safety claims.
- Event-triggered replanning was not validated as beneficial and is not the primary architecture.

## Stage 10 roadmap

Stage 10 will redesign and evaluate state–parameter estimation, beginning with offline comparisons on the frozen Stage 9J replay and then applying an explicit gate before any closed-loop test. Candidate work includes estimator-aware errors-in-variables handling or a joint state–parameter estimator. Stage 10 is not implemented in this consolidation.

Recommended result directory:

```text
results/stage10_joint_state_parameter_estimator/
```

## Reproducibility and artifact policy

Each new stage must preserve its report, aggregate summary CSV, exact command/config or manifest, and only a small representative figure set. Irreplaceable replay/per-run data may be retained when a downstream comparison depends on it. Raw logs, solver artifacts, videos, caches, and repeated plots remain local. See [results/README.md](results/README.md) for the authoritative policy.
