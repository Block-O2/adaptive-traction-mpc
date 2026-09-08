# Phase-3A corrected High-ROM baseline

This compact package freezes the reviewed corrected-baseline interpretation
and is self-contained in a clean Git clone. The approximately 457 MiB local
corrected campaign is represented by compact render inputs and external raw
checksums rather than committed raw traces.

- `CORRECTED_BASELINE_REPORT.md` and `corrected_baseline_comparison.json`
  preserve the matched Rigid NEW versus P1 NEW metrics.
- `FORCE_DECOMPOSITION_REPORT.md`, `force_decomposition_summary.json`,
  `trajectory_component_summary.csv`, and `dense_force_maps.npz` preserve the
  compact analytic/model-derived force interpretation.
- `report_sources/` contains only frame-sampled video state, downsampled
  tracking/force overlays, and frozen analytic-model vectors required by the
  final builders.
- `historical_diagnostics/` retains concise REPORT/JSON/CSV/manifests from
  pre-correction execution-stack, twist, velocity-path, temporal, and P1-event
  audits; bulky windows and figures are intentionally omitted.
- `CLEAN_CLONE_SHA256SUMS` covers files expected in Git.
- `EXTERNAL_RAW_ARCHIVE_SHA256SUMS` identifies the intentionally external
  corrected campaign and all 232 tracked historical raw/media artifacts
  removed during Phase 2.
- `PROVENANCE.json` records the scientific invariants and migration boundary.

The corrected campaign keeps the Human MPC, 140 Ns/m gain, estimator, Safety
Filter, BRAKE, 200 N registered simulation engineering target, models,
trajectories, timing, solver, seed, geometry, and P1 parameters unchanged.
Only the robot translational control-feedback velocity measurement source was
corrected before the matched interface comparison. The smoothed velocity path
remains in Human reconstruction, identification, and MPC measurement.

Corrected 40/80, 90/120, and 120/120 no longer show the old BRAKE/200 N
limitation. P1 is not required for High-ROM feasibility; its remaining benefit
is trajectory-dependent transient smoothing. Historical Rigid BRAKE and P1
approximately 222 N results are explicitly pre-correction diagnostic history.
They remain in Git history and compact diagnostic summaries, not as
current-baseline evidence.

The 200 N target is a registered engineering stress-test target for this
simulation. It is not a clinical safety threshold or a validated hardware
limit.

From the repository root:

```bash
conda run -n mpc_learn python \
  stages/stage4_adaptive_control/scripts/build_phase3a_corrected_professor_html.py

MPLCONFIGDIR=/tmp/phase3a-mpl conda run -n mpc_learn python \
  stages/stage4_adaptive_control/scripts/build_phase3a_force_landscape.py \
  --output-dir /tmp/phase3a-force-landscape
```
