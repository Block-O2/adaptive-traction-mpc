# High-ROM static feasibility audit

Status: **exploratory engineering audit; not a formal experiment**.
No controller benchmark, dynamic rehabilitation rollout, ROM amendment, or controller change was run.

## Coordinate conventions

`q1` is positive hip flexion from a thigh along world +X; the absolute thigh angle is `q1`.
`q2` is positive knee flexion relative to the thigh; the absolute shank angle is `q1-q2`.
The zero pose is a straight horizontal limb. The cuff orientation is `Ry(q2-q1)`.

## Frozen assumptions

Human V2 ROM remains hip 0-80 deg and knee 0-100 deg. The 5 deg soft-limit zone,
25 Nm boundary term, 2 Nms/rad directional limit damping, and 200 N translational
force gate are unchanged. No cuff moment gate exists in the frozen repository.

## Four requested configurations

| pose | physical interpretation | current ROM | current / conditional tau (Nm) | current / conditional force (N) | current / conditional moment (Nm) | blockers |
|---|---|---|---:|---:|---:|---|
| (90,90) | thigh vertical; shank horizontal | invalid: hip | [697.44,6.36] / [22.44,6.36] | 1611.03 / 67.54 | 1.05 / 1.05 | ur10e_human_intersection |
| (120,90) | thigh 120 deg; shank 30 deg | invalid: hip | [18235.13,7.37] / [10.13,7.37] | 41756.32 / 43.55 | 1.22 / 1.22 | ur10e_human_intersection |
| (90,120) | thigh vertical; shank -30 deg | invalid: hip+knee | [696.42,3137.61] / [21.42,12.61] | 9619.72 / 77.99 | 324.31 / 0.30 | ur10e_human_intersection |
| (120,120) | thigh 120 deg; shank horizontal | invalid: hip+knee | [18236.15,3136.59] / [11.15,11.59] | 50998.47 / 52.34 | 1185.90 / 0.46 | ur10e_bed_intersection, ur10e_human_intersection |

## Interpretation rules

A pose outside 80/100 deg is invalid under the current Human V2 declaration even if geometry and IK are clear.
For such poses, current soft-limit torque is reported but not interpreted as physical high-ROM demand.
The conditional column removes only the frozen soft-limit term; it is a diagnostic for deciding whether a model amendment is worth reviewing, not a validated extended-ROM model.
Human-bed penetration, UR10e IK failure, geometric intersections, modeled robot torque-limit violation, and the 200 N conditional force gate are kept as distinct mechanical blockers.
There are 0 strictly clear samples under every current geometry check. When disabled robot-bed/robot-Human collision domains are separated as a surrogate-model issue, 181 samples are otherwise clear.

## Grid findings

The full-pose UR10e IK reached 249 of 289 sampled poses; 40 were unreachable under the deterministic search.
Conditional no-soft-limit cuff force ranged from 4.11 to 121.10 N; 0 samples exceeded 200 N.
The rigid-cuff map was rank 2 at 289 of 289 samples; the point-force submap was rank 1 at 17 knee-extension samples.
The sampled conditional envelope reaches q1=120 and q2=120 algebraically, but this is not a strict current-model feasible region because of the collision-geometry findings below.
On the sampled conditional envelope, q2=120 is intrinsically clear only from q1=70 upward, and q1=120 is intrinsically clear from q2=80 upward. These are grid observations, not continuous-boundary proofs.

## Model/contact limits

The frozen plant enables Human-bed and robot self-contact, but disables robot-bed and robot-Human contact.
This audit queries their signed geometry distances without adding response forces. The model also has no Human self-collision or clinical ROM representation.
Every IK-reachable sample showed a 0.062 m wrist/shank overlap with the provisional identity cuff adapter. This is a current surrogate geometry defect, not evidence that every physical adapter is impossible.
Some selected IK branches also cross the bed; because one static branch per grid point was retained, a negative bed distance is an observed branch blocker rather than proof that all IK branches fail.
The four requested poses have no Human-link or sleeve bed penetration. Their thigh capsule remains tangent at the fixed hip end; 120/120 additionally has a selected-branch UR10e-bed overlap.
The high-flexion poses otherwise lift the distal limb away from the bed. Static balance therefore uses the world-anchored hip plus cuff reaction; this audit does not invent an additional bed-support force.
Consequently, collision-free UR10e results are surrogate-only and do not establish CR12 feasibility.
Target cuff orientation is a continuous function of q2-q1 over the scan. Pointwise IK does not prove a continuous collision-free robot branch or exclude joint-angle branch jumps along a future trajectory.

## Rigid-cuff mechanics

Across the sampled grid, raw mixed-unit B conditioning ranged from 4.803 to 6.170.
The full rigid-cuff map includes sagittal moment and is checked for rank 2 at every pose.
The translational-force-only submap is still rank-deficient at knee extension; the added moment authority is why the rigid-cuff map avoids that old point-force singularity.

## Candidate endpoint classes for the next design review

| class | endpoint | conditional force / moment | main caveat |
|---|---:|---:|---|
| hip_dominant | (100,60) | 52.72 N / 2.29 Nm | identity-adapter wrist/shank overlap |
| knee_dominant | (60,100) | 96.20 N / 0.66 Nm | selected IK branch also intersects bed |
| both_high | (90,90) | 67.54 N / 1.05 Nm | identity-adapter wrist/shank overlap |
| aggressive | (120,90) | 43.55 N / 1.22 Nm | hip 120 is not a clinical-angle claim |

These are endpoint classes for review after geometry repair, not approved dynamic trajectories.
Before an endpoint can sit outside the soft-limit zone, its declared upper ROM must exceed it by the frozen 5 deg margin; merely setting the upper bound equal to the endpoint would retain boundary torque.
The ordinary passive stiffness/rest model is extrapolated in the conditional calculation and must be reviewed rather than assumed valid at 90-120 deg.
Robot/cuff adapter geometry and robot-bed collision representation need revision or explicit validation before any controller campaign.
For the four requested poses, keeping the endpoint outside the frozen 5 deg soft-limit zone would require reviewed upper limits of at least [95,95], [125,95], [95,125], and [125,125] deg respectively; these are software-margin implications, not clinical recommendations.
Changing limits alone is insufficient: the passive stiffness/rest extrapolation, bed/contact representation, identity adapter, and continuous collision-free UR10e path all require review.
No dynamic trajectory or controller comparison is approved by this report.

## Artifacts

- `high_rom_feasibility_summary.json`: compact assumptions, counts, and four-pose details
- `feasible_region.csv`: one row per sampled configuration
- `high_rom_feasibility_heatmaps.png`: classification and conditional cuff force
- `high_rom_conditioning_heatmaps.png`: UR10e and rigid-cuff conditioning

## Continuous-path audit after parameterized adapter

The identity adapter was replaced by a 140 mm attachment-to-cuff-centre side standoff.
Its dimension is 69 mm committed wrist directional envelope + 58 mm cuff radius + 13 mm existing cuff-shell allowance.
The 13 mm radius connector stops at the cuff outer surface. This is a Menagerie UR10e engineering surrogate, not CR12 hardware geometry.

Dense paths use 121 quintic-spaced Human-joint samples from [5,10] deg and continue each UR10e IK branch from the previous solution.
Six exact initial branches were evaluated for every endpoint.

| candidate | strict result | min all-clearance | min robot-human | min adapter-human | bed collision interval end | worst J condition | min joint margin | peak force / moment |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| hip 100/60 | blocked by bed geometry | -103.9 mm | 23.0 mm | 13.0 mm | 0.250 | 11.65 | 70.03 deg | 104.73 N / 16.66 Nm |
| both 90/90 | blocked by bed geometry | -103.9 mm | 23.1 mm | 13.0 mm | 0.292 | 7.45 | 71.40 deg | 108.93 N / 16.66 Nm |
| aggressive 120/90 | blocked by bed geometry | -103.9 mm | 49.0 mm | 13.0 mm | 0.242 | 8.86 | 44.24 deg | 107.02 N / 16.66 Nm |
| knee 60/100 | blocked by bed geometry | -103.9 mm | 23.1 mm | 13.0 mm | 0.517 | 6.29 | 73.39 deg | 110.89 N / 16.66 Nm |

The old systematic wrist/shank overlap is eliminated: selected paths retain positive robot-human clearance and exactly 13 mm minimum adapter-human clearance.
No path is strictly collision-feasible from the committed initial pose because all exact initial IK branches intersect the bed and the collision-disabled cuff proxy starts about 4.6 mm inside the bed plane.
Robot-human, adapter-human, adapter-bed, robot self-collision, IK continuity, joint limits, algebraic singularity, and the 200 N force gate otherwise pass on the selected branches.
The knee-dominant 60/100 path retains robot-bed intersection for roughly half the path and is not recommended.

Conditional design priorities after the initial cuff/bed and robot-base/bed geometry is corrected are 100/60, 90/90, and then 120/90. None is approved for a controller rollout by this audit.
Their respective ROM upper bounds would need review to at least [105,100], [95,100], and [125,100] deg to keep endpoints outside the existing 5 deg soft-limit zone without reducing the other current bound.
The ordinary passive stiffness/rest extrapolation must also be reviewed; no Human V2 parameter was changed here.

See `adapter_geometry_config.json`, `continuous_path_audit.json`, and `continuous_path_clearance.png` for compact evidence.

## Common base placement under revised collision policy

The revised policy ignores finite cuff thickness, thigh, and mid-shank support-plane contact as trajectory-failure criteria. Robot/adapter environment and Human clearance, robot self-collision, distal ankle-point clearance, continuous IK, joint limits, conditioning, and the conditional 200 N cuff-force gate remain required.
No foot body or dynamic distal extension was added.

Selected common UR10e base: [0.800, -0.770, 0.360] m, yaw 20.0 deg.
The search evaluated 81 coarse and 81 local placements using only longitudinal, lateral, height, and yaw coordinates.

| candidate | revised result | min required | robot-bed interval end | robot-human | distal ankle | worst J condition | min joint margin | peak force / moment |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 100/60 hip | STILL GEOMETRICALLY BLOCKED | -103.9 mm | 0.250 | 49.0 mm | 53.1 mm | 6.67 | 51.96 deg | 104.73 N / 16.66 Nm |
| 90/90 both | STILL GEOMETRICALLY BLOCKED | -103.9 mm | 0.292 | 49.0 mm | 53.1 mm | 5.32 | 56.96 deg | 108.93 N / 16.66 Nm |
| 120/90 aggressive | STILL GEOMETRICALLY BLOCKED | -103.9 mm | 0.242 | 49.0 mm | 53.1 mm | 6.13 | 53.44 deg | 107.02 N / 16.66 Nm |

The 140 mm adapter remains unchanged; its minimum Human clearance stays positive on all selected branches.
All three dense paths complete continuous IK on one common branch, but all seven exact initial branches collide with the support plane. The selected branch is limited by the local wrist_2 collision proxy at the fixed cuff pose, so translating or yawing the base cannot remove the initial overlap.
Geometrically ready trajectories: none.
No Human V2 ROM, passive, controller, cost, constraint, bed, or cuff mechanics parameter was changed, and no dynamic rollout was run.

See `base_placement_audit.json` and `base_placement_clearance.png`.

## High-ROM Human V2 passive-model audit

An explicit `human_v2_high_rom_engineering_v2_125deg_both_joints` variant extends the hip and knee upper ROM to 125 deg. Canonical Human V2 is unchanged.
The 5 deg cubic soft-limit zones therefore begin at [120,120] deg. The 120 deg endpoints are exactly on the soft-zone start and remain soft-limit inactive in the quasi-static reference audit.
Ordinary stiffness [10,10] Nm/rad, damping [5,5] Nms/rad, rest [5,10] deg, and all soft-limit coefficients are retained. This passive extrapolation is an engineering assumption pending physical/hardware validation.

| joint | total passive-left static envelope | soft-limit actual envelope | inward boundary direction | damping dissipative |
|---|---:|---:|---:|---:|
| hip | [-25.87,45.94] Nm | [-25.00,25.00] Nm | True | True |
| knee | [-26.75,45.07] Nm | [-25.00,25.00] Nm | True | True |

| trajectory | model decision | peak passive hip / knee | peak required torque norm | peak cuff force (margin) | peak cuff moment |
|---|---|---:|---:|---:|---:|
| 100/60 hip | READY FOR DYNAMIC PILOT | 16.58 / 8.73 Nm | 41.83 Nm | 104.73 N (95.27 N) | 16.66 Nm |
| 90/120 knee/high-folding | READY FOR DYNAMIC PILOT | 14.84 / 19.20 Nm | 41.56 Nm | 110.27 N (89.73 N) | 16.66 Nm |
| 120/120 aggressive | READY FOR DYNAMIC PILOT | 20.07 / 19.20 Nm | 41.69 Nm | 109.02 N (90.98 N) | 16.66 Nm |

All three paths are READY FOR DYNAMIC PILOT at the Human-model and quasi-static cuff-mechanics level. The recommended order is 100/60, 90/120, then 120/120. This is not a completed dynamic/controller test.
The setup-specific support-plane collision from the prior geometry audit is outside this model-amendment decision, per the revised task scope.
No controller or dynamic rollout was run.

See `high_rom_human_v2_config.json`, `passive_model_audit.json`, and `high_rom_passive_torque.png`.

## Professor 120-degree High-ROM re-audit

The engineering High-ROM variant now uses a common [0,125] deg envelope with 5 deg soft zones for hip and knee; canonical Human V2 remains unchanged. The 120 deg references lie at, but not inside, the upper soft-zone boundary.
The completed common base [0.80,-0.77,0.36] m, yaw 20 deg and 140 mm engineering wrist-to-cuff adapter were reused without a new placement search. Robot-bed contact is recorded but is not a blocker for this seated/suspended-setup question.

| path | decision | worst cond(J) | min joint margin | min robot/adapter-Human clearance | min distal clearance | peak passive hip/knee | peak cuff force | peak moment |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| hip_dominant_100_60 | READY FOR DYNAMIC PILOT | 5.77 | 51.69 deg | 13.0 mm | 53.1 mm | 16.58/8.73 Nm | 104.73 N | 16.66 Nm |
| knee_high_folding_90_120 | READY FOR DYNAMIC PILOT | 5.43 | 64.08 deg | 13.0 mm | 53.1 mm | 14.84/19.20 Nm | 110.27 N | 16.66 Nm |
| aggressive_both_120_120 | READY FOR DYNAMIC PILOT | 5.61 | 57.24 deg | 13.0 mm | 53.1 mm | 20.07/19.20 Nm | 109.02 N | 16.66 Nm |

All three ready under the revised non-bed policy: `True`.

## Small High-ROM Fixed-vs-Adaptive dynamic pilot

Exactly six non-formal engineering runs were executed: three High-ROM trajectories by Fixed MPC and Trusted Adaptive MPC, with one shared frozen measurement realization and no retuning.

**Post-run validation disposition:** this table is diagnostic only, not a
validated controller comparison. A required regression found that the
measurement-side low-level robot model evaluated its Jacobian at the original
attachment site rather than at the new 140 mm rigid-offset cuff point. The
frame/Jacobian propagation was corrected and its ideal-law regression now
passes, but the six runs were not repeated because the task authorized only
six controller rollouts.

| trajectory | controller | completion | RMSE / max error | peak angle hip/knee | soft-zone samples | cuff RMS / peak | moment peak | accel RMS | promotions | events |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| hip_dominant_100_60 | fixed_mpc_prior_only | False (total_commanded_cuff_force_gate) | 0.67 / 2.70 deg | 68.07/45.45 deg | 209 | 99.25/161.47 N | 24.59 Nm | 263.25 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |
| hip_dominant_100_60 | trusted_adaptive_mpc | False (total_commanded_cuff_force_gate) | 0.67 / 2.70 deg | 68.07/45.45 deg | 209 | 99.25/161.47 N | 24.59 Nm | 263.25 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |
| knee_high_folding_90_120 | fixed_mpc_prior_only | True (completed) | 1.94 / 4.67 deg | 92.84/115.89 deg | 526 | 112.17/150.65 N | 78.11 Nm | 129.27 deg/s2 | 0 | force=0, ROM=0, solver=0, contacts=0 |
| knee_high_folding_90_120 | trusted_adaptive_mpc | True (completed) | 1.94 / 4.67 deg | 92.84/115.89 deg | 526 | 112.17/150.65 N | 78.11 Nm | 129.27 deg/s2 | 0 | force=0, ROM=0, solver=0, contacts=0 |
| aggressive_both_120_120 | fixed_mpc_prior_only | False (total_commanded_cuff_force_gate) | 0.17 / 1.80 deg | 72.17/76.53 deg | 205 | 102.35/167.54 N | 29.87 Nm | 139.02 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |
| aggressive_both_120_120 | trusted_adaptive_mpc | False (total_commanded_cuff_force_gate) | 0.17 / 1.80 deg | 72.17/76.53 deg | 205 | 102.35/167.54 N | 29.87 Nm | 139.02 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |

Paired Adaptive-minus-Fixed changes:

- `hip_dominant_100_60`: tracking RMSE +0.000 deg; peak cuff force +0.000 N.
- `knee_high_folding_90_120`: tracking RMSE +0.000 deg; peak cuff force +0.000 N.
- `aggressive_both_120_120`: tracking RMSE +0.000 deg; peak cuff force +0.000 N.

The reported soft-zone samples are lower-hip-boundary startup/return transients
(minimum hip angle 4.67--4.96 deg versus the 5 deg lower soft-zone start). No
run entered the upper 120 deg soft zone; the only completed 90/120 pair peaked
at 92.84/115.89 deg. The other four runs stopped before their targets because
the combined low-level feedback plus MPC feedforward command would have exceeded
the 200 N command gate. Their measured physical cuff-force peaks remained
161.47 N and 167.54 N before termination. No Trusted Adaptive run promoted a
challenger, so the Fixed and Adaptive traces are identical and this pilot does
not demonstrate an adaptive benefit.

## Corrected post-Jacobian High-ROM dynamic pilot

Exactly six corrected non-formal engineering runs were executed: three High-ROM trajectories by Fixed MPC and Trusted Adaptive MPC, with one shared frozen measurement realization and no retuning.

| trajectory | controller | completion | RMSE / max error | peak hip/knee | soft lower/upper | cuff RMS/peak | command peak/margin | moment | accel RMS | promotions | events |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| hip_dominant_100_60 | fixed_mpc_prior_only | False (total_commanded_cuff_force_gate) | 0.72 / 2.87 deg | 74.02/48.47 deg | 255/0 | 98.16/142.93 N | 212.82/-12.82 N | 24.43 Nm | 252.81 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |
| hip_dominant_100_60 | trusted_adaptive_mpc | False (total_commanded_cuff_force_gate) | 0.72 / 2.87 deg | 74.02/48.47 deg | 255/0 | 98.16/142.93 N | 212.82/-12.82 N | 24.43 Nm | 252.81 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |
| knee_high_folding_90_120 | fixed_mpc_prior_only | True (completed) | 1.90 / 4.35 deg | 93.02/116.11 deg | 575/0 | 112.66/146.60 N | 178.13/21.87 N | 70.45 Nm | 113.65 deg/s2 | 0 | force=0, ROM=0, solver=0, contacts=0 |
| knee_high_folding_90_120 | trusted_adaptive_mpc | True (completed) | 1.90 / 4.35 deg | 93.02/116.11 deg | 575/0 | 112.66/146.60 N | 178.13/21.87 N | 70.45 Nm | 113.65 deg/s2 | 0 | force=0, ROM=0, solver=0, contacts=0 |
| aggressive_both_120_120 | fixed_mpc_prior_only | False (total_commanded_cuff_force_gate) | 0.19 / 2.00 deg | 75.58/79.76 deg | 248/0 | 102.04/170.65 N | 207.32/-7.32 N | 27.97 Nm | 173.64 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |
| aggressive_both_120_120 | trusted_adaptive_mpc | False (total_commanded_cuff_force_gate) | 0.19 / 2.00 deg | 75.58/79.76 deg | 248/0 | 102.04/170.65 N | 207.32/-7.32 N | 27.97 Nm | 173.64 deg/s2 | 0 | force=1, ROM=0, solver=0, contacts=0 |

Paired Adaptive-minus-Fixed changes:

- `hip_dominant_100_60`: tracking RMSE +0.000 deg; peak cuff force +0.000 N.
- `knee_high_folding_90_120`: tracking RMSE +0.000 deg; peak cuff force +0.000 N.
- `aggressive_both_120_120`: tracking RMSE +0.000 deg; peak cuff force +0.000 N.

### Corrected interpretation

The corrected conclusion is unchanged qualitatively but is now based on a
consistent physical cuff point. The 90/120 pair completed with 21.87 N of
command-force margin and reached 93.02/116.11 deg. The 100/60 and 120/120
pairs stopped at 8.56 s and 7.75 s when attempted total translational commands
reached 212.82 N and 207.32 N. Their physical cuff-force peaks before
termination were 142.93 N and 170.65 N.

No corrected run entered the upper 120 deg soft zone or produced a ROM,
solver, unintended-contact, or robot joint-limit event. Recorded lower-zone
samples remain startup/return hip transients. All Adaptive runs had zero
promotion and therefore used the same population prior and produced the same
trace as Fixed MPC.

For context, the existing nominal 75/90 lower-ROM, seed-44104 evidence reports
0.426 deg RMSE and 1.564 deg maximum error. The completed corrected 90/120
motion reports 1.903 deg RMSE and 4.353 deg maximum error: increases of 1.478
deg (4.47x) and 2.789 deg (2.78x). This is contextual rather than a strict
single-variable comparison because the lower-ROM artifact predates the 140 mm
adapter and uses a different reference path.

The remaining observed blocker is the frozen total-command force constraint
during outbound trajectory/control transients, not geometric feasibility,
Human ROM, upper soft limits, large-ROM-triggered adaptation, or solver/contact
failure. No controller parameter was changed.

## Predictive speed-governor High-ROM pilot

A small non-formal pilot compared the unchanged Fixed MPC under the nominal reference clock and an outer-loop predictive phase-rate governor. The governor is separate from trust confidence and retains the original MPC, population prior, allocator, geometry, and 200 N hard gate.

| trajectory | clock | completed | wall / phase | alpha mean/min | tracking RMSE/max | command P95/peak | physical force RMS/P95/peak | moment RMS/peak | accel/jerk RMS | events |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| hip_dominant_100_60 | fixed_nominal | False (total_commanded_cuff_force_gate) | 8.56 / 8.56 s | 1.000/1.000 | 0.716/2.869 deg | 121.53/212.82 N | 98.16/115.89/142.93 N | 14.41/24.43 Nm | 246.6/8895.9 | force=1, ROM=0, solver=0, contacts=0 |
| hip_dominant_100_60 | predictive_speed_governor | False (total_commanded_cuff_force_gate) | 8.56 / 8.56 s | 1.000/1.000 | 0.716/2.869 deg | 121.53/212.08 N | 98.16/115.89/142.93 N | 14.41/24.43 Nm | 246.6/8895.9 | force=1, ROM=0, solver=0, contacts=0 |
| aggressive_both_120_120 | fixed_nominal | False (total_commanded_cuff_force_gate) | 7.75 / 7.75 s | 1.000/1.000 | 0.188/2.002 deg | 123.31/207.32 N | 102.04/119.45/170.65 N | 13.51/27.97 Nm | 165.8/6908.4 | force=1, ROM=0, solver=0, contacts=0 |
| aggressive_both_120_120 | predictive_speed_governor | False (total_commanded_cuff_force_gate) | 7.75 / 7.75 s | 1.000/1.000 | 0.188/2.002 deg | 123.31/207.32 N | 102.04/119.45/170.65 N | 13.51/27.97 Nm | 165.8/6908.4 | force=1, ROM=0, solver=0, contacts=0 |

The planning threshold is 195 N (5 N inside the unchanged hard gate); candidate alpha values are common to both paths and the existing Stage-4 0.50 minimum plus existing rate limits are reused.

Observed result: neither governed path completed. The 0.30 s seed-sequence
forecast stayed below 195 N until the same control update that crossed the hard
gate, so applied alpha remained 1.0 throughout both runs. For 100/60, the final
forecast found no safe candidate even at alpha 0.50 (199.17 N predicted), but
this occurred on the gate-triggering update before any rate-limited slowdown
could be applied. Its immediate alpha-dot term changed the terminal command
attempt slightly (212.82 to 212.08 N), but did not prevent the gate. For
120/120, the final alpha=1 forecast was only 173.62 N
while the realized command attempt was 207.32 N. The current predictor therefore
provided neither sufficient advance warning nor sufficient next-step fidelity.

The governed and fixed traces consequently have identical reference progress,
tracking, physical interaction, acceleration, and jerk up to termination. There
were no ROM, upper-soft-zone, solver, unintended-contact, or robot-joint-limit
events. The remaining blocker is prediction fidelity/lead time followed by the
unchanged 200 N command-force gate, not demonstrated benefit from time scaling.

Recommended next experiment: an instrumented diagnostic-only replay of the
frozen pre-gate segment comparing the seed-sequence forecast, selected MPC
sequence, and realized next-step command. No horizon, margin, rate, controller, or force-limit change
should be authorized until that mismatch is localized.

## Joint control-progress CEM High-ROM pilot (20 ms diagnostic only)

**Diagnostic-only disposition:** candidate force rejection in these two runs
checked only the 20 ms MPC nodes, while the actual Cartesian command was
recomputed every 5 ms. Both gates occurred between prediction nodes. This
result is preserved but cannot validate the required same-control-path force
constraint; the corrected pilot below expands every held action into four
5 ms constraint substeps.

Two non-formal engineering runs used one batched 32-candidate CEM population to jointly sample the frozen action horizon and one alpha. The corrected fixed-clock evidence was read, not rerun.

| trajectory | completion | time | RMSE/max | alpha mean/min/max | below 1 | predicted/executed command peak | physical cuff RMS/P95/peak | moment RMS/peak | accel/jerk RMS | force prediction MAE/P95/max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hip_dominant_100_60 | False (total_commanded_cuff_force_gate) | 8.86 s | 0.738/3.455 deg | 0.990/0.581/1.000 | 0.33 s | 195.15/200.98 N | 97.80/115.74/158.68 N | 14.58/37.97 Nm | 388.0/15402.9 | 1.24/4.12/6.49 N |
| aggressive_both_120_120 | False (total_commanded_cuff_force_gate) | 7.93 s | 0.173/1.485 deg | 0.999/0.903/1.000 | 0.17 s | 186.35/209.09 N | 101.78/119.21/167.79 N | 13.32/26.12 Nm | 158.6/6527.7 | 0.50/1.42/5.03 N |

Joint-alpha MPC solve latency mean/p95/max: 8.08/8.30/8.49 ms; misses: 0; effective 123.7 Hz.
Estimator+MPC high-level cycle mean/p95/max: 8.73/8.60/46.91 ms; misses: 8.

## Corrected 5 ms joint control-progress CEM High-ROM pilot

Two non-formal engineering runs used one batched 32-candidate CEM population to jointly sample the frozen action horizon and one alpha. The corrected fixed-clock evidence was read, not rerun.

| trajectory | completion | time | RMSE/max | alpha mean/min/max | below 1 | predicted/executed command peak | physical cuff RMS/P95/peak | moment RMS/peak | accel/jerk RMS | force prediction MAE/P95/max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hip_dominant_100_60 | False (total_commanded_cuff_force_gate) | 8.86 s | 0.732/3.490 deg | 0.991/0.574/1.000 | 0.34 s | 243.29/242.99 N | 97.82/116.07/161.83 N | 14.53/35.00 Nm | 361.6/14097.7 | 1.96/5.60/69.66 N |
| aggressive_both_120_120 | False (total_commanded_cuff_force_gate) | 7.93 s | 0.173/1.485 deg | 0.999/0.903/1.000 | 0.17 s | 186.35/209.09 N | 101.78/119.21/167.79 N | 13.32/26.12 Nm | 158.6/6527.7 | 0.96/2.74/46.52 N |

Joint-alpha MPC solve latency mean/p95/max: 26.99/27.36/36.84 ms; misses: 841; effective 37.1 Hz.
Estimator+MPC high-level cycle mean/p95/max: 27.66/27.77/65.53 ms; misses: 841.

### Corrected joint-CEM interpretation

Neither path completed and neither avoided the independent 200 N command gate.
For 100/60, alpha first fell below one at 8.52 s, reached 0.574, and remained
below one for 0.34 s. At 8.86 s the CEM had no feasible candidate; its explicit
fallback produced a 243.29 N predicted and 242.99 N executed command, so the
unchanged final gate stopped the run. This run recorded one MPC feasibility
failure. For 120/120, alpha first fell below one at 7.76 s, reached 0.903, and
remained below one for 0.17 s, but the selected path's 186.35 N predicted peak
underestimated the 209.09 N executed peak. Neither run survived long enough to
demonstrate automatic return to alpha=1.

The 5 ms selected-path comparison now uses the same final CEM action at every
held-action low-level substep. Prediction absolute error mean/p95/max was
1.96/5.60/69.66 N for 100/60 and 0.96/2.74/46.52 N for 120/120. The remaining
large outliers are therefore model/measurement execution residuals or the
explicit infeasible fallback, not the previous seed-versus-winner mismatch.

Against the preserved fixed-clock evidence, 100/60 stopped 0.30 s later but
its command peak increased from 212.82 to 242.99 N, physical-force peak from
142.93 to 161.83 N, tracking RMSE from 0.716 to 0.732 deg, and like-for-like
acceleration RMS from 252.81 to 372.92 deg/s2. The 120/120 run stopped 0.18 s
later; command peak increased from 207.32 to 209.09 N, physical-force peak fell
from 170.65 to 167.79 N, tracking RMSE fell from 0.188 to 0.173 deg, and
acceleration RMS fell from 173.64 to 166.48 deg/s2. These partial pre-gate
changes are not completion benefits.

The required 5 ms force-path expansion raised joint-alpha MPC latency from the
invalid 20 ms-node diagnostic's 8.08 ms mean to 26.99 ms mean. Corrected MPC
mean/p95/max was 26.99/27.36/36.84 ms with 841/841 deadline misses, or 37.1 Hz.
The full estimator-plus-MPC cycle was 27.66/27.77/65.53 ms with 841/841 misses.
Thus the strict 50 Hz target fails. The dominant structural addition is four
RK4/force-path substeps per original MPC step; no population increase or
performance tuning was attempted.

The alpha domain and pacing normalization were common to both trajectories;
there was no trajectory-specific tuning. Robot joint limits remain guaranteed
only by the pre-audited path geometry and unchanged runtime checks because the
four-state Human-space MPC has no robot dynamics state; neither run recorded a
robot joint-limit event. This extension should not replace the failed outer
governor. Stop before tuning and diagnose the no-feasible fallback, the
model-to-measured force residual, and the 5 ms substep compute cost first.

## Constraint-aware High-ROM path time parameterization

This non-formal two-run engineering pilot added one offline forward/backward path-time parameterization layer. The Fixed MPC/CEM, estimator, trust logic, allocator, and independent 200 N gate were unchanged.

One common reserve of 70 N was the ceiling of the worst preserved same-final-action prediction residual; the planning budget was therefore 130 N.

| trajectory | complete | wall time | alpha mean/min/max | below 1 | tracking RMSE/max | planned/executed command peak | physical force RMS/P95/peak | moment peak | accel/jerk RMS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hip_dominant_100_60 | False (total_commanded_cuff_force_gate) | 8.56 s | 1.000/1.000/1.000 | 0.00 s | 0.716/2.869 deg | 111.79/212.82 N | 98.16/115.89/142.93 N | 24.43 Nm | 246.6/8895.9 |
| aggressive_both_120_120 | False (total_commanded_cuff_force_gate) | 7.75 s | 1.000/1.000/1.000 | 0.00 s | 0.188/2.002 deg | 118.77/207.32 N | 102.04/119.45/170.65 N | 27.97 Nm | 165.8/6908.4 |

The planner profile, force gate result, and compute timing above are diagnostic engineering evidence only; they do not modify authoritative Stage-4 results.

Both inverse-dynamics profiles were already below the common 130 N planning
budget at alpha=1 (111.79 N and 118.77 N). The lexicographic planner therefore
preserved the nominal clock exactly; there was no slowdown or recovery interval
and both runs reproduced their preserved fixed-clock baselines exactly.

Both runs still hit the independent command-force gate at 8.56 s (212.82 N)
and 7.75 s (207.32 N). Planner-to-executed command absolute error p95/max was
24.14/131.87 N and 16.20/122.01 N, so the 70 N same-final-CEM-action reserve
does not cover the different inverse-dynamics-path predictor. The current
extension therefore should not replace the failed governor.

One-time planning took 0.464/0.468 s outside the control loop. The unchanged
MPC p95 was 10.19/9.85 ms with zero MPC solves over 20 ms; the full high-level
p95 was 10.64/10.17 ms, with isolated maximum outliers. Next, validate a
single common mapping from planned path state to the selected closed-loop MPC
command using held-out fixed-clock traces before authorizing another pacing
pilot.

## Receding-horizon final-command force-alpha audit

A diagnostic-only replay reproduced the two preserved fixed-clock force-gate outcomes, then swept 101 continuous alpha targets from 0.50 to 1.00 at fixed measured/estimated pre-gate states. Each curve used the one actual final CEM-selected action sequence, 5 ms held-action substeps, frozen rigid-cuff allocation, and exact low-level Cartesian feedback. No additional MPC solve was used.

The common empirical reserve was 111 N. Monotonicity=False, lead-time=False, alpha_min near-gate feasibility=False.

Step-1 gate passed: False. An online pacing pilot is permitted only when this value is true.

Observed diagnosis: 21/25 curves changed by no more than 1 N over alpha=0.50..1.00 because the horizon peak was usually the immediate selected-action command, before the rate-limited alpha target could affect it. At 100/60 with only 0.10 s lead, the direction reversed (F(1)-F(0.5)=-1.35 N; only 76% of dense steps were nondecreasing).

The final-selected-sequence predictor remained accurate at the gate itself but did not anticipate the later CEM action change: maximum next-0.3 s underprediction was 110.44 N, yielding a 111 N common reserve. Within 0.30 s of both gates, robust F_cmd(0.5) exceeded 200 N at every audited state, so no bounded scalar search could return a robustly feasible alpha. The task therefore stops before online implementation or pacing rollout.

A dense 101-alpha curve took about 10.5 ms and was evaluated at 10 Hz for
diagnosis. The unchanged MPC p95 remained 9.69/9.72 ms with zero MPC deadline
misses, but diagnostic full-cycle p95 was 19.96/17.13 ms with 22/15 samples
above 20 ms. This audit therefore does not establish a hard 50 Hz online
pacing implementation.

## Pre-gate action-switch predictability audit

This read-only diagnostic used only the preserved corrected fixed-clock results
and the previously saved final-selected-action force audit; no controller
rollout or parameter change was made. The corrected pilot did not persist the
requested 20 ms raw trace. The finest available pre-gate diagnostic states are
100 ms apart. Exact feedforward, Cartesian position-feedback and
velocity-feedback components, CEM best/elite costs, and per-cycle rejection
statistics are therefore unavailable and were not reconstructed.

The total low-level translational command attempts at the two gates were
212.82 N for 100/60 and 207.32 N for 120/120. The saved causal
final-selected-sequence predictor gave the following values at the requested
lead times:

| path | 0.50 s | 0.30 s | 0.20 s | 0.10 s |
|---|---:|---:|---:|---:|
| 100/60 predicted peak / margin | 132.72 / 67.28 N | 102.38 / 97.62 N | 134.17 / 65.83 N | 113.51 / 86.49 N |
| 120/120 predicted peak / margin | 131.24 / 68.76 N | 122.02 / 77.98 N | 109.06 / 90.94 N | 98.24 / 101.76 N |

No requested lead produced a causal 200 N warning. Prediction margin,
tracking error, reference acceleration and winner first-action norm did not
show a common monotonic precursor. In 100/60, the winner first-action norm
jumped from 20.24 to 58.05 Nm on the saved gate record and the predicted force
jumped from 113.51 to 212.81 N. For 120/120, the last saved record was 0.09 s
before the gate, with a 21.74 Nm action norm and only 98.24 N predicted; the
gate-cycle action and CEM internals were not saved.

A physically interpretable rule, `predicted selected-sequence force >= 200 N`,
warned only at the 100/60 gate record and never in the preserved 120/120
pre-gate records. A 111 N residual reserve calibrated on 100/60 warned through
most of the deliberately gate-selected 1.2 s held-out window, but there is no
preserved unaffected negative window with which to establish specificity; it
is therefore an unlocalized conservative alarm, not evidence that pacing is
predictable. A small regression was not fit because two positive events and no
20 ms negative-control window would make the result event-window leakage.

Decision: **TOO-LATE / CONTROLLER-INTERNAL**. Supported common warning is less
than 0.10 s, whereas the preserved 1.0/s alpha slowdown limit requires 0.10 s
for even a 10% speed reduction and 0.50 s to move from alpha 1.0 to 0.5. Stop
further pacing development. Next inspect the exact final low-level force as an
MPC feasibility constraint, explicit no-feasible-candidate handling with a
HOLD/safe fallback, and 20 ms action-switch/CEM elite diagnostics before any
controller redesign.

## Force-feasibility recovery High-ROM pilot

A two-run, one-seed engineering pilot added only a Stage-4 execution supervisor around the frozen Fixed MPC. It previews the exact 5 ms low-level force, rejects an unsafe first action, freezes path progress, and retains the independent 200 N runtime gate.

| trajectory | complete | class | time | HOLD count/duration | alpha mean/min | tracking RMSE/max | command peak/margin | cuff RMS/P95/peak | moment peak | accel/jerk RMS | latency p95/max | events |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| hip_dominant_100_60 | False (hold_command_force_infeasible) | UNRECOVERABLE | 8.86 s | 1/0.30 s | 0.966/0.000 | 1.012/9.112 deg | 190.59/9.41 N | 97.53/116.22/162.53 N | 38.57 Nm | 467.3/18471.7 | 10.59/44.16 ms | force=0, ROM=0, solver=0, robot=0 |
| aggressive_both_120_120 | False (hold_command_force_infeasible) | UNRECOVERABLE | 7.93 s | 1/0.18 s | 0.977/0.000 | 0.360/4.130 deg | 195.23/4.77 N | 101.84/119.64/170.65 N | 35.87 Nm | 282.3/10974.7 | 10.61/48.57 ms | force=0, ROM=0, solver=0, robot=0 |

The settle criterion is common to both paths: frozen-reference q-error norm <=2 deg, dq norm <=5 deg/s, executable HOLD command <=195 N, continuously for 0.10 s. Recovery uses a coarse bracket plus bisection to 0.001 alpha and ramps upward at the already used 0.25/s rate.

All rejected command attempts remain diagnostic values; only commands that pass both the allocator and exact total-force checks are applied.

Observed result: both original over-limit proposals were rejected before
execution, so the unchanged runtime gate recorded zero events. The initially
safe HOLD command kept executed peaks to 190.59 N and 195.23 N, but the frozen
reference did not settle: after 0.30 s and 0.18 s respectively, none of the
current frozen-MPC HOLD proposal, last safe action, or zero-action HOLD
produced an executable command below 200 N. Both runs therefore terminated as
**UNRECOVERABLE** under this existing-controller HOLD contract before
RECOVERY_SCAN; alpha feasibility could not be evaluated because alpha=0 HOLD
was already unsafe, and neither endpoint was reached. Abrupt emergency stopping also increased the
observed acceleration/jerk metrics, so this is not a smoothness improvement.

Normal MPC p95 remained 9.77/9.77 ms with no MPC deadline miss. Full-cycle p95
was 10.59/10.61 ms, but isolated 44.16/48.57 ms outliers caused 9/444 and
4/397 misses. The recovery filter itself was sub-millisecond and no scan was
executed. The next issue is not path speed: a verified force-feasible HOLD or
MPC-level final low-level-force feasibility/fallback contract is required
before any further pacing or completion experiment.
