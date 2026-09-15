# Stage-5 Interface Identification v1

Status: **offline/shadow-compatible architecture probe only; no parameter is
published to the observer, Goal-MPC, task monitor, or execution path**.

This report reuses the saved Interface Mismatch v1 traces. It is exploratory
engineering evidence, not a formal experiment, continuous robustness proof,
hardware calibration, or clinical safety validation. MuJoCo Human/interface
truth is used only after fitting to label the known plant scale and compute
parameter error.

## Infrastructure audit

| source component | classification | retained idea | why it is not copied directly |
|---|---|---|---|
| Stage-1 windowed LS/NLS | pattern only | bounded `least_squares`, warm start, parameter prior, residual diagnostics | its one-step observed-state regression would create EIV/self-consistency if a candidate interface inversion supplied both the regressor and the “truth” state |
| Stage-1 joint state/parameter MHE | pattern only; selected prototype structure | jointly estimate a finite window's initial nuisance state and static parameters, then propagate implemented dynamics | Spring2D states/equations, thresholds, and mass parameterization do not transfer |
| Stage-4 integral identifier | diagnostic pattern only | data-only SVD/rank/condition, correlation, bound pressure, and last-valid fallback | the Human inverse-dynamics integral regressor is linear in Human base parameters; the cuff measurement model is nonlinear and latent-state coupled |
| Stage-4 incumbent/challenger trust | lifecycle reused in an inactive shell | one challenger, future embargo, retained incumbent, rejection fallback, bounded/smoothed/versioned shadow publication | Human-ID loss units, thresholds, HAC schedule, and control promotion are not reused |

The resulting implementation is a small **single-shooting joint
initial-state/parameter MHE**, not a direct deformation regression and not a
second competing estimator.

## Truth-free service/API boundary

`InterfaceIdentificationMeasurement` contains only:

- sample and arrival timestamps;
- measured robot-cuff pose and twist in WORLD;
- measured cuff force/moment in WORLD at the existing cuff reference;
- current and previous executed robot wrench commands;
- the explicit predictor's causal translational/rotational base-drive history;
- fixed Human-model version.

`ShadowInterfaceIdentificationService` applies the existing nominal observer
only to create a numerical arrival prior. Its stored future residual target is
always the raw robot pose/twist and measured wrench. Neither the input type nor
the trust shell contains MuJoCo truth. The identifier owns a fixed Human model
at construction; the model/version cannot be silently replaced inside a
window.

The older mismatch traces predate raw robot pose/twist/wrench logging. Their
offline adapter composes the stored nominal Human/interface estimates once to
recover the deployable robot-side measurement; candidate parameters never
participate in that reconstruction. The pose composition closes to numerical
roundoff. The reconstructed wrench proxy differs from the separately stored
evaluation-only physical wrench by at most `0.0194` in its native force/moment
components across the six dynamic traces. The proxy, not the evaluation array,
is the fit/validation target. This is still not a substitute for an
independently retained raw sensor record. Future Stage-5 traces now log raw
robot-cuff pose/twist and measured wrench directly, without changing control
behavior.

## Estimator formulation

The candidate physical scales are

\[
\theta_I=[\alpha_t,\alpha_r,\alpha_d],\quad
K_t=\alpha_tK_{t,0},\quad K_r=\alpha_rK_{r,0},\quad
D_t=\alpha_dD_{t,0},\quad D_r=\alpha_dD_{r,0}.
\]

The decision vector contains `theta_I` and one 16-dimensional window-arrival
state

\[
z_0=[q,\dot q,x,\dot x,\vartheta,\dot\vartheta]_0.
\]

The explicit base-drive state is not regenerated from candidate parameters;
it enters from causal command/history and is advanced by known executed-wrench
increments. The fixed Human model and the existing Kelvin-Voigt predictor then
propagate the coupled Human/interface state and predict the subsequent
robot-cuff pose/twist and physical cuff wrench.

The bounded objective is

\[
\sum_{k\in\mathcal F}\|S_y^{-1}(\hat y_k-y_k)\|^2
+\lambda_z\|S_z^{-1}(z_0-z_{0,\mathrm{nom}})\|^2
+\lambda_\theta\|S_\theta^{-1}(\theta_I-\theta_{I,\mathrm{inc}})\|^2.
\]

The default saved-trace probe uses 0.20 s fit data, a 0.05 s embargo, and a
disjoint 0.10 s future validation window. Bounds are `[0.5, 1.5]` for each
scale. Three starts vary both parameter and initial latent state. The nominal
comparator is allowed to refit the same 16-dimensional arrival nuisance state;
the challenger therefore does not win merely by having an arrival-state
advantage.

For identifiability, regularization rows are removed. With `J_theta` and
`J_z` computed by finite differences from measurable prediction residuals, the
reported data Jacobian is

\[
J_{\mathrm{eff}}=(I-J_zJ_z^+)J_\theta.
\]

Rank, singular values, condition, and correlation therefore describe only the
parameter information that remains after local initial-state coupling is
projected out. They do not obtain rank from the prior.

## Offline held-out result

All values below use the same predeclared 0.20/0.05/0.10 s
fit/embargo/validation split. “Improvement” is the reduction in normalized
future robot-pose/twist/wrench RMSE relative to the nominal interface with its
own fitted arrival state.

| saved case | truth scale, evaluation only | fitted `[alpha_t, alpha_r, alpha_d]` | `||parameter error||2` | validation RMSE candidate / nominal | improvement | data rank / condition | max `|corr|` | shadow decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| nominal | `[1,1,1]` | `[0.862,1.004,1.494]` | `0.513` | `0.640 / 0.628` | `-1.91%` | `3 / 7.93` | `0.956` | reject |
| `Kt x0.7` | `[0.7,1,1]` | `[0.760,0.919,1.365]` | `0.379` | `0.409 / 0.419` | `+2.57%` | `3 / 7.07` | `0.951` | reject |
| `Kt x1.3` | `[1.3,1,1]` | `[0.671,0.851,1.330]` | `0.726` | `1.283 / 1.352` | `+5.15%` | `3 / 4.85` | `0.906` | qualify to shadow only |
| `Kr x0.7` | `[1,0.7,1]` | no dynamic window | n/a | n/a | n/a | n/a | n/a | t=0 settled-start reconstruction failure retained |
| `Kr x1.3` | `[1,1.3,1]` | `[1.067,1.088,1.480]` | `0.529` | `0.627 / 0.614` | `-2.11%` | `3 / 10.00` | `0.963` | reject |
| `D x0.7` | `[1,1,0.7]` | `[0.808,0.948,1.401]` | `0.729` | `0.513 / 0.537` | `+4.48%` | `3 / 7.51` | `0.953` | reject |
| `D x1.3` | `[1,1,1.3]` | `[0.848,1.004,1.359]` | `0.163` | `0.435 / 0.433` | `-0.43%` | `3 / 8.56` | `0.963` | reject |

Only 3/6 dynamic cases improve held-out prediction at all. Only the `Kt x1.3`
case clears the inactive 5% future-improvement placeholder, yet its fitted
`alpha_t=0.671` moves in the opposite direction from truth `1.3`. This is the
decisive failure: a prediction-effective candidate in one short window is not
a trustworthy physical K/D estimate for the uncertainty monitor.

No optimizer fit hit the configured parameter bound. All three multistarts
converged to essentially the same solution (largest parameter span below
`2e-4` and negligible validation-loss span). The wrong physical estimates are
therefore not explained by the tested local initial guesses; they point to
task/predictor/latent structural coupling.

The selected fits required 10--18 function evaluations and 8.9--12.8 s per
case in this diagnostic Python implementation. This is an offline prototype,
not a claim of shadow-online throughput; optimization/runtime work is not
justified until the physical identifiability issue is resolved.

### Phase, window, and latent-state information

- OUTBOUND carries the most information in the nominal trace: projected
  information energy `77.6`, versus `39.5` in HOLD and `38.2` in RETURN.
- HOLD is consistently weakest/most correlated. Its local condition number is
  `43.5` nominal and reaches `52.9`/`59.2` for `D x0.7/x1.3`, even though the
  numerical rank remains three.
- On the nominal trace, increasing the inspected window from 0.10 to 0.40 s
  raises the smallest singular value from `1.79` to `4.12`, but maximum
  correlation remains high (`0.826` then `0.856`). More samples improve local
  sensitivity magnitude without proving parameter separation.
- Perturbing the arrival latent state by one-half configured prior scale changes
  the nominal 0.20 s condition number from `5.83` to `4.81` or `3.96`. The data
  geometry is therefore materially arrival-state dependent even though the
  joint optimizer's three tested starts converge together.
- After projecting out the 16 arrival states, fitted-window parameter columns
  retain only roughly 33--86% of their unprojected norm, depending on parameter
  and case. Full numerical rank is not equivalent to reliable physical
  identifiability.

No proposed one- or two-parameter subset is supported across the saved cases:
`alpha_d` does not discriminate `D x0.7` from `D x1.3`, `alpha_t` reverses the
`Kt x1.3` direction, and rotational evidence lacks the `Kr x0.7` dynamic trace.
The implementation therefore does not silently freeze two parameters and call
the remaining one identified.

## Inactive trust/publication shell

The shell retains one shadow incumbent and at most one challenger. A candidate
is scored only after the 0.05 s embargo against future deployable-measurement
RMSE. It checks optimizer validity, data-only projected rank/condition, bound
pressure, at least 20 validation samples, and a provisional 5% relative
improvement. Qualification applies a bounded 0.1 smoothing step to a versioned
**shadow** incumbent; rejection preserves the last valid shadow model. The
controller nominal interface remains unchanged in every outcome.

These are new interface-prediction units and provisional architecture gates;
they are not the Stage-4 Human-ID HAC thresholds. The `Kt x1.3` counterexample
shows they are not yet sufficient for physical publication and must remain
inactive.

## Decision

**C — current task data/model pairing does not identify the proposed physical
interface scales well enough to proceed to shadow-online publication.**

The next justified step is a predeclared, bounded, non-task identification
probe designed to separate translational stiffness, rotational stiffness, and
common damping while the leg remains safely supported, using the newly logged
raw robot pose/twist and wrench. If such excitation is not allowed or remains
uninformative, the interface model must be reparameterized as a smaller
control-effective prediction model rather than presented as physical K/D.
Human ID and value learning remain blocked; no interface update enters control.

Follow-up note: the later
`INTERFACE_INFORMATION_VS_MODEL_FORM_V1.md` self-consistency/model-form audit
supersedes the proposed immediate excitation step. It found both weak
rotational information and a held-out plant/predictor structural bias at true
parameters. The current next step is therefore the minimal identification-side
relative-kinematics predictor correction described there, before any new
excitation is designed.

Compact machine-readable evidence is generated locally at
`results/interface_identification_v1_offline/audit.json` and is intentionally
not promoted as formal evidence.
