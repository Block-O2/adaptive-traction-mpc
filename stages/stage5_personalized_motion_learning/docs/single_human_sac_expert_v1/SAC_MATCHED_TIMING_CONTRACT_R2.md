# Prospectively frozen discrete MATCHED timing R2

Original physical continuous valid HOLD minimum remains 0.5 s. Common comparison phase minima are OUTBOUND 9 s, HOLD 1 s, RETURN 9 s. For every method and phase, eligibility requires `T_min - 1e-9 <= T_actual <= T_min + .020 + 1e-9`, plus the unchanged independent physical evaluator PASS. Total phase time is 19 to 19.060 s.

The .020 s allowance equals `max(.020 policy period, ceil(1/.5) × (.005 activation + .005 receipt endpoint confirmation))`. Source and transparent deterministic runtime establish both ticks; this is frozen at zero SAC training steps. No controller is changed to hit exact clock boundaries. Physical dwell, deadlines, safety, causal actor features/action/reward/scales and commissioning-only mode remain unchanged. Actual physical waiting contributes to J_F. Native and MATCHED-TIMING are separate scopes. Equal phase clocks do not equalize within-phase pacing; residual total timing differences must be reported.
