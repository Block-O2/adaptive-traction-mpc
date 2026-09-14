# Stage-5 Geometry and Mechanics Report

Status: **provisional engineering/smoke validation only**. The dimensions and
mechanical values below are not measured calibration, strict numerical
qualification, hardware validation, or clinical evidence.

## Baseline audit

The audited Stage-3/Stage-4 plant is a torque-actuated UR10e surrogate coupled
to planar Human V2. The important existing mechanisms are distinct:

| Mechanism | Existing definition | Physical meaning in this task |
|---|---:|---|
| Human joint passive spring | `Kq=(10,10) Nm/rad` | Joint resistance about hip/knee; not attachment rigidity. |
| Human joint passive damper | `Dq=(5,5) Nms/rad` | Joint viscous resistance; not cuff damping. |
| P1 interface translation | `Kt=500 I N/m`, `Dt=35.6390267653 I Ns/m` | Kelvin--Voigt attachment deformation; the direct target for the stiffer surrogate. |
| P1 interface rotation | `Kr=20 Nm/rad`, `Dr=1 Nms/rad` | Isotropic cuff orientation compliance; also changed in Stage 5. |
| Rigid cuff equality | `solref=(-6000,-120)`, `solimp=(0.97,0.995,0.0005)` | MuJoCo constraint realization for the rigid-weld plant; not P1 material stiffness. |
| Human--bed contact | `solref=(0.020,1)`, `solimp=(0.90,0.98,0.003)` | Unilateral bed/contact compliance; unchanged. |

The existing `WORLD_FROM_BASE` translation is `(1.10,-0.62,0.04) m`.
With the nominal straight-leg dimensions this longitudinal coordinate lies
beyond the modeled ankle rather than near the upper-middle shank. Human V2
places the cuff at 90% of shank length (`0.360684 m` from the knee), which is
too distal for the requested mid-lower placement.

Stage 3 keeps historical `ATTACHMENT_FROM_CUFF=identity`; the High-ROM path
opts into a 140 mm `+Y` standoff. The 140 mm value is derived from registered
surrogate wrist/cuff/shank geometry, not measured CR12 hardware. Existing
Human cuff axes already give `+X` along the shank, `+Y` lateral/tangential, and
`+Z` radial in the sagittal plane. Stage 5 reuses that convention and makes the
perpendicular bar/stem relationship explicit.

The reusable components are the UR10e model/FK/Jacobian/IK residual, Human V2
link and joint dynamics, Kelvin--Voigt interface evaluation and virtual-work
wrench reconstruction, contact-domain separation, and the existing Stage-4
executable screening/Safety Filter/BRAKE interfaces. Stage 5 does not copy or
edit the Stage-4 controller or its evidence.

The focused audit covered `stage3_full3d` frame, cuff-adapter, Human V2,
coupled-plant, compliant-interface, IK, robot-core, and executable-command
sources/tests; and the Stage-4 current-state record, registered P1 parameter
specification, physical-force contract, control-velocity regression, Safety
Filter tests, and BRAKE tests.

## Provisional Stage-5 geometry

Transform notation is `T_PARENT_CHILD`; it maps coordinates from the child
frame into the parent frame.

| Transform/parameter | Stage-5 v1 value |
|---|---|
| `T_WB` | `R=I`, `t=(0.600,-0.620,0.040) m` |
| `T_WH` | `R=I`, `t=(0,0,0.062) m` |
| `T_EC` rotation | `RotX(+90 deg) = [[1,0,0],[0,0,-1],[0,1,0]]` |
| `T_EC` translation | `(0,0.140,0) m` in `E` |
| Base longitudinal alignment | 40.70% of shank length from knee in the neutral layout |
| Cuff center | 72% of shank length = `0.2885472 m` from knee |
| Visual cuff bar | 80 mm long, 12 mm radius; provisional and visual-only |

Frame `C` uses `+X` along the shank and cuff bar, `+Y` tangential, and `+Z`
radial/principal contact-force direction. The terminal/stem `E +Y` axis maps
to `C -Z`, so the stem approaches radially from above and the bar is exactly
perpendicular. This roll is mechanically material: the initially considered
identity orientation admitted IK branches whose wrist/forearm passed through
the table. The final transform retains the 140 mm length while selecting an
above-table continuous branch.

## Geometry sanity results

The deterministic Stage-5 script evaluated eight Human postures spanning the
current Human V2 ROM and one deliberately uncoordinated edge posture:

| `q1/q2` deg | min singular value | condition number | joint-limit margin | arm--Human clearance | articulated arm--bed clearance |
|---:|---:|---:|---:|---:|---:|
| 0 / 5 | 0.3116 | 6.12 | 51.3 deg | 49.0 mm | 118.3 mm |
| 5 / 10 | 0.3134 | 6.08 | 52.0 deg | 49.0 mm | 131.0 mm |
| 20 / 35 | 0.3138 | 6.07 | 53.5 deg | 49.0 mm | 131.0 mm |
| 40 / 60 | 0.3082 | 6.21 | 56.8 deg | 49.0 mm | 131.0 mm |
| 45 / 84 | 0.3075 | 6.25 | 52.9 deg | 49.0 mm | 131.0 mm |
| 60 / 90 | 0.3096 | 6.29 | 59.3 deg | 49.0 mm | 131.0 mm |
| 80 / 100 | 0.3222 | 6.21 | 70.0 deg | 49.0 mm | 131.0 mm |
| 80 / 20 | 0.2274 | 9.27 | 114.9 deg | 49.0 mm | 131.0 mm |

All eight full-pose IK residuals were below `1e-8`; no active robot
self-contact pair was observed. Clearances exclude the intentional visual
cuff/stem geometry and separate the articulated arm from the donor
base/shoulder mounting geometry. They are sampled-posture, surrogate-geometry
checks, not a continuous swept-volume proof or CR12 collision validation.

## Stage-5 interface mechanics

Stage 5 changes only the P1-style attachment interface in this checkpoint:

| Parameter | Stage-4 P1 reference | Stage-5 v1 |
|---|---:|---:|
| Translational stiffness | `500 I N/m` | `2000 I N/m` |
| Translational damping | `35.6390268 I Ns/m` | `71.2780535 I Ns/m` |
| Rotational stiffness | `20 Nm/rad` | `80 Nm/rad` |
| Rotational damping | `1 Nms/rad` | `2 Nms/rad` |

Stiffness is increased 4x and damping 2x. Under the same effective-mass
assumption, this preserves the previous damping ratio because critical damping
scales with `sqrt(K)`. This is an engineering scaling rule, not an identified
material model.

Static checks give:

- 1 mm translation: `0.5 N` in P1 versus `2.0 N` in Stage 5.
- 10 mm/s translation: `0.356 N` damping force versus `0.713 N`.
- 1 degree rotation: `0.349 Nm` versus `1.396 Nm`.
- deformation under 10/50/100 N: P1 `20/100/200 mm`; Stage 5
  `5/25/50 mm` for each isotropic axis.

The short 50 ms full-plant perturbation probe realized an initial radial
deformation of `0.99985 mm`. At 1.0/0.5/0.25 ms, peak force was
`32.340/32.540/32.405 N`, final deformation was
`8.581/8.596/8.552 mm`, every state stayed finite, and MuJoCo emitted no
warning. The probe includes coupled Human/robot motion and robot gravity-bias
torque, so its peak is not the isolated 1 mm static response. The maximum peak
force difference from the 0.25 ms trace was `0.134 N` in this short case.
These observations support using 0.25 ms as the conservative Stage-5 nominal
step, but do not establish strict convergence or numerical qualification.

Human passive joint parameters, rigid-weld solver parameters, bed contact,
controller gains, costs, constraints, optimizer, and the Stage-4 200 N
engineering target were not changed.

## Visual engineering checks

- [Top view](../results/geometry_mechanics_validation_v1/top_view_stage5_geometry.png)
- [Inverted-T cuff close-up](../results/geometry_mechanics_validation_v1/inverted_t_cuff_closeup.png)
- [Machine-readable validation](../results/geometry_mechanics_validation_v1/validation_report.json)

## Future exploration hooks

`ExplorationSafetyObservation` reserves explicit inputs for physical cuff
force, force slew, interface deformation, cuff position/rotation error,
executable-screening status, Safety-Filter status, and BRAKE status. It makes
no control decision and defines no new threshold. Future exploration should
begin with small ROM, low speed, and small perturbations, with clearly bad
motions rejected or stopped by a separately approved supervisory design.

## Unresolved measurements and calibration

- measured `T_WB`, `T_WH`, and their uncertainty on the actual table;
- actual thigh/shank lengths, radii, joint-axis locations, and cuff center;
- CR12 flange convention, adapter length, bar size, and registered `T_EC`;
- attachment preload, anisotropic translational/rotational stiffness,
  damping, effective mass, hysteresis, friction, and rate dependence;
- continuous collision meshes and clearances for the real robot, table, leg,
  fixture, cables, and operator space;
- timestep/solver qualification under the eventual Stage-5 closed-loop task;
- a separately reviewed exploration-stop policy and any lower Stage-5
  supervisory threshold.
