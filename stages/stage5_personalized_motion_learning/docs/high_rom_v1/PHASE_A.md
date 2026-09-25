# High-ROM v1 — Stage A: model and mechanical screen

**Status:** static candidate found for synchronous and hip-leading coordination; 120° closed-loop TASK and RETURN are untested. This is a new exploratory range. Round19 23/23 and fresh qualification 47/48 retain their original scope.

## Recovered baseline and scope

- Original branch/HEAD: `codex/full3d-cr12-qualified-closeout` / `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`; original index and files were not changed.
- Isolated baseline: `/Users/hankli/Desktop/coding/adaptive-traction-mpc-qualified-baseline`, branch `codex/full3d-cr12-qualified-baseline`, one local commit `c72760ae76a5b77a7291b9108ca20ff10b6c3be6`.
- The 652-entry Round19 frozen source manifest, including both XML models, seven CR12 STL meshes and the controller options file, matches the baseline commit byte-for-byte. The canonical sorted compact-JSON manifest digest matches `2880c67d0844ce551ff068474642a4b6ff9bc1fa2d7c81dfcd6914dd32c1ab99`; options SHA-256 is `d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb`. Key imports resolved inside that worktree, and MuJoCo loaded its CR12 XML and seven meshes. Fifteen summary/contract/audit evidence files were copied explicitly. The large ignored per-case native trace trees were **not** committed; they remain in the original worktree. This commit reconstructs the frozen source/config candidate, not a self-contained raw-trace archive.
- Isolated research branch/worktree: `codex/full3d-cr12-high-rom-v1` / `/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-v1`, derived from the baseline commit. Its High-ROM files remain uncommitted.

## Model and task definition

The new [task/model record](../../configs/high_rom_v1/stage5_goal_task_120_v1.json) starts and returns at `(5°,10°)`, with a goal of `(120°,120°)`. It retains the original 1° arrival and 2°/s velocity tolerances, 0.5 s continuous dwell, 10 s per-phase timeout, 45/75°/s human speed limits, 300/600°/s² human acceleration limits, 200 N cuff force, 60 Nm cuff moment, CR12 torque and speed limits, geometry and 100 ms plan expiry. The three path shapes below are diagnostic probes, not a newly imposed task corridor.

`q1` is hip flexion and `q2` is knee flexion. The absolute shank angle is `phi=q1-q2`; JSON uses degrees and Human V2/MuJoCo use radians. The model's old hard maxima were `(80°,100°)`. High-ROM v1 proposes `(125°,125°)` solely as an **engineering hypothesis**: keeping the original 5° soft-limit margin puts the 120° goal exactly at soft-limit onset and 5° inside the proposed hard limits. The original linear passive stiffness 10 Nm/rad, damping 5 Nms/rad, rest angles `(5°,10°)`, cubic 25 Nm boundary torque and hard joint limits remain active. No stiffness or torque law was weakened. Human anatomical ROM and high-angle passive torque have not been physically measured, so 125° is not a certified human hard limit. The current linear passive model is extrapolated beyond its former 80°/100° domain.

The isolated adapter passes this Human V2 variant to `Stage5CR12SpringDamperPlant`; generated coupled XML has the new joint ranges. `GoalTaskSpec.from_mapping` accepts the versioned record; only goal and ROM bounds differ from the original task fields. Cuff-pose-to-angle reconstruction via `atan2` agrees with the known simulated angles to about `1.3e-14°` at the 33 sampled positions; the tested `phi` stays within the principal interval. This does not establish correct unwrapping for every high-ROM state.

**Integration gap:** the frozen runtime still builds `nominal_control_model()` with `STAGE5_HUMAN` and its old ROM, even when `physical_human` is passed to the plant. The scheduler intersects task bounds with `human_model.q_max_rad`; the estimator's `rom_human` also defaults to old Human V2. Prediction, allocation, terminal reference and normalized progress need one traceable High-ROM model source and a deployable-input audit before any closed-loop use. This Stage-A diagnostic uses explicitly labeled oracle model geometry and does not inject simulation truth into a deployable path.

## Representative path evidence

Each path is a smooth quadratic in normalized progress from `(5°,10°)` to `(120°,120°)`. A 1201-node table envelope plus an inter-node Lipschitz deduction gives conservative **continuous** lower bounds for the modeled thigh, shank, sleeve, cuff bar and adapter. IK, model geom distances and static loads are evaluated at 33 warm-started positions; their between-node behavior is unproved. Values below are minima or maxima along the path, not just at the goal.

| Path | Continuous shank / sleeve lower bound | CR12 IK | Discrete max force / moment | Discrete robot torque limit ratio |
|---|---:|---:|---:|---:|
| Synchronous | 1.601 / 1.278 mm | 33/33 | 85.45 N / 17.01 Nm | 0.369 |
| Hip leads | 1.055 / 0.733 mm | 33/33 | 79.91 N / 15.91 Nm | 0.340 |
| Knee leads | −15.938 / −0.144 mm | 33/33 | 94.92 N / 17.80 Nm | 0.412 |

The synchronous and hip-leading envelopes pass the modeled table check, but their sleeve margin is narrow. The proximal thigh capsule has essentially **zero** modeled table clearance at the fixed hip in every path; no positive clearance is claimed there. The knee-leading path fails the *conservative* 0.46 m shank-length envelope. At 33 nodes its XML shank has a smallest signed table distance of +0.176 mm, so the result is a clearance-contract conflict and insufficient continuous evidence, not proof of physical collision. The smallest sampled robot-to-table distance is 28 mm (base collision geom); modeled sleeve/table distances are at least 1.663, 1.663 and 0.791 mm respectively. These MuJoCo geom distances are discrete.

All 33 warm-start IK samples in each path stayed within CR12 joint limits; the smallest sampled mixed-unit Jacobian singular value was 0.251–0.257 and smallest sampled joint-limit margin was 106°. This is a numerical screen, not a continuous IK or singularity certificate. A diagnostic 8 s smooth clock stayed below the original human speed/acceleration limits and the finite-difference CR12 speed estimates stayed below the original speed limits. There is no robot acceleration certificate. Static Human V2 inverse dynamics with the original passive and gravity terms gave the listed wrench demands; the largest sampled robot static torque ratio, allowing either reaction sign, was 0.412. At the goal the nominal quasi-static cuff demand was 52.045 N and 4.083 Nm. These are ideal static model values, not measured compliant-cuff loads or dynamic safety results.

Only geometric and quasi-static evidence was produced: **zero MuJoCo integration steps and zero smoke rollouts**. Robot/human self-collision, soft tissue, cuff deformation/pressure, cables, unmodeled fixture geometry, anatomy-specific ROM, continuous CR12 swept clearance, robot acceleration, dynamic loads, HOLD, 0.5 s dwell and actual RETURN remain open. The existing provisional installation and table geometry were not moved.

Failure classification: the old 80°/100° configuration is a **configuration limit**; the knee-leading path is a **conservative clearance-contract conflict**, while sampled XML geometry does not prove contact; there was **no sampled IK solver failure**; and high-angle passive validity, continuous robot clearance and coupled dynamic performance remain **insufficient evidence**. No failed sample or unfavorable margin was discarded.

## Stage-B gate and focused cases

Stage A identifies a candidate path; it does **not** authorize a 120° qualification claim. Before a closed-loop Stage-B run, connect the versioned ROM consistently through the deployable model, estimator, predictor, allocator, scheduler, terminal reference, task normalization and coupled plant, with the truth firewall intact. Establish physical support for the proposed hard ROM and high-angle passive law or keep any later claim explicitly simulation-hypothetical. Then use synchronous `(5°,10°)→(120°,120°)→return` as the first development case, hip-leading as a narrow-clearance comparison, and knee-leading as a negative clearance-contract case. Check continuous robot reach/collision and dynamic force, torque and task/return evidence. No Stage-B work was run here.

## Budget, commands and artifacts

The actual `codex` weekly bucket was 9% used at start and 10% at the final read (rounded telemetry); its 10,080-minute window resets at 2026-10-02 05:03:40 UTC. The campaign gate used the actual `get_usage_limits` bucket before each new computation: 11% permits only closeout, 12% or invalid readings prohibit new dispatch. Eight simulated cases checked the deny/allow branch, including user STOP, an invalid reading, changed reset window and the outer 40-point limit. All actual Stage-A computations went through that pre-dispatch gate. This interactive run launched no unattended loop and makes **no in-flight worker-interruption claim**. The 50% weekly reserve and total-new-40-point outer rules remained in force.

Reproduce the static diagnostic from this worktree using:

```sh
MPLCONFIGDIR=/private/tmp/high-rom-mpl /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage5_personalized_motion_learning/scripts/high_rom_v1/diagnose_phase_a.py
```

Artifacts: [full numeric diagnostic](phase_a_diagnostic.json), [structured summary](PHASE_A_SUMMARY.json), and the [diagnostic script](../../scripts/high_rom_v1/diagnose_phase_a.py). Non-simulation checks also used `git show HEAD:<path>` over all frozen manifest entries, SHA-256 verification, isolated imports, CR12 XML load and `GoalTaskSpec.from_mapping`. No controller parameters, task thresholds other than the versioned goal/ROM, physics, installation, table geometry or historical evidence were changed; no reset, stash, clean, delete, push, merge or High-ROM commit occurred.
