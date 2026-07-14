# Stage 5.5 Consolidation Report

## Scope

This report consolidates the Stage 2-5 Spring2D adaptive traction MPC results. It is a summary-only document. No experiments were rerun, no results were changed, and no source code, configs, dynamics, costs, constraints, solvers, estimators, or identifiers were modified for this consolidation.

Source reports:
- `results/archive/legacy_stages/stage2_cem/stage2_cem_solver_comparison_report.md`
- `results/archive/legacy_stages/stage2_cem_feasfirst/stage2_cem_feasfirst_report.md`
- `results/archive/legacy_stages/stage3_filtering/stage3_filtering_report.md`
- `results/archive/legacy_stages/stage4_ukf/stage4_ukf_estimator_report.md`
- `results/archive/legacy_stages/stage5_coupling/stage5_estimator_identifier_coupling_report.md`

## Current Pipeline

The current experimental pipeline is a simulated Spring2D adaptive MPC system:

- Dynamics: verified Spring2D dynamics with state `x = [theta, omega, r, r_dot]`.
- Action: local force action `u = [F_tan, F_rad]`.
- MPC solver: CEM-MPC is the current main solver. Random shooting and feasibility-first CEM remain diagnostic alternatives.
- Estimator: UKF or bias-aware UKF produces the filtered state estimate `x_hat`.
- Identifier: Windowed NLS estimates adaptive model parameters `[m, k, b_r]`.
- Adaptive update: MPC prediction parameters are updated from the identifier output.
- Cost and constraints: the base MPC cost and base constraints remain shared across comparisons.

Important limitations:
- The identifier is not a true physical parameter identification guarantee.
- Bias-aware UKF estimates effective observation bias, not guaranteed true sensor bias.
- The system is not safe adaptive MPC yet.
- No real-robot validation has been performed.

## Findings By Stage

### Stage 2: CEM Solver Comparison

Random shooting was weak under the strict omega/alpha constraints. It could reach the target in some noisy conditions, but feasibility and violation severity remained poor.

CEM improved target-reaching relative to random shooting, especially in the clean case where random shooting ended at `max_time` while CEM reached the target. However, CEM did not solve feasibility. In the primary Stage 2 CEM run, feasible MPC decisions remained low, including `0/68` in clean, `0/45` in noise, and `10/108` in noise_bias.

Feasibility-first CEM improved feasible ratio in some cases, such as clean and noise_bias. It also made control more conservative and did not solve noisy-condition feasibility. In clean, feasibility-first CEM improved feasible ratio but failed to reach the target. In noise, feasible decisions remained `0/46`. In noise_bias, feasible decisions improved to `18/116`, but omega/alpha violations still remained.

Conclusion: CEM is a better main solver than random shooting for target reaching, but solver-side candidate ranking alone is insufficient for runtime safety.

### Stage 3: Simple Observation Filtering

Low-pass and alpha-beta filters changed closed-loop control behavior, but they did not reliably improve state-estimation accuracy.

In several cases, simple smoothing reduced some violation severity metrics or increased feasible counts, but it also introduced lag and sometimes made target reaching worse. For example, alpha-beta under CEM clean ended at `max_time`, and feasibility-first low-pass / alpha-beta under noise_bias also failed to reach the target.

Oracle state references showed that better state information can help, but simple low-pass and alpha-beta filtering are not enough for robust noisy/bias operation.

Conclusion: simple smoothing should not be the main estimator.

### Stage 4: UKF And Bias-Aware UKF

UKF improved noisy-state estimation and reduced omega/alpha severity in several cases. Under CEM + UKF:

- noise reached the target with improved feasible ratio `76/161`.
- noise_bias reduced omega/alpha severity but failed to reach the target, ending near `87.20 deg`.

Bias-aware UKF improved target reaching under biased observations. Under CEM + UKF-bias:

- clean reached target.
- noise reached target.
- noise_bias reached target near `90.01 deg`.

However, UKF-bias did not solve feasible-decision ratio. In the CEM + UKF-bias Stage 4 primary runs, feasible decisions were `0/69`, `0/60`, and `0/73` for clean/noise/noise_bias.

Conclusion: UKF-bias is the best current main estimator for target reaching under biased observations, but feasibility remains unsolved.

### Stage 5: Estimator-Identifier Coupling Ablation

Stage 5 separated:

- state estimate used by MPC,
- input used by the Windowed NLS identifier,
- whether identifier updates are applied,
- whether UKF prediction uses adaptive or frozen model parameters.

Main observations:

- The identifier should use filtered state rather than raw noisy/bias observation.
- Raw identifier input can produce large parameter jumps and worse alpha severity.
- Freezing the identifier hurts standard UKF severely. With standard UKF and frozen identifier, all clean/noise/noise_bias cases ended at `max_time` around `9-11 deg`.
- UKF-bias can complete clean/noise/noise_bias even with frozen identifier, but feasible ratio remains poor.
- Oracle identifier input improves parameter-estimation behavior but does not automatically solve closed-loop feasibility or target reaching for standard UKF under noise_bias.
- Bias-aware UKF target gains appear partly tied to changed controller behavior and effective bias handling, not proof of true sensor-bias identification.

Conclusion: the best current coupling is filtered estimator state into both MPC and identifier, with adaptive updates enabled. The remaining bottleneck is not only estimation or identification; it is runtime constraint enforcement.

## Current Recommended Mainline

Use this as the default research branch for the next step:

- Solver: CEM
- Estimator: UKF-bias
- Identifier: Windowed NLS
- Identifier input: filtered state
- Adaptive update: enabled
- Action: `[F_tan, F_rad]`

Reference branch:

- CEM + UKF + filtered identifier
- This is useful as a more feasibility-oriented diagnostic branch because standard UKF improved feasible ratio and omega/alpha severity in some noisy cases, even though it failed target reaching under noise_bias.

Not recommended as default:

- Raw identifier input
- Frozen identifier with standard UKF
- Low-pass / alpha-beta as the main estimator
- Feasibility-first CEM as the default solver

## Recommended Components Table

| Component | Current recommendation | Reason | Current limitation |
|---|---|---|---|
| Solver | CEM | Best current target-reaching baseline | Does not guarantee feasible decisions |
| Estimator | UKF-bias | Reaches target under clean/noise/noise_bias in current mainline | Feasible ratio remains poor |
| Identifier | Windowed NLS | Existing adaptive parameter-update baseline | Estimates effective model parameters, not guaranteed true physical parameters |
| Identifier input | Filtered state | Better than raw noisy/bias input in coupling ablations | Still sensitive to estimator/controller interaction |
| Adaptation mode | Enabled | Frozen standard UKF fails severely | Parameter jumps can still occur |
| Safety layer | Not implemented | Current system is not safe adaptive MPC | Needs runtime action projection/filter |
| Action | `[F_tan, F_rad]` | Local tangential/radial force action used throughout | Proposed actions can still cause omega/alpha violations |

## Remaining Bottleneck

Target reaching is mostly solved in the current recommended mainline. CEM + UKF-bias + filtered identifier + adaptive updates reaches the target in clean, noise, and noise_bias.

Feasibility and runtime safety are not solved. CEM can still propose actions that lead to omega and alpha violations after execution. Feasibility-first CEM helps in some cases but is not enough, and can make the controller too conservative.

The bottleneck is therefore a runtime safety layer: a mechanism that takes the MPC action and projects it into a one-step feasible action before execution.

## Next Step Proposal: Runtime Safety Filter

The next technical step should introduce an action projection layer:

1. MPC proposes `u_mpc`.
2. A safety filter modifies it to `u_safe`.
3. The environment executes `u_safe`, not `u_mpc`.

Mathematical form:

```text
u_safe = argmin_u ||u - u_mpc||^2
```

subject to one-step safety constraints:

```text
|F_tan| <= F_tan_max
|F_rad| <= F_rad_max
|delta_r_next| <= delta_r_max
|omega_next| <= omega_max
|alpha| <= alpha_max
```

where:

```text
x_next = Phi_dt(x_hat_t, u; theta_hat)
alpha = (omega_next - omega_t) / dt
```

This should be treated as a new safety-filter stage, not as completed safe adaptive MPC. It must preserve the existing Spring2D dynamics, base cost, base constraints, estimator, identifier, and physical/noise settings unless a future task explicitly requests otherwise.

## Final Position

The current mainline should be:

```text
CEM-MPC + UKF-bias + filtered Windowed NLS identifier + adaptive parameter updates
```

This is a strong target-reaching baseline under clean, noisy, and biased observations. It is not safe adaptive MPC. The next major technical gap is runtime action safety, especially for omega/alpha constraints.
