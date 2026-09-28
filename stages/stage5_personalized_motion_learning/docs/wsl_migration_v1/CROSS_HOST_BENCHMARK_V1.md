# Cross-host benchmark v1 — preregistered

Status: `PREREGISTERED_NO_WSL_RESULTS`. Compare Mac reference host with Y9000P WSL2 research-host performance only. No controller development or hardware claim.

The frozen source fingerprint is `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7` over 179 files. Before WSL execution, record and verify the **exact pushed migration HEAD** using `git rev-parse HEAD`; the SHA is determined by the final closeout commit and checked against the remote branch. The case, seed, scientific parameters, scorer-v2 and 100 ms expiration rule stay unchanged.

Cases, in order: `low_ordinary, high_100_sync, high_120_sync, high_120_start_8_13`. Each case has repetitions `r01`–`r06`, yielding **24 WSL runs**. Canonical paths and hashes, ordered run IDs, metrics, and exclusion rule are in `CROSS_HOST_BENCHMARK_V1.json`. Each attempt consumes one slot. Keep every outcome and raw trace, including failure. Never replace a case or rerun to improve results. No controller/source edit before all 24 attempts finish.

Report per-run and grouped compute and activation mean/median/p95/max, activation >55 ms count, >=100 ms planning/source-age events, worker→main timing when emitted, control miss ratio, longest miss streak and maximum command gap. Report COMPLETE, arrival/dwell/RETURN, fallback/stale counts, scorer-v2, force/moment/clearance and host CPU/RAM/OS/WSL/Python/MuJoCo/load. Unavailable fields must be marked `NOT_RECORDED` rather than estimated.

Historical Mac data use the same production fingerprint but were generated at source commit `0cb898b`. They are **not exact migration-HEAD matched** and each has one repetition. The manifest marks them `MAC_REFERENCE_MISSING` under the strict matched rule. Do not convert these contextual rows into six-repeat Mac evidence. This study does not qualify hard real time or clinical safety.
