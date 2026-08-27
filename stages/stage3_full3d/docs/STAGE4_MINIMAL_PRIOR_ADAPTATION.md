# Stage 4 minimal prior-based online adaptation design

## Scope and status

This is an engineering design plus a mechanical structural-observability
audit. It does not change frozen Stage 1, Stage 2, or Stage 3 code, and it does
not run or claim a formal scientific experiment. The cylindrical rigid-cuff
plant, Human-space Adaptive MPC, causal integral regression, contamination
exclusion, update smoothing, last-valid fallback, and MPC constraints remain
the architecture boundary. Tube MPC and UKF are out of scope.

The repository does not currently contain the top-level
`docs/research/CURRENT_STATE.md` named by `AGENTS.md`. The available Stage-1
state file closes the old single-link phase; the active Stage-4 baseline is
therefore grounded in `STAGE4_ONE_SHOT_ADAPTIVE_CLOSEOUT.md`,
`STAGE4_INTEGRAL_UKF_COMPARISON.md`, and the current Stage-4 source.

## 1. Estimator design proposal

### Minimal parameter vector

Use six prior-centered, control-relevant coordinates:

```text
theta_g = [effective_leg_length,
           cuff_alignment_x, cuff_alignment_z]

theta_d = [effective_mass_scale,
           effective_stiffness_scale,
           effective_damping_scale]
```

The two cuff-alignment components form the existing knee-to-cuff vector in the
measured cuff frame. They jointly represent effective cuff distance and
angular alignment; neither shank length nor anatomical cuff fraction is
claimed. The initial hip anchor, common joint axis, and planar basis remain
prior/frontend quantities. This removes the current geometry fit's two free
hip-offset coordinates, with the explicit tradeoff that initial anchor error
becomes model bias.

For dynamics, retain the exact 11-column integral equation but restrict its
candidate model to

```text
beta(theta_d) = B_prior theta_d,
integral(tau dt) = Phi_integral B_prior theta_d.
```

`B_prior` groups the existing base parameters as follows:

- effective mass: all five inertia/gravity combinations;
- effective stiffness: both joint stiffnesses and both stiffness-rest
  combinations, so prior rest angles remain fixed;
- effective damping: both viscous coefficients.

At `[1, 1, 1]`, the 11-vector is exactly the population prior. The MPC still
receives the same `BaseParameterHumanModel`/`PlanarCuffGeometry` abstractions;
there is no controller rewrite and no anatomical parameter recovery claim.

### Online sequence

1. Preprocess measured cuff pose, twist, and wrench using the existing causal
   frontend.
2. Update the three-coordinate geometry MAP fit from clean pose history.
3. Reconstruct joint state and generalized cuff input through the last-valid
   geometry.
4. Form the unchanged 0.50 s causal integral blocks and solve a bounded,
   prior-regularized three-scale regression.
5. Publish the candidate, applied last-valid values, and confidence evidence.
6. Apply an update only through the existing acceptance, smoothing, step-limit,
   physical-validity, and last-valid-fallback path.

No new numerical gate values are proposed here. A later approved Experiment
Spec must register bounds/prior covariance and any decision thresholds before
closed-loop evaluation.

## 2. Observability report

The audit samples the current
`stage4_population_prior_cold_start_high_flexion_23s` reference at 20 ms. The
dynamics audit uses the current 0.50 s integral window and five-measurement
block stride. Rank and condition number are computed after column
normalization. The audit is local to the nominal reference and contains no
sensor noise, state-estimation error, or closed-loop tracking error.

| Horizon | Trajectory state | Geometry rank / condition | Dynamics rank / condition |
|---:|---|---:|---:|
| 1.0 s | initial hold | 1/3 / infinite | 1/3 / infinite |
| 3.5 s | small hip motion complete | 3/3 / 45,602 | 3/3 / 3.24 |
| 6.5 s | small knee motion complete | 3/3 / 345 | 3/3 / 2.64 |
| 10.0 s | larger flexion complete | 3/3 / 60.2 | 3/3 / 2.75 |
| 13.0 s | high flexion reached | 3/3 / 22.0 | 3/3 / 2.90 |
| 14.5 s | high-flexion hold complete | 3/3 / 19.0 | 3/3 / 2.17 |
| 23.0 s | full return complete | 3/3 / 20.0 | 3/3 / 1.32 |

Observed result: the initial hold is not sufficient for either subspace.
Dynamics becomes full-rank and well-conditioned after the first small hip
motion. Geometry is technically full-rank at 3.5 s but remains extremely
weakly conditioned; independent knee/flexion motion is required before its
conditioning becomes moderate. Full rank alone must therefore not set
confidence high. At full history both requested subspaces are full rank, but
this is structural evidence only—not proof of noisy online recovery.

The geometry covariance shape shows the same weakness: its normalized
diagonal terms are very large early and remain more coupled than the dynamics
subspace. The preserved machine-readable report is
`results/stage4_minimal_prior_observability/audit.json`.

## 3. Confidence interface draft

`EstimatorConfidence` publishes:

```text
parameter_names
sample_count
parameter_dimension
rank, full_rank
condition_number
residual_rms
covariance
standard_deviation
accepted
reasons
interpretation = local_estimator_evidence_not_safety_probability
```

Rank/conditioning are calculated on a column-normalized data regressor;
residual and covariance use the original parameter coordinates. Rank
deficiency is not hidden by prior regularization. `accepted` records the
estimator gate outcome, not a safety guarantee. Consumers should log the raw
payload and use a separately registered adaptation policy rather than convert
it into an uncalibrated scalar confidence score.

Covariance is local and residual-scaled. It is not calibrated for the
correlation caused by overlapping integral windows, geometry/state error,
wrench bias, or model discrepancy. Those limitations must be resolved before
using covariance for uncertainty tightening or tube MPC.

## 4. Tests and reproducibility

Added mechanical tests cover:

- exact population-prior recovery at dynamic scales `[1,1,1]`;
- exact projection of the unchanged 11-column integral model into three
  control-relevant scales;
- presence of rank, condition, residual, covariance, and standard deviations;
- explicit rank-deficiency reporting;
- full-history rank of both minimal subspaces on the current 23 s trajectory.

Commands, from `stages/stage3_full3d/`:

```bash
PYTHONPATH=src conda run -n mpc_learn pytest -q tests/test_stage4_minimal_adaptation.py
PYTHONPATH=src conda run -n mpc_learn python scripts/audit_stage4_minimal_adaptation.py \
  --output results/stage4_minimal_prior_observability/audit.json
```

No formal experiment command exists because there is no approved Experiment
Spec for closed-loop minimal adaptation. The existing full Stage-4 rollout is
not rerun or overwritten.
