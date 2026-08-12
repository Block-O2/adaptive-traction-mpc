# Single-Arm Quasistatic Feasibility Atlas

## Scope and status

This study is a quasistatic mechanical diagnostic for the retained nominal
Human Model V2 and single distal shank contact. It asks whether the previously
observed approximately 316 N static demand is widespread across the joint
workspace or concentrated near low knee flexion.

It is not a controller experiment. It includes no closed-loop simulation,
NMPC, trajectory optimization, contact-position scan, second contact, robot
dynamics, or hardware-interface assumption. It does not prove closed-loop
controllability, comfort, or clinical safety, and it does not choose between a
single arm, passive support, or two-contact architecture. The final
architecture remains gated on professor guidance and authoritative hardware
information.

The following retained definitions are used without modification:

- nominal Human Model V2 parameters and passive-joint model;
- distal cuff-equivalent location `sc = 0.90 L2`;
- `slow_passive_flexion_v2` reference;
- analytic single-arm V2 force map;
- SVD stable solve and deterministic two-dimensional box solver;
- frozen equilibrium-controller and baseline results.

## Quasistatic definition and force coordinates

At every posture,

\[
\dot q=0,\qquad \ddot q=0,
\]

so the generalized torque required to hold the passive leg is

\[
\tau_{\mathrm{hold}}(q)=G(q)+
\tau_{\mathrm{passive,left}}(q,0).
\]

The local contact-force vector is named

\[
u=\begin{bmatrix}F_{\parallel}\\F_{\perp}\end{bmatrix},
\]

where `F_parallel` lies along the shank axis and `F_perp` is perpendicular to
the shank. These names correspond to the retained implementation's local
tangent and normal columns; no existing interface was renamed.

For the verified coordinates, the retained analytic map is

\[
A(q)=
\begin{bmatrix}
-L_1\sin q_2 & L_1\cos q_2+s_c\\
0 & -s_c
\end{bmatrix},\qquad
A(q)u=\tau_{\mathrm{hold}}.
\]

Its determinant is (L_1s_c\sin q_2). Therefore `q2 = 0 deg` is explicitly
rank deficient. Atlas exact-force values at that row are `NaN`,
`sigma_min(A) = 0`, and `cond(A) = Inf`; no finite exact force is fabricated.

## Grid and bounded feasibility

The deterministic grid contains 8,181 postures:

- `q1 = 0:1:80 deg`;
- `q2 = 0:1:100 deg`;
- 8,100 nonsingular points and 81 singular extended-knee points.

At each point the analysis records both local force components, force norm,
exact torque residual, singular values and condition number, determinant,
gravity torque, passive torque, and total holding torque. The exact solution
uses `single_arm_v2_stable_force_solve` with relative tolerance `1e-12`.
The maximum exact residual over the nonsingular grid is
`3.57e-14 N m`.

For each symmetric component limit (`+/-80`, `+/-120`, and `+/-200 N`), an
exact solution is feasible only when both local-force components lie within
the box. When it is infeasible, the retained deterministic two-dimensional
box solver minimizes the holding-torque residual. At the rank-deficient row
only, a `1e-12`-scaled positive tie-break makes the existing positive-definite
QP interface deterministic; the row remains classified singular and exact
infeasible, and its exact force remains `NaN`.

## Observed force and conditioning map

| Posture | F_parallel (N) | F_perp (N) | Force norm (N) | cond(A) | sigma_min(A) |
|---|---:|---:|---:|---:|---:|
| Lowest finite grid point `[0,15] deg` | -4.323 | 17.953 | 18.466 | 18.470 | 0.046991 |
| Largest nonsingular point `[0,1] deg` | 4432.247 | 60.931 | 4432.666 | 278.590 | 0.003142 |
| V2 start `[5,10] deg` | -315.030 | 21.011 | 315.730 | 27.791 | 0.031378 |
| V2 peak `[45,84] deg` | -101.646 | -19.417 | 103.484 | 2.721 | 0.239992 |

The lowest-force point lies at the hip ROM boundary and is influenced by the
retained soft-limit/passive torque, which partially cancels gravity there. It
should not be interpreted as a broad interior optimum or a clinical target.

The very large forces are localized near extension rather than spread across
the complete workspace:

- all 745 finite grid points with `force_norm >= 300 N` have
  `q2 = 1..19 deg`;
- the singular row is exactly `q2 = 0 deg`;
- finite `cond(A) >= 100` occurs only in the lowest flexion rows immediately
  above the singular row;
- the nonsingular maximum at `q2 = 1 deg` is dominated by
  `F_parallel`, as expected from the nearly collapsed torque-to-force map.

These observations support a localized low-flexion amplification mechanism
for this model and contact geometry. They do not imply that every
single-contact posture is low force or that all high-flexion postures are
acceptable under every component limit.

## Current V2 reference

The unchanged V2 reference traverses from `[5,10] deg` to `[45,84] deg` and
back. Its quasistatic force range is:

- maximum `315.7298 N` at the start/end configuration;
- minimum `103.4842 N` at the peak-flexion configuration.

The start demand is almost entirely axial (`F_parallel = -315.03 N`), while
the peak-flexion demand is much smaller and better conditioned. This isolates
the previously reported approximately `315.73 N` static requirement as an
endpoint/low-knee-flexion property of the frozen reference, not a uniform
workspace requirement.

The reference-force profile confirms that its quasistatic peak is the
start/end pose `[5,10] deg`, with approximately `315.73 N` total force. The
peak is dominated by `F_parallel`; `F_perp` is comparatively small. The
reference therefore starts in the mechanically unfavorable low-knee-flexion,
near-extension region identified by the atlas.

## Component-bound feasibility

The percentages below use all 8,181 grid points as the denominator; the 81
`q2=0` singular points are included as infeasible. The parenthetical value
uses only the 8,100 nonsingular points.

| Component bound | Feasible points | All-grid fraction | Nonsingular fraction | Start `[5,10]` | Peak `[45,84]` |
|---|---:|---:|---:|---|---|
| `+/-80 N` | 201 | 2.4569% | 2.4815% | Infeasible | Infeasible |
| `+/-120 N` | 4,677 | 57.1691% | 57.7407% | Infeasible | Feasible |
| `+/-200 N` | 6,826 | 83.4372% | 84.2716% | Infeasible | Feasible |

The `+/-80 N` feasible set consists of narrow posture-dependent pockets and
is not a general high-flexion feasible region. Under `+/-120 N`, feasibility
becomes broad at moderate-to-high knee flexion, although edge postures remain
excluded. Under `+/-200 N`, every sampled hip angle is feasible from
`q2 = 33..100 deg`, while the low-flexion band remains the dominant exclusion.

Thus the mechanically favorable region for this frozen model is broadly the
moderate/high-knee-flexion, well-conditioned portion of the workspace under
the 120 N and 200 N component studies. The current `[45,84] deg` peak lies in
that region for 120 N and 200 N, whereas the `[5,10] deg` start lies outside
all three boxes.

The 80 N, 120 N, and 200 N component limits are engineering comparison bounds,
not clinical safety standards. These observations do not establish failure of
the single-arm architecture. Before further NMPC or controller tuning, the
next stage should first confirm trajectory strictness, permitted safety
intervention, and the intended operating envelope.

## Artifacts and reproduction

Tracked implementation and tests:

- `linkage/matlab/runners/run_single_arm_quasistatic_feasibility_atlas.m`;
- `linkage/matlab/src/single_arm_quasistatic_feasibility/`;
- `linkage/matlab/tests/quasistatic_atlas/`.

Headless command:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_single_arm_quasistatic_feasibility_atlas"
```

Generated MAT, CSV, summary, and PNG files are ignored under
`linkage/results/local/single_arm_quasistatic_feasibility_atlas/`. The output
contains the requested force-component, conditioning, feasibility,
minimum-knee-flexion, and V2-reference-overlay maps. No GIF is generated
because this is an open-loop posture scan, not a trajectory-tracking run.

## Validation

The retained regression entry reports `39 passed, 0 failed, 0 incomplete`:
the previous 33 retained tests plus six atlas tests. The new tests verify the
extended-knee rank deficiency, exact torque reconstruction and residual,
agreement of the `[5,10] deg` static force with the frozen `315.73 N`
evidence, finite nonsingular grid and bounded-solver outputs, and exact
agreement between every feasibility mask and its component box.

## Remaining uncertainties

The atlas cannot resolve the real rehabilitation posture, whether the hip and
leg are externally supported, how load is distributed by the cuff and soft
tissue, whether the patient contributes active torque, or what robot command
and measured-force modes are actually available. The allowable force and
comfort envelope is also not established by the three engineering bounds.

Before selecting the next architecture, the project still needs professor and
hardware confirmation of:

- patient posture and which body segments are supported;
- intended cuff/contact location, width, and load-transfer direction;
- whether hip fixation and a fully suspended passive leg are realistic;
- expected patient contribution and rehabilitation ROM endpoints;
- exact robot/controller identity, supported command modes, force sensing,
  update rates, and manufacturer limits.

Those answers, rather than this atlas alone, must determine whether the next
study retains one active contact, adds passive proximal support, or evaluates
another contact architecture.
