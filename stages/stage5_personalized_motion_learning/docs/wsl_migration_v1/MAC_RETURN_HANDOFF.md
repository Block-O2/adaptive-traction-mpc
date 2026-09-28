# Mac return handoff

## Evidence to receive

- Fetch remote branch `codex/wsl-cross-host-evidence-v1`.
- Verify the fetched branch tip against the exact pushed evidence HEAD reported by the Y9000P closeout operator.
- Confirm the branch descends from evidence checkpoint `0d79adb78daa9fee0643be5d1dd9e801aced3978`, whose parent is exact migration HEAD `96010c61a665f4f58ccb9198dbfdf3e2ca8aa014`.
- Confirm production fingerprint `5a4b1d15f0711c349926cba2ed604906853215edd7cfdee6d188a7bac1c72ae7`.

Suggested read-only verification after fetch:

```bash
git fetch origin codex/wsl-cross-host-evidence-v1
git rev-parse origin/codex/wsl-cross-host-evidence-v1
git merge-base --is-ancestor 0d79adb78daa9fee0643be5d1dd9e801aced3978 origin/codex/wsl-cross-host-evidence-v1
git show --stat --oneline origin/codex/wsl-cross-host-evidence-v1
```

Do not automatically replace the Mac production branch with the WSL branch. Do not merge this evidence branch merely to receive it. Archive the WSL reports into canonical provenance through the Mac workflow, preserving the distinction between WSL evidence and Mac production history.

## Scientific claims to preserve

- Preserve `CROSS_HOST_RESULT_INCONCLUSIVE`.
- Do not claim strict Mac-to-WSL speedup, hard-real-time qualification, or elimination of the historical timing tail.
- Preserve the host decision: Mac is the primary source, control, and simulation host for upcoming formal simulation.
- Keep every final formal simulation matrix on one host; do not mix Mac and WSL runs in a single formal matrix.
- Retain Y9000P WSL as an optional future compute/training host. PyTorch/CUDA training requires a separate `PYTORCH_CUDA_TRAINING_ENV`; it was not configured or validated here.

## Hardware milestone to preserve

Runtime assurance is `REQUIRED_BEFORE_HARDWARE_EXPERIMENTS` for publication-quality CR12 work. Current Safe Fallback is precursor evidence, not a complete hardware runtime-assurance layer. The future hardware-translation phase must implement and validate the full requirement recorded in `WSL_CROSS_HOST_CLOSEOUT.md` before real CR12 experiments.

## Raw-data handling

The authoritative raw evidence remains on Y9000P WSL under the roots in `RAW_DATA_MANIFEST.json` (187 files; 1,948,086,815 bytes; hashes verified at closeout). Do not copy the full raw corpus to Mac by default. If a specific trace becomes necessary, select it from the manifest and verify its SHA-256 after transfer.

## Next research task

After canonical evidence archival, define the simulation-learning research baseline and 30-repeat path on the Mac without claiming real-time qualification. Do not start that experiment as part of this handoff.
