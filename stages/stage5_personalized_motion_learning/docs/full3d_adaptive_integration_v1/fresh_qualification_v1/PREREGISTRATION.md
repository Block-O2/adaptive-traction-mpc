# Fresh varied full-3D qualification V1 — preregistration

Status: FROZEN for the V1 pre-outcome source/config/asset seal, after independent
Auditor pre-freeze PASS on 2026-09-23. No formal hidden outcomes were inspected
before this seal. This contract is not editable after formal exposure; a repair
requires a new version and new hidden seed namespace.

## Question and physical execution

Determine whether the current continual adaptive CR12+cuff+Human controller
generalizes to fresh patient/setup/task variation within the current registered
ROM. Each arm executes real MuJoCo CR12 torque actuators, physical cuff, Human
V2, and bed contacts, using the original 0.25 ms physics, 5 ms low-level
execution/200 Hz ideal measurement, 20 ms adaptation cadence, event-driven
waypoint planning, and measured planner-time replay. A plan older than 100 ms
is rejected and task-aborted; the prior/current reference is physically
executed during planning. If planning exceeds 100 ms, the prior reference is
integrated for twenty 5 ms intervals up to the 100 ms watchdog, then the
candidate is rejected without activation. An infeasible planning result also
replays its measured, 5 ms-quantized compute delay (capped at the same 100 ms
watchdog) before a distinct infeasibility abort. Any deadline miss fails the
adaptive timing gate and cannot support hardware-delay safety claims.
The replay is synchronous simulation of measured latency, not proof of
concurrent OS/hardware real-time operation. The freeze hashes the optional
native prefix backend source and the exact local compiled binary because the
selected runtime backend can affect both compute time and behavior.

The high-level candidate set, quintic scheduler and runtime-qualified
endpoint-clearance rejection, mechanics screen (200 N/60 Nm), waypoint cost,
zero value hook, 10 s per-phase timeout, 30 s global timeout, task goal/hold/
return semantics, 0–80/0–100 deg Human ROM, 45/75 deg/s task velocity limits,
and 300/600 deg/s² task acceleration limits are unchanged. CR12, bed, and cuff
plant mechanics are unchanged. No large-ROM, RL/value training, controller
retuning, collision-filter or safety-margin change is allowed.

## Hidden conditional domain and cases

There are 24 accepted setup/task pairs: four task families (`balanced`,
`knee_dominant`, `hip_dominant`, `elevated_start`) × three current-ROM cells
(`ordinary`, `middle`, `near_upper_current_rom`) × two replicates. Start/goal
anchors (degrees) are specified exactly in `fresh_qualification_v1/domain.py`;
independent ±1.5 deg start and ±2 deg goal jitters vary each pair. Fixed
commissioning comprises five task-relative waypoints, four 1.5 s quintic
segments, an initial 20 ms causal history hold and 1 s final settle. Its first
node is the *measured* initial support state; the later nodes and final
registered task start are fixed before any outcome. All task starts have zero
initial physical velocity. Task distance/coordination vary the planner-chosen
quintic durations and velocity profiles; this goal-task API has no independent
prescribed path-speed input, so there is no claim of testing arbitrary
externally commanded velocity waveforms.

Each proposal independently draws (uniform continuous, exact intervals):

| Hidden physical quantity | Interval |
|---|---:|
| height, body mass | 1.68–1.76 m; 67–83 kg |
| thigh/shank length multiplier | each 0.97–1.03 |
| thigh/shank mass multiplier | each 0.90–1.10 |
| thigh/shank COM fraction | each 0.40–0.47 of segment |
| thigh/shank inertia radius fraction | each 0.27–0.33 of segment |
| passive stiffness q1/q2 | each 7–13 Nm/rad |
| passive damping q1/q2 | each 3.5–6.5 Nms/rad |
| rest q1/q2 | 3–8 / 7–14 deg |
| cuff attachment along shank | 0.69–0.75 fraction from knee |
| hip translation relative registered setup | x ±10 mm, z ±6 mm |

Segment lengths, masses, COMs and inertials enter the physical MuJoCo XML;
attachment location enters physical cuff site and its force lever. Bed height,
orientation, CR12 base and actuator specifications, cuff stiffness/damping,
noise/latency, and anatomical angle conventions stay registered. Physical
placement varies only sagittal x/z translation: other placement degrees of
freedom and nonzero initial velocity are not qualified. The 0.46 m deployable
conservative shank-length bound exceeds the domain's maximum physical shank
length (~0.422 m); it remains unchanged.

Generation is arm-independent and before any control outcome. A deterministic
cell-specific SHA-256-derived RNG substream proposes at most 30 cases per
cell. The generation-side screen rejects a proposal if static true shank/
bed-plane clearance anywhere along straight task start↔goal interpolation is
below 2 mm, if an initial shank/bed contact exists,
or if CR12 static IK at start/goal fails. Every proposal and reason is saved.
This screen is *not* a dynamic feasibility guarantee, and its hidden geometry
never reaches the deployable controller. If a cell has no accepted proposal
within 30, generation stops blocked; no cell is silently omitted. The
resulting inference is conditional on this statically screened domain. Once
accepted, no case is excluded or replaced for any controller outcome.

An independent Auditor creates `SEED_MANIFEST.json` using a fresh uint64 root
seed only after source/config/gates/generator freeze. Development seed
`4711001` is forbidden for held-out. The same 24 case keys go to all three
arms, in rotating arm order by case index to balance order/load. No oracle arm
is included because a fair oracle controller would change the physical
execution/estimation problem; any later oracle must be separately labeled.

## Deployable observation and truth boundary

The controller sees robot q/dq, simulated cuff pose/orientation, ideal cuff
twist, physical interface force/moment and timestamps at 200 Hz with zero
configured noise, bias and latency. The ideal twist is a simulation limitation.
The observer reconstructs Human q/dq from these measurements with a fixed
structural prior, then commissioning estimates effective hip/thigh/knee-to-
cuff geometry and beta/residual. Hidden body, geometry, placement, attachment,
Human q/dq and true clearance are used only in physical plant construction,
pre-outcome generation or evaluation. No hidden truth may enter estimator,
planner, MPC, force map, candidate generation or action selection. The true
shank capsule bottom minus bed plane is logged after *every* 0.25 ms physical
step by an evaluation-only monitor; registered online clearance uses fitted
hip/thigh, structural shank upper 0.46 m and fixed 1 mm margin. These are
different quantities and both are reported. Thigh-bed support/contact during
commissioning is permitted; task-period shank-bed contact/negative true
clearance is prohibited. Commissioning shank-bed contact is recorded and
reported, not silently claimed as zero; task safety qualification uses the
task-period gate because nominal loaded commissioning has contact while
bringing the limb to the registered task start.

## Three structurally paired arms

1. `continual_adaptive`: physically executed commissioning fit followed by
   task-period beta and state-residual updates at 20 ms input cadence (beta
   proposals on the established slower estimator trigger). No laws, 10%
   smoothing, bounds, or 3%-of-span per-update cap change.
2. `commissioning_only`: identical physical commissioning and acquired
   geometry/beta/residual handoff, then freezes *both* beta and residual for
   the entire task. This compares the combined continual layer, not beta alone.
3. `fixed_population`: performs the same physical commissioning motion but
   discards its fit and runs the pre-registered nominal geometry/beta/zero
   residual for the task, with no task-period update. Its provenance is marked
   `FIXED_NOMINAL`. This is a non-oracle population comparator.

All arms have identical hidden case, task, low-level controller, physical
plant, constraints and 100 ms rule. Physical commissioning is not counted in
task force/tracking integrals; it is retained separately. A failed handoff,
planning deadline, mechanics failure or safety abort stays in the denominator.

## Exact timing/metric contract

All task arrays hold N+1 boundary observations for N executed 5 ms intervals;
no terminal extra step. At boundary t, compare `q_true(t)` with `q_ref(t)` and
`q_hat(t)` with `q_true(t)`, likewise dq. Task-angle RMSE per joint is the
square root of the mean squared boundary error; combined RMSE is the square
root of the mean over both joints/boundaries. p95 and maximum use absolute
boundary error. Physical interaction integral sums the norm of measured
world-frame cuff force (and separately moment) at each executed interval's
left boundary times its actual `t[i+1]-t[i]`. Peak wrench is measured physical
cuff wrench at 5 ms boundaries; true clearance/contact/ROM are monitored at
every 0.25 ms physics step. Report q/dq terminal error, OUTBOUND/HOLD/RETURN
durations, HOLD validity, estimated-vs-true error, beta accepted/attempted,
rate-limit flags, residual steps, planner mean/median/p95/p99/max, request-to-
activation age, measurement age and all deadline misses. Diagnostics retain
complete adaptation and decision trajectories, not just final aggregates.

## Frozen promotion gates (all must pass)

1. All 24 accepted keys have three complete provenance records or explicit
   preserved runner exceptions; no post-outcome exclusion/replacement; source
   and frozen config/asset hashes unchanged; independent source/result Auditor
   PASS and no deployable hidden-truth path.
2. Continual adaptive completes at least **20/24** entire OUTBOUND/HOLD/RETURN
   tasks, including valid ≥0.5 s HOLD. At least one completion occurs in each
   of the 12 family×range cells. A commissioning handoff abort is a task failure.
3. Across all 24 adaptive arms (including aborted ones), no task-period true
   negative shank/bed clearance, shank/bed contact, hard Human ROM or actual
   acceleration violation, actual cuff peak over 200 N or 60 Nm, CR12 actuator
   command beyond registered limits, or silent solver/allocation failure.
   Each violation is reported individually; no tolerance is added after data.
4. Every activated plan is ≤100 ms old. Adaptive arms have zero planner
   deadline misses/stale-plan aborts. A miss in any other arm must reject the
   stale plan and remain reported; no arm may apply a stale result.
5. On completed adaptive cases, median combined time-aligned q RMSE ≤2 deg,
   pooled completed-case p95 absolute q error ≤5 deg, and median combined dq
   RMSE ≤5 deg/s. These are task tracking gates, not commissioning metrics.
6. At least **18/24** adaptive cases record ≥1 task-period beta proposal,
   ≥1 accepted task-period beta update, and ≥1 nonzero residual update. The
   final-ten-update beta-step distribution and 3%-cap flags are reported; no
   convergence is inferred from completion.
7. Against **each** paired comparator, adaptive has at least **four more
   complete tasks out of 24**; at least four case keys where adaptive completes
   and that comparator does not; and at most one reverse case. This tests
   reference-independent physical task completion, rather than comparing
   each arm's tracking RMSE against its own endogenously chosen/easier
   waypoint schedule. On jointly complete cases we report paired duration,
   tracking, force integral and worst-case differences as secondary evidence,
   but do not promote on survivor-only RMSE. Four net recoveries (16.7
   percentage points) is the predeclared meaningful full-3D effect size; the
   historical reduced-model 20% tracking criterion is not imported.

This small conditional 24-case study cannot establish hardware real-time,
clinical safety, arbitrary 3-D placement, arbitrary speed profiles, or the
future 120–130 deg large-ROM target. In particular,
`current-domain full-3D qualification != large-ROM target-domain validation`.

## Failure policy and stopping

No formal source/config/gate/seed edit after the first hidden outcome. A
failed formal qualification is preserved as failed evidence. Any later repair
returns to separate development, new version and fresh hidden seeds. An
interrupted incomplete artifact is marked infrastructure-interrupted and may
be resumed only after completeness/hash inspection; a completed case/arm is
never rerun. Final status is exactly one of the user-defined five labels.
