# SAC Seed 1 continuation — final evidence

STATUS: SAC_SEED1_300K_COMPLETE

TOTAL STEPS: 300000; resumed at30k with24997 updates and29997 replay records. WALL TIME: 10.617h; effective continuation 7.064 steps/s.

MEMORY RESULT: 30k qualification passed. Long-run peak process-tree PSS 3.867GiB; maximum WSL swap 0.000MiB. Historical guard trigger (audited false alarm): ['SUSTAINED_ANONYMOUS_MEMORY_GROWTH']. Final stop reason: None.

The original12194-step protection was triggered by Windows Available below2GiB while WSL MemAvailable remained healthy. Exact original commit/cache values were not recorded, so its causal proportions cannot be reconstructed. The bounded test directly measured large startup/first-update/evaluation allocations; concurrent video rendering separately caused real host commit pressure. Combined host commit, WSL availability, process-tree, swap and pressure accounting now governs resource decisions. No replay capacity change. The100k cyclic float32 replay uses46,000,000bytes (43.87MiB).

Estimated current-profile SAC tree budget is4.5GiB and whole WSL6GiB at300k/500k/1M, with2GiB Windows commit reserve. Uncapped replay alone would require131.61/219.35/438.69MiB respectively; the actual cyclic replay remains43.87MiB. These remain planning budgets subject to the observed long-run trend and resource guards. Full30s completed evaluations may need5–6GiB tree contingency; this is planning headroom, not a measured guarantee. No RAM/swap expansion.

Late training anonymous-memory slope: 43.17350924433584MiB/10k steps. Descriptive slope over the old, already-warmed PID last50k steps; no cross-PID cancellation. Startup/evaluation/reset/GC high-water changes remain included. This alone neither proves nor excludes a leak. The detailed process, Windows commit, WSL cache/swap and GPU samples are retained. The original15k/20k/25k/30k milestone accounting and30k/100k/300k/1M replay estimates are in ../single_human_sac_memory_v1/SAC_MEMORY_REPORT_V1.md.

|Step|Scope|Tag|VALID|J_F (N s)|F peak (N)|M peak (Nm)|Duration (s)|Safety rejections|
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
|50000|MATCHED|periodic|False|853.203747|120.924020|18.020757|10.000000|189|
|50000|NATIVE|periodic|False|853.203747|120.924020|18.020757|10.000000|189|
|75000|MATCHED|periodic|False|554.462468|111.443548|18.092398|10.000000|175|
|75000|NATIVE|periodic|False|554.462468|111.443548|18.092398|10.000000|175|
|100000|MATCHED|periodic|False|815.229848|126.034411|18.027643|10.000000|143|
|100000|NATIVE|periodic|False|815.229848|126.034411|18.027643|10.000000|143|
|125000|MATCHED|periodic|False|885.814116|108.920552|18.012442|10.000000|162|
|125000|NATIVE|periodic|False|885.814116|108.920552|18.012442|10.000000|162|
|150000|MATCHED|periodic|False|667.447187|125.565581|17.647047|10.000000|150|
|150000|NATIVE|periodic|False|667.447187|125.565581|17.647047|10.000000|150|
|175000|MATCHED|periodic|False|381.481113|167.736376|18.092364|3.320000|9|
|175000|NATIVE|periodic|False|381.481113|167.736376|18.092364|3.320000|9|
|200000|MATCHED|periodic|False|392.685423|162.713130|18.024572|3.420000|24|
|200000|NATIVE|periodic|False|392.685423|162.713130|18.024572|3.420000|24|
|225000|MATCHED|periodic|False|523.960867|152.909606|18.004317|5.645000|18|
|225000|NATIVE|periodic|False|523.960867|152.909606|18.004317|5.645000|18|
|250000|MATCHED|periodic|False|384.186953|162.562854|18.091400|3.340000|0|
|250000|NATIVE|periodic|False|384.186953|162.562854|18.091400|3.340000|0|
|275000|MATCHED|periodic|False|487.745633|122.720974|18.092047|5.920000|0|
|275000|NATIVE|periodic|False|487.745633|122.720974|18.092047|5.920000|0|
|300000|MATCHED|periodic|False|425.229345|125.940828|18.091822|6.075000|0|
|300000|NATIVE|periodic|False|425.229345|125.940828|18.091822|6.075000|0|

WSL observed high-water resident use (MemTotal−MemFree): 6.967GiB; cache: 2.833GiB; nonavailable memory (MemTotal−MemAvailable): 4.249GiB. Windows Vmmem private/working-set peaks: 8.030/5.017GiB. These peaks may occur at different times. Reclaimable cache can occupy spare WSL RAM beyond the6GiB working-memory/reserve planning budget; Vmmem commit, summed process RSS and host physical availability must not be equated. No WSL RAM limit or swap capacity was increased.

RAM forecast sensitivity:

|Total steps|Actual cyclic replay (MiB)|Stable-profile SAC tree budget (GiB)|Positive late-drift extrapolation, SAC tree (GiB)|Observed target reached|
|---:|---:|---:|---:|---|
|300000|43.869|4.5|3.751|True|
|500000|43.869|4.5|4.595|False|
|1000000|43.869|4.5|6.703|False|

The drift column is a sensitivity calculation, not a validated prediction or proof of leakage. It includes evaluation/reset high-water changes and extrapolates only the measured positive anonymous-memory slope. Future500k/1M runs are not qualified by this run; if the drift case exceeds the4.5GiB tree budget, resource diagnosis/requalification is required before extending. Longer complete-task evaluations also remain subject to the separate5–6GiB contingency and the host/WSL guards.

BEST NATIVE: No independently confirmed VALID SAC candidate.
LEARNING TREND NATIVE: No valid complete-task improvement established.

BEST MATCHED: No independently confirmed VALID SAC candidate.
LEARNING TREND MATCHED: No valid complete-task improvement established.

Training return last25 mean: -1004.7912300984661; previous25: -1005.0314173948683. Causal successful training episodes: 0/873. Training returns and invalid truncated J_F are not independently valid task scores.

NEXT: At300k, inspect the saved best valid/negative evidence before separately authorizing any extension.

Checkpoint, replay, optimizer and RNG paths/hashes are in SAVED_BUNDLE.json. Milestone evaluation uses the periodic checkpoint saved before storage/update of the callback transition, matching the preserved orchestration order. The distinct final checkpoint includes any subsequent final update and is the continuation state; a selected best always refers to its exact evaluated periodic checkpoint. All fixed-scale normalization, R2 control semantics, reward, observation, action, period, commissioned frozen model and training hyperparameters remain unchanged. No Human side-study, seed2, other heavy simulation, hardware action or Git mutation.

Evidence: SAC_SEED1_LEARNING_CURVE_COMBINED.csv, SAC_CHECKPOINT_EVALUATION_COMBINED.csv, BEST_CONFIRMED.json, all EVALUATION/CONFIRMATION records, HIP_KNEE_PATH_MANIFEST.json, full raw trace/action archives, MEMORY_SAMPLES.jsonl, RESOURCE_WATCH.jsonl, RESUME_VERIFICATION.json, EXECUTION_PROVENANCE_V1.json and PRESERVATION_AFTER.json. Original failed startup is retained separately; no learning occurred in it. Deterministic replay confirms reproducibility only, not human-population or hardware robustness.

Guard accounting correction: the previous segment stopped at260887 because the old comparison used the mean of all1–4h-old samples. The actual last three comparable prior-hour increases were166.203/70.778/126.853MiB, with no three consecutive128MiB increases. The audited true cumulative anonymous-memory rise767.516MiB remains recorded; no allocator leak has been claimed fixed. Numerical thresholds and all absolute resource safeguards remain unchanged. Supplemental bounded requalification milestones completed: [265000, 270000, 275000, 280000].

The original30k resume preserved24997 optimizer updates and29997 replay records. The resource-only continuation resumes260887 with255883 updates and100000 replay records, restores the saved RNG, and cold-resets the physical episode. No step0 training. Calendar wall including diagnosis gap: 10.617h; summed active segment orchestration wall: 10.459h. Separate PID memory bins and the old mature PID slope prevent a downward RSS jump at restart from masking the previous high-water growth.500k/1M are not resource-qualified by reaching300k.

The full30k memory accounting is also available in C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_memory/output/SAC_MEMORY_REPORT_V1.md.

Post-exit accounting (separate from training peaks): training process count 0; Windows Available 4.107GiB; Windows commit 22.166/32.730GiB, headroom 10.564GiB; WSL MemAvailable 6.967GiB, cache 0.401GiB; swap 0.000MiB. Full accounting: POST_EXIT_RESOURCE_ACCOUNTING.json.

Memory conclusion: no persistent resource-pressure leak was demonstrated in the bounded test. At30k, evaluation peaks were below the25k peak; replay stayed fixed-capacity. The long warm process subsequently accumulated real anonymous-memory high-water growth, so a slow leak has not been conclusively excluded. The guard fix repairs only its time-window calculation. The 300k run completed safely under the corrected guards; the cold restart is not credited as proof of stabilization in a single uninterrupted PID. The forecast stress case starts from the pre-restart260887-step process and retains its measured positive slope. Any500k/1M extension requires renewed resource qualification.

No VALID candidate was found at any formal milestone, so independent best-candidate confirmation replay was never triggered. Formal deterministic success:0/22 scope evaluations. Latest300k NATIVE and MATCHED both ABORTED after6.075s, J_F425.229345N s; these truncated costs are not ranked. The final checkpoint is saved and training is stopped.
