# Stage-5 Progressive Personalization Longitudinal v1

## Frozen starting point

- PA-A authority checkpoint: `4f8b38f` (`stage5: checkpoint progressive human model authority`).
- Interface study remains EXIT C; interface plant/controller condition is fixed nominal.
- Initial active model in both arms is the already supported RPL-A successor:
  `theta_1 = [1.0000584391, 1.0010424687, 1.0193479803]`.
- Evaluation-only Human truth is damping +20%: `[1, 1, 1.2]`.
- Gamma is exactly `0.5`; trust-driven pacing is disabled.
- The unresolved acceleration monitor, registered limits, Goal-MPC, HOLD,
  Safety Filter, BRAKE, 200 N gate, and CEM settings are unchanged.

## Preregistered A/B contract

The seed schedule was written before new outcomes:

`[20260828, 20260829, 20260830, 20260831, 20260832]`.

These are the next consecutive Stage-5 controller-search seeds after the
frozen RPL-A seeds `20260825–20260827`.  Repetition `r` uses the same seed in
both arms.

- **Arm A — fixed_theta_1:** `theta_1` controls every repetition.  Reduced
  Human-ID may operate in shadow, but cannot update control.
- **Arm B — progressive:** one immutable active model controls each complete
  repetition.  A qualified successor is queued and can activate only at the
  next valid repetition boundary.  A second successor cannot gain authority
  until the newly active model has post-update POSITIVE evidence.
- Maximum budget: five repetitions per arm; 0.25 s session-time reset gap;
  integral blocks cannot cross physical resets.

The only control-interface addition is an explicit, atomically paired initial
Human-model object and version passed to each episode.  The online estimator
and acceleration monitor remain on their frozen deployable nominal-model path.
No Human truth enters fitting, validation, queueing, support, or control.

## Repetition results

All ten episodes reached `OUTBOUND → HOLD → RETURN → COMPLETE`.

| Rep | Seed | Fixed active theta | Fixed phases O/H/R/C [s] | Progressive active theta | Progressive phases O/H/R/C [s] |
|---:|---:|---|---|---|---|
| 1 | 20260828 | `[1.0000584, 1.0010425, 1.0193480]` | `0 / 4.295 / 4.970 / 9.050` | `[1.0000584, 1.0010425, 1.0193480]` | `0 / 4.295 / 4.970 / 9.050` |
| 2 | 20260829 | same theta_1 | `0 / 4.230 / 4.950 / 9.095` | `[1.0001204, 1.0017691, 1.0373246]` | `0 / 4.035 / 4.740 / 9.190` |
| 3 | 20260830 | same theta_1 | `0 / 3.845 / 4.540 / 8.655` | `[1.0001141, 1.0015966, 1.0561071]` | `0 / 3.810 / 4.470 / 8.625` |
| 4 | 20260831 | same theta_1 | `0 / 3.690 / 4.390 / 8.775` | `[1.0001045, 1.0014424, 1.0728907]` | `0 / 3.885 / 4.545 / 8.810` |
| 5 | 20260832 | same theta_1 | `0 / 3.785 / 4.455 / 8.390` | `[1.0000946, 1.0013024, 1.0879943]` | `0 / 3.975 / 4.475 / 8.535` |

Task duration is not treated as personalization evidence.  The primary result
is deployable-domain prediction plus causal authority behavior.

## Candidate, queue, activation, and support lineage

| Fit rep | Active predecessor | Raw candidate | Bounded successor | Qualified / post-support session time [s] | Activation |
|---:|---|---|---|---|---|
| 1 | theta_1 | `[1.0006777, 1.0083091, 1.1991145]` | theta_2 `[1.0001204, 1.0017691, 1.0373246]` | `2.795 / inherited theta_1 POSITIVE` | Rep 2 |
| 2 | theta_2 | `[1.0000574, 1.0000436, 1.2251489]` | theta_3 `[1.0001141, 1.0015966, 1.0561071]` | `11.100 / 11.105` | Rep 3 |
| 3 | theta_3 | `[1.0000184, 1.0000547, 1.2239439]` | theta_4 `[1.0001045, 1.0014424, 1.0728907]` | `20.540 / 20.345` | Rep 4 |
| 4 | theta_4 | `[1.0000051, 1.0000425, 1.2239264]` | theta_5 `[1.0000946, 1.0013024, 1.0879943]` | `29.415 / 29.420` | Rep 5 |
| 5 | theta_5 | `[1.0000020, 1.0000377, 1.2245353]` | queued theta_6 `[1.0000853, 1.0011759, 1.1016484]` | `38.475 / 38.280` | not activated; session ended |

Each post-update decision used eight causally later 0.20 s deployable blocks at
its first scheduled look.  Blocks were formed strictly after activation and
never crossed a repetition reset.  In Rep 2 and Rep 4, the challenger became
qualified about 5 ms before current-model support became POSITIVE; the queue
gate held it while support was NEUTRAL and released it only after POSITIVE.
This is direct evidence that NEUTRAL did not permit drift.

Four actual active-model transitions occurred within the five-repetition
budget: theta_1→theta_2→theta_3→theta_4→theta_5.  Theta_6 remained queued.

## Parameter evolution

| Active model | delta alpha_M | delta alpha_K | delta alpha_D | update norm |
|---|---:|---:|---:|---:|
| theta_2 | `+0.0000619` | `+0.0007267` | `+0.0179766` | `0.0179914` |
| theta_3 | `-0.0000063` | `-0.0001726` | `+0.0187824` | `0.0187832` |
| theta_4 | `-0.0000096` | `-0.0001542` | `+0.0167837` | `0.0167844` |
| theta_5 | `-0.0000099` | `-0.0001400` | `+0.0151036` | `0.0151042` |

Alpha_D moves in one consistent direction.  Alpha_M and alpha_K each have one
sign change after the first step, then continue in a stable shrinking direction
toward values close to 1.  This is reported as a direction reversal, but not
as oscillation: neither component alternates direction again.  The final
evaluation-only distance to `[1,1,1.2]` is `0.112013`; this truth distance is
descriptive and was computed only after all online decisions.

## Deployable prediction evolution

The table evaluates the active model and frozen theta_1 on the same progressive
episode's deployable estimated state and measured generalized-input history.

| Rep | Active model | Active loss [Nms²] | theta_1 loss [Nms²] | Active improvement |
|---:|---|---:|---:|---:|
| 1 | theta_1 | `0.00038295` | `0.00038295` | `0.0%` |
| 2 | theta_2 | `0.00030337` | `0.00036060` | `15.87%` |
| 3 | theta_3 | `0.00027712` | `0.00040076` | `30.85%` |
| 4 | theta_4 | `0.00023243` | `0.00040124` | `42.07%` |
| 5 | theta_5 | `0.00021518` | `0.00044656` | `51.81%` |

Active-model loss decreases monotonically repetition by repetition.  The fixed
arm's theta_1 loss is not monotonic (`0.00036577–0.00041734 Nms²`), so the
progressive trend is not attributed merely to repetition number.

## Closed-loop and engineering observations

| Rep | Fixed duration [s] | Progressive duration [s] | Fixed / progressive cumulative force [N·s] | Progressive peak force [N] | Progressive peak moment [Nm] |
|---:|---:|---:|---:|---:|---:|
| 1 | 9.050 | 9.050 | `855.11 / 855.11` | 112.46 | 14.36 |
| 2 | 9.095 | 9.190 | `856.94 / 860.92` | 112.99 | 14.88 |
| 3 | 8.655 | 8.625 | `813.98 / 810.25` | 111.97 | 14.75 |
| 4 | 8.775 | 8.810 | `823.67 / 827.66` | 113.92 | 14.72 |
| 5 | 8.390 | 8.535 | `789.63 / 797.79` | 111.71 | 14.69 |

- Progressive maximum estimated/truth velocity: `[6.473, 11.915]` /
  `[6.417, 11.838] deg/s`.
- Progressive maximum deployable/truth acceleration: `[154.98, 436.99]` /
  `[155.66, 462.54] deg/s²`, below registered `[300, 600] deg/s²`.
- Fixed maximum deployable/truth acceleration: `[152.70, 426.74]` /
  `[161.20, 479.32] deg/s²`.
- MPC: fixed `2012/2012` and progressive `2037/2037` SAFE_ACTION.
- Safety Filter: all samples `SAFE_UNCHANGED`, intervention norm 0.
- Both arms: zero force-gate, BRAKE, structural, and MuJoCo-warning events.
- All matched-pair regression reason lists are empty.
- Path-free Goal-MPC remained active; no full joint trajectory or coordination
  corridor was introduced.

Runtime remains an independent blocker.  Across repetitions, Goal-MPC mean was
`75.03–76.78 ms` fixed and `74.43–80.54 ms` progressive; p95 was
`90.70–93.16 ms` fixed and `90.90–91.73 ms` progressive.  Every solve missed
the 20 ms target.  No runtime optimization was performed here.

## Questions Q1–Q9

1. **Can theta_1 qualify theta_2?** Yes, in Rep 1 from deployable data.
2. **Does theta_2 receive post-update support?** Yes, POSITIVE at session time
   11.105 s after activation at 9.300 s.
3. **Can supported theta_2 qualify/apply theta_3?** Yes; theta_3 activates at
   Rep 3.  The same chain continues through theta_5.
4. **How many active transitions?** Four beyond theta_1.
5. **Does NEUTRAL hold?** Yes.  Two already-qualified proposals were visibly
   blocked until their active predecessor became POSITIVE.
6. **Stable directions or oscillation?** Alpha_D is consistent; alpha_M/K each
   turn once and then settle monotonically.  No repeated oscillation is seen.
7. **Does prediction improve?** Yes, active loss decreases every repetition and
   improves over theta_1 by 15.87–51.81% after activation begins.
8. **Closed-loop acceptable versus fixed?** In this limited matched simulation,
   yes: 10/10 COMPLETE, no registered safety/event regression.  This is not a
   hardware-safety claim.
9. **What limits further progression?** The five-repetition session budget.
   Theta_6 was already qualified, supported by theta_5's POSITIVE evidence, and
   queued but had no Rep 6 boundary.  The frozen smoothing makes movement
   gradual, but it did not block qualification within this budget.

## Decision

**PP2-A — PROGRESSIVE PERSONALIZATION FEASIBLE.**

The preregistered requirements are met: at least two further active bounded
corrections occurred (four observed), every next correction waited for
post-update POSITIVE support, alpha_D evolved consistently without repeated
oscillation, deployable prediction improved, and no matched closed-loop
regression was observed.

The first post-run analysis pass incorrectly treated one sign reversal as
oscillation and emitted PP2-B despite four supported transitions.  No episode
was rerun.  Derived analysis was corrected to report every reversal but reserve
“oscillation” for at least two alternating sign reversals; PP2-B is restricted
to the preregistered one-correction/too-slow case.  Raw traces and metrics are
unchanged.

## Next trust-to-gamma experiment design — not run

To keep personalization and pacing authority separate, freeze the supported
theta_5 model and lineage from this study and disable further control-model
updates.  Use matched seeds for two small arms:

- Arm A: theta_5 fixed, gamma fixed at 0.5.
- Arm B: the same theta_5 fixed; its already-causal post-update POSITIVE event
  initializes persistent current-model trust, then only the existing 0.75 s
  confidence filter, 0.75/0.25 hysteresis, and 0.25/s recovery / 1.0/s slowdown
  may change gamma.

Keep the acceleration monitor, limits, interface, task, CEM, Safety Filter,
BRAKE, and terminal value unchanged.  This isolates
`supported personalized model → current-model trust → gamma` before any future
experiment combines ongoing model updates with dynamic pacing.

## Scope

This is simulation evidence for the registered damping +20% effective Human
condition and fixed nominal interface.  It does not establish anatomical
parameter recovery, hardware safety, acceleration-monitor correctness,
simultaneous Human/interface uncertainty robustness, runtime readiness, or
general 3–5 repetition personalization.
