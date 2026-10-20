# HOLD timing blocker diagnosis

Physical task HOLD requires at least 0.5 s of uninterrupted valid causal dwell, not exactly 1 s. The 1 s minimum is a MATCHED comparison clock. The old planner executes two stationary 0.5 s certified references while that clock waits. Each requires a 5 ms asynchronous activation interval and a 5 ms receipt-owned endpoint recognition interval: 2 × (5+5) ms = 20 ms. A phase transition is checked every 5 ms, before new reference progress is emitted/committed; the SAC callback period is 20 ms but is absent in the old controller.

HOLD entry 19.055 s; first valid captured sample 19.060 s; first credited endpoint 19.065 s; original 0.5 s dwell proved at 19.560 s. First schedule activation/end emission/recognition 19.060/19.560/19.565 s. Second activation/end emission/recognition 19.570/20.070/20.075 s. Final HOLD-to-RETURN decision 20.075 s, so HOLD is 1.020 s. The transparent transition probe reproduces these values and the still-incomplete reference at 20.070 s. This is legitimate scheduler/reference ownership semantics, not a physical/task bug. No controller or task edit is made.

The first diagnostic harness startup failed because its multiprocessing main guard was missing; that attempt is preserved and the harness-only fix is recorded. Detailed trace, causal dwell, source hashes and calls are in JSON.
