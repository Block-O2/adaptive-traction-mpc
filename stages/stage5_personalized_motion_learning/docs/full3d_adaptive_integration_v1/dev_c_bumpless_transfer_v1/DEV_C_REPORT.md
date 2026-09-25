# DEV-C — bumpless adaptive-model control transfer

**Terminal status: `DEV_C_SCOPE_CHANGE_REQUIRED`.** This is a versioned
development/diagnostic result, not fresh full-3D qualification. DEV-C removes
the dominant *local* Human-dynamics activation impulse in four matched
checkpoints, but the current Human-action-only transfer does not meet the
predeclared Human/cuff/CR12 continuity contract over the broader coupled
execution lifecycle. No change is promoted to a formal controller.

## Causal question and frozen boundary

DEV-B identified a 34.780 Nm/5 ms CR12 jump at initial model activation;
matched direct switch gave 34.834 Nm. About 97% of its direction projection
came from the changed Human inverse-dynamics output, propagated through cuff
allocation and `Jᵀ`; that figure applies to the DEV-B matched case, **not**
every later update. A diagnostic ramp had reduced local Human acceleration
9.918 to 0.813 rad/s² without fixing full-session recovery timeouts. DEV-C
therefore separated model *acceptance* from model *control application*,
without altering the fitted geometry, 11-D beta, beta cadence/bounds/3%-span
cap/smoothing, residual learner, task MPC, waypoint set/cost, physical plant,
contact, registered engineering constraints, 100 ms stale-plan contract, or
zero value hook. There was no direct Human torque actuation or hidden truth in
the production path.

Before DEV-C outcome inspection, ordinary 5 ms commissioning command changes
and same-state old-model reanchor established four **development** maximum
adjacent-step gates: Human generalized action **1.30 Nm**, desired total cuff
force **2.69 N**, desired cuff moment **0.58 Nm**, and commanded CR12 torque
**2.06 Nm**. These are not hardware/clinical limits. The checkpoint's previous
*desired* wrench and actual commanded robot torque are included in first-edge
comparisons; terminal non-executed zero commands are excluded. Details and
the ordinary-step values are in `CONTINUITY_FREEZE.md`.

## Implementation and local proof

`BumplessHumanActionTransfer` keeps the latest estimator-accepted model
separate from the currently applied control model. For a substantial action
gap, the first command anchors to the last verified executed Human action,
then a finite quintic fraction blends the retained model's action (with a
vanishing start offset) into the locked accepted model's action. The insertion
point is after Human inverse dynamics and before the existing cuff allocator,
filter, loaded supervisor, and CR12 torque mapping. This does not interpolate
beta, claim an intermediate anatomical model, or bypass execution checks.
New accepted updates queue latest-wins while a transfer is in flight. A
completed transfer counts as physically `FULLY_REALIZED` only after unchanged,
unsaturated `TRACK` execution. Invalid models or an unverified predecessor
fail closed. Tiny same-state action changes can apply directly; this is a
separate path and not covered by the finite-transfer guarantee.

The first fixed-0.25 s design failed a frozen first-edge gate in the middle
matched case (Human action 2.163 Nm, desired force 3.324 N, robot torque
2.085 Nm). Anchoring to the verified preceding executed action repaired that
edge. A fixed-0.25 s full nominal replay then aborted on −0.064 mm deployable
clearance, while the same-code DEV-C-off nominal replay completed. A versioned
action-gap-scaled duration (50 ms minimum; about 249 ms for the strongest
18.24 Nm gap) made the nominal case complete, without changing any scientific
threshold. This nominal comparison does not isolate duration lag as its sole
causal mechanism because the subsequent physical trajectory differs.

From identical DEV-B physical/control checkpoints, the DEV-C-off branch
reproduced the first 40 direct-switch CR12 commands exactly. The v2-duration
DEV-C branch then produced these 5 ms maximum adjacent steps over the local
300 ms window, including predecessor→first command:

| Consumed development case | Direct→DEV-C CR12 step (Nm) | Direct→DEV-C Human-action step (Nm) | Early 200 ms Human componentwise acceleration peak (rad/s²) | Accepted model fully active? |
|---|---:|---:|---:|---|
| near-upper current ROM | 34.780→1.123 | 18.238→0.617 | 9.918→0.532 | `belief_310` |
| middle | 7.655→1.758 | 5.280→0.568 | 6.963→1.573 | `belief_351` |
| ordinary | 2.208→1.468 | 1.111→0.251 | 3.050→1.518 | `belief_351` |
| nominal reference | 0.00463→0.00463 | 0.00137→0.00137 | 0.0296→0.0296 | `belief_322` |

All four selected cases passed all four frozen local gates, and the v3
output-envelope branch also passed those same matched checkpoints. These
results establish local causality and exact new-model takeover at the selected
states, **not** global continuity. The near-upper matched trace retained a
**33,353.295 N simulated bed–thigh normal contact reaction**, present at its
checkpoint. This is neither a cuff force nor a validated real-human load;
DEV-C did not alter the contact model or attribute it to activation.

The versioned force/moment/torque/action and physical acceleration plots are
under `results/.../dev_c_bumpless_transfer_v1/plots_matched_v3_with_moment/`;
matched traces and the corrected aggregate are in `matched_v3/` and
`matched_summary_matched_v3_with_moment.json`. Earlier flawed analysis draft
`matched_summary_v1.json` is retained but superseded: it used measured physical
wrench instead of the previous desired wrench and the wrong acceleration norm.

## Physical sessions and consumed 24-case development replay

The v2-duration nominal session completed with the latest `belief_561`
accepted and fully realized. A balanced-middle session completed; a
near-upper-current-ROM session timed out in ACTIVE_RECOVERY; an ordinary
session stopped with `NO_FEASIBLE_WAYPOINT`. None was excluded.

Only after the selected local cases and representative full sessions did we
run the already-consumed 24 adaptive cases. The authoritative corrected
summary is `regression_v1/regression_summary_dev_c_v3.json`:

| Development lifecycle metric | DEV-A | DEV-C v2 duration |
|---|---:|---:|
| Initialization / commissioning | 24 / 24 | 24 / 24 |
| Task entry | 15 / 24 | 15 / 24 |
| Full OUTBOUND–HOLD–RETURN complete | 2 / 24 | 2 / 24 |

No case changed COMPLETE/ABORTED status versus DEV-A. Abort reasons included
5 recovery timeouts, 3 recovery no-feasible segments, 1 recovery clearance,
4 task no-feasible waypoints, 1 realized cuff-force limit, 2 task velocity
limits, 1 outbound timeout, and **5 stale-plan deadline misses**. The latter
followed the existing fail-closed 100 ms rule; one case's reason changed from
DEV-A clearance abort to stale-plan abort. The 127 recorded planner calls had
mean 31.711 ms, median 8.442 ms, p95 97.307 ms, p99 112.522 ms, maximum
119.396 ms. No acceleration or evaluation-only ROM violations were reported
in this aggregate. Eight aborted episodes ended with the latest accepted
model not yet physically fully realized. The old formal 24-case result stays
failed and unchanged; these replayed cases are **development**, not fresh.

Crucially, task-period transfers violated the frozen **development
continuity** gates: maximum executed adjacent Human action **1.814 Nm**,
desired force **10.914 N**, desired moment **2.346 Nm**, CR12 torque
**6.747 Nm**. The worst pair was TASK `elevated_start_middle_r01`,
t=10.845→10.850 s on the same reference schedule, with blend fraction
0.8915→0.9516. Human-action step was only 0.514 Nm for that pair while
the cuff/robot output was amplified. A separate logging-only replay yielded
an allocator `Jᵀ` component change 6.293 Nm with smaller feedback changes,
but its physical trajectory and total step (4.674 Nm) differed because the
timing-aware simulation observes host planning latency. It supports the
allocation mechanism qualitatively; it is **not** an exact decomposition
of the original 6.747 Nm event. Terminal zero-command rows were erroneously
counted by an earlier draft summary; the v3 summary excludes them without
deleting the draft.

## Output-envelope diagnostic and first remaining divergence

The v3 output-envelope revision was recorded in `DESIGN_REVISIONS.md` before
its outcome. It attempted to slow the blend fraction using deployable loaded
execution previews and the **same four frozen continuity gates**, recheck the
actual selected command before actuation, and abort if the finite handoff
could not finish within four times its computed duration. It kept existing
plant, force filter, supervisor, constraints, task, and estimator unchanged.
Because torque clipping can be non-affine, the analytic candidate-alpha
interval is not a global proof of all feasible fractions; the selected
preview and actual command are checked. The four historical matched local
branches passed again.

The representative `elevated_start_middle_r01` full session then aborted
fail-closed at ACTIVE_RECOVERY start, t≈7.025 s, before the first transfer
command was physically applied. Event `OUTPUT_ENVELOPE_INFEASIBLE` records:
zero Human-action step at the frozen zero-slope first fraction `alpha=0`, but
**5.059 N desired cuff-force step** versus the frozen 2.69 N gate. Latest
accepted model was `belief_351`; the last fully realized control model was
still `population_prior_v1`. The result proves that the **implemented**
zero-slope Human-action-only first step cannot satisfy the cuff-force gate
there. It does **not** prove all nonzero-alpha choices infeasible. Nor does
that one event quantify separate effects of geometry, reference/cuff pose,
5 ms state/estimate evolution, and allocation. The earlier DEV-B 97% dynamics
projection must not be transferred to this different event.

Accordingly, the dominant DEV-B dynamics-switch spike has a local causal
repair, but the desired full Human/cuff/CR12 bumpless lifecycle is not
validated. The last v3 implementation remains explicit development opt-in
(`dev_c_bumpless_transfer=False` by default); formal qualification rejects
it. No fresh qualification or real hardware run was attempted.

## Decision and exactly one next stage

`DEV_C_SCOPE_CHANGE_REQUIRED`: meeting the requested full-output and finite
takeover guarantee for the newly exposed recovery-start case would require
a coordinated handoff of the downstream cuff/geometry/reference/allocator
state, or a separately justified control-output bridge, beyond the
Human-action-only mechanism evaluated here. The **one recommended next stage**
is a matched-state, deployable-input diagnosis of that recovery-start
action→desired-wrench reanchor, varying only action fraction and the already
existing geometry/reference/allocator inputs in isolated diagnostic branches
to identify the first necessary coupled handoff change. Do not implement or
promote such a change under DEV-C; do not retune beta, contact mechanics, MPC,
ROM, constraints, or stale-plan rules based on this result.

`TRANSFER_DESIGN.md`, `MATCHED_STATE_RESULTS.md`, `DESIGN_REVISIONS.md`,
`COMMANDS.md`, `CHANGED_FILES.md`, and `AUDIT_REPORT.md` contain the design,
provenance, exact commands, source ownership, and independent challenge.
All result namespaces are Git-ignored local dependencies; this dirty working
tree is not clean-clone reproducible. No staging, commit, push, reset, stash,
branch switch, deletion, or historical evidence rewrite occurred.
