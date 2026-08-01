# Independent Dynamics-Consistency Audit

## Scope and evidence boundary

This audit independently derives the two-link model implied by the recorded
kinematics:

- generalized coordinates \(q=[q_1,q_2]^{\mathsf T}\);
- thigh absolute angle \(q_1\);
- shank absolute angle \(q_1-q_2\);
- inertial X axis horizontal and Y axis upward;
- fixed hip at the origin.

The derivation begins from COM positions, velocities, kinetic energy, and
potential energy. The professor source expressions are introduced only after
the independent derivation for comparison.

No professor-source equation, parameter, controller, constraint, or integration
setting was changed. No corrected plant is proposed or implemented.

Evidence used:

- preserved source SHA-256
  `b8c95ab1df3507efd610a3a72057e31a33724626d37341bd5d5a4abaa833c19f`;
- the successful MATLAB R2025b captured workspace with 24,001 states;
- a deterministic 2,000-state valid-range grid;
- MATLAB R2025b Update 1 numerical evaluation.

Classification labels have the following meanings:

- **consistent** — agrees in the stated coordinates and interpretation;
- **coordinate-convention equivalent** — agrees after an explicit invertible
  coordinate change;
- **inconsistent** — does not agree in the stated coordinates and is not
  explained by the tested coordinate change;
- **unresolved** — the source does not establish the intended physical
  interpretation.

## 1. Recorded physical quantities

The source records:

| Quantity | Value |
|---|---:|
| \(L_1,L_2\) | \(0.45,0.40\) m |
| \(m_1,m_2\) | \(8.5,3.8\) kg |
| \(l_{c1},l_{c2}\) | \(0.225,0.20\) m |
| \(I_1\) | \(0.1434375\) kg m² |
| \(I_2\) | \(0.0506666666667\) kg m² |
| attachment distances \(s_1,s_2\) | \(0.55L_1,0.50L_2\) |
| displayed normal offsets \(o_1,o_2\) | \(0.13,0.12\) m |

Define

\[
e(\theta)=
\begin{bmatrix}\cos\theta\\\sin\theta\end{bmatrix},
\qquad
n(\theta)=
\begin{bmatrix}-\sin\theta\\\cos\theta\end{bmatrix},
\qquad
\theta_2=q_1-q_2.
\]

## 2. Independent derivation from COM motion and energy

### 2.1 COM positions and velocities

The COM positions implied by the recorded geometry are

\[
r_{c1}=l_{c1}e(q_1),
\]

\[
r_{c2}=L_1e(q_1)+l_{c2}e(q_1-q_2).
\]

Using \(\dot e(\theta)=n(\theta)\dot\theta\),

\[
\dot r_{c1}=l_{c1}n(q_1)\dot q_1,
\]

\[
\dot r_{c2}
=L_1n(q_1)\dot q_1
+l_{c2}n(q_1-q_2)(\dot q_1-\dot q_2).
\]

The link angular velocities are

\[
\omega_1=\dot q_1,\qquad
\omega_2=\dot q_1-\dot q_2.
\]

### 2.2 Kinetic energy

The kinetic energy is

\[
T=
\frac12m_1\dot r_{c1}^{\mathsf T}\dot r_{c1}
+\frac12I_1\dot q_1^2
+\frac12m_2\dot r_{c2}^{\mathsf T}\dot r_{c2}
+\frac12I_2(\dot q_1-\dot q_2)^2.
\]

Define

\[
b=I_2+m_2l_{c2}^2,\qquad
d=m_2L_1l_{c2},
\]

\[
a=I_1+m_1l_{c1}^2+b+m_2L_1^2.
\]

Expanding the kinetic energy gives

\[
T=\frac12(a+2d\cos q_2)\dot q_1^2
-(b+d\cos q_2)\dot q_1\dot q_2
+\frac12b\dot q_2^2.
\]

Therefore \(T=\tfrac12\dot q^{\mathsf T}M(q)\dot q\) with

\[
\boxed{
M(q)=
\begin{bmatrix}
a+2d\cos q_2 & -(b+d\cos q_2)\\
-(b+d\cos q_2) & b
\end{bmatrix}.}
\]

For the recorded values,

\[
a=1.5459166666667,\quad
b=0.2026666666667,\quad
d=0.342.
\]

### 2.3 Potential energy and gravity

Because Y is upward, gravitational potential energy is

\[
V(q)=
g\left[
(m_1l_{c1}+m_2L_1)\sin q_1
+m_2l_{c2}\sin(q_1-q_2)
\right].
\]

Using the standard manipulator convention

\[
M(q)\ddot q+h(q,\dot q)+G(q)=\tau,
\]

the gravity vector is the potential-energy gradient

\[
\boxed{
G(q)=\nabla_qV=
\begin{bmatrix}
g[(m_1l_{c1}+m_2L_1)\cos q_1
+m_2l_{c2}\cos(q_1-q_2)]\\
-m_2gl_{c2}\cos(q_1-q_2)
\end{bmatrix}.}
\]

The physical generalized gravity force is \(-G(q)\).

### 2.4 Coriolis and centrifugal terms

Applying the Euler-Lagrange equation to the independently expanded kinetic
energy gives

\[
\boxed{
h(q,\dot q)=
\begin{bmatrix}
d\sin q_2(-2\dot q_1\dot q_2+\dot q_2^2)\\
d\sin q_2\,\dot q_1^2
\end{bmatrix}.}
\]

One valid Christoffel-form matrix satisfying \(C(q,\dot q)\dot q=h(q,\dot q)\)
is

\[
\boxed{
C(q,\dot q)=
\begin{bmatrix}
-d\sin q_2\,\dot q_2
&
d\sin q_2(\dot q_2-\dot q_1)\\
d\sin q_2\,\dot q_1
&
0
\end{bmatrix}.}
\]

For this choice,

\[
\dot M=
\begin{bmatrix}
-2d\sin q_2\,\dot q_2 & d\sin q_2\,\dot q_2\\
d\sin q_2\,\dot q_2 & 0
\end{bmatrix},
\]

and \(\dot M-2C\) is skew-symmetric.

## 3. Independently derived point Jacobians

### 3.1 Attachment points

The attachment positions are

\[
p_{a1}=s_1e(q_1),
\qquad
p_{a2}=L_1e(q_1)+s_2e(q_1-q_2).
\]

Their Jacobians are

\[
\boxed{
J_{a1}=
\begin{bmatrix}
-s_1\sin q_1 & 0\\
s_1\cos q_1 & 0
\end{bmatrix},}
\]

\[
\boxed{
J_{a2}=
\begin{bmatrix}
-L_1\sin q_1-s_2\sin(q_1-q_2)
&
s_2\sin(q_1-q_2)\\
L_1\cos q_1+s_2\cos(q_1-q_2)
&
-s_2\cos(q_1-q_2)
\end{bmatrix}.}
\]

These match the source attachment-point Jacobians.

### 3.2 Displayed endpoints with rotating normal offsets

The source flips each displayed normal when necessary to keep its Y component
nonnegative. Away from a flip boundary, let the locally constant signs be
\(\sigma_i\in\{-1,+1\}\). The displayed endpoints are

\[
p_{e1}=p_{a1}+\sigma_1o_1n(q_1),
\]

\[
p_{e2}=p_{a2}+\sigma_2o_2n(q_1-q_2).
\]

Since \(dn/d\theta=-e(\theta)\), their Jacobians are

\[
\boxed{
J_{e1}
=J_{a1}
+\begin{bmatrix}-\sigma_1o_1e(q_1)&0\end{bmatrix},}
\]

\[
\boxed{
J_{e2}
=J_{a2}
+\begin{bmatrix}
-\sigma_2o_2e(q_1-q_2)
&
\sigma_2o_2e(q_1-q_2)
\end{bmatrix}.}
\]

At a normal-flip boundary the displayed endpoint definition is discontinuous
and has no single classical Jacobian.

The offset-velocity corrections are tangent to the link and orthogonal to the
displayed normal. Consequently:

- full Cartesian attachment and displayed-endpoint velocities differ;
- their normal velocity components agree away from a flip boundary;
- for a force exactly parallel to the displayed normal,
  \(J_{ei}^{\mathsf T}F_i=J_{ai}^{\mathsf T}F_i\), because the offset
  correction performs zero virtual work against that force.

## 4. Source-versus-derived analytical comparison

### 4.1 Inertia and Coriolis terms

The source inertia matrix has the same diagonal terms but positive
off-diagonal terms:

\[
M_{\mathrm{src}}=
\begin{bmatrix}
a+2d\cos q_2 & b+d\cos q_2\\
b+d\cos q_2 & b
\end{bmatrix}.
\]

The source Coriolis matrix produces

\[
C_{\mathrm{src}}\dot q=
\begin{bmatrix}
-d\sin q_2(2\dot q_1\dot q_2+\dot q_2^2)\\
d\sin q_2\dot q_1^2
\end{bmatrix}.
\]

These are the usual expressions for a relative coordinate whose link-2
absolute angle is \(q_1+q_2\), not the recorded \(q_1-q_2\).

Let

\[
S=\operatorname{diag}(1,-1),\qquad q_+=Sq,\qquad \dot q_+=S\dot q.
\]

Then the numerical and analytical checks both give

\[
M(q)=S^{\mathsf T}M_{\mathrm{src}}(q_+)S,
\]

\[
C(q,\dot q)
=S^{\mathsf T}C_{\mathrm{src}}(q_+,\dot q_+)S.
\]

Thus the source \(M,C\) pair is exactly coordinate-convention equivalent to
the derived pair under \(q_{2+}=-q_2\). However, the source uses the same
positive `th2` in kinematics as \(q_1-q_2\) while using \(M,C\) expressions for
the plus convention. The complete source is therefore inconsistent in its
declared coordinate use.

### 4.2 Gravity

The source-coded gravity term is

\[
G_{\mathrm{src}}=
\begin{bmatrix}
-g[(m_1l_{c1}+m_2L_1)\sin q_1
+m_2l_{c2}\sin(q_1-q_2)]\\
-m_2gl_{c2}\sin(q_1-q_2)
\end{bmatrix}.
\]

It is neither \(G=\nabla V\) nor \(-G\) for the recorded horizontal-X,
upward-Y frame. The tested \(q_2\) sign transformation does not resolve the
sine-versus-cosine angle-reference difference or the second-component sign.

In the successful baseline, this coded term is added to `tau_ctrl` and the
identical value is subtracted in forward dynamics. It therefore cancels to
floating-point precision and does not expose the gravity discrepancy in the
observed trajectory.

### 4.3 Classification

| Comparison | Classification | Basis |
|---|---|---|
| Derived \(M=M^{\mathsf T}\) and \(M\succ0\) on tested states | **consistent** | Zero symmetry residual and positive sampled eigenvalues |
| Derived \(C\dot q=h\) and skew identity | **consistent** | Direct Euler-Lagrange derivation and numerical residual |
| Source \(M,C\) as a self-contained plus-relative-coordinate pair | **consistent** | Source skew identity passes |
| Source \(M\) versus derived \(M\) in the recorded \(q_1-q_2\) coordinate | **inconsistent** | Opposite off-diagonal signs |
| Source \(C\dot q\) versus derived \(h\) in the recorded coordinate | **inconsistent** | Opposite sign on the \(\dot q_2^2\) term in component 1 |
| Source \(M,C\) after \(q_{2+}=-q_2\) transformation | **coordinate-convention equivalent** | Both transformed residuals are exactly zero numerically |
| Derived \(G\) versus numerical \(\nabla V\) | **consistent** | Central-difference residual below \(7.4\times10^{-9}\) N m |
| Source-coded gravity versus \(+\nabla V\) or \(-\nabla V\) | **inconsistent** | Large residual for both tested signs |
| Source \(J_1,J_2\) versus attachment Jacobians | **consistent** | Expressions match exactly |
| Source velocity log versus full displayed-endpoint velocity | **inconsistent** | Source uses attachment Jacobian and omits rotating-offset velocity |
| Source normal damping velocity and normal-force generalized torque | **consistent** | Omitted offset velocity is tangential, so normal projection/work is unchanged |
| Displayed endpoint Jacobian at normal-flip states | **unresolved** | The source's sign flip makes the displayed point discontinuous |
| Intended physical meaning of the displayed offset | **unresolved** | It may be graphics-only or a physical force application point |

## 5. Deterministic numerical checks

### 5.1 State sets

The captured set contains all 24,001 saved baseline states.

The fixed grid contains 2,000 Cartesian-product states within the source's
hard joint-angle and velocity limits:

- \(q_1\) in `[-5, 0, 15, 30, 45, 60, 75, 85]` deg;
- \(q_2\) in `[-5, 0, 15, 30, 45, 60, 75, 90, 105, 120]` deg;
- \(\dot q_1\) in `[-60, -30, 0, 30, 60]` deg/s;
- \(\dot q_2\) in `[-80, -40, 0, 40, 80]` deg/s.

The grid is not filtered by the source's soft hip-knee coordination rules, so
it exercises their surrounding state space as well. No random sampling or
parameter tuning was used.

### 5.2 Results

| Check | Captured trajectory | Fixed grid |
|---|---:|---:|
| State count | 24,001 | 2,000 |
| Max derived/source \(M\) symmetry residual | 0 / 0 | 0 / 0 |
| Min derived/source \(M\) eigenvalue | 0.0655973465 / 0.0655973465 | 0.0655973465 / 0.0655973465 |
| Derived/source condition-number range | 13.1245–36.0836 / same | 5.97481–36.0836 / same |
| Max derived/source skew residual | 5.55e-17 / 2.22e-16 | 1.11e-16 / 1.11e-16 |
| Max numerical-\(\nabla V\) residual | 7.37e-9 N m | 5.94e-9 N m |
| Max source-derived \(M\) element difference | 1.0893333333 | 1.0893333333 |
| Max transformed-\(q_2\) \(M\) residual | 0 | 0 |
| Max source-derived \(C\dot q\) difference | 0.262908752 N m | 1.333493217 N m |
| Max transformed-\(q_2\) \(C\dot q\) residual | 0 | 0 |
| Max source-derived gravity difference | 57.3119919 N m | 60.8003291 N m |
| Max source-plus-derived gravity residual | 42.9553244 N m | 49.0024149 N m |
| Max arm-1 attachment/display velocity difference | 0.0932243 m/s | 0.136136 m/s |
| Max arm-2 attachment/display velocity difference | 0.0276077 m/s | 0.293215 m/s |
| Max arm-1 normal-velocity difference | 4.16e-17 m/s | 4.16e-17 m/s |
| Max arm-2 normal-velocity difference | 1.50e-16 m/s | 1.94e-16 m/s |
| Normal-flip boundary states | 0 | 100 |

The derived and source inertia matrices have identical eigenvalues and
condition numbers because changing the off-diagonal sign is an orthogonal
coordinate transformation. Positive definiteness alone therefore cannot
detect the mixed sign convention.

The 100 fixed-grid normal-switch states are reported but not interpreted as
having a unique displayed-endpoint Jacobian.

## 6. Descriptive baseline torque decomposition

The following decomposition reconstructs the source-coded quantities on all
24,000 baseline transitions. It is descriptive and does not endorse or correct
the model.

| Component | Hip range (N m) | Knee range (N m) | Hip/knee RMS (N m) | Max vector norm (N m) |
|---|---:|---:|---:|---:|
| Coded gravity compensation | -31.5512 to -0.03698 | -0.04880 to 0.65422 | 20.0915 / 0.39771 | 31.5579 |
| Computed-torque feedforward | -1.90256 to 2.52283 | -0.48179 to 0.68338 | 1.64581 / 0.41571 | 2.61374 |
| PD feedback | -10.6545 to 4.33600 | -8.00000 to 1.05832 | 2.93000 / 0.73025 | 12.8062 |
| Arm 1 generalized torque | -1.09819 to 1.08218 | 0 to 0 | 0.78356 / 0 | 1.09819 |
| Arm 2 generalized torque | -3.25612 to 3.28636 | -1.06840 to 1.06910 | 2.07724 / 0.70790 | 3.45359 |
| Safety torque | 0 to 0 | 0 to 0 | 0 / 0 | 0 |
| Net acceleration-driving generalized torque | -8.88792 to 6.24538 | -7.31668 to 1.65453 | 1.72504 / 0.46478 | 10.4616 |

The decomposition reconstructs the logged total torque with maximum residual
\(1.4211\times10^{-14}\) N m. The net acceleration-driving torque is

\[
\tau_{\mathrm{drive}}
=\tau_{\mathrm{total}}
-C_{\mathrm{src}}\dot q
-G_{\mathrm{src}},
\]

so the added and subtracted coded gravity compensation is absent from this net
quantity.

## 7. Confirmed inconsistencies

1. **Mixed \(q_2\) convention.** Kinematics and attachment Jacobians use shank
   angle \(q_1-q_2\), while the source \(M,C\) pair is the model for
   \(q_1+q_2\). The sign transform proves coordinate equivalence of the
   isolated \(M,C\) pair, but it also confirms the complete source mixes the two
   conventions.
2. **Gravity does not match the recorded frame.** The source-coded gravity
   vector does not equal either sign of the independently derived
   potential-energy gradient.
3. **Displayed-endpoint Cartesian velocity is not the logged velocity.** The
   source logs attachment-point Jacobian velocity while displaying a point with
   a rotating normal offset. Normal damping and normal-force generalized torque
   are nevertheless unaffected away from normal flips.

These findings are not automatically corrected.

## 8. Unresolved interpretation questions

1. Is positive knee flexion intended to make the shank angle \(q_1-q_2\), or
   was the intended generalized coordinate a plus-relative angle?
2. Are \(q_1\) and the shank absolute angle measured from horizontal or from
   vertical for gravity purposes?
3. Is `tau_gravity` intended to mean the manipulator \(G(q)\), the physical
   generalized gravity force \(-G(q)\), or only a controller compensation term?
4. Are the normal offsets physical endpoint locations or visualization-only
   geometry?
5. Should endpoint Cartesian velocity include rotation of the normal offset,
   or is only attachment-point/normal velocity physically meaningful?
6. Is the normal-direction sign flip intended as physical switching logic? If
   so, what behavior is intended at its discontinuity?
7. Is the current gravity cancellation in forward dynamics intentional for the
   reference demonstration, even though it prevents the trajectory from
   testing the coded gravity expression?

## 9. Recommended professor questions

The minimum high-value questions are:

1. “For positive knee flexion, should the shank absolute angle be
   \(q_1-q_2\) or \(q_1+q_2\), and which convention was used when deriving
   \(M\) and \(C\)?”
2. “Are the link angles measured from the horizontal bed or from vertical when
   deriving gravity?”
3. “Should `tau_gravity` be \(G(q)\), \(-G(q)\), or merely an exactly cancelled
   computed-torque term?”
4. “Are the displayed normal offsets real force application points, or only
   drawing offsets?”
5. “Should the logged endpoint velocity be full displayed-point velocity or
   attachment-point velocity?”
6. “Should the normal flip be smoothed or otherwise defined at its switching
   boundary?”

## 10. Reproducibility and local evidence

The successful baseline was rerun through
`linkage/matlab/runners/run_professor_reference_capture.m` and exited 0.
The numerical-check implementation is tracked at
`linkage/matlab/audits/run_dynamics_consistency_checks.m`; it reads the
captured workspace and writes its numerical results back to the ignored
baseline directory. Generated workspaces, figures, logs, and numerical
results remain ignored under
`linkage/results/local/professor_reference_baseline/`.

Headless audit command:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath('linkage/matlab/audits'); run_dynamics_consistency_checks"
```

Relevant local evidence:

- `dynamics_consistency_console.log`;
- `dynamics_consistency_results.txt`;
- `dynamics_consistency_results.mat`;
- refreshed `console.log`, `workspace_numeric.mat`, and figures;
- `runner_checkcode.log` and `runner_checkcode_crash_dump.txt`.

An attempted MATLAB `checkcode` invocation returned five analyzer entries and
then MATLAB itself crashed in the background `ddux LicenseLogger` thread. This
was not a professor-source or baseline runtime error. The crash dump was moved
into the ignored local evidence directory. The subsequent full professor
baseline and the numerical dynamics audit both exited 0.

## 11. Publication status and sensitive repository paths

Publishing permission is no longer a blocker for this intake branch and its
detailed derived documentation. The following tracked files disclose recorded
parameters, coded equations, or independently derived equations:

- `linkage/docs/MATLAB_CODE_AUDIT.md`;
- `linkage/docs/SYSTEM_DEFINITION_DRAFT.md`;
- `linkage/docs/DYNAMICS_CONSISTENCY_AUDIT.md` — recorded parameters,
  independently derived equations, source comparisons, and numerical results;
- `linkage/matlab/runners/run_professor_reference_capture.m` — replicated
  source equations used for post-run diagnostics;
- `linkage/matlab/audits/run_dynamics_consistency_checks.m` — independently
  derived equations and deterministic source-comparison calculations.

The professor source and generated local evidence remain ignored and are not
tracked.
