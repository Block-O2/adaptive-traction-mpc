# adaptive-traction-mpc

Adaptive traction MPC experiments for a controlled Spring2D traction task. The repository compares fixed MPC, online identification, adaptive MPC, and safety-oriented variants under reproducible simulation conditions.

The current system is a 2D single-link Spring2D traction model with state

```text
x = [theta, omega, r, r_dot]
```

and action

```text
u = [F_tan, F_rad]
```

## Current Mainline

- System: Spring2D 2D single-link traction.
- MPC solver: CEM.
- Estimator: UKF-bias.
- Identifier: filtered Windowed NLS.
- Main estimator/identifier flow: filtered state into both MPC and identifier.
- Current safety status: simulation evidence only; no formal safety guarantees.

## Result Summary Through Stage 7D

The project has closed several safety-method lines:

- Stage 6 runtime filter: negative baseline; old one-step filtering often destroys target reaching.
- Stage 6b sign diagnosis: sign convention and `F_tan` reversal issues were ruled out.
- Stage 7A alpha-soft CEM: better than runtime filtering, but not robust enough to carry forward.
- Stage 7B fixed-rate governor: failed or mixed; target reaching and safety were not reliable.
- Stage 7C gatekeeper-lite: preserved target reaching and reduced omega tail risk, but failed alpha tail risk.
- Stage 7C alpha-tail gatekeeper revision: revised scoring did not fix alpha p95/max severity.
- Stage 7D safety-aware command governor: failed; target success was `0/3` and safety tails worsened.

Next planned direction: Stage 8 smoother / acceleration-aware CEM action-sequence generation.

Curated results are documented in [results/README.md](results/README.md). Detailed reports are under `docs/reports/` and the relevant `results/stage*/` folders.

## Repository Structure

```text
configs/        Experiment and controller configs.
docs/reports/   Consolidated reports.
results/        Stage-aligned retained evidence and archived raw outputs.
scripts/        Reproducible experiment and analysis entrypoints.
src/            Spring2D dynamics, estimation, identification, MPC, and visualization code.
tests/          Regression tests for core Spring2D and MPC behavior.
```

## Setup

Install dependencies in a Python or conda environment:

```bash
pip install -r requirements.txt
pip install -e .
```

The prior experiment scripts were run in the local `mpc_learn` conda environment:

```bash
conda run -n mpc_learn python -m pytest tests
```

## Basic Commands

Run tests:

```bash
python -m pytest tests
```

Run selected experiment scripts:

```bash
python scripts/run_spring2d_solver_comparison.py
python scripts/run_spring2d_estimator_comparison.py
python scripts/run_spring2d_safety_filter_comparison.py
python scripts/run_spring2d_stage7a_final_validation.py
python scripts/run_spring2d_stage7b_progress_governor.py
python scripts/run_spring2d_stage7c_gatekeeper_lite.py
python scripts/run_spring2d_stage7d_safety_aware_governor.py
```

Use the matching config files under `configs/` when a script exposes `--config`.

## Reporting Discipline

Bad results are retained as experimental evidence. Do not hide failed runs by retuning methods after the fact. Current results are simulation evidence for comparing method behavior, not formal safety guarantees.
