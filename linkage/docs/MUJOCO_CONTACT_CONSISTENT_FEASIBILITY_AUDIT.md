# MuJoCo Contact-Consistent Feasibility Audit

## Question and scope

This offline mechanics diagnostic asks whether the frozen MuJoCo plant admits
a physically consistent support bridge from its measured near-extension rest
state into a region where the bilateral point sleeve can carry the nominal
Human V2 quasistatic load within the existing 200 N interaction gate.

The baseline is `agent/mujoco-sleeve-robot-v2` (`9d082c3`, Draft PR #22).
The CR12-like 6-DoF robot, Human V2 parameters, bilateral point sleeve,
unilateral compliant bed, and force limits are unchanged. No dynamic takeoff,
normal controller, handoff, Windowed NLS, R3C, or recovery logic is run.

This is simulation mechanics evidence, not a hardware or clinical claim.

## Candidate geometry and normal convention

The supplied candidate is

\[
q_1(q_2)=\operatorname{atan2}\!\left(
L_2\sin q_2,\;L_1+L_2\cos q_2\right).
\]

For each capsule point, the audit defines the world-up surface gap

\[
g=z_{center}-r-z_{bed}.
\]

Therefore `gdot > 0` is separating and forces `lambda=0`; `gdot = 0` can
admit a nonnegative normal reaction; `gdot < 0` requires motion into the bed
and invalidates that posture/path. MuJoCo reports compressive contact force in
contact-frame component zero, but geom ordering can change its world sign, so
the audit does not infer normal direction from array order. It uses the
explicit world-up gap and force.

With physical upward bed force, equilibrium is

\[
\tau_{req}=J_s^T F_{robot}+\sum_iJ_{point,i}^T n_{up}\lambda_i.
\]

This is the prompt's minus-sum form with the inward penetration Jacobian
`J_b=-J_point`.

## Nominal generalized load

The primary load is the retained complete Human V2 quasistatic formulation at
zero velocity:

\[
\tau_{req}=G(q)+K_{passive}(q-q_{rest})-\tau_{soft,rhs}(q).
\]

The cubic 5-degree soft-limit torque and its registered 25 Nm boundary value
are included. This matters near extension. The PR #22 MJCF joints reproduce
gravity plus linear spring/damping, but do not implement this cubic soft-limit
term. At the 5-degree audit posture, the analytic gravity-plus-linear-passive
load agrees with MuJoCo `qfrc_bias-qfrc_passive` to `4.33e-12 Nm`; the soft
term is then added from the retained Human V2 formulation as required by this
audit. A later dynamic study must resolve this MJCF/source-model mismatch
explicitly rather than silently changing the audit load.

For each contact mode, a constrained quadratic solve minimizes
`||F_robot||` subject to exact generalized equilibrium and `lambda_i >= 0`.
Feasibility additionally requires both Cartesian components and the force norm
to remain within 200 N. Matrix rank alone is not a feasibility result.

## Measured rest and contact entry

The unchanged plant settles at

- `q=[-0.004627, 0.713027] deg`;
- bed force `62.962 N`;
- sleeve force `4.101 N`.

At the same measured q2, the candidate formula gives `q1=0.341140 deg`, an
offset of `0.345768 deg` from measured q1. The measured compliant rest has
distal thigh and distal shank bed contact, but the candidate path tangent makes
the distal thigh and all interior thigh points separate. The distal shank
surface also separates (`gdot=+1.57e-5 m/rad` at measured rest), so its normal
reaction must be zero for the candidate motion. Only the proximal thigh/hip
point remains kinematically maintained, and its generalized-force direction
is exactly `[0,0]` because the hip point is fixed.

On the ideal candidate path itself:

- it never requires penetration, so it is contact-kinematically valid;
- all non-proximal thigh points separate at q2=0 and are geometrically above
  the bed for q2>0;
- the smaller shank capsule radius leaves every shank support point 5 mm above
  the bed along the formula-defined ankle-center geometry;
- the only maintained bed point remains the zero-moment proximal thigh point.

Thus the admissible augmented map has the same rank and force authority as the
robot-only sleeve map. Adding quarter-point capsule samples at
`q2=0/rest/5/10/20 deg` produces exactly the same minimum robot forces and
contact classification as the endpoint catalog.

## Results

| q2 | q1 on path | robot / augmented rank | minimum robot force `[Fx,Fz]` N | norm / reserve | admissible bed reaction | classification |
|---:|---:|:---:|---:|---:|---:|---|
| 0.000° | 0.000° | 1 / 1 | no exact force; residual 25.20 Nm | -- | proximal thigh 0 N | rank/unilateral incompatible |
| 0.713° | 0.341° | 2 / 2 | `[6550.68, 26.75]` | 6550.74 / −6350.74 N | proximal thigh 0 N | force-limit infeasible |
| 2.250° | 1.076° | 2 / 2 | `[64.52, 35.06]` | 73.43 / +126.57 N | proximal thigh 0 N | nominal robot-only feasible |
| 2.500° | 1.196° | 2 / 2 | `[−124.24, 36.22]` | 129.41 / +70.59 N | proximal thigh 0 N | nominal robot-only feasible |
| 5.000° | 2.392° | 2 / 2 | `[−469.55, 44.90]` | 471.69 / −271.69 N | proximal thigh 0 N | force-limit infeasible |
| 10.000° | 4.784° | 2 / 2 | `[−311.47, 49.53]` | 315.39 / −115.39 N | proximal thigh 0 N | force-limit infeasible |
| 15.000° | 7.175° | 2 / 2 | `[−227.58, 49.93]` | 232.99 / −32.99 N | proximal thigh 0 N | force-limit infeasible |
| 19.000° | 9.087° | 2 / 2 | `[−192.14, 50.25]` | 198.60 / +1.40 N | proximal thigh 0 N | robot-only feasible |
| 20.000° | 9.564° | 2 / 2 | `[−185.48, 50.33]` | 192.19 / +7.81 N | proximal thigh 0 N | robot-only feasible |

Within the 0--25 degree scan, refined 200 N crossings give two nominal
force-feasible intervals:

- `[2.1162, 2.6261] deg`: a narrow soft-limit/load-cancellation island;
- `[18.7948, 25] deg`: the persistent feasible interval through the scan end.

The first island is not a continuous bridge from rest. The interval from the
measured resting q2 (`0.7130 deg`) to `2.1162 deg` is already infeasible, and
the path becomes infeasible again from `2.6261` to `18.7948 deg`. It must not
be interpreted as a robust threshold or a usable handoff merely because the
nominal force cancels over a narrow range.

## Classification

`SUPPORT_AUTHORITY_GAP`

The candidate geometry itself is nonpenetrating, but motion-consistent bed
contacts provide no nonzero generalized-force direction. Consequently there
is no contact-assisted feasible interval continuous from measured rest and no
overlap that connects bed support to persistent robot-only feasibility.

The distal shank contact would be mechanically valuable: near rest its upward
normal direction maps approximately to `[+0.838, -0.401] Nm/N`, including a q2
component. In the frozen geometry/path it is separating at measured rest and
then 5 mm clear of the bed, so unilateral mechanics forbid using that reaction.
The distal thigh direction supplies q1 moment only and is also separating.

This audit therefore does not support advancing the current point-sleeve plant
directly to dynamic bridge validation. Before another takeoff, the project must
establish whether the real sleeve transmits a moment, whether there is a second
mechanical attachment/support channel, or whether a different contact-consistent
path can retain a physically available distal support. The MuJoCo plant must
also explicitly reconcile the retained Human V2 soft-limit torque before a
source-faithful dynamic comparison.

## Reproduction and evidence

```bash
conda run -n mpc_learn python \
  scripts/run_mujoco_contact_feasibility_audit.py \
  --output-dir linkage/results/mujoco_contact_consistent_feasibility_audit
```

- [summary.json](../results/mujoco_contact_consistent_feasibility_audit/summary.json)
- [posture_feasibility.csv](../results/mujoco_contact_consistent_feasibility_audit/posture_feasibility.csv)
- [force/rank/feasibility timeline](../results/mujoco_contact_consistent_feasibility_audit/force_rank_feasibility_timeline.png)
- [force margin/contact mode](../results/mujoco_contact_consistent_feasibility_audit/force_margin_contact_mode.png)
