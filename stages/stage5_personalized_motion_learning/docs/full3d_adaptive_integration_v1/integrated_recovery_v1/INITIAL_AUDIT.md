# Independent mechanics and replay audit

Date: 2026-09-24. Evidence class: development / evaluation-only diagnosis.
Auditor performed source inspection and independent calculations; no controller,
estimator, configuration, plant or historical result was edited by the Auditor.
This file is the Auditor's sole repository change.

## Decision

The mechanics evidence supports the campaign terminal status
`BLOCKED_MECHANICS_OR_DEPLOYMENT_INFORMATION`. This is not a conclusion that
every task is dynamically impossible, nor that contact explains every prior
failure. It means that full-domain recovery cannot yet be interpreted under a
resolved intended fixed-hip / thigh / bed physical relationship.

The campaign amendment allows correction of a demonstrated assembly defect to
restore documented intended mechanics. The inspected evidence does not select
one such correction: moving the hip, changing thigh collision shape, changing
bed geometry/compliance, permitting pelvic motion, or constraining downward
placement are different substantive physical/domain choices. None follows
uniquely from a force-frame or unit bug. The user retains the original unknown
domain and physical constraints. Excluding the affected cases or weakening
contact to get a passing controller would violate that boundary.

Stopping here therefore follows the new integrated contract's mechanics gate;
it does not reinstate DEV-C's obsolete method restriction. Coherent control
development can resume after the intended mechanical relationship is resolved.
The already observed ordinary-case failures also show that resolving mechanics
will not by itself establish integrated recovery or adaptation benefit.

## Independent causal findings

Stage-3 `coupled.py:43-52,183-198` defines bed plane height 0.012 m, nominal
fixed hip height 0.062 m and thigh capsule radius 0.050 m. The capsule's
proximal sphere is centered at the fixed hip. Stage-5 `plant.py` replaces the
hip transform from `geometry.world_from_human`; `fresh_qualification_v1/scenario.py`
adds the hidden hip translation. The registered generator varies hip z by
plus/minus 6 mm (`domain.py:65-66`). Hence the proximal sphere's signed gap
is exactly the hidden hip z shift and cannot be changed by either Human joint.

For `balanced_near_upper_current_rom_r01`, the shift is -0.004819128111260734 m.
Independent checkpoint and initial-state geometric evaluations give the same
4.819128 mm penetration. At t=7.025 s the bed-thigh contact force is
33,353.29515926 N normal and 322.83548030 N tangential. Independently applying
the contact-frame wrench transformed by `contact.frame.T` as equal/opposite
world loads with `mj_applyFT` gives Human generalized load
[15.36388125, 0] Nm, equal to `qfrc_constraint`.

The Human normal-contact Jacobian is approximately [-5.55e-17, 0]. The enormous
normal force therefore has essentially no joint-controlled separation
direction at this fixed proximal sphere. Tangential force, acting through a
47.590 mm lever at the solver contact point, supplies the observed hip load.
No extraction, Newton/kilonewton or frame-conversion error was found.
This remains a simulated reaction, not a validated human load prediction.

Eleven of the 24 consumed formal cases have negative fixed proximal gaps.
The original domain screen and `TruePhysicsMonitor` check shank clearance and
shank-bed contact; they do not certify whole-leg nonpenetration. Their original
shank-specific metrics remain valid within that limited definition.

## Force timestamps and numerical impulse

`replay_integrated_contact_v1.py` wraps `mujoco.mj_step2` without changing its
inputs. `SpringDamperCoupledUR10eHumanV2.step()` first executes `mj_step1`,
applies the existing interface/soft-limit forces, then executes `mj_step2`.
The wrapper samples contact forces immediately after that solve/integration,
before `observe()` / `_refresh()` recomputes next-boundary forward dynamics.
Thus contact geometry and solved force describe the executed interval's
left boundary even though `data.time` has advanced to its right boundary.

The recorded impulse is the sum of the solved normal force times each actual
physics interval duration. It is a discrete numerical contact impulse, not
a continuous-time or experimental measurement. The Auditor independently
recomputed the raw arrays; all intervals are contiguous, finite, and 0.25 ms
up to floating-point representation. No next-boundary refreshed force was
substituted into this integral.

| Replay | Intervals / duration | Thigh normal peak / impulse / contact duration | Shank normal peak / impulse / contact duration |
|---|---|---|---|
| balanced near-upper R01 | 28,100 / 7.025 s | 33,353.295159 N / 234,306.898494 N s / 7.025 s | 94.829040 N / 80.453856 N s / 1.14175 s |
| balanced ordinary R01 | 28,120 / 7.030 s | 0 N / 0 N s / 0 s | 91.383507 N / 73.469499 N s / 1.085 s |
| development nominal | 28,100 / 7.025 s | 195.002635 N / 8.172986 N s / 0.829 s | 119.327203 N / 109.790661 N s / 1.2495 s |

Strongest-case thigh contact begins at t=0 and persists throughout all 28,100
intervals with invariant 4.819128 mm penetration. Nominal has 3,316 thigh
contact intervals at only roundoff-scale penetration (minimum -4.16e-17 m).
It must not be described as having no thigh load. Ordinary is thigh-contact-free;
neither contrast is free of all Human-bed contact because both have shank contact.

## Replay integrity and limits

The Auditor independently confirmed exact final `mjSTATE_INTEGRATION` equality
against each original DEV-B checkpoint for all three replays. This vector
includes full physics/user/warmstart integration state; it is not a hash of
every intermediate state or the entire serialized controller object.

For the strongest case, independent comparisons also found exact equality of
qpos, qvel, qacc, qacc_warmstart, qfrc_constraint, efc_force, ctrl, body/site/geom
positions, old and target model values, current observation/measurement,
mapped reference, reference q/dq/ddq, phase, step/time, pending plan, active
segment and last desired pose. The last-eight-row preactivation JSON differs
only in the new presence of `robot_torque_components` on its last row; common
data match. The Auditor did not claim byte-identical complete pickle files or
independent historical substep-state equality at every interval.

The force instrumentation is read-only and the saved endpoint evidence is
consistent with an unchanged physical replay. Recorded historical planning
delay was deliberately replayed. Wall time with instrumentation provides no
new latency, hardware real-time, generalization or formal-qualification evidence.

All 607 baseline source/config/asset hashes independently matched current files,
and the saved dependency archive's SHA-256 matched `BASELINE_MANIFEST.json`.
This protects the reviewed local dependency basis; it does not make the dirty
working tree clean-clone reproducible.

## Validation scope and remaining action

Checks used targeted source reads and lightweight Python/NumPy/MuJoCo
calculations in `mpc_learn`, with the registered Stage-3/4/5 source paths. One
Auditor comparison initially used invalid direct equality on array-containing
geometry dictionaries, raised `ValueError`, and was rerun using exact serialized
value comparisons; the corrected check passed. No failed rollout was hidden.
No formal or fresh held-out experiment was run by the Auditor. No scientific
variables, parameters, assumptions or acceptance criteria changed. No staging,
commit, push, reset, stash, branch switch or deletion occurred.

Exactly one recommended next step: resolve and document the intended fixed-hip,
proximal-thigh and bed relationship across the full registered placement domain,
with its physically justified support/contact model, before implementing a
versioned mechanics change and resuming integrated development.
