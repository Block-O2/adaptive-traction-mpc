# Zero-value 30-repetition baseline V3

**ZERO_VALUE_30REP_BASELINE_COMPLETE:** 30/30 repetitions completed in one fresh continuous Scientific Simulation session from Rep1. Every physical, scientific, lifecycle, zero-value and sensor-time gate passed. There were no genuine physical/scientific failures. The V2 campaign remains a separate FAIL with preserved evidence. Source before this campaign: `6b07720b459900951056aeff851d3989fe4bbd6d` on `codex/zero-value-30rep-baseline-v3`.

The registered case, options and seed 20260918 match V2. Human adaptation continued, learned value remained zero, and the repaired sensor deadline was the only production behavior change inherited from the forensic branch. Controller mathematics, Human dynamics, waypoint objective, safety limits, clearance criterion, Scientific Mode and raw scorer-v2 were unchanged. All preflight regressions passed (47 tests and one single-repetition physical/scientific PASS).

| Rep | J_F_task (N s) | J_F_session (N s) | Peak force (N) | Peak moment (N m) | Min deployable clearance (mm) | Human version after | Wall plan age (ms) | Raw scorer-v2 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | 498.286447 | 498.668945 | 108.719 | 14.435 | 17.871 | 626 | 55.458 | PASS |
| 2 | 501.521818 | 502.669308 | 108.759 | 14.415 | 17.701 | 903 | 55.401 | PASS |
| 3 | 501.042531 | 502.190423 | 108.770 | 14.419 | 17.768 | 1179 | 54.667 | PASS |
| 4 | 500.673938 | 501.821536 | 108.758 | 14.419 | 17.772 | 1455 | 52.221 | PASS |
| 5 | 500.185449 | 501.332895 | 108.765 | 14.422 | 17.791 | 1731 | 54.075 | PASS |
| 6 | 500.185485 | 501.332406 | 108.770 | 14.424 | 17.796 | 2007 | 54.337 | PASS |
| 7 | 499.691235 | 500.838324 | 108.775 | 14.425 | 17.805 | 2283 | 1615.327 | FAIL(plan_age) |
| 8 | 499.687986 | 500.835854 | 108.779 | 14.426 | 17.807 | 2559 | 1656.721 | FAIL(plan_age) |
| 9 | 499.685734 | 500.833575 | 108.782 | 14.426 | 17.813 | 2835 | 58.475 | PASS |
| 10 | 499.632913 | 500.780750 | 108.784 | 14.426 | 17.819 | 3111 | 59.537 | PASS |
| 11 | 501.049175 | 502.196369 | 108.786 | 14.426 | 17.876 | 3387 | 54.348 | PASS |
| 12 | 501.039582 | 502.186463 | 108.786 | 14.422 | 17.858 | 3663 | 56.665 | PASS |
| 13 | 501.036000 | 502.182853 | 108.787 | 14.422 | 17.858 | 3939 | 56.149 | PASS |
| 14 | 501.031845 | 502.178672 | 108.787 | 14.421 | 17.859 | 4215 | 63.266 | PASS |
| 15 | 500.645201 | 501.792062 | 108.788 | 14.421 | 17.860 | 4491 | 57.034 | PASS |
| 16 | 500.642093 | 501.789050 | 108.788 | 14.421 | 17.825 | 4767 | 69.030 | PASS |
| 17 | 501.129424 | 502.276411 | 108.788 | 14.420 | 17.826 | 5043 | 64.373 | PASS |
| 18 | 501.124704 | 502.271753 | 108.787 | 14.419 | 17.832 | 5319 | 56.048 | PASS |
| 19 | 501.120002 | 502.267029 | 108.787 | 14.418 | 17.833 | 5595 | 57.368 | PASS |
| 20 | 501.115470 | 502.262476 | 108.786 | 14.417 | 17.834 | 5871 | 55.584 | PASS |
| 21 | 501.111146 | 502.258131 | 108.786 | 14.417 | 17.835 | 6147 | 57.799 | PASS |
| 22 | 501.107056 | 502.254023 | 108.785 | 14.416 | 17.836 | 6423 | 57.206 | PASS |
| 23 | 501.103220 | 502.250170 | 108.784 | 14.415 | 17.837 | 6699 | 74.662 | PASS |
| 24 | 501.547807 | 502.694830 | 108.801 | 14.415 | 17.859 | 6976 | 61.592 | PASS |
| 25 | 501.544089 | 502.691281 | 108.801 | 14.415 | 17.861 | 7253 | 61.258 | PASS |
| 26 | 501.541081 | 502.688258 | 108.801 | 14.414 | 17.862 | 7530 | 57.286 | PASS |
| 27 | 501.538347 | 502.685509 | 108.800 | 14.414 | 17.862 | 7807 | 129.326 | FAIL(plan_age) |
| 28 | 501.535869 | 502.683019 | 108.800 | 14.413 | 17.863 | 8084 | 69.064 | PASS |
| 29 | 501.533640 | 502.680778 | 108.800 | 14.413 | 17.863 | 8361 | 67.073 | PASS |
| 30 | 501.531638 | 502.296326 | 108.800 | 14.413 | 17.864 | 8638 | 58.084 | PASS |

Rep1–5 versus Rep6–30 mean J_F_task: 500.342037 versus 500.916430 N s (+0.1148%). Mean J_F_session: 501.336621 versus 502.048255 N s (+0.1419%). Late task sample SD is 0.642500 N s, range 1.914894 N s, and mean absolute adjacent late change 0.139592 N s. These are descriptive natural baseline noise scales from one continuous session; the complete mean, median, SD, range, relative and adjacent changes for force/moment metrics are in `BASELINE_VARIABILITY_SUMMARY.json`.

Human model sequence increased monotonically from 626 after Rep1 to 8638 after Rep30 without reset. The 11-parameter beta vector changed by L2 2.785406 from Rep1 to Rep30; component and adjacent drift, residual parameters and per-rep state boundaries are preserved in `HUMAN_MODEL_PROGRESSION_V3.json` and `PER_REPETITION_V3.json`. The waypoint policy produced 1 unique selected sequence(s), 390 total decisions and 95 explicit null/unscored candidates; every scored candidate retained learned value zero. There were 0 adjacent sequence changes. The minimum deployable clearance across repetitions was 17.701 mm; minimum native evaluation-only clearance was 25.605 mm. Full trends appear in `CLEARANCE_TREND_V3.json`.

All 29 inter-repetition boundaries passed native-state and model-version continuity checks. Mean settle was 0.000000 s, mean hold 0.005000 s, and maximum total 0.005000 s. Task OUTBOUND/HOLD/RETURN durations and initial/final Human and CR12 q/dq are in each per-repetition JSON row.

The mandatory whole-session audit found 35411 sensor samples with minimum/maximum interval 0.005000000000/0.005000000000 s and unique intervals at 9 decimal places [0.005]. Applied control intervals were chronological within and across all 30 repetitions; the 29 recorded inter-repetition control gaps matched the 5 ms boundary hold. There was no duplicate, missed 5 ms sample, unexpected 10 ms gap, invalid causal-history spacing or control-time anomaly. The prior time-bookkeeping failure did not recur.

Raw scorer-v2 wall-time-only FAIL occurred 3 times: Rep 7 (1615.327 ms), Rep 8 (1656.721 ms), Rep 27 (129.326 ms). All raw wall-time conditions and source-age, activation-latency, control-miss/gap data are preserved in `REALTIME_CHARACTERIZATION_SUMMARY.json`. Scientific baseline validity is PASS; counterfactual realtime validity is reported separately under the unchanged strict `<100 ms` rule. Historical `RSS_RUNTIME_QUALIFICATION_NOT_MET` remains in force; no realtime qualification was attempted.

All 30 V3 checkpoint hashes and 305 V3 raw-file hashes were reverified. Both preserved V2 failed attempts were reverified byte for byte: 113 raw/10 checkpoints, then 143 raw/13 checkpoints. Large trajectories and checkpoints remain Git-ignored; compact manifests are saved. The final local/remote commit SHA is recorded after push in the locally saved `results/zero_value_30rep_baseline_v3/REMOTE_VERIFICATION_V3.json` and in the task handoff. The completed baseline supplies a descriptive variability scale for a possible future waypoint headroom study; this task does **not** authorize or start that study. No value learning, RL, realtime or hardware run was started. No causal adaptation benefit, statistical significance or optimality is claimed.
