# Hybrid Tube Force Controller V1

## Status and scope

This stage implements the first task-level closed-loop formulation around the
retained Human Model V2 and single-arm equilibrium endpoint-force controller.
The rehabilitation task is represented as a frozen geometric path, flexible
monotone timing, a configurable joint-space tube, and a terminal task set.

This implementation does not add bed contact, load transfer, CBF, NMPC, a
complete safety supervisor, a second contact, or a real robot model. The
80/120/200 N component bounds and 0/5/10 degree tube caps are engineering
sensitivity cases, not clinical safety limits or clinical tolerances.

The full 12-case dynamic matrix is a formal scientific run and remains pending
user execution under the repository research policy. Consequently, this
tracked report records the implemented contract and mechanical validation; it
does not promote unrun dynamic metrics, GIFs, or terminal classifications as
formal evidence.

## Frozen task and governed reference

The existing `slow_passive_flexion_v2` reference is unchanged. It is
reparameterized by (s\in[0,1]):

\[
q_{\mathrm{path}}(s)=q_{\mathrm{V2}}(16s),\quad
q_s=16\dot q_{\mathrm{V2}},\quad
q_{ss}=16^2\ddot q_{\mathrm{V2}}.
\]

Progress is monotone and cannot reverse. The reference manager produces

\[
q_g=q_g(s),\qquad
\dot q_g=q_{g,s}\dot s,\qquad
\ddot q_g=q_{g,ss}\dot s^2+q_{g,s}\ddot s,
\]

so governed position, velocity, and acceleration are derived from one spatial
trajectory rather than independently switched references. A jerk-limited
progress governor slows or pauses as predicted force utilization approaches
the selected component bound.

The component-wise task tube is

\[
|q_{g,i}(s)-q_{\mathrm{path},i}(s)|\leq\delta_i(s).
\]

Its quintic schedule varies continuously with the frozen path's knee-flexion
region. It is narrow through ordinary flexion and expands smoothly around the
repeated low-flexion endpoint region. A zero-degree cap exactly recovers the
frozen geometric path. Cubic spatial interpolation is contracted against a
dense tube check to prevent between-node overshoot.

## Force-aware spatial plan

At deterministic progress nodes, the manager enumerates allowed hip/knee
offsets and evaluates the retained quasistatic force map. Its normalized cost
contains:

- geometric path deviation;
- axial force (F_{\mathrm{parallel}}^2);
- total force norm;
- force change and posture-change smoothness;
- ROM/soft-limit margin.

Nominal progress rate supplies the progress-loss preference in the temporal
governor. Exact force-box feasibility is preferred before cost ranking;
infeasible candidates retain their deterministic bounded torque residual and
are not represented as exact solutions. Candidate postures outside ROM or in
an active soft-limit zone are rejected. This prevents an apparently low axial
force obtained through unbounded perpendicular force or hidden boundary
penetration.

The retained controller then maps the governed reference to a bounded local
contact force

\[
u=[F_{\mathrm{parallel}},F_{\mathrm{perp}}]^\mathsf{T},\qquad
\tau_{\mathrm{contact}}=A(q)u,
\]

with the existing deterministic two-dimensional box solver and explicit force
slew bounds. Human Model V2, its passive model, contact position, force map,
and equilibrium-controller gains are unchanged.

The simulated plant always starts at the frozen V2 start posture rather than
being silently pre-positioned at a lower-force point inside a wider tube. This
preserves the known approximately 315.73 N quasistatic start demand. If that
initial suspended posture is infeasible under a selected force box, the
manager must report it; the tube is not permission to hide an unmodeled setup
or support phase.

## Terminal and failure contract

- `TASK_COMPLETE`: (s=1), the measured posture is inside the terminal tube,
  and the current posture has an exact bounded holding solution.
- `TRANSFER_REQUIRED`: progress cannot continue, but the present posture can
  be held within the configured force bound.
- `INFEASIBLE`: the present posture itself lacks an exact bounded holding
  solution.

V1 implements neither retreat nor external support. It validates only a
suspended single-contact task ending in the existing V2 terminal region. It
does not claim safe achievement of (q_2=0); the structural rank loss at
(q_2=0) remains. If full lowering requires external load transfer, that
contact must be modeled in a later stage.

## Comparison matrix and recorded metrics

The formal runner compares the current strict time-indexed V2 closed loop and
tube caps 0, 5, and 10 degrees at each of the 80, 120, and 200 N component
bounds. It records completion state/time, final progress, terminal and maximum
path deviation, component/total force and force rate, force RMS, ROM margin,
soft-limit activity, mapping conditioning, torque residual, slowdown/pause
duration, force-aware-deviation duration, and controller feasibility.

The formal command is intentionally reserved for the user:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_hybrid_tube_force_controller_v1"
```

It writes MAT/CSV/text, five static comparison figures, and representative
80/120/200 N GIFs under the ignored directory:

```text
linkage/results/local/hybrid_tube_force_controller_v1/
```

No tracked report should be updated with those dynamic results until the
formal output has been reviewed.

## Mechanical validation

The retained regression entry checks monotone bounded progress, exact recovery
of the frozen path at a zero-degree cap, continuous tube containment,
finite/continuous spatial derivatives, explicit force/residual consistency,
terminal classification, ROM and soft-limit exclusion, reproduction of the
approximately 315.73 N strict static start demand, and the lower-force
direction of the wider tube at that endpoint.

These checks establish implementation contracts only. Whether flexible timing
is materially used, whether the PR #12 quasistatic reduction survives the full
dynamic closed loop, whether any case seeks a hip boundary, and the final
classification of all 12 cases remain formal-run questions.
