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
- [Stage 10A dynamics and parameterization audit](results/stage10a_dynamics_audit/stage10a_dynamics_parameterization_audit.md)
- [Stage 10F MHE branch closeout](results/stage10f_mhe_divergence_audit/stage10f_report.md)
- [Stage 11A information-metric audit](results/stage11a_information_metric_validation/stage11a_report.md)
- [Stage 11B passive parameter-subspace audit](results/stage11b_parameter_subspace_audit/stage11b_report.md)

## Current validated findings

- Scaled multiple-shooting NMPC works under oracle or nominally accurate models in the tested Spring2D conditions.
- A long-horizon planner plus short-horizon tracker restores crossing in the initial-angle-offset case.
- Stage 9J identifies parameter error as the dominant measured contribution to the adaptive–oracle true-alpha gap; its interaction residual is diagnostic, not causal proof.
- Stage 9K identifies errors-in-variables bias in the current UKF-to-NLS cascade.
- Huber and Cauchy Windowed NLS variants did not pass the offline improvement gate, so the Stage 9K closed-loop comparison was not run.
- Stage 10A shows that inverse-mass ratios provide a valid affine parameterization, while `k` and `b_r` are not reliably separable on the retained trajectories.
- Stage 10B–10F show that the tested fixed-weight online MHE route does not pass the alpha, state, failure-rate, or solve-time gates; the branch is closed after alignment and fallback audits.
- Stage 11A finds that information level predicts parameter-update quality only moderately and does not justify hard or soft update gating.
- Stage 11B finds numerical rank without a practically stable passive parameter subspace. Stage 11C estimated-state/true-state pairing is implemented and smoke-tested, but its full audit remains pending.

Negative and mixed results are retained rather than tuned away.

## Known limitations

- Validation is simulation-only and single-link.
- The current UKF-to-NLS cascade uses estimated state as regressor input and shows biased/overconfident parameter estimates.
- Initial long-horizon planning occurs before the current identifier has meaningful episode data.
- Stronger noise and model mismatch can amplify true alpha.
- Current uncertainty diagnostics do not justify formal confidence bounds, robust tightening, or safety claims.
- Event-triggered replanning was not validated as beneficial and is not the primary architecture.

## Midterm closeout and next method

Stages 10A–10F completed the current joint-MHE investigation on the frozen Stage 9J replay. The single- and multiple-shooting variants failed their predeclared offline gates, and the rolling audit found no remaining hidden indexing, output-selection, or failed-solve overwrite bug after the confirmed corrections. The tested fixed-weight online MHE route is therefore closed rather than tuned further.

Stages 11A–11B then audited passive information and identifiable parameter subspaces. Their evidence does not support information-gated reduced NLS or a stable passive coordinate subspace. Stage 11C contains a paired estimated-state/true-state implementation for separating EIV from passive-information limits; only its smoke validation is complete, so no Stage 11C scientific conclusion is claimed here.

Future experiments should use a separately scoped method and result directory. Existing negative and mixed results remain part of the retained empirical record.

## Reproducibility and artifact policy

Each new stage must preserve its report, aggregate summary CSV, exact command/config or manifest, and only a small representative figure set. Irreplaceable replay/per-run data may be retained when a downstream comparison depends on it. Raw logs, solver artifacts, videos, caches, and repeated plots remain local. See [results/README.md](results/README.md) for the authoritative policy.
