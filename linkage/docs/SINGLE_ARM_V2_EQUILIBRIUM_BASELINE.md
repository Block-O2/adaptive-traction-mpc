# Single-Arm V2 Equilibrium-Preserving Baseline

## Scope and interpretation

This local engineering baseline evaluates whether one ideal two-dimensional
force at the Human Model V2 distal shank cuff can drive the 16 s
`slow_passive_flexion_v2` trajectory. It does not model robot dynamics,
hardware limits, patient active torque, external support, clinical safety, or
clinical efficacy.

The following remain frozen and reproducible:

- the V1 plant;
- the historical single-contact negative endpoint-force baseline;
- the Human Model V2 direct-joint-torque oracle baseline.

All new functions use the `single_arm_v2_*` namespace. The generated evidence
is ignored under
`linkage/results/local/single_arm_v2_equilibrium_baseline/` and is not an
authoritative clinical or robot experiment.

## Endpoint-only plant and analytic map

The V2 plant receives no direct joint torque:

\[
F_{world}=R(q)u,\qquad
u=[F_t,F_n]^T,\qquad
R=[t\ n],
\]

\[
\tau_{contact}=J_c(q)^T R(q)u=A(q)u,
\]

\[
M(q)\ddot q+h(q,\dot q)+G(q)+\tau_{passive,left}(q,\dot q)
=\tau_{contact}.
\]

For \(\phi=q_1-q_2\), distal position \(s_c=0.90L_2\), and the local shank
frame used by V2, independent multiplication gives

\[
A(q)=
\begin{bmatrix}
-L_1\sin q_2 & L_1\cos q_2+s_c\\
0 & -s_c
\end{bmatrix},
\qquad
\det A=L_1s_c\sin q_2.
\]

The implementation records `det(A)`, `sigma_min(A)`, and `cond(A)` at every
sample. Desired forces are obtained using an SVD solve; `inv(A)` is never
formed.

## Reference preflight

Preflight was performed at every 0.002 s sample before either closed-loop
case. It solves

\[
A(q_{ref})u_{static}=G(q_{ref})+
\tau_{passive,left}(q_{ref},0)
\]

and

\[
A(q_{ref})u_{ff}=M\ddot q_{ref}+h+G+
\tau_{passive,left}(q_{ref},\dot q_{ref}).
\]

Observed nominal results:

| Quantity | Observed value |
|---|---:|
| peak \(|F_t|\) | 315.861949 N |
| peak \(|F_n|\) | 21.443758 N |
| peak \(\|F\|\) | 316.551129 N at 1.264 s, flexion |
| peak \(\|\dot F\|\) | 118.668074 N/s at 13.842 s, return |
| peak static-force norm | 315.7298 N |
| peak static generalized torque | 41.3686 N m |
| peak dynamic-increment generalized torque | 2.1257 N m |
| minimum `sigma_min(A)` | 0.0313783 at 0 s, initial hold |
| maximum `cond(A)` | 27.7907 at 0 s, initial hold |
| maximum exact SVD residual | 4.42e-14 N m |
| ±80 N reference feasible fraction | 0.000000 |
| ±80 N minimum-residual RMS / maximum | 6.91913 / 8.8138 N m |

The dominant demand is static gravity/passive support, not trajectory
acceleration. The ±80 N case is already infeasible at the reference level;
its closed-loop failure is therefore a physical/constraint result rather than
a controller runtime failure.

## Equilibrium-preserving controller

At each measured state,

\[
e=q-q_{ref},\qquad \dot e=\dot q-\dot q_{ref},
\]

\[
\ddot q_{cmd}=\ddot q_{ref}-K_pe-K_d\dot e,
\]

\[
\tau_{des}=M\ddot q_{cmd}+h+G+\tau_{passive,left}.
\]

An SVD solve gives \(A u_{des}=\tau_{des}\). The deterministic two-input
boundary-enumeration solver then minimizes

\[
\left\|W_\tau(Au-\tau_{des})/\tau_{scale}\right\|^2+
\lambda_{ref}\left\|(u-u_{des})/F_{scale}\right\|^2+
\lambda_{du}\left\|(u-u_{prev})/(du_{scale}\Delta t)\right\|^2
\]

subject to the force and slew boxes. `lambda_ref` is centered on the
equilibrium force rather than zero. `lambda_du=0` in this baseline so that a
well-conditioned, unconstrained command returns exactly to `u_des`; the
explicit slew constraint remains active. The measured ideal torque residual
confirms this property at numerical precision.

The first command is the force-box-feasible optimum for `u_des(t0)`, then used
as `u_prev`; the measured initial rate is numerical zero
(below 3.2e-10 N/s).

### Single documented gain revision

The requested older endpoint gains,
`Kp=diag([36,49])`, `Kd=diag([12,14])`, were tried first. They produced a
0.0077 degree return undershoot below the V2 soft-zone start. The one allowed
global revision reused the already validated V2 oracle gains for both cases:

- `Kp=diag([180,140])`;
- `Kd=diag([28,22])`.

No further search, per-case tuning, force-bound change, or trajectory change
was performed. Even after the one revision, the ideal case still activates
the soft limit near the end of the return, so that outcome is retained.

## Fixed case definitions

Reference preflight automatically produced the ideal bounds:

- \(|F_t|\le379.034339\) N;
- \(|F_n|\le25.732509\) N;
- \(|\dot F_t|\le142.393303\) N/s;
- \(|\dot F_n|\le14.809843\) N/s.

The engineering case uses the same gains, trajectory, initial state, time
step, and rate limits, but fixes both force components to ±80 N.

## Closed-loop results

| Metric | ideal_authority | engineering_bound |
|---|---:|---:|
| completed full 16 s | yes | yes |
| q1/q2 RMSE (deg) | 0.002336 / 0.006161 | 10.8060 / 52.4848 |
| q1/q2 maximum error (deg) | 0.005534 / 0.017403 | 16.9957 / 82.6100 |
| peak \(\|F\|\) (N) | 316.565 | 95.016 |
| peak \(\|\dot F\|\) (N/s) | 119.047 | 143.161 |
| force-feasible fraction | 1.000000 | 0.000000 |
| hard force saturation fraction | 0.000000 | 0.978503 |
| slew saturation fraction | 0.000000 | 0.062867 |
| torque residual RMS / max (N m) | 1.14e-14 / 4.33e-14 | 8.19457 / 16.7970 |
| ROM violation samples | 0 | 0 |
| soft-limit active samples | 473 | 8000 |
| minimum `sigma_min(A)` | 0.031371 | 0.004269 |
| maximum `cond(A)` | 27.7973 | 205.035 |
| first acceptance event | 14.920 s, return | 0 s, initial hold |

The ideal command is unconstrained and equilibrium preserving to numerical
precision. Its remaining acceptance issue is the 473-sample soft-limit
activation during the final return; this is not caused by force/slew
saturation, torque residual, or poor mapping condition. Consequently the
specified ideal success criteria are not fully met.

The engineering case is dominated by the force bound from the first sample.
Its static support deficit drives large tracking error, persistent soft-limit
activity, feedback growth, and later condition degradation. Conditioning is a
consequence/amplifier of the state departure, not the initiating cause.
There is no numerical-residual classification and no runtime error.

## Oracle comparison and decision

The direct-joint-torque V2 oracle remains an actuator-authority lower bound,
not a fair endpoint-force comparison. It records q1/q2 RMSE of
7.18e-10/2.74e-9 degrees, zero ROM violation, and zero soft-limit activation;
this only confirms that the reference and V2 plant are sound.

Under the required classification rules, this baseline is
`ideal_not_accepted_do_not_enter_nmpc`. Fixed-model planner/NMPC work is not
yet justified. The next investigation should address the terminal
soft-boundary/reference interaction or sampled endpoint tracking design in a
new approved task, without changing this result or the ±80 N evidence.

## Reproduction

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_single_arm_v2_equilibrium_tests"
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_single_arm_v2_equilibrium_baseline"
```

Both commands are fully headless. The baseline creates exactly one GIF for
`ideal_authority`; no engineering-case GIF is generated.
