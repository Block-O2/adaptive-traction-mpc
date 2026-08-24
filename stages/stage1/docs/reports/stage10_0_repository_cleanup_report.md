# Stage 10-0: Repository Consolidation Report

Date: 2026-07-14  
Pre-cleanup Git revision: `f75b3f6028af0c9cc74001730af4a4c7a1f4f279`

## Outcome

Repository consolidation completed without changing algorithms, controller behavior, dynamics, configs, metrics, experiment conclusions, horizons, weights, constraints, solvers, or scientific parameters. No experiment was rerun. No commit or push was performed.

The pre-cleanup evidence is recorded in `docs/reports/stage10_0_repository_cleanup_inventory.md`.

## Space reduction

| Scope | Before | After | Reduction |
|---|---:|---:|---:|
| Whole working repository including `.git` | 1,354,832 KiB | 958,996 KiB | 395,836 KiB (386.6 MiB, 29.2%) |
| `results/` | 466,380 KiB | 72,412 KiB | 393,968 KiB (384.7 MiB, 84.5%) |
| Curated Stage 1–8 archive | old archive plus active stage folders | 6,024 KiB | 5.9 MiB retained |

Most reduction came from the old 325 MiB `results/_archive/`, Stage 8A raw trajectories, and redundant Stage 9 plots. Active Stage 9J/9K data accounts for most of the remaining 71 MiB result tree.

## Files and directories moved

- Moved all curated Stage 1–7 directories from `results/stage*` to `results/archive/legacy_stages/<original-stage-name>/` using `git mv`.
- Moved the untracked Stage 8A–8E directories to the same legacy archive while preserving their original names.
- Moved five unique final reports from the old ignored archive into their matching Stage 2–5 directories:
  - `stage2_cem_solver_comparison_report.md`
  - `stage2_cem_feasfirst_report.md`
  - `stage3_filtering_report.md`
  - `stage4_ukf_estimator_report.md`
  - `stage5_estimator_identifier_coupling_report.md`
- Added `results/archive/legacy_stages/README.md` and a Stage 1 conclusion/retention README.
- Stage 9 directories were deliberately not moved because scripts use those output roots and Stage 9K directly consumes the Stage 9J replay path.

## Files deleted

- Removed the remaining old `results/_archive/` content after preserving its five unique reports. The old archive had 315 files before cleanup; 310 regenerable or duplicate files were deleted. These consisted primarily of raw time-series CSVs, repeated GIFs, extra figures, and byte-identical Stage 6/6b closeout copies.
- Removed all 27 Stage 8A per-condition time-series logs plus five surplus figures.
- Removed surplus Stage 8 figures: 12 from Stage 8B, 9 from Stage 8C, 11 from Stage 8D, and 11 from Stage 8E.
- Removed six tracked surplus Stage 7 figures after archival.
- Removed 279 surplus Stage 9A–9I figures. Every affected stage retains its final report, final summary, and up to three representative figures; Stage 9H also retains its boundary summary.
- Removed Python bytecode trees and `.pytest_cache/` before and after validation.
- No ambiguous data, experiment script, config, source file, test, or legacy prototype was deleted.

## Deliberately retained evidence

- All Stage 9J report/summary/per-run/mode-audit/replay/config/command data, all twelve required diagnostic plots, and one local three-times-slow GIF.
- All Stage 9K offline per-run/summary, conditioning, calibration, planner-time diagnosis, gate, command, report, and ten required figures.
- Minimal authoritative Stage 9C, 9D, 9G, and 9H evidence.
- Final reports and summaries for every other Stage 9 sub-stage.
- All experiment scripts, including historical and possible future-deprecation candidates.
- All `legacy/`, `assets/`, and `third_party/` content because their purpose or external provenance is outside this cleanup's result-retention authority.
- Existing negative and mixed conclusions, including Stage 9K's failed offline gate and skipped closed-loop run.

Large retained result artifacts that are currently untracked or ignored:

| Size | Artifact | Reason |
|---:|---|---|
| 23 MiB | `results/stage9j_gap_decomposition/stage9j_per_run.csv` | Explicitly required Stage 9J audit evidence |
| 15 MiB | `results/stage9j_gap_decomposition/best_full_adaptive_initial_theta_offset_seed101_slow3x.gif` | Local visual inspection only; ignored by Git |
| 8.7 MiB | `results/stage9k_identifier_ablation/stage9k_offline_per_run.csv` | Explicitly required Stage 9K offline evidence |
| 5.6 MiB | `results/stage9j_gap_decomposition/stage9j_mode_audit.csv` | Explicitly required mode-isolation evidence |

## Documentation and policy changes

- Rewrote the root `README.md` as the current project entry point with the required architecture, validated findings, limitations, commands, and Stage 10 roadmap.
- Rewrote `results/README.md` to distinguish archived and active results, designate authoritative Stage 9 data, and define the artifact policy.
- Added `results/reproducibility_manifest.md` covering authoritative Stages 9C, 9D, 9G, 9H, 9J, and 9K.
- Updated `.gitignore` for build/test/type/lint caches, local outputs, solver runtime artifacts, and generated videos while explicitly keeping curated Markdown, CSV, and PNG evidence visible to Git.
- Fixed Stage 1 report links after archival and redirected the Stage 5.5 source-report paths to the new legacy archive.

## Broken-reference audit

- Markdown local-link scan after cleanup: 0 broken links.
- README command/path audit: all referenced scripts and configs exist.
- `--help` checks for the open-loop, Stage 9C, 9D, 9G, 9H, 9J, and 9K commands all exited 0.
- No source or test imports code from `results/`.
- Historical configs still point to their original Stage 2/5/6/7 output directories. They are output destinations, not imports; configs were protected from behavioral edits, and rerunning a historical experiment may recreate those local directories.
- `scripts/run_spring2d_stage7a_refine.py` contains a report-text reference to a removed historical log directory. It does not import the data at that line and remains a manual deprecation candidate.

## Validation

Commands run:

```text
conda run -n mpc_learn python -m pytest tests
conda run -n mpc_learn python -m compileall -q src scripts tests
conda run -n mpc_learn python scripts/run_spring2d_openloop.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9c_scaled_nmpc_validation.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9d_nmpc_stress_validation.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9g_crossing_alpha_frontier.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9h_planner_tracker.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py --help
conda run -n mpc_learn python scripts/run_spring2d_stage9k_identifier_ablation.py --help
```

Results:

- Test suite: **10 passed in 0.45 s**.
- Compile/import check: **passed**.
- CLI/path checks: **7/7 passed**.
- The open-loop help check emitted Matplotlib/fontconfig cache warnings because the user cache directories were not writable in the sandbox; it used a temporary cache and exited 0.
- No old experiment was executed.

## Remaining tracked files larger than 5 MiB and 20 MiB

| Size | Tracked file | Review status |
|---:|---|---|
| 6.19 MiB | `assets/robots/cr12_12_pending/meshes/Thin39C8017Baiiu_9.stl` | Retained asset |
| 13.56 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_1.gif` | Manual review |
| 11.41 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_2.gif` | Manual review |
| 8.14 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_3.gif` | Manual review |
| 10.77 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_4.gif` | Manual review |
| 12.80 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_5.gif` | Manual review |

No tracked file is larger than 20 MiB.

## Remaining manual-review items

1. Decide separately whether the five tracked legacy GIF variants should be reduced; they are outside the requested `results/` consolidation.
2. Decide whether the embedded `third_party/mujoco_menagerie/` Git checkout should become a submodule, external dependency, or remain local. It occupies about 604 MiB but is already ignored and was not modified.
3. Before a future commit, intentionally select the untracked Stage 8–9 scripts/results and the pre-existing `robust_windowed_nls_identifier.py`; do not use broad `git add` without review.
4. The four modified tracked source files were already modified before Stage 10-0 and were not touched here. Their scientific changes require separate review.
5. Exact generating Git revisions for untracked Stage 9 artifacts were unavailable; the reproducibility manifest says so explicitly.

## Exact Stage 10 directory recommendation

```text
results/stage10_joint_state_parameter_estimator/
```

Stage 10 should begin with offline estimator comparison on the unchanged `results/stage9j_gap_decomposition/stage9j_replay.csv`. No Stage 10 estimator was implemented here.

## Final `git status --short`

The exact post-validation status is recorded below after the final cache cleanup.

```text
 M .gitignore
 M README.md
 M docs/reports/stage1_spring2d_adaptive_mpc_report.md
 M docs/reports/stage5_5_consolidation_report.md
 M results/README.md
R  results/stage1_spring2d/figures/adaptive_conditions_comparison.png -> results/archive/legacy_stages/stage1_spring2d/figures/adaptive_conditions_comparison.png
R  results/stage1_spring2d/tables/adaptive_conditions_summary_table.csv -> results/archive/legacy_stages/stage1_spring2d/tables/adaptive_conditions_summary_table.csv
R  results/stage1_spring2d/tables/identifier_conditions_summary_table.csv -> results/archive/legacy_stages/stage1_spring2d/tables/identifier_conditions_summary_table.csv
R  results/stage2_cem/figures/solver_comparison.png -> results/archive/legacy_stages/stage2_cem/figures/solver_comparison.png
R  results/stage2_cem/tables/solver_comparison_summary.csv -> results/archive/legacy_stages/stage2_cem/tables/solver_comparison_summary.csv
R  results/stage2_cem_feasfirst/figures/solver_comparison.png -> results/archive/legacy_stages/stage2_cem_feasfirst/figures/solver_comparison.png
R  results/stage2_cem_feasfirst/tables/solver_comparison_summary.csv -> results/archive/legacy_stages/stage2_cem_feasfirst/tables/solver_comparison_summary.csv
R  results/stage3_filtering/figures/filtering_comparison.png -> results/archive/legacy_stages/stage3_filtering/figures/filtering_comparison.png
R  results/stage3_filtering/tables/filtering_summary.csv -> results/archive/legacy_stages/stage3_filtering/tables/filtering_summary.csv
R  results/stage4_ukf/figures/ukf_comparison.png -> results/archive/legacy_stages/stage4_ukf/figures/ukf_comparison.png
R  results/stage4_ukf/tables/ukf_summary.csv -> results/archive/legacy_stages/stage4_ukf/tables/ukf_summary.csv
R  results/stage5_coupling/figures/coupling_comparison.png -> results/archive/legacy_stages/stage5_coupling/figures/coupling_comparison.png
R  results/stage5_coupling/tables/coupling_summary.csv -> results/archive/legacy_stages/stage5_coupling/tables/coupling_summary.csv
R  results/stage6_safety_filter/closeout/safety_filter_summary.csv -> results/archive/legacy_stages/stage6_safety_filter/closeout/safety_filter_summary.csv
R  results/stage6_safety_filter/closeout/stage6_runtime_safety_filter_report.md -> results/archive/legacy_stages/stage6_safety_filter/closeout/stage6_runtime_safety_filter_report.md
R  results/stage6b/closeout/sign_convention_probe.txt -> results/archive/legacy_stages/stage6b/closeout/sign_convention_probe.txt
R  results/stage6b/closeout/stage6b_diagnosis_report.md -> results/archive/legacy_stages/stage6b/closeout/stage6b_diagnosis_report.md
R  results/stage6b/closeout/ukf_bias_clean_diagnostics.png -> results/archive/legacy_stages/stage6b/closeout/ukf_bias_clean_diagnostics.png
R  results/stage6b/closeout/ukf_bias_noise_bias_diagnostics.png -> results/archive/legacy_stages/stage6b/closeout/ukf_bias_noise_bias_diagnostics.png
R  results/stage7a_alpha_soft/README.md -> results/archive/legacy_stages/stage7a_alpha_soft/README.md
R  results/stage7a_alpha_soft/clean_theta_trajectories.png -> results/archive/legacy_stages/stage7a_alpha_soft/clean_theta_trajectories.png
R  results/stage7a_alpha_soft/cleanup_manifest.md -> results/archive/legacy_stages/stage7a_alpha_soft/cleanup_manifest.md
R  results/stage7a_alpha_soft/stage7a_final_report.md -> results/archive/legacy_stages/stage7a_alpha_soft/stage7a_final_report.md
R  results/stage7a_alpha_soft/stage7a_final_summary.csv -> results/archive/legacy_stages/stage7a_alpha_soft/stage7a_final_summary.csv
R  results/stage7a_alpha_soft/target_success_treach_summary.png -> results/archive/legacy_stages/stage7a_alpha_soft/target_success_treach_summary.png
R  results/stage7b_progress_governor/figs/alpha_omega_p95_bar.png -> results/archive/legacy_stages/stage7b_progress_governor/figs/alpha_omega_p95_bar.png
R  results/stage7b_progress_governor/figs/clean_alpha_trajectory.png -> results/archive/legacy_stages/stage7b_progress_governor/figs/clean_alpha_trajectory.png
R  results/stage7b_progress_governor/figs/noise_bias_theta_theta_cmd_trajectory.png -> results/archive/legacy_stages/stage7b_progress_governor/figs/noise_bias_theta_theta_cmd_trajectory.png
R  results/stage7b_progress_governor/stage7b_minimal_report.md -> results/archive/legacy_stages/stage7b_progress_governor/stage7b_minimal_report.md
R  results/stage7b_progress_governor/stage7b_minimal_summary.csv -> results/archive/legacy_stages/stage7b_progress_governor/stage7b_minimal_summary.csv
R  results/stage7c_gatekeeper_alpha_tail/figs/alpha_p95_max_bar.png -> results/archive/legacy_stages/stage7c_gatekeeper_alpha_tail/figs/alpha_p95_max_bar.png
R  results/stage7c_gatekeeper_alpha_tail/figs/clean_nominal_vs_selected_alpha_max.png -> results/archive/legacy_stages/stage7c_gatekeeper_alpha_tail/figs/clean_nominal_vs_selected_alpha_max.png
R  results/stage7c_gatekeeper_alpha_tail/figs/clean_theta_trajectory.png -> results/archive/legacy_stages/stage7c_gatekeeper_alpha_tail/figs/clean_theta_trajectory.png
R  results/stage7c_gatekeeper_alpha_tail/stage7c_alpha_tail_report.md -> results/archive/legacy_stages/stage7c_gatekeeper_alpha_tail/stage7c_alpha_tail_report.md
R  results/stage7c_gatekeeper_alpha_tail/stage7c_alpha_tail_summary.csv -> results/archive/legacy_stages/stage7c_gatekeeper_alpha_tail/stage7c_alpha_tail_summary.csv
R  results/stage7c_gatekeeper_lite/figs/alpha_p95_max_bar.png -> results/archive/legacy_stages/stage7c_gatekeeper_lite/figs/alpha_p95_max_bar.png
R  results/stage7c_gatekeeper_lite/figs/clean_alpha_trajectory.png -> results/archive/legacy_stages/stage7c_gatekeeper_lite/figs/clean_alpha_trajectory.png
R  results/stage7c_gatekeeper_lite/figs/clean_theta_trajectory.png -> results/archive/legacy_stages/stage7c_gatekeeper_lite/figs/clean_theta_trajectory.png
R  results/stage7c_gatekeeper_lite/stage7c_report.md -> results/archive/legacy_stages/stage7c_gatekeeper_lite/stage7c_report.md
R  results/stage7c_gatekeeper_lite/stage7c_summary.csv -> results/archive/legacy_stages/stage7c_gatekeeper_lite/stage7c_summary.csv
R  results/stage7d_safety_aware_governor/figs/alpha_p95_max_bar.png -> results/archive/legacy_stages/stage7d_safety_aware_governor/figs/alpha_p95_max_bar.png
R  results/stage7d_safety_aware_governor/figs/clean_theta_theta_cmd_target.png -> results/archive/legacy_stages/stage7d_safety_aware_governor/figs/clean_theta_theta_cmd_target.png
R  results/stage7d_safety_aware_governor/figs/target_success_T_reach.png -> results/archive/legacy_stages/stage7d_safety_aware_governor/figs/target_success_T_reach.png
R  results/stage7d_safety_aware_governor/stage7d_report.md -> results/archive/legacy_stages/stage7d_safety_aware_governor/stage7d_report.md
R  results/stage7d_safety_aware_governor/stage7d_summary.csv -> results/archive/legacy_stages/stage7d_safety_aware_governor/stage7d_summary.csv
D  results/stage7a_alpha_soft/alpha_p95_max_severity_by_method_condition.png
D  results/stage7a_alpha_soft/omega_p95_max_severity_by_method_condition.png
D  results/stage7b_progress_governor/figs/clean_theta_theta_cmd_trajectory.png
D  results/stage7c_gatekeeper_alpha_tail/figs/omega_p95_max_bar.png
D  results/stage7c_gatekeeper_lite/figs/omega_p95_max_bar.png
D  results/stage7d_safety_aware_governor/figs/omega_p95_max_bar.png
 M src/traction_mpc/identification/windowed_ls_identifier.py
 M src/traction_mpc/mpc/cost.py
 M src/traction_mpc/mpc/fixed_mpc.py
 M src/traction_mpc/mpc/solvers/cem.py
?? docs/reports/stage10_0_repository_cleanup_inventory.md
?? docs/reports/stage10_0_repository_cleanup_report.md
?? results/archive/legacy_stages/README.md
?? results/archive/legacy_stages/stage1_spring2d/README.md
?? results/archive/legacy_stages/stage2_cem/stage2_cem_solver_comparison_report.md
?? results/archive/legacy_stages/stage2_cem_feasfirst/stage2_cem_feasfirst_report.md
?? results/archive/legacy_stages/stage3_filtering/stage3_filtering_report.md
?? results/archive/legacy_stages/stage4_ukf/stage4_ukf_estimator_report.md
?? results/archive/legacy_stages/stage5_coupling/stage5_estimator_identifier_coupling_report.md
?? results/archive/legacy_stages/stage8a_ukf_sensitivity/
?? results/archive/legacy_stages/stage8b_oracle_diagnosis/
?? results/archive/legacy_stages/stage8c_constraint_revision/
?? results/archive/legacy_stages/stage8d_low_freq_cem/
?? results/archive/legacy_stages/stage8e_explicit_nmpc/
?? results/reproducibility_manifest.md
?? results/stage9a_proper_nmpc/
?? results/stage9b_nmpc_diagnosis/
?? results/stage9c_scaled_nmpc_validation/
?? results/stage9d_nmpc_stress_validation/
?? results/stage9e_nmpc_recovery/
?? results/stage9f_crossing_lexicographic_nmpc/
?? results/stage9g_crossing_alpha_frontier/
?? results/stage9h_planner_tracker/
?? results/stage9i_adaptive_planner_tracker/
?? results/stage9j_gap_decomposition/
?? results/stage9k_identifier_ablation/
?? scripts/run_spring2d_stage8a_ukf_sensitivity.py
?? scripts/run_spring2d_stage8b_oracle_diagnosis.py
?? scripts/run_spring2d_stage8c_constraint_revision.py
?? scripts/run_spring2d_stage8d_low_freq_cem.py
?? scripts/run_spring2d_stage8e_explicit_nmpc.py
?? scripts/run_spring2d_stage9a_proper_nmpc.py
?? scripts/run_spring2d_stage9b_nmpc_diagnosis.py
?? scripts/run_spring2d_stage9c_scaled_nmpc_validation.py
?? scripts/run_spring2d_stage9d_nmpc_stress_validation.py
?? scripts/run_spring2d_stage9e_nmpc_recovery.py
?? scripts/run_spring2d_stage9f_crossing_lexicographic_nmpc.py
?? scripts/run_spring2d_stage9g_crossing_alpha_frontier.py
?? scripts/run_spring2d_stage9h_planner_tracker.py
?? scripts/run_spring2d_stage9i_adaptive_planner_tracker.py
?? scripts/run_spring2d_stage9j_gap_decomposition.py
?? scripts/run_spring2d_stage9k_identifier_ablation.py
?? src/traction_mpc/identification/robust_windowed_nls_identifier.py
```
