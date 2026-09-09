# Phase-3A final repository delivery validation

Date: 2026-09-09

Phase-2 provenance source commit: `5b91ea37a07fd84f5ff5c07e117ed3ebb6b6688e`

Validated branch: `codex/interface-phase3a-de23ea3`

This record covers delivery mechanics and reproducibility only. It does not
change or reclassify any controller, model, parameter, trajectory, threshold,
or scientific result.

## Final verification record

| Check | Result |
|---|---|
| Active Stage-4 regression | **PASS** — 252 passed in 58.52 s; 0 failed; 0 errors |
| Isolated temporary-worktree regression | **PASS** — 252 passed in 66.84 s; 0 failed; 0 errors |
| Report-only reproducibility regression | **PASS** — 4 passed in 17.83 s after adding the matched interaction-force plots |
| Clean-worktree input boundary | **PASS** — detached Phase-2 source tree plus only the reviewed tracked REPORT patch; no local untracked evidence used |
| `CLEAN_CLONE_SHA256SUMS` | **PASS** — 54/54 expected Git files verified after this record was added |
| Professor HTML regeneration | **PASS** — tracked compact inputs only; deterministic SHA-256 `d480e25ae692de1d3d27303c8bf3ab5e6bb58c8ca73d2698dbe898118fae4bce` |
| Professor HTML offline checks | **PASS** — 1,853,683 bytes; 3 embedded videos; 3 decoded videos; 3 posters; 3 canvases; 3 matched physical-force plots; 0 external URLs |
| Interaction-force plots | **PASS** — corrected 40/80, 90/120, and 120/120 only; Rigid NEW and P1 NEW physical translational cuff-force norms; common 0–150 N axis; no reference lines |
| Professor HTML browser visual inspection | **NOT_RUN** — the available browser surface rejected local `file://` URLs under its security policy; no workaround was attempted |
| Force-landscape regeneration | **PASS** — 126 x 126 grid; 0.0611068745–182.2979845 N; no 200/220/250 N crossing; reference array match PASS |
| Markdown link/image audit | **PASS** — 198 Markdown files; 110 local links/images checked; 0 broken candidates |
| Current dependency scan | **PASS** — no retained builder/runtime import depends on deleted historical runners or raw campaign paths |
| `git diff --check` | **PASS** |

The professor builder was also regenerated in the isolated temporary worktree
and produced the same HTML and embedded-video hashes. The force landscape was
generated into a temporary directory; it did not run a controller or advance a
scientific trajectory.

## Evidence boundary

No new scientific trajectory was run during Phase-2 cleanup or this delivery
validation. Historical High-ROM raw/media evidence is intentionally external
to the final Git tree and remains identifiable through
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../results/summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).
The files expected in a clean Git checkout are covered by
[`CLEAN_CLONE_SHA256SUMS`](../../results/summaries/phase3a_corrected_high_rom/CLEAN_CLONE_SHA256SUMS).

The corrected low-latency robot control-feedback velocity baseline remains the
authoritative High-ROM interpretation. Pre-correction BRAKE/approximately
222 N reports remain retired diagnostic provenance only; their numerical
contents were not rewritten during delivery polish.
