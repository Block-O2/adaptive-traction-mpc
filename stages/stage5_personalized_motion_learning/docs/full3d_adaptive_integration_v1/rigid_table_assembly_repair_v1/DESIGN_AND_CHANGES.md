# Design and change record

## Pre-outcome geometry diagnosis and repair

The historical 33.35 kN simulated bed–thigh force was caused by a −4.819128
mm fixed proximal capsule–table overlap. Fixed hip means q1/q2 cannot remove
that overlap. Old ±6 mm symmetric vertical installation sampling allowed it;
that sampling and the failed historical qualification remain untouched.

The new *evaluation/generation-side* `rigid_table_assembly_v1/assembly.py`
implements the approved fixed-hard-table interpretation. Historical negative
hip-z offsets are reflected above nominal tangency with their absolute
magnitude preserved. Existing legal placements ≥0.1 mm are copied unchanged;
near-tangent placements are raised only to +0.1 mm. The latter is a deliberately
small positive installation margin, separate from 1 nm numerical signed-gap
tolerance and the historical 2 mm shank static screen. The old maximum +6 mm
height remains the upper legal installation variation. The selection uses
geometry alone before controller outcomes, not task completion or tracking.

The full assembly screen distinguishes fixed thigh gap; sampled full-thigh and
shank task geometry; initial Human capsules, sleeve, cuff bar, adapter and
articulated CR12 distances to table; robot/Human distances; initial contacts;
start/goal IK and joint limit margins. Even `contype=0` / `conaffinity=0` geoms
are explicitly measured. Base/link1 mount geoms are inventoried but not
conflated with articulated robot sweep. A finite visual table footprint does
not limit the MuJoCo plane collision. Dynamic contact is monitored per pair
through physical integration and remains separate from static assembly.

The screen retains the original task start↔goal 2 mm shank conditioning, but
does not reject all commissioning shank surface contact: moving limb contact
may be legitimate. It records the commissioning static shank minimum
separately. It refuses fixed/table or robot/body penetration in reset/goal
where measured. An IK-search failure is classified as initialization/search,
not proven physical infeasibility. The robot initial state and cuff interface
are reconstituted by the same normal CR12 `reset` path after the geometry
changes; no old checkpoint/model fit is imported.

**Scope correction after independent audit:** the emitted `ASSEMBLY_VALID`
label means the fixed proximal and registered *initial/task-endpoint* screen
passed. It is not proof that all commissioning references or intermediate
CR12/cuff configurations are nonpenetrating. Every old24 candidate has at
least one negative *static commissioning reference* shank gap, from −6.417 to
−55.582 mm across all 24 (−6.417 to −49.482 mm across the executed 22).
The prior experiment contract explicitly allowed and recorded commissioning
shank–table contact; this is not retroactive formal exclusion. It is, however,
a material reference/identification limitation on a rigid table: the exact
commanded joint waypoint is geometrically unrealizable. The actual controlled
Human deviates instead and contacts the table by about 1 mm at most in these
executed traces. No controller/reference was changed mid-replication.

The evaluation-only executed-boundary geometry audit samples each recorded
5 ms Human/CR12 state (not every 0.25 ms physical state) and checks modeled
capsules, provisional sleeve/cuff bar, adapter and articulated robot solids,
including collision-disabled pairs. One repaired strongest case reaches a
−0.479 mm *disabled-collision sleeve*–table signed gap in commissioning;
there is no MuJoCo contact force for this pair because the historical mask is
disabled. This prevents claiming that the entire physical cuff envelope was
validated, despite removal of the fixed proximal thigh artifact. The cuff
geoms are provisional model surrogates, not measured hardware envelopes.

## Pre-outcome physical checks

The static MuJoCo sweep gave 1303.829 N initial thigh–table contact at −1 mm
gap, and zero initial contact at 0, +0.01, +0.05, +0.1 and +0.2 mm in one fixed
template. Zero initial contact at tangency does not override historical
195.003 N peak during actual nominal commissioning, so tangency is not admitted.

The 0.1 s unactuated physical prefix used actual CR12, compliant cuff, Human,
bed and native `mj_step2` force extraction. It is a mechanics check, not a
controller test. Historical strongest overlap remained at 33,353.295 N for
the entire 0.1 s; its versioned repaired counterpart had zero thigh–table
contact/force. The unchanged legal comparison and +0.1 mm nominal reference
also had zero thigh–table contact/force. The normal impulse used each actual
0.25 ms physical interval, not boundary samples or an extra terminal step.

## New discovery during complete-assembly screening

Two old cases with legal proximal thigh gaps are *not* declared valid:
`balanced_near_upper_current_rom_r02` has −1.773 mm sleeve–table initial
signed distance; `balanced_ordinary_r02` has −2.513 mm. The sleeve geom has
collision disabled, so contact enumeration alone would hide this overlap.
At this v1 screen, correction within the existing +6 mm hip-height limit was
not yet demonstrated; they were invalid in v1 and not forced into that
executed set. A separately versioned v2 rule below resolves one initial
assembly, not its full motion envelope. All 24 originals remain in the mapping and historical
denominator. No sleeve shape or collision mask was changed.

## Controller and physics isolation

Only a new evaluation-side package, new development case JSON and runner
instrumentation were added. No existing production controller/estimator,
Stage-3/5 physics, CR12 asset, cuff parameters, table shape, collision
settings, task goals, motion/force/ROM limits, stale-plan rule, value hook or
historical result was modified. `run_executed_case` is invoked with
`dev_a_recovery=True`, `dev_c_bumpless_transfer=False`, timing-aware latency
replay, continual adaptive arm and `formal_qualification=False`. The simulator
uses the new hidden geometry but the deployable controller does not receive it.
The physical interaction path is still actual CR12 torque actuation, compliant
cuff transmission and Human V2 MuJoCo motion with fresh sensor-boundary
feedback. Completion differences are observed under assembly changes with
unchanged controller source; causal attribution is limited by different
initial physical states and timing-aware replanning, and cannot be credited
to a controller revision.

## Subsequent geometry-only v2 extension

The v1 screen motivated a separately versioned calculation using only the
initial sleeve signed gap and the pre-existing +6 mm installation ceiling.
One case needs a further +1.873398 mm and passes the unchanged initial/goal
screen at +3.650576 mm total hip shift; the other would need +7.178067 mm
total and remains outside the allowed installation range. All 22 v1-valid
case files are unchanged. The additional physical run commissioned but its
first ACTIVE_RECOVERY call rejected all five candidates due to −0.931382 mm
estimated-origin shank geometry. The sampled-path sleeve later overlapped
the table by −3.132480 mm while that collision pair was disabled. This
demonstrates a remaining whole-path envelope issue; no additional hip lift
was selected from the run outcome. See `ENVELOPE_EXTENSION_V2.md`.
