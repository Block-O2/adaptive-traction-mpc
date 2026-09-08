# Phase-3A corrected High-ROM baseline

This compact package freezes the reviewed corrected-baseline interpretation
without adding the approximately 469 MB local raw campaign to Git.

- `CORRECTED_BASELINE_REPORT.md` and `corrected_baseline_comparison.json`
  preserve the matched Rigid NEW versus P1 NEW metrics.
- `FORCE_DECOMPOSITION_REPORT.md`, `force_decomposition_summary.json`,
  `trajectory_component_summary.csv`, and `dense_force_maps.npz` preserve the
  compact analytic/model-derived force interpretation used by the professor
  report.
- `PROVENANCE.json` and `SOURCE_SHA256SUMS` bind this package to the frozen
  local evidence and the already tracked OLD-versus-NEW evidence.

The corrected campaign keeps the Human MPC, 140 Ns/m gain, estimator,
Safety Filter, BRAKE, 200 N registered simulation engineering target, models,
trajectories, timing, solver, seed, geometry, and P1 parameters unchanged.
Only the robot translational control-feedback velocity measurement source was
corrected before the matched interface comparison. The smoothed velocity path
remains in Human reconstruction, identification, and MPC measurement.

The 200 N target is an engineering stress-test target for this simulation. It
is not a clinical safety threshold or a validated hardware limit. Historical
BRAKE and P1 222 N results remain preserved as diagnostic history and are not
rewritten or deleted.
