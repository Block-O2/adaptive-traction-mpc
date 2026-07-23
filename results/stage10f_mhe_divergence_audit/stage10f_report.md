# Stage 10F: Rolling MHE Divergence Audit

- Audited 854 MHE updates over all 24 replay runs after the confirmed failed-solve fallback repair.
- Solver failures: 692; runs with a thresholded first-divergence event: 24/24.
- The audit logs every updated window, arrival-shift consistency, current-output consistency, fallback handling, and aligned control/measurement deque checks.

## Decision

All five consistency checks passed in all 24 replay runs. No additional implementation/output inconsistency was found. The remaining behavior is attributable to the tested fixed online multiple-shooting formulation (conditioning/weighting/observability and computational cost), not a hidden rolling-index bug. Recommend closing the online MHE branch and moving to sigma-point smoothing plus smoothed-state parameter estimation; do not implement that route in this stage.
