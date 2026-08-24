# Stage 10A: Dynamics, Sensitivity, and Parameterization Audit

## Scope

This audit reads the current Spring2D implementation and the unchanged Stage 9J replay. It does not modify dynamics, estimators, controllers, weights, horizons, constraints, or replay data; it does not run a closed-loop experiment and does not implement MHE, EM, TLS, or IV.

Command:

```text
conda run -n mpc_learn python scripts/run_spring2d_stage10a_dynamics_audit.py
```

Analyzed data: 8,597 transitions from 24 Stage 9J runs across eight conditions. Identifier conditioning uses 854 windows with the implemented 70-transition window, 10-step update interval, state weights `[1, 0.25, 8, 0.6]`, and parameter scaling `[1, 450, 20]`.

## 1. Exact implemented dynamics

The state and input are

\[
x=[\theta,\omega,r,\dot r]^T,\qquad
u=[F_{\tan},F_{\mathrm{rad}}]^T.
\]

The generalized acceleration order inside the implementation is

\[
z=[\ddot r,\dot\omega]^T=M^{-1}(Q-h).
\]

Let \(r_e=\max(r,10^{-6})\), \(a(\theta)=\partial x_b/\partial\theta\), and \(a'(\theta)=\partial^2x_b/\partial\theta^2\). The current configuration uses `linear_sin`, hence

\[
a=A\cos\theta,\qquad a'=-A\sin\theta,\qquad A=0.035.
\]

The implemented mass matrix is

\[
M=\begin{bmatrix}
m/3 & \tfrac12ma\cos\theta\\
\tfrac12ma\cos\theta & m(r_e^2/3-ar_e\sin\theta+a^2)
\end{bmatrix}.
\]

The generalized force is

\[
Q_r=\rho F_{\mathrm{rad}},
\]

\[
Q_\theta=\rho r_eF_{\tan}
+a(F_{\mathrm{rad}}\cos\theta-F_{\tan}\sin\theta).
\]

The non-input terms are

\[
\begin{aligned}
h_r={}&b_r\dot r+k(r_e-L_0)+\tfrac12mg\sin\theta
-\tfrac13mr_e\omega^2
+\tfrac12ma'\cos\theta\,\omega^2,\\
h_\theta={}&b_\theta\omega+\tfrac12mgr_e\cos\theta
+\tfrac23mr_e\dot r\omega
-ma\sin\theta\,\dot r\omega\\
&-\tfrac12mr_ea\cos\theta\,\omega^2
-\tfrac12mr_ea'\sin\theta\,\omega^2
+maa'\omega^2.
\end{aligned}
\]

Therefore the exact continuous state equations are

\[
\dot\theta=\omega,
\qquad
\dot\omega=\left[M^{-1}(Q-h)\right]_2,
\qquad
\dot r=\dot r,
\qquad
\ddot r=\left[M^{-1}(Q-h)\right]_1.
\]

The wording \(\dot r=\dot r\) distinguishes the derivative of the third state from the fourth state variable. In vector form the implementation returns `[omega, omega_dot, r_dot, r_ddot]`.

The discrete map \(\Phi_{\Delta t}\) is classical fixed-input RK4:

\[
\begin{aligned}
k_1&=f(x,u;p),\\
k_2&=f(x+\tfrac12\Delta t k_1,u;p),\\
k_3&=f(x+\tfrac12\Delta t k_2,u;p),\\
k_4&=f(x+\Delta t k_3,u;p),\\
x^+&=x+\tfrac{\Delta t}{6}(k_1+2k_2+2k_3+k_4),
\end{aligned}
\]

followed by \(r^+=\max(r^+,10^{-6})\).

The implemented discrete alpha is

\[
\alpha_k=\frac{\omega_{k+1}-\omega_k}{\Delta t}
=\frac{e_\omega^T\Phi_{\Delta t}(x_k,u_k;p)-\omega_k}{\Delta t}.
\]

## 2. Module consistency audit

| Module | Dynamics source | Step | Parameters used | Result |
|---|---|---:|---|---|
| Spring2D simulation | NumPy `step_dynamics` | 0.01 s | true physical parameters | Reference implementation |
| UKF / UKF-bias | same NumPy `step_dynamics` for every sigma point | 0.01 s | mode-selected true, nominal, or NLS parameters | Same equations, signs, gravity, and RK4 |
| Windowed NLS | same NumPy `step_dynamics` in its one-step residual | 0.01 s | substitutes `[m,k,b_r]`; other constants fixed | Same equations, signs, gravity, and RK4 |
| Long-horizon planner | CasADi transcription of the same equations | 0.03 s | solve-frozen `[m,k,b_r]` | Same continuous model; different integration step |
| Short-horizon tracker | same CasADi transcription | 0.03 s | solve-frozen `[m,k,b_r]` | Same continuous model; different integration step |

No sign, gravity, parameter-name, mass-matrix, force-direction, or RK4-form mismatch was found. The symbolic implementation explicitly expands the same 2-by-2 solve used by NumPy. At replay states, symbolic versus NumPy RK4 differed by at most `2.22e-16` at 0.01 s and `4.44e-16` at 0.03 s.

There is one explicit multirate difference: simulation, UKF, and NLS use `dt=0.01`, while planner/tracker use one RK4 step at `prediction_dt=0.03`. The controller holds each action for three simulation steps. One RK4 step of 0.03 s is not mathematically identical to three RK4 steps of 0.01 s, although both integrate the same continuous equation. This is reported as a discretization mismatch, not changed here.

The UKF-bias model additionally keeps its four bias states constant during prediction and adds configured process noise. That augmentation does not change the first four physical-state equations.

## 3. Parameter sensitivities

Factor the mass matrix and non-input terms as

\[
M=mG(\theta,r),\qquad
h=d+m c,
\]

with

\[
d=\begin{bmatrix}b_r\dot r+k(r_e-L_0)\\b_\theta\omega\end{bmatrix}.
\]

Then

\[
z=G^{-1}\left(\frac{Q-d}{m}-c\right).
\]

Holding the state, input, and other parameters fixed gives the continuous-time acceleration sensitivities

\[
\frac{\partial z}{\partial m}
=-G^{-1}\frac{Q-d}{m^2},
\]

\[
\frac{\partial z}{\partial k}
=-G^{-1}\frac{[r_e-L_0,\ 0]^T}{m},
\qquad
\frac{\partial z}{\partial b_r}
=-G^{-1}\frac{[\dot r,\ 0]^T}{m}.
\]

The corresponding instantaneous angular sensitivities are the second components. For the actual discrete metric, the exact implemented derivatives are

\[
\frac{\partial\alpha_k}{\partial p}
=\frac{e_\omega^T}{\Delta t}
\frac{\partial\Phi_{\Delta t}}{\partial p},
\qquad p\in\{m,k,b_r\},
\]

where the RK4 stage sensitivities include both direct parameter derivatives and state-mediated derivatives at stages 2–4. These exact derivatives were evaluated with CasADi autodiff on the planner/tracker transcription.

### Finite-difference validation

Autodiff was checked against centered finite differences using the NumPy simulation map on all 8,597 replay transitions.

| Parameter | Maximum absolute AD–FD error | Maximum scaled error |
|---|---:|---:|
| `m` | `1.35e-8` | `2.33e-9` |
| `k` | `3.61e-11` | `3.61e-11` |
| `b_r` | `8.08e-10` | `8.08e-10` |

The true-parameter one-step model reproduced replay alpha with RMSE `3.73e-15`, confirming action alignment and metric semantics.

### Sensitivity by condition

Raw derivatives have different units, so the comparison below uses dimensionless relative-parameter sensitivity \(|p\,\partial\alpha/\partial p|\).

| Condition | `m` p95 | `k` p95 | `b_r` p95 | p95 `cond(J_scaled)` |
|---|---:|---:|---:|---:|
| clean | 44.54 | 2.334 | 0.233 | 2,957 |
| initial theta offset | 42.96 | 2.484 | 0.278 | 6,326 |
| mass mismatch | 41.74 | 2.653 | 0.276 | 22,769 |
| noise | 44.45 | 2.376 | 0.261 | 218 |
| noise bias | 44.49 | 2.439 | 0.277 | 191 |
| low-k mismatch | 44.40 | 2.362 | 0.243 | 11,368 |
| high-k mismatch | 44.40 | 2.346 | 0.236 | 2,770 |
| stronger noise | 44.60 | 2.654 | 0.284 | 104 |
| all transitions | **44.33** | **2.398** | **0.260** | **8,426** |

Across all transitions, mass sensitivity is about 18.5 times the stiffness sensitivity and 170 times the radial-damping sensitivity at p95.

The state/input regions agree with the equations:

- `m` is observable when generalized non-gravity force imbalance \(\|Q-d\|\) is large, especially with tangential actuation. Its top sensitivity decile has mean `|F_tan|=7.13` and mean `||Q-d||=2.24`.
- `k` requires radial deformation. Its top sensitivity decile has mean `|r-L0|=0.00801`, compared with `0.000772` in the mass-sensitive top decile.
- `b_r` requires radial velocity. Its top sensitivity decile has mean `|r_dot|=0.0178`, versus `0.00600` in the mass-sensitive top decile.

Noise and stronger noise produce smaller numerical Jacobian condition numbers, but this is not evidence of better physical identifiability: noisy estimated states inject apparent regressor variation while simultaneously worsening errors-in-variables bias.

## 4. Identifier residual Jacobian and conditioning

For one transition, the implemented data residual is

\[
r_i(p)=W\left[x_{i+1}^{\mathrm{obs}}-\Phi_{0.01}(x_i^{\mathrm{obs}},u_i;p)\right],
\]

so

\[
\frac{\partial r_i}{\partial[m,k,b_r]}
=-W\frac{\partial\Phi_{0.01}}{\partial[m,k,b_r]}.
\]

The regularizer is

\[
r_{\mathrm{reg}}=\sqrt\lambda D^{-1}(p-p_{\mathrm{previous}}),
\qquad
J_{\mathrm{reg}}=\sqrt\lambda D^{-1},
\]

with \(D=\mathrm{diag}(1,450,20)\). Conditioning below uses the stacked data Jacobian after column scaling by \(D\); information-matrix values additionally include the implemented regularization.

Across 854 windows:

- numerical rank was 3 in 100% of windows;
- smallest singular value: median `0.0110`, fifth percentile `9.51e-5`;
- `cond(J_scaled)`: median `64.6`, p95 `8.43e3`, maximum `2.36e4`;
- regularized information condition number: median `489`, p95 `998`;
- absolute column-correlation p95: `m-k=0.99991`, `m-b_r=0.99447`, `k-b_r=0.99508`;
- median scaled column norms: `m=0.562`, `k=0.538`, `b_r=0.0152`.

Thus full numerical rank does not imply robust separation. `b_r` has very weak leverage, and `k` and `b_r` both enter the same radial generalized-force channel as `k*(r-L0) + b_r*r_dot`. They can only be separated when deformation and radial velocity vary independently. Current closed-loop trajectories frequently make those two regressors nearly collinear.

Conclusion: `k` and `b_r` are not reliably and separately identifiable from the current trajectories, even though a numerical rank test usually returns 3.

## 5. Parameterization audit

### Raw `[m,k,b_r]`

This form is physically direct but not parameter-affine because the mass matrix is inverted and the accelerations depend on `1/m`, `k/m`, and `b_r/m`. The discrete RK4 residual is also nonlinear through parameter-dependent intermediate states.

### Inverse-mass ratios `[1/m,k/m,b_r/m]`

Define

\[
\lambda=1/m,\qquad \kappa=k/m,\qquad \beta=b_r/m.
\]

The continuous acceleration equation is exactly affine:

\[
Gz+c=H(x,u)
\begin{bmatrix}\lambda\\\kappa\\\beta\end{bmatrix},
\]

where

\[
H=\begin{bmatrix}
Q_r & -(r_e-L_0) & -\dot r\\
Q_\theta-b_\theta\omega & 0 & 0
\end{bmatrix}.
\]

This reconstruction matched the implemented continuous acceleration to `1.42e-14` maximum absolute error. It follows directly from the code; it is not an invented effective parameter.

The affine regression remains poorly conditioned. After comparable column scaling, all windows are numerically rank 3, but its p95 condition number is `6.92e3` and the `k/m`–`b_r/m` column-correlation p95 is `0.99466`.

The discrete RK4 map is not exactly affine in these parameters because RK4 intermediate states depend on them. The affine form is therefore valid for continuous/acceleration regression, not for treating the existing one-step RK4 residual as a linear least-squares problem.

### `m`-only and `1/m`-only

With `k` and `b_r` fixed, the continuous acceleration is affine in `1/m` and nonlinear but one-to-one in `m`. Both reduced MHE parameterizations describe the same physical degree of freedom if reciprocal bounds and priors are mapped consistently. `1/m` is the cleaner reduced parameter because it enters the acceleration equation directly and affinely.

### Effective inertia

Eliminating the radial acceleration gives the exact angular Schur-complement inertia

\[
I_{\mathrm{eff}}(x)=m\left(G_{22}-\frac{G_{12}^2}{G_{11}}\right).
\]

The geometry factor varies over replay from `0.03286` to `0.04716` with median `0.03756`; it is state-dependent, not a new constant. Because the unknown scalar factor is still exactly `m`, a separate constant “effective inertia” parameter is not justified.

## 6. TLS/IV assessment

A valid parameter-affine errors-in-variables form exists for `[1/m,k/m,b_r/m]`. Both sides depend on estimated state, and acceleration must be differenced or treated as latent, so ordinary least squares is biased. This makes a structured or weighted TLS comparison mathematically relevant.

However:

- ordinary unweighted TLS assumptions are not satisfied by correlated UKF state errors and heteroscedastic finite-difference acceleration noise;
- the affine regressor is still severely ill-conditioned;
- closed-loop controls are correlated with estimated state;
- no valid external or delayed instrument has yet been demonstrated.

Therefore structured/weighted TLS is justified as an offline Stage 10B baseline. Generic TLS is not justified as a final estimator, and IV should not enter Stage 10B until a concrete instrument and its exogeneity argument are specified.

## 7. Required final answers

1. **What are the exact implemented dynamics?** The moving-base polar equations are `z=M^-1(Q-h)` with the exact matrix and force terms written in Section 1, integrated by fixed-input RK4 and radial clamping. Alpha is the adjacent-omega finite difference.

2. **Are simulation and all estimator/controller models consistent?** Their continuous dynamics, signs, gravity, parameter roles, and RK4 form are consistent. The explicit difference is multirate discretization: simulation/UKF/NLS use 0.01 s, planner/tracker use 0.03 s. Parameter sources differ intentionally by controller mode.

3. **Why does `m` dominate true-alpha error?** Tangential/generalized actuation enters angular acceleration through inverse mass, while `k` and `b_r` reach angular acceleration only through radial deformation/velocity and mass-matrix coupling. The replay keeps `|r-L0|` and `|r_dot|` small. Dimensionless mass sensitivity is 18.5 times `k` and 170 times `b_r` at p95.

4. **Are `k` and `b_r` separately identifiable?** Not reliably. They are numerically rank-separable in aggregate windows, but their columns are frequently almost collinear, `b_r` leverage is weak, and p95 conditioning is severe.

5. **Is `m`, `1/m`, or effective inertia the best reduced parameter?** `1/m` is the best reduced parameter. `m` is a useful matched comparator. A new constant effective-inertia parameter is not supported because the exact effective inertia is state-dependent geometry times `m`.

6. **Is TLS/IV mathematically justified?** A structured weighted TLS baseline is mathematically justified by the exact affine EIV form. Naive TLS is not sufficient, and IV is not yet justified because no valid instrument has been established.

7. **What exact estimator set should Stage 10B implement?** Initial Stage 10B should implement: (a) inverse-mass-only joint state/parameter MHE as the primary estimator; (b) an otherwise identical `m`-only MHE as a reciprocal-parameterization control; and (c) an offline structured/weighted TLS baseline on `[1/m,k/m,b_r/m]`. Do not include full `[m,k,b_r]` MHE or IV in the initial set. Full MHE should remain gated on new excitation/conditioning evidence; IV should remain gated on a defensible instrument.

## Outputs

- `results/stage10a_dynamics_audit/sensitivity_summary.csv`
- `results/stage10a_dynamics_audit/conditioning_summary.csv`
- `results/stage10a_dynamics_audit/figs/01_relative_alpha_sensitivity_by_condition.png`
- `results/stage10a_dynamics_audit/figs/02_identifier_jacobian_conditioning.png`
- `results/stage10a_dynamics_audit/figs/03_observability_regions.png`

No formal observability, safety, or stability guarantee is claimed.
