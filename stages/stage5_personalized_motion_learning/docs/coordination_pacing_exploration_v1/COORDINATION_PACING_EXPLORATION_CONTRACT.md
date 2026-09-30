# Coordination & Pacing Exploration Contract v1

Primary question: Does relative hip-knee path coordination reduce interaction cost after nominal pacing is matched?

Native arm: deform relative coordination and let all production scheduling, mechanics, governor, RSS and safety act normally.

Matched arm: same path deformation and original execution, with each decision's exact baseline nominal duration requested on the registered grid; infeasible fixed schedules are rejected; realized timing residual is measured and only sufficiently matched comparisons support coordination-isolated claims.

Coordination family: baseline phase waypoint sequence plus smooth endpoint-zero normalized-progress relative hip/knee deformation; common start and endpoint retained; separate synchronous comparator; no equal instantaneous velocity assumption.

Safety: Original ROM, velocity, acceleration, continuous clearance, mechanics force/moment, controller, RSS, scientific validity and task semantics remain authoritative; no offline time stretching or artificial idle time.

Baseline, conditions, outcomes, matched tolerance, budget, validation split and stop rules are frozen in the accompanying JSON and CONDITION_MATRIX.json. No learning is trained.
