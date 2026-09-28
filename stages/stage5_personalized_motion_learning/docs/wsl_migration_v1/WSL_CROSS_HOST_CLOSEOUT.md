# Y9000P WSL cross-host closeout

## Final status

`CROSS_HOST_RESULT_INCONCLUSIVE`

This closeout freezes the existing 24-slot Y9000P WSL benchmark without rerunning, filtering, imputing, or improving the dataset. The evidence commit `0d79adb78daa9fee0643be5d1dd9e801aced3978` is a direct child of migration HEAD `96010c61a665f4f58ccb9198dbfdf3e2ca8aa014`. Its production fingerprint remains `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7`.

The frozen matrix contains all 24 registered slots: 6 `COMPLETE`, 15 `ABORTED`, and 3 `EXCEPTION`. Missing metrics for exception slots remain missing. Across 265 planner events, no event reached 100 ms and the maximum was 59.360 ms. Across 243 activation events, 102 exceeded 55 ms, none reached 100 ms, and the maximum was 96.652 ms. Three disposition source-age events reached 100 ms, all in `TASK`; they produced three stale rejections and zero stale activations. No `COMMISSIONING` source-age event reached 100 ms. The evidence records 19 Safe Fallback commits and a maximum actual command gap of 375.038 ms.

The historical approximately 191 ms planner tail was not observed in this sample. Because the available Mac reference is not an exact-HEAD, repetition-matched reference, this does not establish a WSL speedup or elimination of the timing tail.

## What WSL established

- The repository and environment are portable to Y9000P WSL.
- MuJoCo 3.10.0 runs in the preserved Python 3.10.21 WSL environment.
- The deterministic gate passed 17/17, including Safe Fallback 11/11; smoke passed.
- The NVIDIA RTX 4060 and WSL CUDA 12.6 bridge are visible. The benchmark did not use a GPU scientific path.
- The approximately 191 ms planner tail was not observed in the frozen 24-run sample.

## What WSL did NOT establish

- No strict Mac speedup was established.
- No hard-real-time improvement was established.
- No reduction of the system-level timing tail was proven.
- No clinical or hardware safety claim was established.
- The evidence gives no reason to move the final formal simulation campaign to WSL.

## Current host decision

For upcoming scientific simulation, the Mac remains the primary source, control, and simulation host. Y9000P WSL is retained as an optional compute and training host. Later PyTorch/CUDA value-model training may use Y9000P only after a separate `PYTORCH_CUDA_TRAINING_ENV` is created and validated; PyTorch is not currently configured or verified. Final formal simulation matrices must not mix hosts.

## HARDWARE_PUBLICATION_REQUIREMENT

Publication-quality project results are expected ultimately to include real CR12 hardware experiments. Therefore the runtime/execution issue is not permanently deferred as optional future work. It is classified as:

`REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`

Before CR12 hardware experiments, the hardware-translation phase must revisit, implement, and validate at least:

- a phase-independent low-level execution layer;
- command heartbeat and watchdog behavior;
- bounded stale-command behavior;
- deterministic trajectory buffering or an equivalent execution primitive;
- controlled braking and zero-speed safe hold;
- independent force, velocity, and joint limits;
- high-level planner/value crash fallback;
- low-level command timeout semantics;
- a real-time/native execution environment;
- timing fault injection;
- latency and WCET characterization;
- hardware E-stop integration.

Current Safe Fallback is useful precursor evidence, but it is not a complete hardware runtime-assurance layer. This closeout permits learning-algorithm development to proceed before that hardware milestone; it does not waive or satisfy the milestone.

## Evidence and raw-data retention

- Authoritative tracked summaries, reports, plots, manifests, hashes, and provenance are under `stages/stage5_personalized_motion_learning/docs/wsl_migration_v1`.
- Authoritative raw evidence remains only in the WSL repository under the three roots recorded in `RAW_DATA_MANIFEST.json`, principally `stages/stage5_personalized_motion_learning/results/cross_host_benchmark_v1`.
- The manifest covers 187 files totaling 1,948,086,815 bytes. Closeout verification found every file present with matching byte count and SHA-256.
- A Windows staging copy exists at `C:\Users\HankL\Desktop\Coding\adaptive_traction_mpc\evidence_staging`. It contains summaries and plots only, is not a complete raw-data mirror, and is not the authoritative source for this closeout.
- No bulk raw trajectories were added to Git or copied for Mac return. A future trace-specific transfer must select files using the manifest and recheck hashes.

## Git closeout policy

The migration branch history remains unchanged. The closeout is published on `codex/wsl-cross-host-evidence-v1`; no merge, force push, main/master push, reset, stash, clean, or branch deletion is part of this closeout.
