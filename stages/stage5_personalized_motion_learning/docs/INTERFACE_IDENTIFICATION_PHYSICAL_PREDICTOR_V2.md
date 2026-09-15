# Stage-5 Identification-Side Physical Predictor v2

Status: **identification-only exploratory predictor; Gate 2 did not pass, so
the existing estimator was not rerun and no parameter was published**.

No MuJoCo run was performed. The audit reuses saved Interface Mismatch v1
traces. Goal-MPC, its control-grade interface predictor, loaded execution,
HOLD, task logic, limits, and safety chain remain unchanged.

## Control-grade versus identification-grade models

The frozen **control-grade predictor** retains its explicit force-driven
interface state and executable-wrench-increment propagation. It is optimized
for short-horizon candidate screening and is not modified by this work.

The new **identification-grade predictor** is intended to preserve the physical
meaning of candidate Kelvin--Voigt parameters. It recomputes deformation from
robot/Human relative kinematics and does not use the old base-drive state. It
is currently offline only.

## State and transition

The 16-dimensional nuisance state remains compatible with the existing
windowed estimator:

\[
z=[q,\dot q,x,u,\theta,\omega],
\]

where `x,u,theta,omega` are robot-cuff relative translation, translation rate,
rotation vector, and angular rate, all expressed in the Human cuff frame.
They imply the robot cuff state through

\[
p_R=p_H+R_Hx,\qquad R_R=R_H\exp([\theta]_\times),
\]

\[
v_R=v_H+\omega_H\times R_Hx+R_Hu,\qquad
\omega_R=\omega_H+R_H\omega.
\]

Candidate parameters retain the original physical definition:

\[
K_t=\alpha_tK_{t,0},\quad K_r=\alpha_rK_{r,0},\quad
D_t=\alpha_dD_{t,0},\quad D_r=\alpha_dD_{r,0}.
\]

At each 0.25 ms substep the interface law is

\[
F_H=K_t(x-x_0)+D_tu,
\]

\[
M_H=K_r(\theta-\theta_0)+D_r\omega+x\times F_H.
\]

The fixed Stage-5 Human model maps this Human-site wrench to generalized input
and propagates `q,dq`. The same physical wrench is shifted to the robot cuff
reference point with the existing Stage-5 wrench transform. The recorded final
loaded executable wrench is held over each 5 ms measurement interval and the
reduced robot model uses

\[
a_R=M_R^{-1}(F_{cmd}-F_{interface,R}),\qquad
\dot\omega_R=I_R^{-1}(M_{cmd}-M_{interface,R}).
\]

Robot pose/twist and Human state are advanced together; relative interface
coordinates are then recomputed from their new kinematics. Thus executable
wrench is a robot input, not an independent interface-drive replacement.

### Fixed robot-side approximation

`M_R=[1.6588,1.9707,1.6369] kg` and isotropic
`I_R=0.108742 kg m2` are fixed identification-side nuisance constants copied
as a numeric snapshot of the existing provisional operational response scales.
They are not fitted, not interface parameters, and are not read by control.

Known approximations are constant diagonal operational mass/inertia, no robot
Jacobian variation, no joint torque-saturation dynamics, no bed reaction, and
the assumption that inherited bias/posture terms have already been handled by
the loaded executable command. This is a reduced model, not Python MuJoCo.

## Gate 1: true-parameter closure

All metrics use the existing 0.20 s fit, 0.05 s embargo, and 0.10 s held-out
window, with evaluation-only true parameters and consistent initial state.

| saved case | old normalized RMSE | v2 normalized RMSE | reduction | v2 position / linear velocity | v2 rotation / angular velocity | v2 force / moment | v2 q RMSE | v2 dq RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nominal | 2.050 | 1.110 | 45.9% | 4.43 mm / 0.0320 m/s | 1.11 deg / 0.0997 rad/s | 1.34 N / 0.364 Nm | 0.24/2.06 deg | 0.87/9.72 deg/s |
| `Kt x0.7` | 1.421 | 0.743 | 47.7% | 2.73 mm / 0.0198 m/s | 0.85 deg / 0.0679 rad/s | 1.25 N / 0.312 Nm | 0.36/1.76 deg | 0.78/7.49 deg/s |
| `Kt x1.3` | 2.113 | 1.151 | 45.5% | 4.35 mm / 0.0397 m/s | 1.10 deg / 0.1207 rad/s | 0.80 N / 0.497 Nm | 0.21/1.96 deg | 1.26/10.57 deg/s |
| `Kr x1.3` | 0.987 | 0.454 | 54.0% | 1.00 mm / 0.0127 m/s | 0.51 deg / 0.0496 rad/s | 1.54 N / 0.355 Nm | 0.50/1.30 deg | 1.50/6.76 deg/s |
| `D x0.7` | 1.727 | 0.938 | 45.7% | 3.49 mm / 0.0203 m/s | 1.02 deg / 0.0768 rad/s | 1.91 N / 0.430 Nm | 0.34/1.99 deg | 1.13/9.06 deg/s |
| `D x1.3` | 1.321 | 0.769 | 41.8% | 2.65 mm / 0.0174 m/s | 0.90 deg / 0.0703 rad/s | 1.63 N / 0.397 Nm | 0.41/1.85 deg | 1.59/9.04 deg/s |

V2 improves all six dynamic cases; mean v2/old normalized RMSE is `0.532`.
The relative-motion formulation therefore materially reduces the previous
model-form residual. It does not close it: joint-2 velocity error remains
`6.8--10.6 deg/s`, and force error remains `0.8--1.9 N`.

## Gate 2: held-out parameter landscapes

The primary objective is mean squared normalized held-out residual. Values
below are normalized RMSE for readability; the minimum is computed from the
squared objective.

| landscape | tested values | normalized RMSE sequence | truth | grid minimum | truth/min objective ratio | local slope / curvature | max correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Kt x0.7`, `alpha_t` | 0.5/0.6/0.7/0.8/0.9 | 0.766/0.742/0.743/0.755/0.770 | 0.7 | 0.6 | 1.005 | 0.100 / 1.494 | 0.954 |
| `Kr x1.3`, `alpha_r` | 1.1/1.2/1.3/1.4/1.5 | 0.510/0.478/0.454/0.438/0.427 | 1.3 | 1.5 boundary | 1.133 | -0.182 / 0.712 | 0.962 |
| `D x0.7`, `alpha_d` | 0.5/0.6/0.7/0.8/0.9 | 0.947/0.942/0.938/0.935/0.932 | 0.7 | 0.9 boundary | 1.013 | -0.071 / 0.147 | 0.893 |
| nominal, `alpha_t` | 0.8/0.9/1.0/1.1/1.2 | 1.093/1.101/1.110/1.118/1.127 | 1.0 | 0.8 boundary | 1.030 | 0.192 / 0.031 | 0.944 |
| nominal, `alpha_r` | 0.8/0.9/1.0/1.1/1.2 | 1.140/1.119/1.110/1.107/1.109 | 1.0 | 1.1 | 1.004 | -0.127 / 1.534 | 0.944 |
| nominal, `alpha_d` | 0.8/0.9/1.0/1.1/1.2 | 1.114/1.112/1.110/1.108/1.106 | 1.0 | 1.2 boundary | 1.006 | -0.043 / 0.053 | 0.944 |

The `Kt x0.7` truth is practically close to the shallow minimum, and nominal
`alpha_r` is also near a shallow local optimum. The required gate nevertheless
fails:

- `Kr x1.3` improves monotonically beyond truth and has a 13.3% squared-
  objective penalty at the true value;
- `D x0.7` and nominal damping prefer the upper grid edge;
- nominal translational stiffness prefers the lower grid edge;
- `alpha_t/alpha_r` projected correlations remain `0.893--0.962` despite
  numerical rank three and conditions `5.77--8.12`.

These are not estimator failures: they occur before parameter fitting, using
true initial state and one-dimensional true-neighborhood landscapes.

## Gate 3: existing estimator

**Not reached.** The existing bounded joint initial-state/parameter estimator
was intentionally not rerun because Gate 2 did not establish
`theta_truth approximately argmin J_validation`. Fitted parameters, multistart,
and window-length tables would not have a valid physical interpretation yet.

## Decision and next step

**B — v2 improves closure, but true parameters still do not consistently
minimize held-out prediction error. No excitation should be designed yet.**

The remaining smallest model-form issue is robot-side propagation. A constant
diagonal operational inertia cannot reproduce the configuration-dependent
UR10e response represented by the loaded execution chain. Its residual is
being absorbed by interface stiffness/damping.

The next implementation should remain identification-only and add the minimum
deployable robot dynamics boundary needed to propagate that chain:

- robot `q,dq`, applied joint-torque command, cuff Jacobian, and bias/feedback
  decomposition at the same timestamp as cuff pose/twist and wrench;
- a configuration-dependent joint/operational response from the existing robot
  model, or a separately validated causal robot-response model;
- interface reaction applied through the same robot cuff Jacobian/reference
  point before recomputing relative kinematics.

Then repeat Gates 1 and 2. Only if the monotone/boundary parameter landscapes
move back toward truth should the unchanged estimator be run or a dedicated
excitation be designed.

## Evidence limitations

The saved mismatch traces predate direct raw robot pose/twist logging. Robot
targets here are evaluation-only sensor-equivalent reconstructions from saved
plant Human/interface truth, and interface velocity uses an offline finite
derivative. The local grids are diagnostics, not global identifiability or
hardware-validation claims.

Compact evidence is local and ignored by Git at
`results/interface_physical_predictor_v2_offline/audit.json`.
