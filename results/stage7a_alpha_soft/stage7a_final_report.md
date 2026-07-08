# Stage 7A-final Alpha-Soft CEM Stress Validation Report

## 范围
- 本脚本只做 Stage 7A-final stress validation；不是新的调参 sweep。
- 对照方法固定为 `baseline_cem`, `runtime_filter_old`, `alpha100_omega0`, `alpha200_omega0`。
- alpha-soft 方法使用 `alpha_constraint_mode=soft`，`omega` soft weight 为 0，alpha 不作为 hard feasibility constraint。
- `runtime_filter_old` 复用旧 one-step runtime safety filter 配置；baseline CEM 行为保持 `safety_mode=off`。
- Spring2D dynamics、UKF/UKF-bias、Windowed NLS identifier、estimator/identifier data flow、基础 cost/constraints、solver 设置、max_time/max_steps 均未在脚本中修改。
- stress 条件只通过 per-run config override 显式注入，并记录在 summary CSV 中；没有 post-result manual tuning。
- 以下结论是仿真经验结果，不是 formal safety guarantee。

## Commands Run
- `conda run -n mpc_learn python -m compileall scripts/run_spring2d_stage7a_final_validation.py`
- `conda run -n mpc_learn python -m pytest tests`
- `conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7a_final_validation.py`

## Stress Overrides
| condition | base | true_param_overrides | mpc_overrides |
|---|---|---|---|
| clean | clean | `{}` | `{}` |
| noise | noise | `{}` | `{}` |
| noise_bias | noise_bias | `{}` | `{}` |
| model_mismatch_light | clean | `{'m': 1.32, 'k': 495.0, 'b_r': 14.4}` | `{}` |
| model_mismatch_heavy | clean | `{'m': 1.5, 'k': 540.0, 'b_r': 10.8}` | `{}` |
| larger_target | clean | `{'theta_target': 1.8325957145940461}` | `{'target_theta': 1.8325957145940461}` |
| worse_initial_state | clean | `{'theta_init': 0.04, 'omega_init': -0.18, 'r_init': 0.33, 'r_dot_init': -0.03}` | `{}` |
| combined_stress | noise_bias | `{'m': 1.32, 'k': 495.0, 'b_r': 14.4, 'theta_init': 0.04, 'omega_init': -0.18, 'r_init': 0.33, 'r_dot_init': -0.03}` | `{}` |

## Aggregate Metrics
| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | alpha p95 std | omega p95 avg | omega max avg | T_reach avg | action smooth avg | runtime avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_cem | 6/8 | 0.9953 | 4.845 | 9.135 | 1.286 | 0.1368 | 0.3367 | 2.26 | 0.2124 | 62.04 |
| runtime_filter_old | 1/8 | 0.4072 | 2.268 | 12.17 | 0.9907 | 0.1437 | 0.2996 | 6.76 | 0.1397 | 99.68 |
| alpha100_omega0 | 7/8 | 0.9629 | 4.68 | 11.7 | 1.148 | 0.2072 | 0.4118 | 2.43 | 0.2125 | 52.43 |
| alpha200_omega0 | 6/8 | 0.912 | 4.223 | 10.55 | 1.045 | 0.1628 | 0.3659 | 2.362 | 0.1946 | 63.31 |

## Required Answers
1. `alpha200_omega0` 是否仍是 stress validation 下最佳候选？
- 否。按 target success、alpha mean、alpha p95、alpha max、omega p95、T_reach 的固定排序，最佳 alpha-soft 候选是 `alpha100_omega0`。
- `alpha200_omega0`: target=6/8, alpha_mean_avg=0.912, alpha_p95_avg=4.223, omega_p95_avg=0.1628。
- `alpha100_omega0`: target=7/8, alpha_mean_avg=0.9629, alpha_p95_avg=4.68, omega_p95_avg=0.2072。

2. `alpha100_omega0` 是否比 `alpha200_omega0` 更稳定？
- 否/不明显。这里用 target success 不更差且 alpha p95 跨条件标准差更低作为稳定性判据；alpha100 std=1.148, alpha200 std=1.045。

3. alpha-soft CEM 是否一致保持 target reaching？
- 两个 alpha-soft 方法的较差 target success 为 6/8。若不是 8/8，则不能声称一致保持。

4. 相比 baseline，是否降低 alpha mean、p95、max severity？
- `alpha100_omega0`: mean 改善 5/8 条件，p95 改善 3/8，max 改善 1/8；平均 delta mean/p95/max=-0.03236/-0.1649/2.568。
- `alpha200_omega0`: mean 改善 6/8 条件，p95 改善 7/8，max 改善 4/8；平均 delta mean/p95/max=-0.08324/-0.6224/1.418。

5. 是否恶化 omega tail risk？
- `alpha100_omega0`: omega p95 比 baseline 更差 7/8 条件，omega max 更差 6/8；平均 delta p95/max=0.07039/0.07513。
- `alpha200_omega0`: omega p95 比 baseline 更差 4/8 条件，omega max 更差 6/8；平均 delta p95/max=0.02602/0.0292。

6. 是否仍优于旧 one-step runtime filter？
- 是。旧 filter target=1/8, alpha_mean_avg=0.4072; 最佳 alpha-soft target=7/8, alpha_mean_avg=0.9629。

7. alpha-soft CEM 是否强到可以作为 Stage 7A final candidate carry forward？
- 否，当前 stress validation 证据不足以强 carry forward。

8. 如果不够，下一步应是 progress governor 还是 PSF/gatekeeper-lite？
- 建议下一步是 `progress governor`，而不是继续做 alpha-soft weight tuning；除非某个单一 stress 条件给出非常明确、可复现的权重敏感证据。

9. 是否建议继续调 alpha-soft weight？
- 不建议把下一步默认设为更多 alpha-soft weight tuning。本次验证只保留 `alpha100_omega0` 与 `alpha200_omega0` 的证据对照。

## Outputs
- `stage7a_final_summary.csv` contains all per-method/per-condition metrics.
- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.
- Plots are under `figs/`.

Bad or mixed results are reported as-is.
