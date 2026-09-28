# Cross-host comparison

## Decision

**CROSS_HOST_RESULT_INCONCLUSIVE**

All four strict Mac references are missing: the available Mac evidence uses commit `0cb898b61497b51b5d2a645b3941d03dd3f3f74b` and one repetition per case, while WSL used exact migration HEAD `96010c61a665f4f58ccb9198dbfdf3e2ca8aa014`. The production fingerprint is identical, but the exact-HEAD and repetition requirements are not. Therefore no matched host speedup is claimed.

The WSL evidence also does not support a substantial-improvement claim. All 24 preregistered slots ran without replacement, but only 6 completed, 15 aborted, and 3 ended as exceptions. All 6 evaluable runs passed scorer-v2; 18 were not evaluable.

## Frozen source and protocol

- Migration branch: `codex/learning-wsl-migration-v1`
- Exact HEAD: `96010c61a665f4f58ccb9198dbfdf3e2ca8aa014`
- Production fingerprint: `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7` (exact Mac checkpoint match)
- Protocol: 4 cases × 6 repetitions = 24 slots; 24 executed; 0 replacement runs; no scientific variables changed
- Thresholds: planning >30 ms, planning >=100 ms, activation >55 ms, disposition source-age >=100 ms

## WSL distributions

Event columns are pooled across every run with runtime artifacts. Exception slots without artifacts remain in the functional counts and are not imputed.

| Case | COMPLETE | Instrumented | Planner median / p95 / max (ms) | Activation p95 / max (ms) | Activation >55 | Source-age >=100 | Safe Fallback | Max command gap (ms) | Mac strict match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| low ordinary | 5/6 | 5/6 | 35.79 / 40.18 / 44.10 | 77.61 / 82.67 | 49 | 0 | 0 | 314.21 | MISSING |
| high 100 sync | 0/6 | 4/6 | 5.51 / 52.60 / 59.36 | 82.64 / 93.31 | 5 | 2 | 1 | 337.11 | MISSING |
| high 120 sync | 0/6 | 6/6 | 6.75 / 48.70 / 54.98 | 88.42 / 91.57 | 24 | 1 | 8 | 375.04 | MISSING |
| high 120 variable-start | 1/6 | 6/6 | 7.84 / 49.59 / 51.83 | 89.67 / 96.65 | 24 | 0 | 10 | 301.28 | MISSING |

Across all cases, the largest planner compute event was 59.360 ms and the largest activation age was 96.652 ms. No planner or activation event reached 100 ms, so the historical ~191 ms planner tail was not observed in this preregistered WSL sample. This is an observation for 24 slots, not evidence that the tail is eliminated.

Three disposition source-age >=100 ms events occurred, all in `TASK`, with a maximum observed disposition age of 116.035 ms. They produced three stale rejections and zero stale activations. No `COMMISSIONING` source-age >=100 ms event was observed. The campaign recorded 19 Safe Fallback commits across the 21 instrumented runs. The maximum actual command gap was 375.038 ms.

## Questions A–G

A. **Typical planner latency:** not shown to be significantly lower. Historical Mac numbers are not strictly matched, and WSL functional instability prevents a clean speedup conclusion.

B. **Activation tail:** not shown to be lower. WSL activation p95 values and maxima vary substantially by case and run; 102 activation events exceeded 55 ms.

C. **100–200 ms heavy-tail:** no planner or activation event in this sample reached 100 ms. However, three commissioning disposition source-age events reached or exceeded 100 ms. The correct conclusion is “not observed for planner/activation in this preregistered sample,” not “resolved.”

D. **Historical ~191 ms planner tail:** not observed; WSL planner maximum was 59.360 ms.

E. **COMMISSIONING source-age >=100 ms:** not observed. The three >=100 ms disposition source-age events were all `TASK` stage.

F. **Safe Fallback frequency:** 19 commits were observed. The Mac manifest does not contain a strictly matched fallback count, so a decrease cannot be established.

G. **Host/runtime variability:** not clearly narrower than Mac. WSL produced 6 COMPLETE, 15 ABORTED and 3 EXCEPTION outcomes, with activation and command-gap variability. The one-run-per-case Mac context cannot support a formal variance comparison.

## Mac evidence scope

Every case is `MISSING` for strict matching. The available Mac runs share the production fingerprint but use a different commit and one repetition. Directional historical deltas are preserved in `WSL_CROSS_HOST_BENCHMARK_RESULTS.json` under `historical_directional_delta`; they are not host-speedup estimates.

## Research-host recommendation

Use the Mac as the simulation host for the final baseline freeze, 30-repeat baseline, value-learning dataset generation, learning-enabled simulation, and final fresh simulation evaluation unless a later, separately authorized WSL qualification resolves the present functional instability. Keep each final simulation matrix on one host.

The Y9000P WSL may be considered for PyTorch value training only after a separate CUDA/PyTorch environment validation. This campaign did not benchmark GPU training, and the current WSL environment does not include PyTorch. Neither host is declared real-time qualified.

## Limitations

Per-run timestamps and load averages were recorded. The frozen runner did not record process CPU percent or memory-used snapshots, so those fields are explicitly unavailable rather than reconstructed after the fact. Windows background activity was recorded at setup but was not fully controllable.
