# Zero-value 30-repetition baseline V2 — stopped formal campaign

Final status: **ZERO_VALUE_30REP_BASELINE_FAIL**. Replacement attempt `formal_session_02` accepted Rep 1–13 in one continuous Scientific Simulation session. Rep 14 aborted in OUTBOUND with **`LOW_LEVEL_EXECUTION:INCREMENTAL_CLEARANCE_LOST_ALIGNED_CAUSAL_HISTORY`**. Its physical validity, scientific validity and raw scorer-v2 are all FAIL; this is a genuine controller/scientific stop condition. Rep 15–30 were not run. No further repair or restart was attempted.

The earlier V2 `formal_session_01` stopped at Rep 11 due a fixed-interval force bookkeeping defect, documented in `V2_REPAIR_01.md` with 113 raw hashes and 10 checkpoint hashes preserved. One permitted harness repair passed 18 regression tests; `formal_session_02` restarted fresh at Rep 1. The V1 failed baseline remains preserved at local commit `22c6859214256a46e75d47ad153ed9be3c3a2f72`.

Frozen source ancestry `f0d87e386caeaf88ddc0f52c5c8335e8efa71098`; production fingerprint `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`. The validated boundary/runtime and V2 harness hashes appear in `PRODUCTION_FINGERPRINT_V2.json`. The same registered case, options and seed ran on Y9000P Ubuntu WSL2. Controller mathematics, Human dynamics, waypoint objective, Scientific scheduler semantics and safety thresholds were not changed.

| Rep | J_F_task (N s) | J_F_session (N s) | Peak force (N) | Peak moment (N m) | Human version after | Wall plan age (ms) | Raw scorer-v2 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | 498.286447 | 498.668945 | 108.719 | 14.435 | 626 | 57.335 | PASS |
| 2 | 501.521818 | 502.669308 | 108.759 | 14.415 | 903 | 52.856 | PASS |
| 3 | 501.042531 | 502.190423 | 108.770 | 14.419 | 1179 | 53.820 | PASS |
| 4 | 500.673938 | 501.821536 | 108.758 | 14.419 | 1455 | 53.739 | PASS |
| 5 | 500.185449 | 501.332895 | 108.765 | 14.422 | 1731 | 55.321 | PASS |
| 6 | 500.185485 | 501.332406 | 108.770 | 14.424 | 2007 | 56.529 | PASS |
| 7 | 499.691235 | 500.838324 | 108.775 | 14.425 | 2283 | 1547.244 | FAIL(plan_age) |
| 8 | 499.687986 | 500.835854 | 108.779 | 14.426 | 2559 | 1670.334 | FAIL(plan_age) |
| 9 | 499.685734 | 500.833575 | 108.782 | 14.426 | 2835 | 54.859 | PASS |
| 10 | 499.632913 | 500.780750 | 108.784 | 14.426 | 3111 | 57.186 | PASS |
| 11 | 501.049175 | 502.196369 | 108.786 | 14.426 | 3387 | 54.845 | PASS |
| 12 | 501.039582 | 502.186463 | 108.786 | 14.422 | 3663 | 53.102 | PASS |
| 13 | 501.036000 | 502.182853 | 108.787 | 14.422 | 3939 | 52.336 | PASS |

Rep 14 has no accepted J_F_task/J_F_session value: it aborted after 1.460000 s of OUTBOUND. The raw session result reports an evaluation exception from a duplicate ABORTED terminal timestamp; the preserved launch and summary both give the earlier true abort reason. The exception did not cause the physical/scientific failure. `REP_14_FAILURE.json` records both events; raw data was not rewritten.

Rep 1–5 mean task cost was **500.342037 N s**. The observed Rep 6–13 task mean was **500.251014 N s**, but Rep 6–30 late-phase mean, variance and relative change cannot be estimated. `BASELINE_VARIABILITY_SUMMARY.json` labels the 13-repetition prefix incomplete; it is not a 30-repetition natural-variability baseline or a headroom threshold.

Human model version increased monotonically from 626 after Rep 1 to 3939 after Rep 13 without reset. The accepted prefix had 1 unique waypoint sequence pattern(s). All 169 accepted-rep decisions kept learned value zero, with 44 explicitly null/unscored candidates; 3 additional zero-value decisions are preserved for aborted Rep 14. Thirteen outgoing settle/hold boundaries completed, including the physically continuous Rep 13→14 transition. Their mean settle was 0.000000 s and mean hold 0.005000 s; maximum total was 0.005000 s.

Raw scorer-v2 wall-time-only FAIL among accepted repetitions occurred 2 time(s): Rep 7 (1547.244 ms), Rep 8 (1670.334 ms). Maximum accepted-prefix wall plan age was 1670.334 ms. Those events remain counterfactual realtime failures under the unchanged strict `<100 ms` rule but did not contaminate scientific trajectories. Rep 14's raw scorer failure has physical/terminal causes and is not reclassified as wall-only.

All 13 latest-attempt checkpoint hashes and 143 raw-file hashes were reverified. Large trajectories/checkpoints remain Git-ignored. Compact manifests, per-repetition CSV/JSON, model/waypoint progression, boundary and realtime summaries are saved here. The 30/30 completion condition was not met, so no V2 commit or push was made; remote V2 SHA does not exist. **Do not enter waypoint headroom study from this failed baseline.** No value learning, RL or hardware work was started.
