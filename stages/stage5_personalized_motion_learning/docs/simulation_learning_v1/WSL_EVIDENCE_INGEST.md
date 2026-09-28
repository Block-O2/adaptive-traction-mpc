# WSL evidence ingest

Status: `CROSS_HOST_RESULT_INCONCLUSIVE` (historical result retained).

The Mac learning checkout started clean at `codex/learning-wsl-migration-v1`, HEAD `96010c61a665f4f58ccb9198dbfdf3e2ca8aa014`. `git ls-remote` verified `codex/wsl-cross-host-evidence-v1` at `012be7152022494bfa6d3617853881fa8b817cfc`; the fetched range has the learning HEAD as merge base and adds only 17 files under `stages/stage5_personalized_motion_learning/docs/wsl_migration_v1/`. It adds reports, JSON/CSV summaries, plots, raw-data manifest, closeout and Mac handoff. It changes no production source, config, scorer, plant, controller or historical result. The three evidence-only commits were cherry-picked locally as `2cc0f74`, `1dbaf3d`, `195fd9f`; no merge or push occurred.

The frozen production source map has 179 files, all matching their SHA-256 entries. Its calculated fingerprint is `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7`, matching the WSL record. This is source equivalence, not a matched host performance comparison.

The WSL preregistered 24 slots had 6 COMPLETE, 15 ABORTED, 3 EXCEPTION, with no replacement. Of the six evaluable runs, six passed scorer-v2. Three >=100 ms disposition source-age events were rejected and zero stale activations were observed. The ~191 ms historical planner tail was not seen in this sample; no claim of its elimination follows. Strict Mac references at the same commit and repetition count were missing. The raw corpus (187 files, 1,948,086,815 bytes) remains on WSL under the archived hash manifest; it was not copied to Mac or added to Git.

Mac remains the primary scientific simulation host. Y9000P WSL is an optional future PyTorch/CUDA training host after separate environment validation. Neither host is real-time qualified. Runtime assurance remains `REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`.

Canonical source evidence: `docs/wsl_migration_v1/CROSS_HOST_COMPARISON.md`, `WSL_CROSS_HOST_CLOSEOUT.md`, `MAC_RETURN_HANDOFF.md`, `WSL_CROSS_HOST_BENCHMARK_RESULTS.json`, `RAW_DATA_MANIFEST.json`, `WSL_FINAL_FINGERPRINTS.json` (all relative to the Stage-5 directory).
