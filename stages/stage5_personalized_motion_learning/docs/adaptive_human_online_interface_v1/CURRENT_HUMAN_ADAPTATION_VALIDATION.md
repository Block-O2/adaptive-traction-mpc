# Current-version bounded Human qualification

CURRENT_HUMAN_ADAPTATION_CONFIRMED. Four inherited development fixtures, three arms per fixture, identical physical truth and commissioning path within each trio. All use the registered 5/10° → 120/120° → HOLD → 5/10° task. These are exposed development conditions, with one repetition per arm; no statistical population qualification.

| fixture | height m | mass kg | stiffness pair | damping pair | length scales | cuff fraction | hip X/Z m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| high_rom_nominal_sync_120_v1 | 1.72 | 75.0 | [10.0, 10.0] | [5.0, 5.0] | [1.0, 1.0] | 0.72 | [0.0, 0.0001] |
| high_rom_matrix_light_soft_sync_v1 | 1.68 | 68.0 | [8.0, 8.0] | [4.0, 4.0] | [1.0, 1.0] | 0.72 | [-0.003, 0.002] |
| high_rom_matrix_heavy_stiff_sync_v1 | 1.75 | 82.0 | [12.0, 12.0] | [6.0, 6.0] | [1.0, 1.0] | 0.72 | [0.003, 0.003] |
| high_rom_matrix_short_segments_sync_v1 | 1.72 | 75.0 | [10.0, 10.0] | [5.0, 5.0] | [0.98, 0.98] | 0.7 | [-0.004, 0.002] |


All four continual and all four commissioning-only arms pass the unchanged physical and scientific-mode checks. Fixed nominal passes only nominal. Heavy/stiff times out; short-segment recovery aborts; light/soft returns outside the true endpoint criterion despite the runner's COMPLETE string. Failed partial-task integrals cannot be ranked against complete-task integrals.

| Human | arm | runtime | physical | J_F (N s) | F peak (N) | M peak (Nm) | duration (s) | task beta accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| matrix_heavy_stiff_sync | commissioning_only | COMPLETE | PASS | 1424.23 | 131.12 | 17.69 | 15.910 | 0 |
| matrix_heavy_stiff_sync | continual_adaptive | COMPLETE | PASS | 1432.45 | 131.12 | 17.75 | 15.970 | 29 |
| matrix_heavy_stiff_sync | fixed_population | ABORTED | FAIL | 982.09 | 143.20 | 15.27 | 10.000 | 0 |
| matrix_light_soft_sync | commissioning_only | COMPLETE | PASS | 1020.89 | 100.17 | 13.59 | 15.455 | 0 |
| matrix_light_soft_sync | continual_adaptive | COMPLETE | PASS | 1042.95 | 100.09 | 13.58 | 16.010 | 30 |
| matrix_light_soft_sync | fixed_population | COMPLETE | FAIL | 1000.36 | 89.42 | 16.42 | 16.235 | 0 |
| matrix_short_segments_sync | commissioning_only | COMPLETE | PASS | 1220.52 | 114.65 | 15.14 | 15.510 | 0 |
| matrix_short_segments_sync | continual_adaptive | COMPLETE | PASS | 1220.26 | 114.72 | 15.14 | 15.490 | 29 |
| matrix_short_segments_sync | fixed_population | ABORTED | FAIL | 0.00 | 87.32 | 14.17 | 0.000 | 0 |
| nominal_sync_120 | commissioning_only | COMPLETE | PASS | 1237.49 | 115.48 | 15.71 | 16.000 | 0 |
| nominal_sync_120 | continual_adaptive | COMPLETE | PASS | 1236.98 | 115.48 | 15.71 | 15.995 | 31 |
| nominal_sync_120 | fixed_population | COMPLETE | PASS | 1237.22 | 115.54 | 15.70 | 15.990 | 0 |


| Human continual | beta delta L2 | task updates | residual changes | actual execution models | planner numeric models | torque residual RMS (Nm) |
| --- | --- | --- | --- | --- | --- | --- |
| high_rom_matrix_heavy_stiff_sync_v1 | 1.8942 | 29 | 727 | 727 | 13 | 0.7044, 0.1960 |
| high_rom_matrix_light_soft_sync_v1 | 1.7999 | 30 | 732 | 732 | 13 | 0.5938, 0.1502 |
| high_rom_matrix_short_segments_sync_v1 | 0.8954 | 29 | 739 | 739 | 13 | 0.2509, 0.0588 |
| high_rom_nominal_sync_120_v1 | 0.7104 | 31 | 765 | 765 | 14 | 0.1010, 0.0195 |


Continual adaptation is numerically active and consumed. The light/soft J_F is about 2.16% worse than commissioning-only, heavy/stiff about 0.58% worse; nominal and short-segment differences are small. No uniform benefit claim. Commissioning is sufficient to restore physical validity in these four conditions; this experiment does not isolate causal performance benefit of every continual update.

The JSON contains initial/final beta, exact Human truth, effective geometry actually used, causal/truth tracking RMSE, force mean/RMS/peak, moment integral/peak, clearance, attempted-update rejection reasons and model hashes. Continual task beta accepts nominal/light/heavy/short = 31/30/29/29; no attempted dynamic update was rejected. Between-update samples are not counted as rejected fits. Residual RMS is the on-path measured generalized-torque regressor residual, before residual correction; it is not held-out prediction accuracy.

The legacy TASK controller_model_version string is blank. That logging gap is reported rather than used as evidence. Actual command-call numerical beta/residual hashes, planner worker-input snapshots and mechanics belief sequence records provide consumption evidence, tied to exact active source locations in CURRENT_HUMAN_ADAPTATION_SOURCE_EVIDENCE.json. Repetition persistence is source-audited; the new qualification has no multi-repetition longevity test. Geometry is commissioning-frozen; task updates change effective dynamics and residual only. Full shank length and cuff fraction are not separately identified.

Three multiprocessing launch failures are retained as EXCEPTION attempts; after the main guard repair the nominal three-arm rerun completed. No safety threshold, physical fixture or cost was adjusted to obtain completion.
