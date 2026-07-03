# Stage 1 Spring2D Adaptive MPC Report

## 1. Overview

This stage studies a simplified 2D Spring2D traction environment before moving to MuJoCo or hardware. The object is represented as a moving-base polar spring/elastic rod in a vertical 2D plane.

The local force input is:

```text
u = [F_tan, F_rad]
```

where `F_tan` is tangential force and `F_rad` is radial/contact force. The experiment compares:

- fixed true-parameter MPC
- fixed mismatched MPC with identifier logging only
- adaptive MPC using online parameter estimates

Observation conditions:

- `clean`: no observation noise or bias
- `noise`: Gaussian observation noise
- `noise_bias`: Gaussian observation noise plus constant bias

## 2. Mathematical Formulation

State:

```text
x = [theta, omega, r, r_dot]
```

Action:

```text
u = [F_tan, F_rad]
```

All fixed and adaptive MPC runs use the same shared cost structure and base constraints. The current acceleration-related MPC quantity is:

```text
alpha = (omega_next - omega) / dt
```

The MPC task includes penalties on angular target tracking, radial deformation, control effort, angular acceleration, and forward angular progress. The shared base constraints include force limits, radial deformation limits, angular velocity limits, and angular acceleration limits.

There is no explicit gravity compensation outside the dynamics. Gravity appears only through the Spring2D dynamics model.

The online identifier estimates task-relevant effective parameters:

```text
[m, k, b_r]
```

These estimates are useful for prediction control but should not be interpreted as guaranteed recovery of true physical parameters under noisy or biased observations.

## 3. Experiment Summary

These metrics are from the current organized Stage 1 result set in `results/stage1_spring2d/`. `alpha_step` is computed from logged adjacent angular velocities.

| run | target_reached | final theta deg | T_reach s | max \|F_rad\| N | max \|delta_r\| mm | max \|omega\| rad/s | max \|alpha_step\| rad/s^2 | max \|F_tan\| N | done_reason |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Fixed true MPC | False | 89.97 | NA | 0.761 | 12.00 | 1.679 | 13.66 | 8.769 | max_time |
| Identifier-only fixed mismatch / clean | False | 10.50 | NA | 1.000 | 4.87 | 1.558 | 43.19 | 12.830 | max_time |
| Identifier-only fixed mismatch / noise | False | 10.32 | NA | 1.000 | 4.75 | 1.344 | 38.04 | 12.467 | max_time |
| Identifier-only fixed mismatch / noise_bias | False | 9.78 | NA | 1.000 | 5.67 | 1.731 | 38.03 | 12.313 | max_time |
| Adaptive MPC / clean | False | 89.92 | NA | 0.707 | 12.07 | 1.956 | 13.78 | 8.914 | max_time |
| Adaptive MPC / noise | False | 89.62 | NA | 0.880 | 12.11 | 1.940 | 16.61 | 9.291 | max_time |
| Adaptive MPC / noise_bias | False | 86.09 | NA | 1.000 | 13.85 | 2.300 | 19.90 | 9.193 | max_time |

## 4. Embedded Visuals

### Fixed True-Parameter MPC

![Fixed true-parameter MPC](../../results/stage1_spring2d/videos/fixed_true.gif)

### Fixed Mismatched MPC, Clean Observation

![Fixed mismatched clean](../../results/stage1_spring2d/videos/fixed_mismatch_clean.gif)

### Adaptive MPC, Clean Observation

![Adaptive clean](../../results/stage1_spring2d/videos/adaptive_clean.gif)

### Adaptive MPC, Noisy Observation

![Adaptive noise](../../results/stage1_spring2d/videos/adaptive_noise.gif)

### Adaptive MPC, Noisy and Biased Observation

![Adaptive noise bias](../../results/stage1_spring2d/videos/adaptive_noise_bias.gif)

## 5. Analysis

The true-parameter fixed MPC nearly reaches the target but fails the strict threshold. Its final angle is `89.97 deg`, just below the nominal `90 deg` target.

The fixed mismatched baseline underperforms strongly. In all three observation conditions, final angle remains around `10 deg`, despite the identifier recording parameter estimates.

Online identification plus adaptive MPC improves final angular progress substantially. After preserving warm-start state during adaptive parameter updates, adaptive clean rises from the earlier low-angle failure mode to `89.92 deg`. Adaptive noise also reaches near-target final angle, while noise_bias remains lower at `86.09 deg`.

Preserving warm-start fixed the previous adaptive clean low-angle failure. Earlier diagnostics showed that recreating the MPC object after each parameter update discarded `last_solution`, causing a post-update tangential-force drop. The current result preserves solver state and warm-start continuity.

Noise and bias degrade performance and expose instability. The final adaptive runs under noise and noise_bias no longer satisfy the strict target condition, and noise_bias has the worst final angle among adaptive conditions.

Random shooting struggles to find strictly feasible trajectories under the current omega and alpha constraints. The current constraints are represented in the MPC objective/penalty structure, but there is not yet a separate runtime safety layer that guarantees constraint satisfaction after action selection.

## 6. Limitations

- Random shooting is not a strict constrained optimizer.
- Noisy and biased observations affect both the MPC state input and the identifier.
- Runtime `omega` and `alpha_step` violations remain.
- The identifier estimates effective task-relevant parameters, not guaranteed true physical parameters.
- No robust or safe adaptive MPC has been implemented yet.
- The strict success threshold can mark near-target behavior as failure.

## 7. Next Steps

- Add a `theta_tolerance_deg` success criterion.
- Add a solver abstraction.
- Test CEM-MPC against the current random shooting baseline.
- Run an identifier ablation: Windowed NLS vs Robust NLS.
- Later add uncertainty tightening and a runtime safety filter.

## 8. Organized Result Paths

Stage 1 organized result folder:

```text
results/stage1_spring2d/
```

Main subfolders:

- `results/stage1_spring2d/figures/`
- `results/stage1_spring2d/videos/`
- `results/stage1_spring2d/tables/`
