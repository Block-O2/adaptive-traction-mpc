# Zero-value 30-repetition baseline v1 — stopped formal attempt

Final status: **ZERO_VALUE_30REP_BASELINE_FAIL**. One formal continuous session attempted Rep 1–7; Rep 1–6 passed all required gates, and Rep 7 completed the task with physical and Scientific Simulation PASS but **raw scorer-v2 FAIL**. The frozen stop rule ended the session before Rep 8. No second formal session or targeted repeat was run. The original harness result says `ZERO_VALUE_30REP_BASELINE_PARTIAL` because it counted completed task records; it is retained unchanged. This report adjudicates the failed required gate as FAIL.

Frozen source HEAD `f0d87e386caeaf88ddc0f52c5c8335e8efa71098`; frozen 618-file production fingerprint `56a25e2411d1da5ece6e168960fbc26624b0fd4d6bdcd35cab1102c27a300edb`. The validated boundary runtime has its separately recorded SHA in `PRODUCTION_FINGERPRINT.json`. One registered low-ROM ordinary case and unchanged options/seed were used on Y9000P Ubuntu WSL2. No controller, objective, Human dynamics, safety threshold or scientific configuration changed.

| Rep | J_F_task (N s) | J_F_session (N s) | Peak force (N) | Peak moment (N m) | Max plan age (ms) | Human version | Scorer-v2 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | 498.286447 | 498.668945 | 108.719430 | 14.435377 | 55.062 | 626 | PASS |
| 2 | 501.521818 | 502.669308 | 108.759482 | 14.414645 | 55.452 | 903 | PASS |
| 3 | 501.042531 | 502.190423 | 108.770301 | 14.418724 | 57.151 | 1179 | PASS |
| 4 | 500.673938 | 501.821536 | 108.757627 | 14.419281 | 57.853 | 1455 | PASS |
| 5 | 500.185449 | 501.332895 | 108.764808 | 14.422405 | 59.311 | 1731 | PASS |
| 6 | 500.185485 | 501.332406 | 108.770457 | 14.424339 | 58.200 | 2007 | PASS |
| 7 | 499.691235 | 500.455783 | 108.775016 | 14.425083 | 1660.052 | 2283 | FAIL |

The sole failed scorer-v2 condition in Rep 7 is `plan_age`: maximum source-to-activation wall age **1660.052 ms**, versus the unchanged **100 ms** raw-scorer threshold. Rep 1–6 maxima were 55.062–59.311 ms. All other raw scorer conditions passed. The mode-aware Scientific Simulation validity remained PASS because its simulation-time chronology, version and receipt checks passed; physical validity also remained PASS. Raw scorer-v2 PASS was explicitly required by the frozen baseline contract, so the session cannot be promoted. This is a measured gate failure, not a logging defect. The raw scorer result and its wall-time criterion were not edited after observation.

Rep 1–5 mean J_F_task was **500.342037 N s**. A Rep 6–30 late-phase mean, variance and relative change cannot be computed: only Rep 6 passed before the Rep 7 failure. The 7 observed task/session values and first-six accepted adjacent differences are retained in `PER_REPETITION.csv` and `BASELINE_VARIABILITY_SUMMARY.json`; they are not a complete natural-variability estimate.

Human model version increased from 626 after Rep 1 to 2283 after Rep 7, with no reset detected. The seven observed repetitions used 1 waypoint sequence pattern(s). All 91 decisions kept learned value zero; 25 unscored candidate records used explicit null score/value semantics. The six outgoing boundaries settled in 0 s and held for 0.005 s each; none exceeded 0.05 s. Native state continuity and fresh episode lifecycle checks passed through Rep 7. Rep 7 has no outgoing boundary because the session stopped.

The **six** end-of-repetition checkpoints and **73** raw-file hashes were reverified. Rep 7 has no promotable checkpoint. Large trajectories and checkpoint payloads remain in Git-ignored local results; compact manifests, model and waypoint progression, boundary timings, and per-repetition data are in this directory. Since 30/30 did not pass, the requested commit/push condition was not met. A waypoint headroom study should **not** use this attempt as its complete 30-repetition baseline; first decide a new, separately frozen protocol for the scorer-v2 wall-age criterion.
