# Cleanup Manifest

## Current Stage-Aligned Locations

### `results/stage7a_alpha_soft/`

- Contains the Stage 7A alpha-soft CEM closeout.
- Retained `stage7a_final_report.md`.
- Retained `stage7a_final_summary.csv`.
- Retained `clean_theta_trajectories.png`.
- Retained `alpha_p95_max_severity_by_method_condition.png`.
- Retained `omega_p95_max_severity_by_method_condition.png`.
- Retained `target_success_treach_summary.png`.
- Added `README.md` to clarify that this is a Stage 7A method closeout, not the final project result.

### `results/stage6_safety_filter/closeout/`

- Moved runtime filter negative-baseline evidence here:
  - `stage6_runtime_safety_filter_report.md`
  - `safety_filter_summary.csv`
  - `ukf_bias_safety_on_noise_bias.gif`

### `results/stage6b/closeout/`

- Moved sign-convention diagnostic evidence here:
  - `stage6b_diagnosis_report.md`
  - `sign_convention_probe.txt`
  - `ukf_bias_clean_diagnostics.png`
  - `ukf_bias_noise_bias_diagnostics.png`

## Deleted Earlier During Stage 7A Cleanup

- Deleted intermediate `results/stage7a_alpha_soft/` contents from the full sweep before recreating this closeout folder.
- Deleted `results/stage7a_alpha_soft_pre_ranking_fix/`.
- Deleted `results/stage7a_diagnosis/`.
- Deleted `results/stage7a_final_validation/` after retaining the final report, summary, and representative figures.
- Deleted `results/stage7a_refine/`.
- Deleted `results/stage7a_safety_aware_cem/`.

These folders were removed because Stage 7A alpha-soft CEM is closed out and the intermediate logs, CSVs, and figures are no longer needed for future reporting.

## Realignment Cleanup

- Removed the misleading `results/final_evidence/` structure.
- Moved its Stage 7A contents into `results/stage7a_alpha_soft/`.
- Moved runtime filter evidence into `results/stage6_safety_filter/closeout/`.
- Moved Stage 6b sign-diagnosis evidence into `results/stage6b/closeout/`.
- Added `results/README.md` to document the stage-based organization.

## Left Untouched

- Left `results/reports/` untouched.
- Left `results/stage1_spring2d/` through `results/stage5_coupling/` untouched.
- Left existing `results/stage6_safety_filter/` artifacts untouched except for adding `closeout/`.
- Left existing `results/stage6b/` artifacts untouched except for adding `closeout/`.
- Did not modify `src/`, `scripts/`, `tests/`, or `configs/`.

## Missing Expected Media

- No gif/video was found under the removed `results/stage7a_final_validation/`, so four representative figures were retained instead.
