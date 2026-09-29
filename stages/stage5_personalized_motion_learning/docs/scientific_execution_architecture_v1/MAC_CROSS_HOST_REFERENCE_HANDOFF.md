# Mac scientific reference evidence for WSL comparison

This handoff packages the **original four Mac representative runs** from `results/scientific_execution_v2/`. No simulation was rerun and no production source or scientific config was changed. The four cases are `representative_low_rom_ordinary_v1`, `representative_high_rom_hip_v1`, `representative_120_sync_v1`, and `representative_120_variable_start_v1`.

## Integrity and source identity

- Archive: `mac_cross_host_reference_v1_compact.zip` — **49,635,283 bytes**; SHA256 `980ca74958e489298ac5c095bee710911e3c4ee8d72237e040e05385cc0e7f30`.
- `MAC_CROSS_HOST_REFERENCE_V1.sha256.json` is the archive-hash sidecar. A file cannot contain its own full-file hash without changing that hash; the ZIP's internal `BUNDLE_MANIFEST.json` therefore records every source and member hash, while this sidecar records the final ZIP hash.
- All 32 original raw files (eight per case) were present and matched the published `RAW_DATA_MANIFEST_V2.json` in size and SHA256. Exact case JSON, options config, runtime source and the ten launch-recorded source-file hashes were checked. All 617 files in `PRODUCTION_FINGERPRINT.json` and 618 files in `PRODUCTION_FINGERPRINT_V2.json` matched their recorded hashes.
- The published manifest records pre-commit HEAD `d312b96400dd459d51ee9744ce469e5bebf417b2`; these runs used the uncommitted Scientific Mode implementation later committed as `8da559fd579e32e53516f909527a25c3de22fc98`. The execution HEAD is **not independently embedded in each raw run**; the recorded HEAD is corroborated by the exact per-file source hashes. Final published production fingerprint: `0b3c66bcf853255f70b59f8196ccfe5ea554c18fe3690be327c831fc9f52e358`.
- The fixed case JSONs and launch commands contain no explicit RNG seed; each case's registered replicate/cell and full case hash are retained. Do not invent a seed value.

## Contents and comparison granularity

Each case contains original byte-for-byte `trace.npz` (all 48 arrays), `summary.json`, `config_snapshot.json`, launch provenance and final mode-aware scorer result, plus exact case JSON. `runtime_events.json` retains request/version vectors, activation certificates, phase/handoff and fallback events. `native_core.npz.xz` has **every native row**, with original float64 sim time, Human q/dq (`qpos/qvel` columns 0–1), CR12 q/dq (columns 2–7), six actuator torques, contact-pair values and a derived 1-based step index. No numeric value was rounded or downsampled. Host monotonic timestamps were omitted because they are not cross-host scientific state.

| Case | Native rows |
| --- | ---: |
| low-ROM ordinary | 62,300 |
| high-ROM hip | 103,540 |
| 120/120 synchronous | 104,180 |
| 120/120 variable-start | 103,700 |

The original trace holds estimated/evaluation-only Human q/dq, CR12 q/dq, reference q/dq/ddq, force, moment, clearance, selected waypoint labels, task phase and physics-step labels at its **recorded trace cadence**. Mac raw evidence did not record force, moment or clearance on every native step. Compare those arrays at their original trace nodes; compare native time/qpos/qvel/torque/contact at every native row. Phase transitions, scorer conditions and final state are in `summary.json` and the mode-aware result. This distinction prevents inventing unrecorded native-step measurements.

## WSL use

After pulling the branch, verify the ZIP SHA256 against the sidecar, then verify member hashes against internal `BUNDLE_MANIFEST.json`. Python's standard `zipfile` and `lzma` modules and NumPy can decode `native_core.npz.xz`: decompress its bytes with `lzma.decompress`, wrap with `io.BytesIO`, then call `numpy.load(..., allow_pickle=False)`. Load `trace.npz` directly from ZIP bytes. Align by `native_step_index_1based` and original `time_s`; report the first differing native row and the first differing trace node for each field. Apply only the cross-host tolerances preregistered for the WSL study. This bundle is scientific comparison evidence, not a realtime or hardware qualification artifact.
