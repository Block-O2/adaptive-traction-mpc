# SAC Seed 1 continuation v1

Status: SAC_SEED1_SAVED_STOP. Total steps: 260887; continuation wall 8.943 h; effective 7.171 steps/s.

Memory qualification passed at 30k: startup and evaluation high-water allocations, no sustained leak/swap; replay stays 100000 transitions (46,000,000 bytes). Windows Available alone is not a leak indicator. Long-run observations are in RESOURCE_WATCH.jsonl and MEMORY_SAMPLES.jsonl. Resources take priority; no RAM/swap expansion or other heavy experiment.

Same checkpoint, replay, Adam optimizer, entropy state, fixed normalization and RNG restored. Cold physical reset only. R2 scientific contract and source hashes remain unchanged. The latest user instruction extends orchestration to 300k total, superseding the earlier stop-at-30k and historical orchestration wall budget; no seed 2 and no automatic steps beyond 300k.

Stop reason: RESOURCE_RISK; error: None.

|Step|Scope|Tag|VALID|J_F|F peak|M peak|Duration|Interventions|
|---:|---|---|---|---:|---:|---:|---:|---:|
|50000|NATIVE|periodic|False|853.203747|120.924020|18.020757|10.000000|189|
|50000|MATCHED|periodic|False|853.203747|120.924020|18.020757|10.000000|189|
|75000|NATIVE|periodic|False|554.462468|111.443548|18.092398|10.000000|175|
|75000|MATCHED|periodic|False|554.462468|111.443548|18.092398|10.000000|175|
|100000|NATIVE|periodic|False|815.229848|126.034411|18.027643|10.000000|143|
|100000|MATCHED|periodic|False|815.229848|126.034411|18.027643|10.000000|143|
|125000|NATIVE|periodic|False|885.814116|108.920552|18.012442|10.000000|162|
|125000|MATCHED|periodic|False|885.814116|108.920552|18.012442|10.000000|162|
|150000|NATIVE|periodic|False|667.447187|125.565581|17.647047|10.000000|150|
|150000|MATCHED|periodic|False|667.447187|125.565581|17.647047|10.000000|150|
|175000|NATIVE|periodic|False|381.481113|167.736376|18.092364|3.320000|9|
|175000|MATCHED|periodic|False|381.481113|167.736376|18.092364|3.320000|9|
|200000|NATIVE|periodic|False|392.685423|162.713130|18.024572|3.420000|24|
|200000|MATCHED|periodic|False|392.685423|162.713130|18.024572|3.420000|24|
|225000|NATIVE|periodic|False|523.960867|152.909606|18.004317|5.645000|18|
|225000|MATCHED|periodic|False|523.960867|152.909606|18.004317|5.645000|18|
|250000|NATIVE|periodic|False|384.186953|162.562854|18.091400|3.340000|0|
|250000|MATCHED|periodic|False|384.186953|162.562854|18.091400|3.340000|0|

Only VALID and independently replay-confirmed candidates can be ranked. Invalid timeout costs never enter best-candidate comparisons. Deterministic repeats are reproducibility evidence, not human-population robustness. Every evaluation retains full physics trace, raw actions and hip/knee path. Training episodes retain compact action evidence and learning curve.

Prior comparator values and memory accounting remain in the preserved R2 and SAC_MEMORY_REPORT_V1 reports. No reward, action, observation, normalization, safety, physical task, policy period, training hyperparameter or buffer-capacity change. No Git stage/commit/push.

Next: continue the same state only if stopped for a temporary resource condition and separately authorized; at 300k report learning trend and recommend any extension, never run it automatically.
