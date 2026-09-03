# Complete-model-lock 40/40 commissioning

Base scan spec SHA: `02114e3217eb0f993531951e51e946c5ca1087a37661f6aa68f36ba75adeec79`
Additive commissioning spec SHA: `dabea8f7a493a41d898dcefeb9b6ac89b88aac5517b7af9ac901c6c7ba635c60`

The previous run remains `diagnostic_invalid_full_model_freeze`.

| Run | Task | Force | Endpoint deg | Return deg | RMSE deg | Physical peak N | Low-level max ms |
|---|---|---|---:|---:|---:|---:|---:|
| invalid old | SAFE_INCOMPLETE | STRICT_PASS | 1.681794 | 0.612729 | 0.806891 | 122.961262 | 22.792625 |
| corrected repeat 1 | COMPLETE | STRICT_PASS | 0.000511 | 0.011742 | 0.162417 | 117.456348 | 0.812876 |
| corrected repeat 2 | COMPLETE | STRICT_PASS | 0.000511 | 0.011742 | 0.162417 | 117.456348 | 0.666167 |

Deterministic repeat: `True`.
Both repeats had zero 5 ms safety-path misses, with maxima 0.813 and 0.666 ms.
The old 22.793 ms observation is classified as
`instrumentation_or_host_scheduling_overhead_outside_algorithmic_core`: it was
not reproduced, while actions and physical trajectories matched exactly. The
timer excludes file I/O, plotting, snapshots, and replay, so no file-I/O cause
is claimed. Repeat 2 separately had one isolated 20 ms MPC/high-level wall-clock
miss; repeat 1 had none, and it did not change the deterministic trajectory.

The corrected target-hold true-minus-estimated mean bias was
[-0.013353, -0.021955] deg, versus approximately [0.042183, -1.755077] deg in
the invalid run. Endpoint and return errors were 0.000511 and 0.011742 deg,
both within the unchanged 0.068969 deg evaluator tolerance. The phase completed
at 14.107000 s versus the analytical 14.106061 s boundary (one 1 ms simulation
sample past it).

Decision for remaining 26 cells: `GO`.

No other endpoint, tuning, or threshold change was run.
