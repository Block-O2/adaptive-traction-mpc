# Results Index and Artifact Policy

## Layout

```text
results/
├── archive/legacy_stages/     Curated Stage 1–8 evidence
├── stage9*/                   Active Stage 9 reports and retained evidence
├── stage10*/                  Joint-estimator audits and MHE closeout
└── stage11*/                  Passive-information and subspace audits
```

Archived results are closed historical baselines. Active results remain at their script-default paths so existing reproduction commands and the Stage 9J-to-9K replay dependency do not break.

## Authoritative Stage 9 evidence

| Stage | Role | Authoritative files |
|---|---|---|
| Stage 9C | Scaled multiple-shooting NMPC validation | `stage9c_scaled_nmpc_validation/stage9c_report.md`, `stage9c_summary.csv` |
| Stage 9D | Stress and initial-offset validation | `stage9d_nmpc_stress_validation/stage9d_report.md`, `stage9d_summary.csv` |
| Stage 9G | Crossing–alpha feasibility frontier | `stage9g_crossing_alpha_frontier/stage9g_report.md`, `stage9g_summary.csv` |
| Stage 9H | Long-horizon planner plus short-horizon tracker | `stage9h_planner_tracker/stage9h_report.md`, `stage9h_summary.csv`, `stage9h_boundary_summary.csv` |
| Stage 9J | Mode audit and adaptive–oracle gap decomposition | `stage9j_gap_decomposition/stage9j_report.md`, `stage9j_summary.csv`, `stage9j_per_run.csv`, `stage9j_mode_audit.csv` |
| Stage 9K | Identifier diagnosis and robust offline ablation | `stage9k_identifier_ablation/stage9k_report.md`, `stage9k_offline_summary.csv`, `stage9k_offline_per_run.csv`, `stage9k_conditioning.csv`, `stage9k_uncertainty_calibration.csv` |

The authoritative replay input for Stage 10 offline estimator comparison is:

```text
results/stage9j_gap_decomposition/stage9j_replay.csv
```

Do not rename, filter, or regenerate this file implicitly. Stage 10 comparisons should consume the same replay rows and document any explicit preprocessing.

## Authoritative Stage 10–11 evidence

| Stage | Role | Authoritative files |
|---|---|---|
| Stage 10A | Dynamics, sensitivity, and parameterization audit | `stage10a_dynamics_audit/stage10a_dynamics_parameterization_audit.md`, `sensitivity_summary.csv`, `conditioning_summary.csv` |
| Stage 10B | Matched single-shooting MHE and weighted-TLS benchmark | `stage10b_estimator_benchmark/stage10b_report.md`, `offline_summary.csv`, `offline_gate.json`, `offline_per_run.csv` |
| Stage 10C | Multiple-shooting MHE benchmark before the arrival-index correction | `stage10c_multiple_shooting_mhe/stage10c_report.md`, `offline_summary.csv`, `offline_gate.json`, `offline_per_run.csv` |
| Stage 10D | MHE formulation and alignment sanity audit | `stage10d_mhe_sanity_audit/stage10d_report.md`, `equivalence_summary.csv`, `oracle_sanity_summary.csv` |
| Stage 10E | Corrected multiple-shooting MHE benchmark | `stage10e_corrected_mhe_benchmark/stage10e_report.md`, `offline_summary.csv`, `offline_gate.json`, `offline_per_run.csv` |
| Stage 10F | Rolling MHE divergence and branch-closeout audit | `stage10f_mhe_divergence_audit/stage10f_report.md`, `update_trace.csv`, `first_divergence_events.csv`, `consistency_checks.csv` |
| Stage 11A | Task-relevant information-metric validation | `stage11a_information_metric_validation/stage11a_report.md`, `metric_summary.csv`, `gate_validation.csv`, `window_metrics.csv` |
| Stage 11B | Passive parameter-subspace audit | `stage11b_parameter_subspace_audit/stage11b_report.md`, `condition_summary.csv`, `subspace_summary.csv`, `profile_summary.csv`, `window_metrics.csv` |

Stage 11C is implemented and smoke-tested but is not yet authoritative full-run evidence. Its smoke output remains local.

## Retention policy

Every curated stage should contain:

- a final report;
- a final aggregate summary CSV;
- the config snapshot, manifest, or exact command needed to interpret it;
- at most a small representative figure set (normally one to three);
- only irreplaceable per-run or replay data required for a published conclusion or downstream comparison.

Raw trajectories, debug logs, repeated seed plots, solver output, caches, intermediate tuning exports, and videos are generated locally and should not be committed unless a report explicitly designates one as irreplaceable evidence. Stage 9J/9K retain more than three plots because those named diagnostic figures jointly support the decomposition and identifier conclusions. The local Stage 9J GIF is for visual inspection and is not an authoritative metric source.

Adaptive profile grids such as `profile_grid.csv` are recomputable raw artifacts and are intentionally ignored. Compact profile, window, condition, and subspace summaries are the retained evidence.

## Future stage naming

Use one directory per scientific stage, with lowercase snake-case names:

```text
results/stage12_example_method/
```

Follow-up ablations should use a clear suffix only after their scope is defined. Do not place temporary runs in a curated stage directory; use an ignored local output root and promote only final evidence.

The complete Stage 9 reproduction map is in `results/reproducibility_manifest.md`. Results are empirical simulation evidence and do not establish formal safety or stability.
