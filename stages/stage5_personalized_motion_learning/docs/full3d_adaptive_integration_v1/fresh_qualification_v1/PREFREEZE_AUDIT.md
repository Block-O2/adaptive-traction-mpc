# Fresh varied full-3D qualification: independent prefreeze audit

Date: 2026-09-23. Evidence class: source and existing-artifact audit only. No
fresh case, hidden seed, or formal held-out run was generated for this note.
Starting branch/HEAD: `codex/stage5-architecture-recovery` /
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. The worktree was already
dirty; this note does not claim those earlier changes.

## Pre-freeze result

**The existing `run_executed_case` cannot execute the requested varied 24-case,
three-arm qualification as written.** Its public arguments are output path,
actuation toggle, timeout, and latency-replay toggle. It constructs the fixed
`STAGE5_HUMAN`, `STAGE5_GEOMETRY`, default interface, fixed low/moderate task,
fixed commissioning waypoints, and ideal 200 Hz measurement case internally
(`runtime.py`, especially lines 190-215 and 378-417). The command-line wrapper
adds no setup, task, or arm parameters. A new, versioned runner with explicit
immutable case and arm records is a prerequisite; changing only a case JSON
would not vary the MuJoCo plant. Do not run held-out cases until this is audited
and frozen.

## Requested variation versus actual physical support

| Requested dimension | Current source capability | Required qualification boundary |
|---|---|---|
| A: Human mass, inertia, COM, passive stiffness/damping/rest | `HumanV2Parameters` accepts height, body mass, passive terms and rest angles; Stage-3 coupled XML writes their resulting masses, inertials, joint stiffness/damping/springref. Segment masses derive from body mass, lengths from height, COM and inertia from fixed length/mass ratios (`stage3_full3d/.../human.py`, lines 18-65; `coupled.py`, lines 174-207). | A height/body-mass draw genuinely varies physical values, but **not independently**. If the intended unknown family requires independent segment mass, COM or inertia, add a versioned plant-only parameter record and verify every XML inertial field. Do not quietly narrow A to height/body mass. The controller prior must remain frozen across hidden cases. |
| B: thigh/shank geometry and cuff lever arm | Height changes both lengths and the sleeve center through fixed ratios; the sleeve site is generated from `sleeve_center_m` (`coupled.py`, lines 193-215). The effective geometry estimator fits hip x/z, thigh length and **knee-to-cuff distance**; it does not separately identify full shank length from sleeve fraction (`effective_model.py` module contract). | Independent thigh/shank/lever variation needs a versioned physical parameterization. The hidden plant may vary both shank and lever, but report any non-identifiability honestly. Do not use hidden shank length or attachment truth in the deployable estimator. |
| C: hip/bed/robot placement | `Stage5Geometry` has world/base, world/Human and end-effector/cuff transforms; the CR12 model builder accepts geometry (`cr12_plant.py`, lines 56-68, 109-145). The actual `SensorBoundaryPlant` constructor does not pass geometry through (`cr12_plant.py`, lines 356-370). The bed plane height is a Stage-3 constant (`coupled.py`, lines 180-185). | Implement and test case-specific plant placement. Keep controller coordinate conventions and structural priors explicit. World-frame rotation or changed bed height needs a separate frame/clearance audit; translating the hip/robot alone is narrower than this dimension. |
| D: cuff attachment/interface | `Stage5CR12SensorBoundaryPlant` can receive plant interface parameters, but the current runner uses the default. Controller observer has its own nominal interface parameter record (`controller_interface.py`, lines 52-127). | Inject variation on the plant side only; do not pass true stiffness, damping, rest offset or attachment transform into the observer/low-level controller. Check physical site and robot model transform consistency if attachment geometry changes. |
| E: initial q and possibly dq | Plant reset accepts a q vector and solves IK, but runner uses fixed task start and then sets all qvel to zero (`runtime.py`, lines 190-211). | Multiple feasible q starts require task/commissioning consistency and fixed pre-outcome feasibility filtering. Nonzero initial dq is unsupported by this initialization and current task-start semantics; include only after a separately reviewed contract and implementation. |
| F: task start/goal/coordination/duration/profile | `GoalTaskSpec` can describe different endpoints/limits in principle, but the runner binds `PROVISIONAL_LOW_MODERATE_GOAL_TASK` throughout; `_candidate` also reads that global (`runtime.py`, lines 165-178, 190-191, 394-396). Commissioning waypoints remain absolute nominal values. The task spec explicitly rejects a provided full joint trajectory or fixed joint coordination ratio (`task.py`, lines 135-151). | Pass the same case spec to initialization, candidate construction, state machine, scheduler, planner, logs, and all arms. Define “coordination/profile” as varied endpoint geometry or admissible task timing unless a **new versioned task contract** explicitly adds trajectory prescriptions. Preserve current Human ROM q1 0–80°, q2 0–100° and 10 s phase timeout; do not import the 120–130° region. |

## Truth, safety and timing risks to gate before freeze

1. The current nominal controller prior is assembled from `STAGE5_HUMAN` and
   `STAGE5_GEOMETRY` (`runtime.py`, lines 82-102), separately from the physical
   plant. After case injection, verify object identity and data flow: hidden
   parameters may construct MuJoCo and evaluation records only; controller
   geometry, beta prior, observer, prediction, candidate generation, wrench
   mapping and action must receive nominal/causally estimated values. The
   `truth_firewall` JSON booleans at lines 1016-1021 are assertions in a result
   record, not a source-level proof. Use guard tests with deliberately extreme
   hidden values to detect accidental plumbing into the controller.
2. `SessionClearanceContract` uses fitted hip/thigh plus a fixed 0.46 m shank
   upper bound, fixed 0.012 m bed, 0.045 m radius and 0.001 m margin
   (`runtime.py`, lines 105-158). The nominal accepted trace had only
   +0.279 mm sampled minimum clearance, while an earlier run had 61 negative
   estimated-clearance samples (`ACCEPTANCE_REPORT.md`, sections 6 and 8).
   Freeze a structural bound valid for the entire hidden shank/placement/bed
   family **before** seeds. If the bound makes a cell impossible, say so at
   generation-time mechanical screening; never lower the bound after outcomes.
   Sampled positive clearance is not forward invariance or a between-substep
   contact guarantee. Audit actual Human-bed contacts as evaluation data.
3. CR12/Human and CR12/bed geom collisions are filtered; Human-bed and most
   CR12 self-contact remain active (`coupled.py`, lines 106-112;
   `cr12_plant.py`, lines 148-185). Any “collision safe” label must name these
   exclusions. Current planner has no future CR12 reach screen; current-state
   command feasibility happens in low-level execution (`ACCEPTANCE_REPORT.md`,
   sections 1 and 3). Mechanical generation screening may use oracle plant
   geometry but must be completed before outcomes, be logged, and not leak
   into deployable planning.
4. Physics is 0.25 ms, command/measurement 5 ms, adaptation 20 ms, and waypoint
   decisions event-driven. Timing replay rounds measured planner wall time up
   to 5 ms and rejects age above 100 ms (`runtime.py`, lines 800-832). It is
   controlled synchronous replay, not concurrent or hardware-real-time
   validation. The existing runtime study qualifies a development corpus; it
   does not prove deadlines on the varied domain. At every formal arm/case,
   require timing replay, account for each arm's actual compute delay, and
   preserve stale-plan aborts. Execute arms in preregistered shuffled order or
   otherwise control machine-load ordering.
5. Align every error at identical boundary timestamps; require N intervals and
   N+1 boundary states, exact terminal boundary, interval force cost weighted
   by executed duration, and no proposed-but-unexecuted interval (`runtime.py`,
   lines 930-1034; `TIMING_ERRATUM.md`). An aborted arm remains in the paired
   denominator, with its observed interval and abort reason. Never compare
   unequal horizons only on survivors.

## Arms and 24-case design recommendation

Predefine 24 accepted **setup/task cases**, preferably 4 task families × 3
current-ROM operating-range cells × 2 independent replicates, while each case
also carries a preregistered A–E physical draw. The design must show actual
coverage of every requested variation and avoid collapsing independent
unknowns into one linked scale. Generate a bounded pool and apply only
pre-outcome, arm-independent mechanical feasibility filters; save all proposed
and rejected draws with reasons. Once an accepted case is exposed to any arm,
never replace or exclude it because of completion, accuracy, contact, timeout,
or numerical failure. The Auditor should generate and seal hidden seeds only
after source/config/assets/ranges/gates/generator are frozen; Builder should
see the cases only through the execution interface, not a result-informed
selection process.

Run adaptive, commissioning-only, and fixed/population arms on the **same
physical case, measurement stream model, task, limits, plant initialization,
commissioning duration, execution stack and latency rule**. Commissioning-only
may retain the acquired geometry/beta/residual handoff but freeze task-time
updates. Fixed/population must use its frozen prior from the outset; if it
shares the physical commissioning trajectory, log the exposure and prohibit
belief updates. These are distinct comparator definitions; preregister them
before evaluation. Keep physical commissioning cost separate from task cost,
or include it for every arm consistently. Any oracle is a labeled
non-deployable diagnostic with explicit information access and must never be
counted as a deployable success baseline. A beta-only arm is optional and must
not displace the three required arms.

Suggested **pre-outcome** numerical gates for discussion at freeze: 24/24
well-formed case/arm provenance and truth-firewall checks; zero hard ROM,
realized motion/wrench/actuator/registered-clearance violations in every
arm (any failed case makes the safety gate fail); no silent stale-plan
activation above 100 ms; all task intervals time-aligned and accounted for;
task completion reported as a count with a fixed required minimum (e.g.
22/24, chosen now, not after results); nonzero task-time beta/residual update
attempts and logged effects under the adaptive arm; predeclared paired
tracking statistic such as median within-case time-aligned RMSE improvement
over *each* comparator, with a fixed effect threshold and failure penalty.
The old reduced-model 20% threshold has no full-3D justification and must not
be copied automatically. A per-case completion threshold, effect size,
aggregation rule, and treatment of comparator failures must be frozen before
any held-out outcomes; 24 cases cannot justify a broad reliability claim by
itself. Report force integral and peaks, latency distribution, estimator error,
geometry-fit acceptance, contact, and near-upper-ROM strata as secondary
metrics, including adverse values.

## Audit decision

Prefreeze status: **not ready for formal held-out execution**. The Builder may
implement a new versioned case/arm harness and run declared development/smoke
checks, then freeze a complete scientific contract. The Auditor will review
that frozen source/contract and only then generate the sealed hidden seed
manifest. No source/config/parameter or historical artifact was changed by
this audit note; no formal case was run, and no git staging/commit/push/reset
or branch switch was performed.
