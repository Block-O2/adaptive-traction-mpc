# Single-Arm V2 Diagnostic Closeout

## Confirmed status

- Human Model V2: **PASS**.
- Equilibrium-preserving endpoint-force controller: **PASS**.
- Ideal-authority single-contact mathematical authority: **PASS**.
- ±80 N/component engineering case: **reference-level INFEASIBLE**.
- Original zero soft-limit activation acceptance: **NOT MET**.
- Fixed-model NMPC remains paused.

These subsystem classifications do not replace the original overall result:
the controller preserves equilibrium under ideal authority, but the complete
acceptance gate remains unmet because the ideal rollout contains soft-limit
activity.

| Confirmed metric | Value |
|---|---:|
| peak force norm | 316.551 N |
| peak static force norm | 315.730 N |
| peak dynamic generalized-torque increment | 2.126 N m |
| ±80 N reference feasible fraction | 0% |
| ideal q1/q2 RMSE | 0.00234° / 0.00616° |
| ideal torque residual | numerical precision |
| ideal force/slew saturation | 0 / 0 |
| ideal soft-limit active samples | 473 |
| engineering force saturation | 97.850% |
| engineering torque residual RMS | 8.195 N m |

## Root-cause diagnosis

The engineering case is infeasible from the initial static-hold phase. Most
of the required contact force supports gravity and passive joint resistance;
the dynamic trajectory increment is small by comparison. The later large
tracking error, soft-limit activity, condition-number degradation, and jerk
occur after the state has departed from the reference. NMPC cannot remove a
static force deficit that is already present at reference level.

## Unresolved soft-limit item

The reference hip angle starts and ends at 5°, while the lower hip soft-zone
also begins at 5°. The ideal maximum hip error is only about 0.0055°.
Therefore, the 473 active samples may reflect a small boundary penetration;
the count alone does not establish danger or controller failure. No separate
formal diagnostic has measured the maximum penetration or corresponding
soft-limit torque, so this item remains **unresolved**. No new experiment is
run for this closeout.

## Modeling boundary

The 316 N result applies only to the combined assumptions used here: a fully
passive patient, fixed hip, unsupported suspended leg, no bed/support frame/
sling/weight relief, no patient active torque, one distal ideal two-dimensional
contact force, and no robot-body or soft-tissue interface dynamics. It is not
a clinical required force. The ±80 N bound is not a safety standard.

## Subsequent decision points

- Pure single-arm ideal-authority NMPC as an algorithmic upper bound.
- Re-evaluate one arm after adding passive proximal support.
- Consider two active contacts later.
- First confirm the real posture, support, contact method, and hardware
  capability with the professor.
