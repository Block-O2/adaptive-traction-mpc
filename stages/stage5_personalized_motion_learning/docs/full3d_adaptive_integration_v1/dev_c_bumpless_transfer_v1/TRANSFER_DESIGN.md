# DEV-C control-effect transfer design

## Boundary and scope

The estimator still accepts fitted effective geometry, 11-D beta, and state
residual under the preexisting laws. DEV-C changes only how an accepted Human
model's inverse-dynamics *control action* becomes active. Planning and state
observation see the accepted belief as before. There is no interpolation of
beta or modification to identification data, cadence, smoothing, bounds, or
the 3%-of-span cap.

The production insertion point is
`HumanWaypointMPCShadowContractV1.command(..., action_transform=...)`, after
the accepted model computes desired generalized action `u_H` in Nm and before
the existing cuff-wrench allocator/force filter/loaded supervisor/CR12
`Jᵀ` torque mapping. The callback defaults to `None` so historical non-DEV-C
callers are unchanged. `runtime._execute_interval` installs the callback only
for explicit `dev_c_bumpless_transfer=True` development runs. Formal
qualification with DEV-C enabled is rejected pending a new frozen campaign.

## Control equation

At the first 5 ms command after a large accepted-model change, the last
verified executed action `u_prev` is the output anchor. For current deployable
state estimate `x_hat` and requested reference acceleration `a_ref`, define

`u_old = M_old.inverse_dynamics(x_hat, a_ref)`

`u_new = M_locked_new.inverse_dynamics(x_hat, a_ref)`

`delta_anchor = u_prev − u_old(start)`.

For `s = clip((t−t_start)/T,0,1)` and
`alpha(s)=10s³−15s⁴+6s⁵`, the action passed downstream is

`u_applied = (1−alpha)(u_old + delta_anchor) + alpha u_new`.

At `alpha=0`, `u_applied=u_prev` exactly; at `alpha=1`, the anchor vanishes and
the locked new accepted model is exact. The source and target actions are
recomputed at each fresh deployable state/reference; the held anchor is an
output-level correction, not a frozen Human trajectory. This convex action
bridge is a control-application device, not a claim that intermediate beta
vectors correspond to anatomical patients. The existing candidate-planning
mechanics screen remains active. Each transformed execution action passes the
existing allocator, force/moment filter, loaded supervisor, robot limits, and
physical CR12–cuff–Human stepping in their original order; the planning
mechanics screen does **not** separately recheck every intermediate blended
action.

If the same-state model-effect action gap is at most 0.19321618 Nm (twice the
largest ordinary commissioning 5 ms Human-action change), the accepted model
applies directly. Identical dynamic models are no-op promotions. These paths
still use the original execution/safety layers.

## Duration revision and source of numbers

The initial fixed 0.25 s design repaired the strongest local jump but had
a preserved nominal full-session clearance failure; the unchanged, same-code
DEV-C-off replay completed. Subsequent accepted-model differences in that
session were much smaller than the strongest 18.24 Nm initial effect, yet each
received the full 0.25 s delay. The versioned v2 duration policy retains the
same quintic bridge but scales each event from the deployable action gap:

`T = max(0.05, 1.25·1.875·0.005·2.0·||u_new−u_prev||/(2.06−0.34350449)) s`.

`1.875` is max `d alpha/ds`; 0.005 s is one control interval; 2.0 is a
conservative rounded local CR12-torque/Human-action ratio from the strongest
matched DEV-B activation; 2.06 Nm is the frozen local robot-step gate; and
0.34350449 Nm is the observed ordinary maximum adjacent-step robot variation
from the pre-DEV-C four-case corpus. The 1.25 factor adds engineering margin.
This formula is a *development* rate policy, not a global hardware or
configuration-independent torque bound. The unchanged measured four-output
gates remain the acceptance test. There is no hard upper bound on `T` for
arbitrary finite accepted action gaps; logs record each actual duration.
The nominal v1→v2 replay is a strong same-setup outcome comparison, but does
not isolate model-version lag as the *only* mechanism behind clearance: the
duration change also changes the entire later control trajectory.

The v1 fixed-duration config, v1 adverse nominal session, and earlier failed
matched first-edge result remain available under separate paths. The v2
action-gap-scaled config generated the four-case local pass and 24-case
development regression. It is not globally continuity-qualified.

## Output-envelope revision and limit discovered

After v2's later task-period transfers exceeded frozen cuff/CR12 step gates,
the versioned v3 opt-in config added a deployable loaded-execution preview and
an output-level alpha envelope. It keeps the existing filters and supervisor,
checks the chosen physical command again before actuation, and fails closed
if no allowable step exists or transfer cannot finish within four times its
planned duration. This is a new transfer-specific fail-closed rule, not a
change to physical force/ROM/clearance limits. The analytic candidate-alpha
interval assumes an affine preview; clipping can make the complete mapping
non-affine, so the selected preview and actual output receive explicit
checks. We do not claim the interval is universally the largest feasible set.

Four original matched checkpoints still passed under v3. A representative
full session (`elevated_start_middle_r01`) instead aborted at the first
ACTIVE_RECOVERY transfer. At the frozen zero-slope start fraction `alpha=0`,
the Human action was anchored exactly to the previous command (zero step),
but the desired cuff-force step preview was 5.059 N (>2.69 N). The manager
correctly refused actuation and never declared the accepted `belief_351`
fully realized. This establishes infeasibility for the **implemented
zero-slope first-step transfer**, not for every possible nonzero-alpha or
coupled handoff. The available event does not isolate how much of the force
reanchor came from geometry, pose/reference, state evolution, or allocation.
The v3 source remains development-only opt-in and is **not promoted**.

## Repeated updates and physical realization

An in-flight target is locked. New accepted beta/residual updates are
latest-wins queued; they do not restart `alpha` or change the target inside
the active bridge. At mathematical completion the current locked model becomes
the active control model. It counts as **FULLY_REALIZED** only after an
enabled, unsaturated, `TRACK` command passed both filters unchanged. A
`BRAKE`, filtered, or saturated command does not prove the accepted Human
action reached the robot. Then, if a newer accepted model is pending, another
finite anchored transfer can begin. Intermediate queued versions may be
superseded. Under perpetual faster-than-transfer updates, the latest accepted
version can lag the fully realized version; the contract does not guarantee
every intermediate version is physically realized. If updates stop, the last
accepted version is reached after the current locked transfer and one pending
transfer, provided ordinary execution remains in unchanged TRACK. This is a
conditional, not an unconditional safety guarantee.

Invalid/nonfinite accepted models or a missing verified predecessor fail
closed; no reverse instantaneous snap to an old model is attempted. The
existing safety supervisor/abort response remains authoritative. Model
transfer uses only deployable estimated state, reference, model versions, and
already commanded action. True Human q/dq, hidden geometry, and evaluation
contact are logged only, never used by the transfer decision.

## Implementation map

- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/bumpless_transfer.py`:
  `BumplessHumanActionTransfer.offer`, `.apply`, `.note_execution`, `.snapshot`.
- `src/traction_mpc_stage5/human_waypoint_shadow.py`:
  `HumanWaypointMPCShadowContractV1.command` action-transform insertion.
- `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py`:
  `_execute_interval` and `run_executed_case` integration, event/trace output.
- `configs/full3d_adaptive_integration_v1/dev_c_bumpless_transfer_v1.json`,
  `dev_c_bumpless_transfer_v2.json`, and `dev_c_bumpless_transfer_v3.json`:
  preserved development revisions; v3 is the last explicit opt-in, not a
  qualified production default.
