# Stage-4 report generalization: audited descriptive analysis

## Integrity

All 36 preregistered arms passed the final integrity audit: exact 4×3×3 coverage, complete finite artifacts, exact frozen metrics, matched exogenous inputs and initial conditions, frozen controller semantics, 36/36 completion, full reference progress, and no recorded safety, ROM, contact, solver, or MuJoCo-warning event. This is simulation evidence only.

## Absolute performance and generalization

PD+FF had the lowest mean tracking RMSE in all four patient cells, but its combined acceleration and jerk RMS were consistently higher than both MPC controllers. Fixed and Adaptive MPC therefore offered a much smoother measured-state envelope, not a universal tracking advantage over PD+FF.

For the moderate mixed patient, mean RMSE was 0.741° (PD+FF), 1.035° (Fixed), and 0.897° (Adaptive). Adaptive reduced the fixed-model mean RMSE while preserving the low-MPC acceleration/jerk regime.

Patient transitions are mechanism changes rather than a validated scalar mismatch dose. Mass and isolated geometry did not monotonically worsen tracking; the moderate mixed case produced the clearest tracking and load degradation. Across nominal-relative deltas, no controller dominated tracking, smoothness, force, moment, and robot effort simultaneously.

## PD+FF versus Fixed MPC

Fixed MPC was smoother in acceleration and jerk in every matched arm. Its tracking advantage was inconsistent: Fixed lowered RMSE in 4/12 matched comparisons, while PD+FF lowered it in 8/12. Force, moment, and robot-torque differences were small and directionally mixed. PD+FF should remain visible because removing it would hide the central tracking-versus-smoothness trade-off.

## Fixed versus Adaptive MPC

Adaptive RMSE was lower than or equal to Fixed in all 12 matched cells; the benefit was essentially zero in the unpromoted nominal seed, small in nominal/mass/geometry cases, and largest for the moderate mixed patient. Maximum error was often unchanged and improved only in a subset. Adaptive generally reduced cuff-moment RMS but increased cuff-force RMS and robot-torque RMS slightly, so the adaptive result is not a uniform load reduction.

## Adaptation behavior

Nominal promoted in 2/3 seeds, mass in 3/3, geometry in 3/3, and moderate mixed in 3/3. Consequently, the strong statement that nominal usually retains the prior is not supported in this three-seed set. Promotion remains a trust-gated control-effective-model event, not recovery of physical anatomy.

## Report-facing recommendations

Use tracking RMSE, maximum tracking error, combined acceleration RMS, cuff-force peak with 200 N margin, and first-promotion time/remaining trajectory as the five clearest report metrics. Keep jerk as a secondary smoothness detail. Show nominal, isolated geometry, and moderate mixed patients; the mixed patient best demonstrates adaptive tracking benefit, while nominal exposes the non-negligible promotion frequency. Keep PD+FF in the main table.

The strongest synchronized Fixed-versus-Adaptive media candidate is `registered_moderate_anchor`, seed `64122`: it has the largest matched RMSE benefit in the study and makes the force/torque trade-off visible. The six remaining trajectory-demo rollouts remain worthwhile only for the separate descriptive claim of task generalization; they are not needed to strengthen the completed patient-statistical claim and add no seed-level inference.

## Concise claim verdicts

- **Patient generalization — supported:** all frozen controllers completed all four simulated patient mechanisms and three seeds without recorded constraint events.
- **No-retuning robustness — supported:** one frozen controller definition and gain lock were used across all 36 arms.
- **Adaptive-vs-fixed benefit — conditionally supported:** matched RMSE improved or tied in 12/12, with the largest benefit under mixed mismatch, but load/effort trade-offs and nominal promotions remain.
- **Motion smoothness — conditionally supported:** MPC was consistently smoother than PD+FF; Adaptive-versus-Fixed changes were small and seed-dependent.
- **Interaction/constraint behavior — supported for constrained engineering behavior, not load reduction:** all margins remained positive with zero recorded events, while load changes were mixed.
- **Overall comprehensive performance envelope — conditionally supported:** completion, tracking, smoothness, and constraints remained useful across the tested simulation envelope, but no controller dominated every metric and n=3 remains descriptive.
