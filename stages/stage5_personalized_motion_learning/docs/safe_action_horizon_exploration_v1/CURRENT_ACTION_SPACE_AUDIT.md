# Current action-space audit

Read-only audit of all 390 V3 decisions. Action is the next 2D Human hip/knee waypoint increment from the fresh deployable state. Existing candidates are positive phase-progress pairs at 0.5 or 1.0 scale of 20% task span, with five hip/knee ratios. Scheduling, continuous clearance, and predicted mechanics screens are already applied.

| Phase | Decisions | Feasible candidate count, median | Max pairwise target distance, median (deg) | Angular spread, median (deg) | 0.25 s predicted path spread, median (deg) |
|---|---:|---:|---:|---:|---:|
| OUTBOUND | 180 | 9.0 | 3.971 | 30.438 | 2.032 |
| HOLD | 30 | 1.0 | 0.000 | 0.000 | 0.000 |
| RETURN | 180 | 10.0 | 3.971 | 30.438 | 2.038 |

The complete per-decision pairwise, direction, hip/knee-ratio, cost-gap and feasibility-margin values are in JSON. Identical chosen labels alone cannot prove that ranking is robust or that this small positive-progress lattice covers the legal action landscape. Counterfactual rollouts are needed before judging headroom.
