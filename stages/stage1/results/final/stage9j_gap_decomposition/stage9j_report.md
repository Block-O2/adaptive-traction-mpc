# Stage 9J Adaptive Planner–Tracker Gap Decomposition

## 实验与审计结论

- 模式隔离审计：通过。失败项：无。
- 每个 run 独立创建环境、噪声 wrapper、UKF、NLS、planner/tracker；主实验严格使用一次长时域规划，未启用事件触发重规划。
- primary crossing 与所有 primary alpha 指标均来自 true simulated state；estimated 与 planner/tracker predicted 指标分列保存。
- 跨 8 个条件，true alpha max gap 的平均绝对分解量：状态 0.1564，参数 8.202，交互残差 0.6676。交互残差只是诊断量，不作因果证明。
- Stage 9J 有 21 个 fixed/adaptive run 的 true-alpha 最大值相同，但完整 true-alpha 轨迹相同的 run 为 0 个。
- Stage 9K 唯一建议：**B. 跨条件 true alpha max 的平均绝对参数贡献最大（8.2，状态 0.156，交互 0.668）。**

## 聚合结果

| condition | method | crossing | true alpha p95 | p99 | max | violation duration | tracking RMSE |
|---|---|---:|---:|---:|---:|---:|---:|
| clean | baseline_cem | 1 | 9.026 | 13.13 | 14.29 | 0.9233 | nan |
| clean | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| clean | state_error_only | 1 | 2.88 | 2.961 | 3.179 | 0.02 | 0.03867 |
| clean | parameter_error_only | 1 | 3.377 | 6.315 | 6.363 | 0.18 | 0.6281 |
| clean | fixed_nominal_planner_tracker | 0 | 2.906 | 6.073 | 6.363 | 0.26 | 2.114 |
| clean | full_adaptive_planner_tracker | 1 | 3.258 | 6.181 | 6.363 | 0.26 | 0.57 |
| initial_theta_offset | baseline_cem | 1 | 7.832 | 10.92 | 12.14 | 1.033 | nan |
| initial_theta_offset | oracle_planner_tracker | 1 | 2.918 | 2.97 | 2.996 | 0 | 0.04434 |
| initial_theta_offset | state_error_only | 1 | 2.919 | 2.97 | 2.996 | 0 | 0.04419 |
| initial_theta_offset | parameter_error_only | 1 | 2.889 | 6.041 | 6.246 | 0.15 | 0.7662 |
| initial_theta_offset | fixed_nominal_planner_tracker | 0 | 3.199 | 5.682 | 6.246 | 0.98 | 2.107 |
| initial_theta_offset | full_adaptive_planner_tracker | 1 | 3.049 | 5.858 | 6.246 | 0.26 | 0.6325 |
| noise | baseline_cem | 1 | 7.993 | 14.02 | 25.91 | 1.17 | nan |
| noise | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| noise | state_error_only | 1 | 2.949 | 3.063 | 3.262 | 0.08 | 0.0406 |
| noise | parameter_error_only | 1 | 3.173 | 6.314 | 6.363 | 0.2733 | 0.6906 |
| noise | fixed_nominal_planner_tracker | 0 | 3.273 | 6.011 | 6.489 | 1 | 2.125 |
| noise | full_adaptive_planner_tracker | 1 | 3.197 | 6.112 | 6.489 | 0.3467 | 0.6228 |
| noise_bias | baseline_cem | 1 | 7.723 | 10.15 | 11.96 | 0.9267 | nan |
| noise_bias | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| noise_bias | state_error_only | 1 | 2.883 | 3.051 | 3.313 | 0.02667 | 0.0425 |
| noise_bias | parameter_error_only | 1 | 3.238 | 6.314 | 6.363 | 0.3033 | 0.6705 |
| noise_bias | fixed_nominal_planner_tracker | 0 | 3.278 | 6.064 | 6.856 | 0.9533 | 2.124 |
| noise_bias | full_adaptive_planner_tracker | 1 | 3.302 | 6.191 | 6.856 | 0.36 | 0.63 |
| stronger_noise | baseline_cem | 1 | 9.373 | 28.41 | 31.01 | 1.013 | nan |
| stronger_noise | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| stronger_noise | state_error_only | 1 | 3.185 | 3.947 | 4.213 | 0.24 | 0.0548 |
| stronger_noise | parameter_error_only | 1 | 4.186 | 33.76 | 34.8 | 0.4167 | 0.735 |
| stronger_noise | fixed_nominal_planner_tracker | 0 | 3.352 | 6.01 | 6.619 | 0.97 | 2.123 |
| stronger_noise | full_adaptive_planner_tracker | 1 | 4.723 | 25.67 | 40.24 | 0.57 | 0.6764 |
| mass_mismatch | baseline_cem | 0.6667 | 9.927 | 25.54 | 36.74 | 1.187 | nan |
| mass_mismatch | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| mass_mismatch | state_error_only | 1 | 2.88 | 2.961 | 3.179 | 0.02 | 0.03864 |
| mass_mismatch | parameter_error_only | 1 | 3.255 | 17.31 | 18 | 0.22 | 1.203 |
| mass_mismatch | fixed_nominal_planner_tracker | 0 | 4.168 | 16.19 | 17.49 | 3.72 | 2.536 |
| mass_mismatch | full_adaptive_planner_tracker | 1 | 3.312 | 16.72 | 17.49 | 0.88 | 0.9262 |
| parameter_mismatch_low_k | baseline_cem | 1 | 8.424 | 10.54 | 11.4 | 0.99 | nan |
| parameter_mismatch_low_k | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| parameter_mismatch_low_k | state_error_only | 1 | 2.88 | 2.961 | 3.179 | 0.02 | 0.03864 |
| parameter_mismatch_low_k | parameter_error_only | 1 | 3.367 | 6.343 | 6.393 | 0.21 | 0.6679 |
| parameter_mismatch_low_k | fixed_nominal_planner_tracker | 0 | 2.952 | 6.045 | 6.372 | 0.35 | 2.116 |
| parameter_mismatch_low_k | full_adaptive_planner_tracker | 1 | 3.055 | 6.125 | 6.372 | 0.26 | 0.5818 |
| parameter_mismatch_high_k | baseline_cem | 0.6667 | 7.315 | 10.05 | 11.88 | 0.9333 | nan |
| parameter_mismatch_high_k | oracle_planner_tracker | 1 | 2.88 | 2.96 | 3.179 | 0.02 | 0.03844 |
| parameter_mismatch_high_k | state_error_only | 1 | 2.88 | 2.961 | 3.179 | 0.02 | 0.03864 |
| parameter_mismatch_high_k | parameter_error_only | 1 | 3.29 | 6.233 | 6.338 | 0.18 | 0.652 |
| parameter_mismatch_high_k | fixed_nominal_planner_tracker | 0 | 3.45 | 5.997 | 6.338 | 1.49 | 2.136 |
| parameter_mismatch_high_k | full_adaptive_planner_tracker | 1 | 3.257 | 6.098 | 6.338 | 0.26 | 0.624 |

## Required Questions

1. **Are all controller modes correctly isolated?** Yes。oracle/state-error/parameter-error/fixed/full 的 state 与 parameter source 均由断言和逐次 solve 审计行验证；fixed 的控制参数在所有 planner/tracker 调用中保持 condition-specific nominal 值。

2. **Were Stage 9I fixed/adaptive results affected by reuse or wrong metric sources?** 未发现结果字典、controller state、轨迹或 primary true-state metric 的复用证据。Stage 9I 代码确有诊断覆盖不足（没有完整两因素分解，且 planned-alpha 汇总值重复写入时序行），但 raw alpha 本身由 true omega 差分得到。Stage 9I fixed/adaptive 相同 scalar max 共 29 组。

3. **Why were raw-alpha values identical?** Stage 9J 有 21 个 fixed/adaptive run 的 true-alpha 最大值相同，但完整 true-alpha 轨迹相同的 run 为 0 个。 相同的只是最大值时，原因是 fixed 与 adaptive 在首次 NLS 更新前使用相同 nominal 初始参数、相同估计状态和相同首个 planner/tracker action，因而共享同一个早期 alpha 峰；后续动作和 theta 轨迹会在 NLS 更新后分离。这不是完整数组复用。若完整 alpha 轨迹相同而 crossing 不同，在相同初态、dt 与 true-state crossing 定义下数学上不应发生；本次审计未见这种矛盾。

4. **Main adaptive–oracle alpha-gap source?** 按跨条件平均绝对 true-alpha-max 分解，最大项是 parameter error（state=0.1564, parameter=8.202, interaction=0.6676）。交互项不解释为严格因果。

5. **Does UKF-bias state estimation alone cause crossing failure?** initial_theta_offset 的 state_error_only crossing rate=1；据此回答见该成功率，而不是用容差判据替代 theta >= target。

6. **Do NLS parameters alone cause high true alpha?** initial_theta_offset parameter_error_only true alpha max=6.246，oracle 对应=2.996；跨条件参数贡献量见分解表。

7. **Are NLS estimates accurate at initial planning?** No。初次 planner 调用发生在 0 个 identifier samples 时；NLS estimate 等于 condition-specific nominal initialization。三个参数的平均 planner-time relative error=0.2715，episode 结束时=0.3251。

8. **Why does stronger noise amplify alpha?** 日志 artifact 被 true-state差分排除；stronger_noise 的绝对分解量 state=1.034, parameter=31.62, interaction=4.41，最大诊断项为 parameter。物理响应是 estimator/parameter 误差经真实闭环动力学作用后的结果。

9. **Does adaptive genuinely outperform fixed?** 24 个 primary runs 中 adaptive crossing=24/24，fixed=0/24；同时必须结合 summary 中 true-alpha 与 violation 指标判断，不能仅凭 crossing 宣称全面优越。

10. **Single Stage 9K intervention?** B. 跨条件 true alpha max 的平均绝对参数贡献最大（8.2，状态 0.156，交互 0.668）。 本任务未实施 Stage 9K。

## 实现与复现

- 新增脚本：`scripts/run_spring2d_stage9j_gap_decomposition.py`。
- 主命令：`conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py`。
- 诊断字段补全命令（复用已完成 baseline）：`conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py --reuse-baseline`。
- 结果：`stage9j_per_run.csv`、`stage9j_summary.csv`、`stage9j_mode_audit.csv` 与 `figs/`。
- 未修改 MPC/planner weights、rho_alpha、horizon、UKF covariance、NLS window/loss、constraints、target criterion、solver settings、rollout duration 或 Spring2D dynamics。
- 未加入 robustness/safety method，未启用 event-triggered replanning，未声称 formal safety/stability。
