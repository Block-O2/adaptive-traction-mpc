# V2 High-ROM Mechanics Boundary

Status: mechanics characterized before Phase-2 outcomes.

## Verified plant envelope

The unchanged verified Human-V2 plant registers hard joint limits of
`q1 in [0,80] deg` and `q2 in [0,100] deg`, with a 5 deg cubic soft-limit
layer. Therefore 120--130 deg on either joint is outside this plant contract.
Testing it would require a separately versioned Human model and cannot be
created by disabling the current limits.

The unexecuted suspended Phase-2 V1 preregistration used:

- q1 goal: 66--75 deg;
- q2 goal: 82--95 deg;
- eight of 24 proposed held-out cases, with two cases in each task profile.

This enters the upper soft-limit neighborhood without crossing the registered
hard limit. It is the maximum defensible target envelope for the present plant,
not a clinical ROM claim. The V1 formal study was not run and therefore does
not validate that envelope.

## Table/contact boundary

The unexecuted Phase-2 V1 benchmark is explicitly suspended and planar. Later
development added only an analytical shank capsule against a flat bed
(`bed z=0.012 m`, shank radius `0.045 m`); it is not a contact-dynamics, thigh,
cuff, or robot-collision model. Using that limited mechanics model:

- a dense grid over the high-goal box, full height range 0.88--1.12, and the
  minimum declared hip height gives a minimum geometric shank clearance of
  `0.16824 m` at height scale 0.88, q=`[66,95] deg`;
- the full Cartesian product of the initial-state and placement ranges is not
  a valid lying-bed family: the worst analytical initial clearance is
  `-0.12900 m` at height scale 1.12, minimum hip height, q=`[6,28] deg`.

Thus the suspended Phase-2 domain must not be reinterpreted as a lying-bed
contact validation. A conditioned lying-bed development family required
reference clearance >= `0.01 m`, static force <= `150 N`, and static moment <=
`45 Nm`. In `bed_feasible_development_v4`, all three high-ROM cases completed
for adaptive and oracle with zero analytical shank-bed clearance events. This
is development evidence only; a formal bed-valid held-out study was not frozen
or run. Subject-specific full shank length remains simulation truth for this
evaluation because V1 showed it cannot be split from cuff fraction using cuff
kinematics alone; it is not consumed by the deployable controller.

## Historical 120-degree evidence

Historical corrected 40/80, 90/120, and 120/120 artifacts use a separately
labelled suspended high-ROM engineering model and fixed/model-specific
execution stack. They are preserved as engineering diagnostics, not promoted
to hidden-setup adaptive evidence. In particular, the retained mechanism audit
reports `FILTER_INFEASIBLE` at 40/80 and 120/120 and a path-dependent safe
90/120 comparison; larger ROM alone did not determine feasibility.

## Fresh V2.2 formal result

The fresh V2.2 held-out matrix subsequently executed 12 high-ROM cases with
goal q1 `66.244--74.175 deg` and q2 `82.234--94.575 deg`. V2.2 and oracle both
completed all 12 with zero registered ROM and analytical shank/flat-bed
clearance events. This formally validates the preregistered high-ROM subset in
simulation under the current reduced mechanics contract; it does not expand
the plant ROM or hardware claim.

## Claim boundary

V2.2 has fresh formal held-out evidence up to sampled goals `74.175/94.575 deg`
inside the declared `75/95 deg` envelope. It cannot claim 120--130 deg support,
lying-bed validity outside the conditioned family, contact dynamics,
thigh/cuff collision safety, CR12 reachability, physical cuff safety, or
clinical suitability.
