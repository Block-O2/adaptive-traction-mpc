# SAC Seed 1 continuation v1

Status: SAC_SEED1_300K_COMPLETE. Total steps: 300000; continuation wall 1.516 h; effective 7.167 steps/s.

Memory qualification passed at 30k: startup and evaluation high-water allocations, no sustained leak/swap; replay stays 100000 transitions (46,000,000 bytes). Windows Available alone is not a leak indicator. Long-run observations are in RESOURCE_WATCH.jsonl and MEMORY_SAMPLES.jsonl. Resources take priority; no RAM/swap expansion or other heavy experiment.

Same checkpoint, replay, Adam optimizer, entropy state, fixed normalization and RNG restored. Cold physical reset only. R2 scientific contract and source hashes remain unchanged. The latest user instruction extends orchestration to 300k total, superseding the earlier stop-at-30k and historical orchestration wall budget; no seed 2 and no automatic steps beyond 300k.

Stop reason: None; error: None.

|Step|Scope|Tag|VALID|J_F|F peak|M peak|Duration|Interventions|
|---:|---|---|---|---:|---:|---:|---:|---:|
|275000|NATIVE|periodic|False|487.745633|122.720974|18.092047|5.920000|0|
|275000|MATCHED|periodic|False|487.745633|122.720974|18.092047|5.920000|0|
|300000|NATIVE|periodic|False|425.229345|125.940828|18.091822|6.075000|0|
|300000|MATCHED|periodic|False|425.229345|125.940828|18.091822|6.075000|0|

Only VALID and independently replay-confirmed candidates can be ranked. Invalid timeout costs never enter best-candidate comparisons. Deterministic repeats are reproducibility evidence, not human-population robustness. Every evaluation retains full physics trace, raw actions and hip/knee path. Training episodes retain compact action evidence and learning curve.

Prior comparator values and memory accounting remain in the preserved R2 and SAC_MEMORY_REPORT_V1 reports. No reward, action, observation, normalization, safety, physical task, policy period, training hyperparameter or buffer-capacity change. No Git stage/commit/push.

Next: continue the same state only if stopped for a temporary resource condition and separately authorized; at 300k report learning trend and recommend any extension, never run it automatically.
