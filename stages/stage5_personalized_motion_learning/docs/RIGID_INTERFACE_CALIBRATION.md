# Stage-5 Rigid-Interface Calibration

## Status and scope

This is a provisional simulation engineering calibration, not a hardware
measurement, clinical limit, formal Stage-5 baseline, or numerical
qualification. Geometry v1 is unchanged: `T_WB`, `T_WH`, `T_EC`, the 72%
shank cuff location, and the perpendicular inverted-T interpretation remain
fixed. Human passive joint mechanics also remain `Kq=(10,10) Nm/rad` and
`Dq=(5,5) Nms/rad`. No learning, RL, controller tuning, trajectory tuning, or
new exploration threshold was introduced.

## Mechanics audit

The five mechanics layers are distinct:

1. **Human joints:** MuJoCo hip/knee joint springs and dampers use the unchanged
   Human V2 values above. These model passive joint mechanics; metallic links
   do not justify increasing them.
2. **Interface translation:** the inherited checked-in implementation is an
   objective, diagonal Kelvin--Voigt bushing expressed in the moving Human
   cuff frame. The rest translation is zero. Selected stiffness remains
   isotropic; damping is axis-specific because the audited apparent mass is
   axis-specific.
3. **Interface rotation:** an independent isotropic SO(3) rotation-vector
   Kelvin--Voigt law with zero rest rotation.
4. **MuJoCo constraints/contacts:** the donor weld retains
   `solref=(-6000,-120)` and `solimp=(0.97,0.995,0.0005)` in XML, but that weld
   is disabled for the Stage-5 bushing. Bed contact remains
   `solref=(0.020,1)` and `solimp=(0.90,0.98,0.003)`. The integrator is
   `implicitfast`.
5. **P1 mechanism:** although earlier campaign naming used “progressive”, the
   checked-in `evaluate_interface` force law is linear Kelvin--Voigt. No
   retained nonlinear or progressive spring term exists in the audited source.

## Effective mass and damping design

For each of the eight geometry-checkpoint postures, the full 8-DoF MuJoCo mass
matrix and relative site Jacobian were used:

`m_eff(a) = 1 / (aᵀ J_rel M⁻¹ J_relᵀ a)`, with
`J_rel = J_robot_cuff - J_human_cuff`.

The translational apparent-mass range was `1.173--3.486 kg`; per-axis medians
in cuff `(axial,tangential,radial)` order were
`(1.659,1.971,1.637) kg`. The rotational apparent-inertia range was
`0.04185--0.24636 kg m²`, with overall median `0.10874 kg m²`. Candidate
damping uses `zeta=0.85` and `D_i=2 zeta sqrt(K m_eff_i)`; rotational damping
uses the analogous inertia expression. Contact constraints are not folded into
this local apparent-mass formula.

## Translational candidate scale

| Kt (kN/m) | Dt axial/tangential/radial (Ns/m) | force at 0.5/1/2/5 mm (N) | deformation at 10/25/50/100 N (mm) | deformation at 200 N (mm) |
|---:|---:|---:|---:|---:|
| 2 | 97.92 / 106.73 / 97.27 | 1 / 2 / 4 / 10 | 5 / 12.5 / 25 / 50 | 100 |
| 5 | 154.82 / 168.75 / 153.80 | 2.5 / 5 / 10 / 25 | 2 / 5 / 10 / 20 | 40 |
| 10 | 218.95 / 238.65 / 217.50 | 5 / 10 / 20 / 50 | 1 / 2.5 / 5 / 10 | 20 |
| 25 | 346.19 / 377.34 / 343.90 | 12.5 / 25 / 50 / 125 | 0.4 / 1 / 2 / 4 | 8 |
| 50 | 489.59 / 533.64 / 486.35 | 25 / 50 / 100 / 250 | 0.2 / 0.5 / 1 / 2 | 4 |

Every Kt candidate was exercised in two postures, three cuff axes, both signs,
and all four translation and four rotation magnitudes: 96 probes per Kt, 480
total. All were finite and produced zero MuJoCo warnings. The 2/5 kN/m choices
remain visibly too compliant; 10 kN/m is the soft edge of the target regime.
The 50 kN/m candidate is smoke-stable but reaches the unchanged 200 N Stage-4
engineering gate at only 4 mm and has higher transient slew and timestep
sensitivity than 25 kN/m.

## Rotational candidate scale

| Kr (Nm/rad) | Dr (Nms/rad) | moment at 0.25/0.5/1/2 deg (Nm) | angle at 5 Nm (deg) |
|---:|---:|---:|---:|
| 80 | 5.014 | 0.349 / 0.698 / 1.396 / 2.793 | 3.581 |
| 160 | 7.091 | 0.698 / 1.396 / 2.793 / 5.585 | 1.790 |
| 320 | 10.028 | 1.396 / 2.793 / 5.585 / 11.170 | 0.895 |

Each rotational candidate received 48 dynamic probes. All were finite with no
MuJoCo warnings. The initial `Kr=160` replay produced about 4.76--4.89 degrees
under the observed 13--14 Nm load. The explicitly requested tightened
`Kr=320`, `Dr=10.028` pair was therefore re-run to target roughly 2--3 degrees
while retaining finite compliance. It remained finite with zero warnings.

## Timestep and ROM evidence

The shortlisted 25 and 50 kN/m candidates were run from identical 2 mm radial
and 1 degree rotational perturbations at 1.0, 0.5, and 0.25 ms.

| Kt | dt (ms) | peak force (N) | translation settle (s) | peak slew (N/s) | slew difference vs 0.25 ms | peak induced moment (Nm) |
|---:|---:|---:|---:|---:|---:|---:|
| 25 kN/m | 1.0 | 50.0 | 0.111 | 12,122 | 3.84% | 1.875 |
| 25 kN/m | 0.5 | 50.0 | 0.110 | 11,824 | 1.28% | 1.828 |
| 25 kN/m | 0.25 | 50.0 | 0.110 | 11,675 | reference | 1.806 |
| 50 kN/m | 1.0 | 100.0 | 0.0480 | 35,237 | 5.94% | 2.962 |
| 50 kN/m | 0.5 | 100.0 | 0.0505 | 33,923 | 1.99% | 2.856 |
| 50 kN/m | 0.25 | 100.0 | 0.05125 | 33,261 | reference | 2.812 |

This supports “smoke-stable” or “provisional engineering candidate”, not
“numerically qualified”. Across the eight static ROM poses, reachability was
8/8, minimum robot joint-limit margin was `51.33 deg`, minimum 6D Jacobian
singular value was `0.2274`, maximum condition number was `9.27`, minimum
robot--Human clearance was `49.0 mm`, and minimum articulated arm--bed
clearance was `118.3 mm`. For the selected 25 kN/m case, maximum cuff position
consistency error was `3.43e-10 mm`, rotation consistency error was
`2.29e-12 deg`, and preload force was `8.57e-9 N`. No frame mismatch was found.

## Frozen Stage-5 Plant v1

The selected interface is:

- `Kt=(25000,25000,25000) N/m`
- `Dt=(346.191,377.339,343.900) Ns/m`
- `Kr=320 Nm/rad`
- `Dr=10.028 Nms/rad`
- zero translational and rotational rest offsets
- nominal physics timestep `0.25 ms`

Its translational interpretation is `1 mm -> 25 N`; `50/100/150/200 N`
correspond to `2/4/6/8 mm`. The 200 N value remains only the existing Stage-4
simulation engineering gate, not a clinical, hardware-certified, or measured
tissue threshold.

`Stage-5 Plant v1` means a high-stiffness translational cuff--shank
interface, with finite rotational compliance representing a tightly strapped
but not perfectly rigid cuff. It remains a provisional engineering surrogate,
not hardware-calibrated cuff mechanics.

## Limited prescribed-trajectory replay

The selected interface was replayed with the unchanged Stage-4 model-based
MPC/CEM and Safety Filter/BRAKE, an ideal 200 Hz measurement case, 5 ms control
period, and 0.25 ms physics timestep. The registered Stage-5 model was fixed;
geometry and dynamic estimator accepted/rejected update counts were all zero.

| replay | progress | tracking RMSE hip/knee (deg) | force integral (N s) | peak force (N) | peak slew (N/s) | peak moment (Nm) | peak translation (mm) | peak rotation (deg) | SF/BRAKE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cold-start prefix to 20/35 deg, 6.5 s | 100% | 1.65 / 3.62 | 577.73 | 111.56 | 17,603 | 13.57 | 4.460 | 2.426 | 1300 unchanged / 0 brake |
| teaching prefix through 38/80 deg hold, 9.5 s | 100% | 1.36 / 2.91 | 948.58 | 121.90 | 17,603 | 14.13 | 4.867 | 2.518 | 1900 unchanged / 0 brake |

Both limited replays completed with no force-gate event, BRAKE transition,
nonfinite state, or MuJoCo warning. These forces and tracking errors are
observed engineering results, not a success qualification; no parameters were
tuned to improve them.

## Unresolved hardware calibration

The physical cuff material stack, fastener/joint compliance, load path,
directional stiffness, damping, hysteresis, backlash, slip, rate dependence,
mount compliance, actual effective mass/inertia, sensor alignment/bias, and
safe hardware operating envelope remain unmeasured. Those quantities must
replace this provisional calibration before any hardware or clinical claim.

Machine-readable details and all individual probes are in
`results/rigid_interface_calibration/calibration_report.json`; replay summaries
and traces are in its `baseline_replay/` subdirectory.
