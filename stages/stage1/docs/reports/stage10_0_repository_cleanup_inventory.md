# Stage 10-0: Repository Consolidation — Pre-cleanup Inventory

Inventory captured on 2026-07-14 before any Stage 10-0 move or deletion.

## Scope and protection

This is repository maintenance only. The inventory protects `src/`, `configs/`, `tests/`, `scripts/`, `AGENTS.md`, `pyproject.toml`, and `requirements.txt`. Experiment scripts are retained even when their result directories are archived. No controller, dynamics, estimator, identifier, metric, configuration, solver, or experiment conclusion is changed.

Current Git revision: `f75b3f6028af0c9cc74001730af4a4c7a1f4f279`.

## Git status before cleanup

```text
 M src/traction_mpc/identification/windowed_ls_identifier.py
 M src/traction_mpc/mpc/cost.py
 M src/traction_mpc/mpc/fixed_mpc.py
 M src/traction_mpc/mpc/solvers/cem.py
?? results/stage8a_ukf_sensitivity/
?? results/stage8b_oracle_diagnosis/
?? results/stage8c_constraint_revision/
?? results/stage8d_low_freq_cem/
?? results/stage8e_explicit_nmpc/
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

The four modified source files and the untracked robust identifier predate this cleanup and are treated as user work. They will not be edited by Stage 10-0.

Tracked-file inventory: 195 files total, including 52 under `results/`. Files present but not tracked: 956, including 778 under `results/` (ignored files included). Stage 1–7 curated result directories are tracked; Stage 8–9 directories and scripts are currently untracked.

## Repository size before cleanup

Total working repository including `.git`: 1,354,832 KiB (about 1.29 GiB). `results/` is 466,380 KiB (about 455 MiB).

| Top-level entry | Size | File count |
|---|---:|---:|
| `.git/` | 185 MiB | 1,307 |
| `.pytest_cache/` | 20 KiB | 5 |
| `.vscode/` | 4 KiB | 1 |
| `assets/` | 17 MiB | 21 |
| `configs/` | 44 KiB | 11 |
| `docs/` | 28 KiB | 3 |
| `legacy/` | 59 MiB | 45 |
| `results/` | 455 MiB | 830 |
| `scripts/` | 2.5 MiB | 77 |
| `src/` | 912 KiB | 105 |
| `tests/` | 80 KiB | 10 |
| `third_party/` | 604 MiB | 66 |

Top-level files (`AGENTS.md`, `README.md`, `.gitignore`, `pyproject.toml`, and `requirements.txt`) are each below 4 KiB. `third_party/mujoco_menagerie/` is an embedded Git checkout and is already ignored; it is outside this result-consolidation scope.

## Result-stage sizes before cleanup

| Result stage | Size | Files | Classification |
|---|---:|---:|---|
| `stage1_spring2d` | 424.5 KiB | 3 | Archive; retain two summaries, one figure, and a conclusion note |
| `stage2_cem` | 84.9 KiB | 2 | Archive; retain report, summary, and one figure |
| `stage2_cem_feasfirst` | 89.9 KiB | 2 | Archive; retain report, summary, and one figure |
| `stage3_filtering` | 120.0 KiB | 2 | Archive; retain report, summary, and one figure |
| `stage4_ukf` | 136.4 KiB | 2 | Archive; retain report, summary, and one figure |
| `stage5_coupling` | 189.8 KiB | 2 | Archive; retain report, summary, and one figure |
| `stage6_safety_filter` | 13.7 KiB | 2 | Archive; retain negative-result report and summary |
| `stage6b` | 899.2 KiB | 4 | Archive; retain diagnosis, probe, and two diagnostic figures |
| `stage7a_alpha_soft` | 346.1 KiB | 8 | Archive; retain report, summary/manifest, and three figures |
| `stage7b_progress_governor` | 535.1 KiB | 6 | Archive; retain report, summary, and three figures |
| `stage7c_gatekeeper_alpha_tail` | 512.0 KiB | 6 | Archive; retain report, summary, and three figures |
| `stage7c_gatekeeper_lite` | 357.2 KiB | 6 | Archive; retain report, summary, and three figures |
| `stage7d_safety_aware_governor` | 324.8 KiB | 6 | Archive; retain report, summary, and three figures |
| `stage8a_ukf_sensitivity` | 24.0 MiB | 37 | Archive; delete regenerable logs; retain report, summary, and three figures |
| `stage8b_oracle_diagnosis` | 1.8 MiB | 17 | Archive; retain report, summary, and three representative figures |
| `stage8c_constraint_revision` | 1.3 MiB | 14 | Archive; retain report, summary, and three representative figures |
| `stage8d_low_freq_cem` | 4.6 MiB | 16 | Archive; retain report, summary, and three representative figures |
| `stage8e_explicit_nmpc` | 1.0 MiB | 16 | Archive; retain report, summary, and three representative figures |
| `stage9a_proper_nmpc` | 575.8 KiB | 9 | Keep active; retain report, summary, and representative figures only |
| `stage9b_nmpc_diagnosis` | 426.7 KiB | 8 | Keep active; retain report, summary, and representative figures only |
| `stage9c_scaled_nmpc_validation` | 3.2 MiB | 26 | Keep authoritative minimal evidence: report, summary, and representative figures |
| `stage9d_nmpc_stress_validation` | 10.2 MiB | 78 | Keep authoritative minimal evidence: report, summary, and representative figures |
| `stage9e_nmpc_recovery` | 2.1 MiB | 35 | Keep active; retain report, summary, and representative figures only |
| `stage9f_crossing_lexicographic_nmpc` | 11.9 MiB | 137 | Keep active; retain report, summary, and representative figures only |
| `stage9g_crossing_alpha_frontier` | 161.9 KiB | 6 | Keep authoritative minimal evidence: report, summary, and three figures |
| `stage9h_planner_tracker` | 1.0 MiB | 13 | Keep authoritative minimal evidence: report, both summaries, and representative figures |
| `stage9i_adaptive_planner_tracker` | 1.5 MiB | 13 | Keep active; retain report, summary, and representative figures only |
| `stage9j_gap_decomposition` | 47.9 MiB | 20 | Preserve: report, summary, per-run, mode audit, replay, manifest/command, required plots, and one GIF |
| `stage9k_identifier_ablation` | 13.8 MiB | 18 | Preserve: report, offline data/summaries, conditioning, calibration, gate, planner diagnosis, command, and required plots |

In addition, the old ignored `results/_archive/20260708_125740/` occupies about 325 MiB. It contains old Stage 2–7 reports plus regenerable raw logs, GIFs, and duplicated closeout artifacts. Unique reports will be retained in the new curated legacy archive; redundant raw outputs will be removed.

## Large tracked files

Tracked files larger than 5 MiB:

| Size | File |
|---:|---|
| 6.19 MiB | `assets/robots/cr12_12_pending/meshes/Thin39C8017Baiiu_9.stl` |
| 13.56 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_1.gif` |
| 11.41 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_2.gif` |
| 8.14 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_3.gif` |
| 10.77 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_4.gif` |
| 12.80 MiB | `legacy/stage_1/ongoing_parts/integrated_sim_3d_v15_5.gif` |

No tracked file is larger than 20 MiB. The five legacy GIF variants are likely consolidation candidates, but `legacy/` is outside the requested result-stage cleanup, so they are retained for manual review.

## Duplicates, caches, temporary artifacts, and empty directories

- `results/_archive/20260708_125740/` duplicates the current Stage 6 and 6b closeout reports, summaries, probe, and two figures byte-for-byte.
- The old archive contains many byte-identical GIFs reused across Stage 2–5. Examples include `cem_noise_bias.gif` (five copies), `cem_clean.gif` (five copies), and repeated random-shooting GIFs.
- Stage 9H has six byte-identical per-seed planner-tracking plots. Stage 9I has three identical plots for each oracle/adaptive/replan mode. These are safe candidates for representative-figure retention.
- Repeated filenames such as `alpha_max_bar.png`, `clean_alpha_trajectories.png`, and condition-specific action/theta plots mostly belong to distinct stages, so a shared basename alone is not treated as proof of duplicate content.
- Generated caches: `.pytest_cache/` and 15 `__pycache__/` trees under `tests/`, `scripts/`, and `src/`, containing Python 3.10/3.14 bytecode.
- No project `.log`, `.tmp`, `.DS_Store`, or `ipopt.out` file was found outside ignored Git internals.
- Only empty directories found are internal to `third_party/mujoco_menagerie/.git/`; they are outside scope.

## References and hardcoded result paths

References that constrain cleanup:

- `scripts/run_spring2d_stage9k_identifier_ablation.py` consumes `results/stage9j_gap_decomposition/stage9j_replay.csv`; this replay is the authoritative Stage 10 offline-estimator input and must remain at its current path.
- Stage 9 scripts use default output roots matching their current `results/stage9*` directories. Stage 9 directories are therefore not moved.
- Stage 1's report in `docs/reports/stage1_spring2d_adaptive_mpc_report.md` links to the old Stage 1 figure/video paths and must be updated after archival.
- `docs/reports/stage5_5_consolidation_report.md` references old `results/reports/stage2...stage5` report paths that are already absent; these stale paths must be corrected to the curated legacy archive.
- Configs for Stage 2, 5, and 6 contain their historical `results/stage*` output roots. Configs are protected and will not be changed; rerunning those scripts may recreate active output directories, which is acceptable generated-output behavior.
- Several baseline configs and scripts refer to `results/logs/`, `results/videos/`, and `results/figures/`; these are generated local outputs and remain ignored.
- `scripts/run_spring2d_stage7a_refine.py` references an old Stage 7A log path. The script is retained as a deprecation/manual-review candidate; no behavior change is made here.
- No test or source import was found that imports Python code from `results/`.

## Archive conclusions and retention rationale

The Stage 1–8 conclusions are taken from their existing reports, not inferred from filenames:

- Stage 1 established the Spring2D experiment and initial fixed/adaptive evidence.
- Stage 2 retained CEM and feasibility-first solver-selection evidence.
- Stage 3 evaluated filtering under noise and bias.
- Stage 4 established UKF-bias as the later mainline estimator.
- Stage 5 established the filtered UKF-bias to filtered Windowed NLS data flow.
- Stage 6 runtime filtering is a negative baseline because it often destroys target reaching; Stage 6b ruled out sign convention and tangential-force reversal as the main issue.
- Stage 7 variants were closed as negative or mixed: alpha-soft CEM was insufficient, the fixed-rate governor was unreliable, gatekeeper variants did not resolve alpha tails, and the Stage 7D governor failed target reaching.
- Stage 8A supported retaining default UKF-bias settings; Stage 8B–8E did not find a simple oracle-budget, low-frequency, task-urgency, or minimal direct-shooting remedy that jointly preserved crossing and reduced all alpha-tail metrics.

## Planned deletions versus manual review

Safe to delete after this inventory: Python/test caches; old ignored Stage 1–8 raw logs and repeated GIFs under `results/_archive/`; extra Stage 8–9 plots beyond the explicitly retained representative set; and byte-identical Stage 6/6b archive duplicates.

Manual review, therefore retained: all `legacy/` content; `third_party/`; the robot mesh assets; all Stage 9J/9K data named in the task; the Stage 9J GIF; any result artifact whose role is ambiguous; and all experiment scripts.
