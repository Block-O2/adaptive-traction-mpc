# Ideal Endpoint-Force Baseline

## Scope and interpretation

This baseline replaces direct human joint-torque actuation with one ideal
bidirectional cuff force at the shank contact point:

\[
u=\begin{bmatrix}F_t\\F_n\end{bmatrix},\qquad
F_{\mathrm{world}}=\begin{bmatrix}t(q)&n(q)\end{bmatrix}u,\qquad
\tau_{\mathrm{contact}}=J_c(q)^\mathsf{T}F_{\mathrm{world}}.
\]

It is an ideal actuator upper bound, not a claim about the unresolved
laboratory robot interface. Endpoint-force runs contain no joint torque,
robot dynamics, SDK, online identification, patient active torque, hidden
state/torque clipping, or extra safety torque. The ideal cuff may pull or push
in both local directions. These results do not establish clinical safety or
direct hardware deployability.

The retained `computed_torque_pd.m` is called unchanged for a separate oracle
comparison. That oracle uses direct generalized joint torque and true plant
parameters, so its actuator authority is fundamentally different.

## Controller

With \(e=q-q_{\mathrm{ref}}\) and
\(\dot e=\dot q-\dot q_{\mathrm{ref}}\),

\[
\ddot q_{\mathrm{cmd}}
=\ddot q_{\mathrm{ref}}-K_p e-K_d\dot e,
\]

\[
\tau_{\mathrm{req}}
=M(q)\ddot q_{\mathrm{cmd}}+h(q,\dot q)+G(q)+B\dot q.
\]

Writing \(A(q)=J_c(q)^\mathsf{T}[t(q)\ n(q)]\), each sampled command solves the
standard convex regularized problem

\[
\min_u\;
\|W_\tau(Au-\tau_{\mathrm{req}})\|_2^2
+\lambda_u\|u\|_2^2
+\lambda_{\Delta u}\|u-u_{\mathrm{prev}}\|_2^2
\]

subject to

\[
u_{\min}\le u\le u_{\max},\qquad
|u-u_{\mathrm{prev}}|\le \dot u_{\max}\Delta t.
\]

The regularizers use positive signs; negative signs would reward large forces
and command jumps rather than regularize them. The two-input box QP is solved
without Optimization Toolbox by deterministic enumeration of the free,
four-edge, and four-corner active sets.

One fixed configuration is used for all trajectories and patient profiles:

| Setting | Value |
|---|---:|
| Sample/integration step | 0.002 s |
| \(K_p\) | diag(36, 49) s\(^{-2}\) |
| \(K_d\) | diag(12, 14) s\(^{-1}\) |
| \(W_\tau\) | diag(0.55, 1.00) |
| \(\lambda_u,\lambda_{\Delta u}\) | \(2\times10^{-4},\,2\times10^{-3}\) |
| \(F_t,F_n\) bounds | \([-300,300]\) N |
| component force-rate bounds | 2500 N/s |

The initial \(q,\dot q\) exactly match the initial reference. The previous
force is initialized to the same hard-bounded steady reference solution, so
the recorded first command rate is zero rather than an artificial zero-force
release.

## Trajectories and profiles

All references use an initial hold, quintic flexion, peak hold, quintic
return, and final hold over 8 s.

- `knee_dominant`: \(q=[20,25]^\circ\) to \([24,75]^\circ\); the hip has only
  4 degrees of reference following and lower generalized-torque weight.
- `coordinated_path`: \(q=[18,25]^\circ\) to \([42,75]^\circ\), with deviation
  measured perpendicular to this straight joint-space coordination path.
- `conflicting_boundary`: \(q=[20,25]^\circ\) to \([78,1]^\circ\), deliberately
  approaching the single-contact map singularity at \(q_2=0\).

The deterministic profiles are `nominal`, `short_light` (0.85 length and
0.65 mass scales), and `tall_heavy` (1.15 length and 1.35 mass scales). They
are synthetic engineering stress cases, not clinical patient populations.

## Observed endpoint-force results

All 9 endpoint-force cases completed the full numerical rollout without a
nonfinite plant, force, acceleration, jerk, or torque-residual signal. A
completed rollout is not a tracking success.

| Task | Profile | RMSE \(q_1/q_2\) (deg) | Coupling/path metric (deg) | Residual RMS (N m) | Hard/slew saturation | max cond(\(A\)) | joint/velocity limit samples |
|---|---|---:|---:|---:|---:|---:|---:|
| knee | nominal | 22.19 / 60.74 | hip excursion 34.73 | 5.03 | 41.1% / 2.20% | 2597 | 3435 / 318 |
| knee | short/light | 22.41 / 61.21 | hip excursion 26.79 | 2.17 | 0% / 1.22% | 3365 | 3714 / 232 |
| knee | tall/heavy | 1.09 / 2.99 | hip excursion 6.08 | 0.48 | 0% / 0% | 15.4 | 0 / 0 |
| coordinated | nominal | 22.26 / 60.92 | path RMSE 6.36 | 5.07 | 41.6% / 2.20% | 1913 | 3458 / 318 |
| coordinated | short/light | 22.44 / 61.30 | path RMSE 6.33 | 2.17 | 0% / 1.20% | 2950 | 3720 / 233 |
| coordinated | tall/heavy | 1.13 / 3.12 | path RMSE 0.33 | 0.49 | 0% / 0% | 15.7 | 0 / 0 |
| conflicting | nominal | 10.84 / 30.14 | n/a | 3.44 | 0% / 2.20% | 2894 | 3464 / 301 |
| conflicting | short/light | 10.97 / 30.25 | n/a | 1.28 | 0% / 1.22% | 3365 | 3714 / 232 |
| conflicting | tall/heavy | 10.28 / 28.55 | n/a | 6.96 | 29.0% / 2.82% | 3794 | 3000 / 378 |

The normal tasks are therefore not robustly completed by this fixed
controller. Only the tall/heavy profile keeps both normal tasks inside the
recorded joint/velocity limits, with low tracking/path error. Nominal and
short/light develop small sustained generalized-torque residuals near the
initial posture, move toward \(q_2=0\), and then enter a poorly conditioned
single-contact geometry. The nominal case also reaches the \(F_t\) bound.
This parameter dependence is retained as an observed negative result; no
profile-specific tuning was applied.

Force and motion extrema further show the difference:

| Task/profile | max \(|F_t|/|F_n|/\|F\|\) (N) | max force-rate norm (N/s) | max \(|\ddot q_1|/|\ddot q_2|\) (deg/s²) | max \(|j_1|/|j_2|\) (deg/s³) |
|---|---:|---:|---:|---:|
| knee nominal | 300 / 73.0 / 302.5 | 2994 | 2402 / 8793 | 44360 / 164862 |
| knee short/light | 177.8 / 36.0 / 179.5 | 2724 | 2071 / 8019 | 74909 / 269521 |
| knee tall/heavy | 165.7 / 51.4 / 173.1 | 106 | 41.7 / 152.9 | 446 / 1910 |
| coordinated nominal | 300 / 73.8 / 302.3 | 3000 | 2438 / 8835 | 44478 / 165237 |
| coordinated short/light | 179.6 / 36.3 / 181.0 | 2722 | 2084 / 8059 | 74997 / 270061 |
| coordinated tall/heavy | 172.1 / 51.3 / 179.3 | 127 | 42.9 / 157.2 | 458 / 1963 |

The force-rate norm can exceed 2500 N/s because each component is bounded
separately at 2500 N/s; the two-dimensional norm remains below
\(2500\sqrt{2}\) N/s.

## Conflicting-boundary interpretation

The conflicting cases are capability probes, not code tests. All three remain
finite, but all have large tracking errors, thousands of joint-limit samples,
condition numbers above 2800, and nonzero slew-limit activity. The tall/heavy
case additionally spends 29.0% of samples on a hard force bound and reaches a
52.28 N m maximum generalized-torque residual. Failure is therefore expressed
through poor conditioning, residual, saturation, and constraint violations as
intended; it is not classified as a runtime failure.

## Oracle comparison

The unchanged oracle PD completes all 9 trajectory/profile combinations with
RMSE below \(2.6\times10^{-8}\) degrees and no joint/velocity-limit sample.
Its peak direct joint-torque norm ranges from 22.9 to 67.7 N m. This is only a
true-model, direct-generalized-torque lower-bound reference. It does not show
that the endpoint-force controller could attain the same result and must not
be read as a fair actuator-to-actuator comparison.

## Validation and artifacts

Commands:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_ideal_endpoint_force_tests"
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_ideal_endpoint_force_baseline"
```

MATLAB: `25.2.0.3042426 (R2025b) Update 1`.

The test command passes 24/24 tests: 15 retained plant regressions and 9 new
tests for force-frame mapping, the deterministic box solver, hard/slew bounds,
trajectory smoothness, coordination-path construction, singular-boundary
exposure, force-only dynamics, and oracle/endpoint authority separation.

Ignored evidence is under
`linkage/results/local/ideal_endpoint_force_baseline/`, including all 18 MAT
workspaces, per-run and aggregate CSV metrics, configuration/command/version
records, logs, and exactly one 65-frame synchronized GIF:
`representative_coordinated_path_nominal.gif`.

The only execution warning is MATLAB's inability to access the user's default
`~/Documents/MATLAB` directory; repository execution and output capture are
unaffected.

## Conclusion and next task

There is no dynamics-model, solver, finite-value, or headless-execution
blocker. The fixed controller itself is not a satisfactory across-profile
baseline: the force regularization/residual and single-contact conditioning
interact strongly with patient inertia, and normal-task success is not
profile-independent.

The recommended next task is a controller-design review, not NMPC or
profile-by-profile tuning: nondimensionalize the force/residual
regularization, define an explicit equilibrium-preserving force
parameterization, and add a conditioning-aware reference-manager feasibility
gate. Any parameter change or new experiment should be approved in a new
experiment specification before execution.
