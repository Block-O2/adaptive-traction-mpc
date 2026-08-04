# Physical Human Two-Link Plant Baseline

> **Frozen V1 evidence.** The implementation, runners, and tests used for this
> report are archived at annotated tag `linkage-pre-v1-code-cleanup`. The
> metrics and conclusions below remain frozen. Checkout that tag to reproduce
> this baseline; ignored local result artifacts are retained separately.

## Coordinate convention

The implemented state is \(q=[q_1,q_2]^\mathsf{T}\). The hip is fixed at the
origin, \(X\) is horizontal, and \(Y\) is upward. The thigh absolute angle is
\(q_1\), measured counterclockwise from \(+X\). Positive \(q_2\) is knee
flexion, so the shank absolute angle is
\(\phi=q_1-q_2\).

The parameters are nominal engineering values, not clinically validated
anthropometric data. The `short_light` and `tall_heavy` profiles use fixed
length and mass scale factors \((0.85,0.65)\) and \((1.15,1.35)\);
center-of-mass locations and inertias are recomputed from the scaled values.

## Implemented equation

The plant is

\[
M(q)\ddot q+h(q,\dot q)+G(q)+B\dot q
  =\tau_{\mathrm{joint}}+\tau_{\mathrm{contact}},
\]

with \(B=0\) by default. Define

\[
b=I_2+m_2l_{c2}^2,\qquad
d=m_2L_1l_{c2},\qquad
a=I_1+m_1l_{c1}^2+b+m_2L_1^2.
\]

The separately implemented dynamics are

\[
M=
\begin{bmatrix}
a+2d\cos q_2 & -(b+d\cos q_2)\\
-(b+d\cos q_2) & b
\end{bmatrix},
\]

\[
h=
\begin{bmatrix}
d\sin q_2(-2\dot q_1\dot q_2+\dot q_2^2)\\
d\sin q_2\dot q_1^2
\end{bmatrix},
\quad
C=
\begin{bmatrix}
-d\sin q_2\dot q_2 & d\sin q_2(\dot q_2-\dot q_1)\\
d\sin q_2\dot q_1 & 0
\end{bmatrix},
\]

and

\[
G=
\begin{bmatrix}
g[(m_1l_{c1}+m_2L_1)\cos q_1+m_2l_{c2}\cos(q_1-q_2)]\\
-m_2gl_{c2}\cos(q_1-q_2)
\end{bmatrix}.
\]

For the single shank contact point,

\[
p_c=L_1
\begin{bmatrix}\cos q_1\\\sin q_1\end{bmatrix}
+s_c
\begin{bmatrix}\cos\phi\\\sin\phi\end{bmatrix},
\quad
J_c=
\begin{bmatrix}
-L_1\sin q_1-s_c\sin\phi & s_c\sin\phi\\
L_1\cos q_1+s_c\cos\phi & -s_c\cos\phi
\end{bmatrix}.
\]

With \(n=[-\sin\phi,\cos\phi]^\mathsf{T}\), \(v_c=J_c\dot q\), and an
externally supplied endpoint velocity \(v_r\), the damping-only force applied
to the human is

\[
F_c=-c_n n^\mathsf{T}(v_c-v_r)n,\qquad
\tau_{\mathrm{contact}}=J_c^\mathsf{T}F_c.
\]

No spring, normal-direction sign flip, joint clipping, or hidden safety logic
is present.

## Module and API summary

| Module | Purpose |
|---|---|
| `default_parameters`, `validate_parameters` | Construct and validate nominal and deterministic scaled engineering profiles |
| `kinematics`, `shank_contact_kinematics` | Link/COM geometry and shank contact position, normal, Jacobian, and velocity |
| `dynamics_terms`, `potential_energy`, `total_energy` | Return \(M,h,C,G\), potential energy, and total mechanical energy |
| `damping_contact_force` | Return \(F_c\), \(J_c^\mathsf{T}F_c\), and relative-power diagnostics |
| `continuous_dynamics`, `rk4_step` | Evaluate forward dynamics and take a deterministic fixed-step RK4 update |
| `reference_trajectory` | Return \(q_\mathrm{ref},\dot q_\mathrm{ref},\ddot q_\mathrm{ref}\) for three smooth references |
| `computed_torque_pd` | Oracle computed-torque PD used only to validate the plant |
| `simulate_episode` | Run and record one deterministic closed-loop episode |

All implementation modules are under
`linkage/matlab/src/human_two_link/`. Tests and shell-reproducible entry
points are under `linkage/matlab/tests/` and `linkage/matlab/runners/`.

## Test methods and tolerances

MATLAB R2025b Update 1 completed 15 tests: 15 passed, 0 failed, and 0
incomplete.

| Check | Method and acceptance condition |
|---|---|
| Mass matrix | Deterministic valid-state grid; \(\lVert M-M^\mathsf{T}\rVert_\infty\le10^{-12}\), minimum eigenvalue \(>0\) |
| Coriolis terms | Same grid; \(\lVert C\dot q-h\rVert_\infty\le10^{-12}\) |
| Manipulator identity | Independent central difference for \(\dot M\), step \(10^{-7}\); symmetric residual of \(\dot M-2C\le10^{-8}\) |
| Gravity | Central difference of potential energy, step \(10^{-6}\); infinity-norm error \(\le10^{-7}\) |
| Contact Jacobian and velocity | Independent central differences, step \(10^{-7}\); infinity-norm errors \(\le10^{-8}\) |
| Contact normal | Unit length to absolute tolerance \(10^{-14}\) |
| Damping contact | Relative power \((v_c-v_r)^\mathsf{T}F_c\le10^{-12}\); zero normal relative speed gives force \(\le10^{-12}\) |
| Contact disabled | \(F_c\), generalized contact torque, and relative power exactly zero |
| Finite values | All tested dynamics and energy values finite across all three profiles |
| RK4 | Deterministic equality plus decreasing-step unforced convergence |

For the RK4 convergence check over 2 s, the state error relative to a
0.0025 s reference fell from \(8.175503730\times10^{-2}\) at
\(\Delta t=0.04\) s to \(1.780446029\times10^{-3}\) at
\(\Delta t=0.02\) s. Maximum absolute energy error fell from
\(6.902383550\times10^{-2}\) J to \(2.085400919\times10^{-3}\) J.

These are deterministic software-consistency checks, not experimental or
clinical validation.

## Headless commands

The successful commands were:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -logfile /Users/hankli/Desktop/coding/adaptive-traction-mpc/linkage/results/local/human_two_link_baseline/test_console.log -batch "addpath(genpath('linkage/matlab')); run_human_two_link_tests"
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -logfile /Users/hankli/Desktop/coding/adaptive-traction-mpc/linkage/results/local/human_two_link_baseline/baseline_console.log -batch "addpath(genpath('linkage/matlab')); run_human_two_link_baseline"
```

Both runners set `DefaultFigureVisible` to `off`, require no interaction, and
write only to the ignored
`linkage/results/local/human_two_link_baseline/` directory.

## Aggregate baseline table

All cases use \(\Delta t=0.002\) s, an 8 s horizon, the same
\(K_p=\operatorname{diag}(180,140)\) and
\(K_d=\operatorname{diag}(28,22)\), and the matching true plant parameters.
Each row combines the contact-disabled and damping-contact runs for one
trajectory/profile pair. RMSE entries are \([q_1,q_2]\) in degrees.

| Trajectory | Profile | RMSE disabled | RMSE damping | Max force damping (N) | Max torque norm disabled / damping (N m) |
|---|---|---:|---:|---:|---:|
| Slow coordinated | Nominal | [0.2626, 0.2201] | [0.2955, 0.2341] | 3.126 | 45.379 / 43.740 |
| Slow coordinated | Short/light | [0.2303, 0.2100] | [0.2635, 0.2233] | 3.205 | 25.169 / 24.144 |
| Slow coordinated | Tall/heavy | [0.3053, 0.2327] | [0.3315, 0.2457] | 3.015 | 70.168 / 67.971 |
| Faster low amplitude | Nominal | [0.2593, 0.2189] | [0.2868, 0.2332] | 3.051 | 44.040 / 44.040 |
| Faster low amplitude | Short/light | [0.2288, 0.2094] | [0.2564, 0.2224] | 3.121 | 24.264 / 24.264 |
| Faster low amplitude | Tall/heavy | [0.2995, 0.2307] | [0.3217, 0.2449] | 2.945 | 68.562 / 68.562 |
| Phase shifted | Nominal | [0.2619, 0.2199] | [0.2938, 0.2340] | 3.125 | 43.695 / 43.695 |
| Phase shifted | Short/light | [0.2300, 0.2099] | [0.2621, 0.2232] | 3.200 | 24.095 / 24.095 |
| Phase shifted | Tall/heavy | [0.3040, 0.2322] | [0.3297, 0.2457] | 3.015 | 67.968 / 67.968 |

Across the nine cases in each contact mode, mean RMSE changed from
\([0.26465,0.22043]^\circ\) with contact disabled to
\([0.29345,0.23406]^\circ\) with damping enabled. Thus this moving-damper
abstraction slightly increased tracking error in every paired case. Mean
maximum torque norm changed from 45.927 N m to 45.387 N m.

All 18 simulations completed. There were zero joint-limit, velocity-limit,
contact-dissipativity, and NaN/Inf violations. The overall maxima were:
tracking error \([2.0372,2.0000]^\circ\), velocity
\([20.4906,31.9958]^\circ/\mathrm{s}\), acceleration
\([1184.43,6367.12]^\circ/\mathrm{s}^2\), generalized-torque norm
70.168 N m, and contact force 3.205 N.

## Failures and limitations

There were no failed or incomplete MATLAB tests and no failed baseline cases.
The first sandboxed MATLAB launch exited before MATLAB initialized and created
no log; rerunning the identical headless command with permission to launch the
Desktop-installed executable exited 0.

The high peak accelerations, especially 6367.12 deg/s² for the short/light
damping case, occur during the imposed initial tracking offset and are
reported without gain tuning or clipping. The configured acceleration bounds
apply to reference generation; this baseline does not define or enforce a
plant acceleration limit.

The computed-torque PD law uses exact plant parameters and direct abstract
human generalized torque. It is only an oracle plant-validation baseline, not
the future rehabilitation controller, and the synthetic profiles do not
demonstrate patient generalization. No robot dynamics, model mismatch,
measurement uncertainty, clinical trajectory set, NMPC, identification,
adaptation, or robust/safety layer is included.

The real robot control input remains unresolved. It must be selected after
reviewing the actual robot interface and supported control modes; the
externally supplied \(v_r\) in the damping module is only an interaction
abstraction.
