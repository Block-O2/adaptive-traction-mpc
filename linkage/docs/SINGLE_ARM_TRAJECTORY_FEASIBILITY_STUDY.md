# Single-Arm Trajectory Feasibility Study

## Scope

This study is an open-loop inverse-dynamics and contact-force preflight. It does not run trajectory tracking, modify the frozen Human Model V2 or single-arm equilibrium baseline, or test NMPC. The nominal V2 patient parameters and the existing distal shank contact position `sc = 0.90 L2` are used throughout.

The reported forces are ideal two-dimensional cuff forces. They are diagnostic consequences of the stated model and support assumptions, not clinical force requirements or hardware safety limits.

## 1. Trajectory source audit

### Current Human Model V2 trajectory

The implemented `slow_passive_flexion_v2` reference was confirmed to use:

- `q_start = [5; 10] deg` and `q_peak = [45; 84] deg`;
- one shared quintic/minimum-jerk progress variable for both joints;
- a fixed-ratio straight line in joint space during flexion and return; and
- a 16 s hold-flex-hold-return-hold schedule.

Its original purpose is Human Model V2 plant/reference and exact-model oracle validation. It was not designed using single-contact force, contact-map conditioning, or human-interface-force criteria. It is therefore a contact-independent joint-space validation trajectory.

### Professor reference trajectory

The preserved source `linkage/matlab/reference/professor_original/singleArmDual.m` was read only. Its SHA-256 remained `b8c95ab1df3507efd610a3a72057e31a33724626d37341bd5d5a4abaa833c19f`.

The actual reference equations are

```text
q1(t) = 32.5 deg [1 - cos(2 pi 0.2 t)]
q2(t) = 35.0 deg [1 - cos(2 pi 0.2 t)]
```

Thus the reference begins at `[0; 0] deg`, reaches `[65; 70] deg`, has frequency 0.2 Hz and period 5 s, and is evaluated for 12 s. The 12 s endpoint is not a cycle boundary and is approximately `[58.79; 63.31] deg`.

The reference-coordinate conversion is unambiguous: the professor source explicitly defines `q1` as the absolute thigh angle, positive `q2` as knee flexion, and the shank absolute angle as `q1-q2`, matching Human Model V2. The resulting V2 calculation is nevertheless labeled **translated professor trajectory diagnostic** because the plant and actuation assumptions are not the professor experiment. The original source includes two normal contact-force points at `0.55 L1` and `0.50 L2`, direct computed joint torque, safety torque, force clipping, and hard angle/velocity clipping. Its coded gravity term is included in the control torque and subtracted in forward dynamics, giving coded gravity cancellation.

## 2. Coordinates, force names, and equations

The verified coordinates are

```text
q1 = absolute thigh angle
q2 = positive knee-flexion angle
shank angle = q1 - q2
```

At each prescribed trajectory sample, the required generalized torque is

```text
tau_required = M(q) ddq + h(q,dq) + G(q) + tau_passive_left(q,dq)
```

The static and dynamic parts are defined consistently as

```text
tau_static  = G(q) + tau_passive_left(q,0)
tau_dynamic = tau_required - tau_static
```

The local contact components are named `F_parallel` along the shank axis and `F_perp` perpendicular to it. With `R=[parallel, perpendicular]`,

```text
F_world = R(q) [F_parallel; F_perp]
tau_contact = Jc(q)' F_world = A(q) [F_parallel; F_perp]
```

For the current contact kinematics,

```text
A(q) = [ -L1 sin(q2),  L1 cos(q2) + sc
                    0,              -sc ]
det(A) = L1 sc sin(q2)
```

Consequently, the two-dimensional map is full rank for `sin(q2) != 0`, but it loses rank at an extended knee (`q2=0`). In a full-rank posture, the two contact components can realize two generalized torques, but the square map leaves no redundant force direction with which to reduce interface force while preserving an arbitrarily prescribed torque pair.

The analysis records `q`, `dq`, `ddq`, required/static/dynamic torque, local and world force, singular values, condition number, determinant, and the following torque sources separately: gravity, passive stiffness/damping/soft limit, inertial plus Coriolis, parallel-force contribution, and perpendicular-force contribution.

## 3. Three diagnostic trajectories

### A. Current V2

The frozen 16 s trajectory is used without modification.

### B. Translated professor trajectory

The analytic professor reference, including analytic velocity, acceleration, and jerk, is evaluated with the nominal Human Model V2 and its distal single contact. This is not a reproduction of the professor experiment because the original two contact points, direct joint torque, and gravity-cancellation structure are deliberately absent from this preflight.

### C. Minimal force-aware candidate

A fixed, deterministic 27-candidate grid searched a single smooth intermediate waypoint:

- waypoint hip angle: `{5, 8, 12} deg`;
- waypoint knee angle: `{35, 45, 55} deg`; and
- first outbound phase duration: `{2.8, 3.2, 3.6} s`.

All candidates use quintic segments, exactly preserve the current start `[5;10] deg`, peak `[45;84] deg`, total duration 16 s, and 1 s peak hold, and remain continuous through `q`, `dq`, and `ddq`. Candidates must satisfy V2 ROM, reach the unchanged peak, `max|dq| <= 0.40 rad/s`, and `max|ddq| <= 1.5 rad/s^2`. The objective includes peak `|F_parallel|`, peak force norm, force RMS, a low-`sigma_min(A)` penalty, velocity, acceleration, jerk, and peak-target error. This small search cannot exploit fast inertial cancellation.

The selected diagnostic candidate uses waypoint `[8;45] deg`, a 3.6 s knee-first stage, a 3.9 s coordinated stage, and the symmetric return. It is an engineering diagnostic, not a clinically validated trajectory.

## 4. Unified numerical results

| Metric | Current V2 | Professor translated | Force-aware candidate |
|---|---:|---:|---:|
| peak force norm (N) | 316.551 | 7.1723e7* | 316.385 |
| peak `|F_parallel|` (N) | 315.862 | 7.1723e7* | 315.704 |
| peak `|F_perp|` (N) | 21.444 | 96.122 | 21.653 |
| force RMS (N) | 198.090 | 2.1522e6* | 160.076 |
| peak `|Fy_world|` (N) | 48.878 | 86.230 | 77.736 |
| peak `|Fx_world|` (N) | 312.822 | 7.1723e7* | 312.656 |
| min `sigma_min(A)` | 0.031378 | 0 | 0.031378 |
| max `cond(A)` | 27.791 | Inf | 27.791 |
| peak `|tau_hip|` (N m) | 42.025 | 45.078 | 41.306 |
| peak `|tau_knee|` (N m) | 7.734 | 34.670 | 7.810 |
| peak static torque norm (N m) | 41.369 | 41.804 | 41.220 |
| peak dynamic torque norm (N m) | 2.126 | 5.294 | 2.273 |
| max `|dq|` (rad/s) | 0.3726 | 0.7676 | 0.3272 |
| max `|ddq|` (rad/s2) | 0.1765 | 0.9646 | 0.2721 |
| max `|jerk|` (rad/s3) | 0.2822 | 1.2122 | 0.7856 |
| target ROM reached | yes | yes | yes |

\* The professor diagnostic passes exactly through `q2=0`, where `A` is rank deficient. Three sampled points are exactly rank deficient and 83 have `sigma_min(A)<1e-4`. The displayed `7.1723e7 N` is the largest finite value on the `dt=0.002 s` grid at `q2=0.0001105 deg`; it is discretization-dependent evidence of divergence near the singularity, not a meaningful finite force requirement. At the exact singular samples the prescribed torque pair is not exactly realizable; the maximum pseudoinverse solve residual is 24.895 N m.

## 5. Peak-force explanation and torque decomposition

For Current V2, peak force occurs at `t=1.264 s` and `q2=10.0466 deg`. The peak local components are approximately `F_parallel=-315.862 N` and `F_perp=20.879 N`. At that frame, the static and dynamic parallel-force contributions are `-313.879 N` and `-1.983 N`, respectively; approximately 99.4% of the peak parallel component comes from the static term. Across the trajectory, peak static generalized-torque norm is 41.369 N m while peak dynamic norm is only 2.126 N m.

For the force-aware candidate, peak force occurs at `t=0.192 s` and `q2=10.0489 deg`. Its static and dynamic parallel-force contributions are `-313.790 N` and `-1.914 N`. The candidate therefore inherits essentially the same low-flexion static lower bound as Current V2.

For the translated professor trajectory, the finite-grid force peak occurs at `t=9.998 s`, just before exact extension, and `q2=0.0001105 deg`. The parallel solution is dominated by the singular amplification of static demand; the exact extended-knee samples are rank deficient rather than high-but-finite force solutions.

The decomposition plots show that the required torque is dominated by gravity plus passive resistance for the two slow V2 trajectories. Inertial and Coriolis torque is comparatively small. Large axial force is therefore not being created primarily by aggressive trajectory acceleration.

## 6. Structural interpretation

The results directly support the following bounded conclusions:

- Current V2 is a contact-independent joint-space validation trajectory.
- The translated professor reference has a more severe near-extension problem under the current **single distal contact plus Human Model V2** assumptions because it repeatedly reaches `q2=0`.
- A single distal two-dimensional contact can realize both generalized torques in full-rank regions, but the square map provides no contact-force-direction redundancy for a fixed prescribed double-joint trajectory.
- As knee flexion approaches zero, `det(A)=L1 sc sin(q2)` approaches zero, `sigma_min(A)` collapses, and the required parallel force is amplified.
- For Current V2, the dynamic demand is much smaller than the static demand.

These results do not establish that all single-arm rehabilitation robots are infeasible, that every taught trajectory has the same issue, that the professor approach is wrong, that 300 N is clinically necessary, or that single-arm systems are categorically inferior to dual-arm systems.

## 7. Did the force-aware trajectory improve feasibility?

Only partially. Relative to Current V2, the selected candidate reduces force RMS from 198.090 N to 160.076 N, a 19.2% reduction in exposure. It does **not** significantly reduce peak force: 316.551 N to 316.385 N, only 0.052%.

The reason is structural within the imposed design constraints. Both trajectories must begin and end at `[5;10] deg`, so both retain the same poorly conditioned low-knee-flexion static state. Moving the knee first avoids spending as much of the interior trajectory in higher-force configurations, but it cannot remove the endpoint peak without changing the endpoint posture, support assumptions, contact geometry, or required static generalized torque.

Thus force-aware joint-space timing and waypoints can reduce RMS demand, but this small admissible design family cannot remove the approximately 316 N peak while preserving the exact current endpoints and unsupported passive-leg assumptions.

## 8. Remaining uncertainties

- The current diagnostic assumes a fully passive leg, fixed hip, no bed or limb support, no active patient torque, one ideal distal planar contact, and no robot or soft-tissue interface dynamics.
- The professor coordinate translation is clear, but its trajectory was not designed for the present V2 plant or single-contact authority; comparison is diagnostic only.
- The fixed 27-point candidate grid is intentionally small and does not prove global trajectory optimality.
- The allowed endpoint constraint fixes the low-flexion static peak. This study does not test whether clinically acceptable endpoint changes are available.
- No real robot command mode, force limit, comfort model, or clinical protocol is assessed.

## 9. Recommended next stage

Before fixed-model NMPC, decide which physical assumptions may change. The most informative next trajectory-level study would jointly examine clinically acceptable minimum knee flexion and contact location, or add an explicitly modeled passive support, while keeping force and conditioning objectives visible. If the unsupported, exact `[5;10] deg` endpoint must remain, an optimizer alone should not be expected to eliminate its static peak.

## 10. Reproducibility and artifacts

Run headlessly with:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_single_arm_trajectory_feasibility_study"
```

The ignored output directory is `linkage/results/local/single_arm_trajectory_feasibility_study/`. It contains the full MAT workspace, comparison/search/time-series CSV files, command and MATLAB-version records, source audit, console log, summary, and six static PNG figures. No closed-loop tracking was run and no GIF was generated.
