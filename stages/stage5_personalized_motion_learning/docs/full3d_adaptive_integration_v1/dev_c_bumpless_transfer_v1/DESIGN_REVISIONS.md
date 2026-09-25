# DEV-C development change log

## Frozen contract

`CONTINUITY_FREEZE.md` and config were written before any DEV-C physical output.
The four numeric continuity gates (1.30 Nm action, 2.69 N force, 0.58 Nm moment,
2.06 Nm CR12 torque per 5 ms) and 0.25 s initial duration remain fixed.
Independent Auditor identified the direct retarget jump `alpha·Δtarget` before
the first DEV-C output; the design was corrected to a locked in-flight target
and a latest-wins pending target. No result informed this correction.

## Local revision 1: old model at new deployable state

Observed in `results/.../dev_c_bumpless_transfer_v1/matched_v1/`:

- Largest case: direct 34.780445 Nm first robot step; bumpless 1.334044 Nm,
  new belief fully realized at t=7.275 s.
- Middle case: new branch **failed the frozen gate on the first interval**:
  Human action 2.162841 > 1.30 Nm, total desired force 3.324445 > 2.69 N,
  robot torque 2.085425 > 2.06 Nm. Internal record-to-record differences
  were smaller; ignoring the checkpoint→first-command edge would falsely pass.
- Ordinary and nominal branches had no gate violation in the local window.

Mechanism: at alpha=0 the old dynamics were evaluated using the newly
activated state estimate and reference. That same-state old-model action can
differ from the Human action actually executed one control interval earlier.
Thus zero model-blend fraction alone is not a bumpless **control-output** handoff.
The v1 failed traces are preserved; no threshold, geometry, estimator, model,
force/ROM/acceleration limit, plant, or task changed.

## Local revision 2: executed-action anchor

At the start of a large model-effect transition, verify that the immediately
preceding action was physically commanded in `TRACK` with
`SAFE_UNCHANGED` filter and unsaturated CR12 torque. Define the offset

`delta_anchor = u_previously_executed − u_old_model(q_hat_now,dq_hat_now,a_req_now)`.

During the finite 0.25 s transfer, request

`u_applied = (1−alpha)[u_old_model(q_hat,dq_hat,a_req)+delta_anchor]
           + alpha u_locked_new_model(q_hat,dq_hat,a_req)`.

At alpha=0 the requested Human action equals the last verified executed
action. At alpha=1 the offset vanishes exactly and the locked accepted model
takes full control. All intermediate actions still pass the existing allocator,
force filter, supervisor, CR12 actuator limits, and physical plant. A missing
or unverified predecessor fails closed rather than claiming continuity.

This is a targeted development revision after the recorded v1 failure,
not a new frozen scientific hypothesis or a post hoc threshold change.
The output namespace `matched_v2/` must be compared against the unchanged
`matched_v1/` and preserved DEV-B direct branch before promotion.

## Full-session revision 3: model-effect-scaled duration (decision before rerun)

`sessions_nominal_v1/` is a preserved adverse result: nominal development
case aborted on `SESSION_CLEARANCE_LIMIT` at about −0.064 mm deployable
clearance during RETURN. A same-code explicit DEV-C-off comparison in
`sessions_nominal_direct_v1/` completed, as did historical DEV-A. This is a
DEV-C-specific full-session regression, not a reason to change clearance.
The first startup transfer was a no-op; later beta/residual promotions created
11 fixed 0.25 s transfers, even though their model action gaps were only
0.25–1.99 Nm rather than the 18.24 Nm strongest DEV-B activation gap. The
fixed duration introduced avoidable accepted-model lag.

Before evaluating revision 3, the proposed policy is to keep the *same*
quintic fraction and locked-target/latest-wins semantics but size each finite
duration from the deployable, same-state Human-action gap at its start:

`T = max(0.050 s, 1.25 × 1.875 × 0.005 s × 2.0 × ||u_new-u_anchor||
                   / (2.06−0.34350449) Nm)`.

The 1.875 factor is the maximum derivative of the quintic smoothstep. The
2.0 Nm CR12/Nm Human-action factor conservatively rounds up the 1.91 ratio
observed in the independently matched strongest activation. The numerator's
1.25 is an explicit engineering factor; the denominator reserves the largest
ordinary 5 ms CR12 change measured before DEV-C from the frozen 2.06 Nm gate.
Thus the 18.24 Nm historical effect still takes approximately 0.25 s,
whereas a 1–2 Nm later update can complete in 50 ms. This is a development
rate schedule, **not** a universal proof of bounded CR12 torque for all
geometries. The unchanged four frozen output gates must still be measured
on matched traces, and physical/clearance guards remain authoritative.

The policy is only a control-application change: it does not alter beta,
residual, fitting cadence, bounds, or any accepted model. The original fixed
0.25 s config and adverse session are preserved. Revision 3 uses a new config
and `matched_v3/`, `sessions_*_v2/` output namespaces. If it does not resolve
the nominal regression without creating a new local discontinuity, do not
relax the frozen gates or session clearance contract.

## Full-session revision 4 decision: control-output envelope (before evaluation)

The consumed 24-case revision-3 regression retained 24 commissioning,
15 task entries, and 2 completions, but exposed an important failure of
generalization of the local continuity test. During a later TASK model
transfer in `elevated_start_middle_r01`, a 5 ms pair within unchanged TRACK
and the same waypoint schedule had approximately 0.514 Nm Human action change,
10.914 N desired force change, and 6.747 Nm CR12 command change. These exceed
the frozen 2.69 N/2.06 Nm output gates, despite the four selected matched
activations passing. A second case had a 4.167 Nm robot step. Initial analysis
incorrectly included terminal abort rows with non-executed zero commands;
`regression_summary_dev_c_v3.json` excludes them and preserves both earlier
draft summaries. A logging-only replay confirms that allocator `Jᵀ` contribution
is a major driver, with smaller feedback changes. This is a later-update
**transfer-output** problem, not merely OS noise.

Before producing any revision-4 outcome, the proposed narrow extension is:

1. Keep the accepted model, action-level convex blend, executed-action anchor,
   locked target, latest-wins queue, and v2 duration law.
2. At each 5 ms in-flight step, use the *existing* deployable loaded-execution
   context to preview candidate actions through the existing cuff allocation,
   pose/velocity feedback, and CR12 `Jᵀ` mapping. Advance `alpha` no farther
   than the largest candidate satisfying the **already frozen** four adjacent
   output gates relative to the previous actually commanded TRACK output.
   No true Human state/contact enters this preview.
3. The existing force filter/supervisor still run once on the selected action.
   Verify the resulting executable output before physical actuation; if it
   differs materially from preview and exceeds a frozen gate, fail closed
   and preserve the diagnostic, never apply an unverified jump.
4. Bound an active transfer to at most four times its originally computed
   duration. If the target cannot become fully active inside that window,
   abort explicitly rather than allowing indefinite old-model reliance.

This is an output-level control-application guard, **not** a new physical force,
ROM, clearance, or hardware safety limit. It can create a new explicit
transfer-deadline abort if the frozen output envelope cannot be met; such a
case must be reported as a DEV-C failure, not hidden. The four output gates
remain unchanged. Local matched, representative sessions, and (only if those
pass) a new 24-case development regression use fresh `*_v4/` result namespaces;
the revision-3 24-case results remain untouched. The extra preview computation
must also be timed/reported. If this proves too costly or cannot preserve
existing filter/supervisor semantics, stop with scope-change evidence rather
than deleting checks or weakening gates.

## Revision 4 observed outcome (not promoted)

All four original matched checkpoints passed the same frozen gates under v3,
but their output envelope did not bind; they cannot validate behavior at a
genuinely constrained later handoff. In the representative physical
`elevated_start_middle_r01` replay, recovery began at about 7.025 s and
the first v3 transfer command failed closed with
`MODEL_TRANSFER_NO_OUTPUT_CONTINUOUS_ACTION`. Endpoint diagnostics at the
frozen zero-slope `alpha=0` show a **zero Human-action step** yet a **5.059 N
desired cuff-force step** (gate 2.69 N). No transfer command was applied and
`belief_351` was not fully realized. This proves infeasibility of the
implemented zero-slope first step, not every possible action fraction. The
event does not separate geometry, reference/pose, state evolution and
allocation contributions. The failure artifact and the earlier v2 24-case
regression remain intact; no second 24-case v3 regression was launched.
