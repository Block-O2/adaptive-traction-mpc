# adaptive-traction-mpc

Adaptive traction MPC experiments with online task-relevant parameter adaptation.

The current repository scope is the Stage 1 Spring2D 2D simulation only. MuJoCo assets and legacy prototypes are kept for reference, but the current closed-loop adaptive MPC results are based on the Spring2D environment.

## Goal

The project studies robotic traction control for elastic, spring-like, or limb-like objects. The controller applies a local contact force

```text
u = [F_tan, F_rad]
```

where `F_tan` is the tangential traction force and `F_rad` is the radial/contact force. The immediate goal is to compare fixed MPC, online identification, and adaptive MPC under clean, noisy, and biased observations.

## Current Pipeline

- Spring2D moving-base elastic rod dynamics
- Observation wrapper for clean, noisy, and biased observations
- Windowed nonlinear least-squares identifier for task-relevant parameters `[m, k, b_r]`
- Fixed-model MPC baseline
- Adaptive MPC with online parameter updates

The current MPC uses shared cost and shared base constraints across fixed and adaptive variants. There is no explicit gravity compensation outside the dynamics.

## Stage 1 Report

Current report:

- [Stage 1 Spring2D Adaptive MPC Report](docs/reports/stage1_spring2d_adaptive_mpc_report.md)

Curated Stage 1 outputs are organized under:

```text
results/stage1_spring2d/
```

## Setup

Install dependencies in a virtual environment or conda environment:

```bash
pip install -r requirements.txt
pip install -e .
```

## How To Run

Fixed true-parameter MPC:

```bash
python scripts/run_spring2d_fixed_mpc.py --config configs/spring2d_fixed_mpc.yaml
```

Fixed mismatched MPC with identifier logging:

```bash
python scripts/run_spring2d_identifier_conditions.py --config configs/spring2d_identifier_conditions.yaml
```

Adaptive MPC conditions:

```bash
python scripts/run_spring2d_adaptive_mpc_conditions.py --config configs/spring2d_adaptive_mpc_conditions.yaml
```

## Current Findings

- Fixed true-parameter MPC nearly reaches the target under the strict threshold.
- Mismatched fixed MPC underperforms.
- Adaptive MPC improves after online parameter updates and after preserving warm-start state across parameter updates.
- Noise and bias expose instability.
- Random shooting struggles with strict `omega` and `alpha` constraints.

Bad results are kept as experimental evidence rather than hidden or tuned away.

## Limitations

- No CEM solver yet.
- No robust identifier yet.
- No runtime safety filter yet.
- No MuJoCo closed-loop adaptive MPC yet.
- No real robot validation yet.

## Next Steps

- Add a `theta_tolerance_deg` success criterion.
- Add a CEM-MPC solver abstraction.
- Run identifier ablation experiments.
- Add safe adaptive MPC with uncertainty tightening and runtime safety filtering.

## Repository Layout

- `src/traction_mpc/`: Spring2D dynamics, environments, estimation, identification, MPC, evaluation, and visualization code.
- `configs/`: reproducible experiment configs.
- `scripts/`: runnable experiment scripts.
- `docs/reports/`: curated reports.
- `results/stage1_spring2d/`: curated Stage 1 outputs intended for tracking.
- `legacy/`: archived prototypes kept for reference.
- `assets/` and `third_party/`: robot and MuJoCo assets for later stages.
