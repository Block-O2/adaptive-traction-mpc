# Stage 9K Identifier Diagnosis and Robust Offline Ablation

## Decision

- Offline gate: **FAIL**. Selected identifier: `none`.
- Closed-loop Stage 9K-B: **not run**.
- Next technical direction: **improved identifier** — true-state replay 明显优于 UKF-input replay（0.0346 vs 0.236），下一步应是 estimator-aware errors-in-variables 或 joint state-parameter identifier。
- Robust covariance is a local pseudo-inverse diagnostic only; no formal confidence guarantee is claimed.

## Offline stress comparison

| method | parameter error | 1-step | multi-step | alpha RMSE | update TV | bound hits | gate |
|---|---:|---:|---:|---:|---:|---:|---|
| windowed_nls_current | 0.3376 | 0.03493 | 0.1866 | 2.413 | 426 | 0.02595 | - |
| windowed_nls_huber | 0.4738 | 0.03851 | 0.2169 | 2.887 | 475.7 | 0.03571 | - |
| windowed_nls_cauchy | 0.4742 | 0.03846 | 0.2165 | 2.881 | 474.1 | 0.03571 | - |

## Required Questions

1. **Current NLS diagnosis.** 主要问题是 UKF-input 导致的 errors-in-variables bias，而不是 optimizer 不收敛。平均参数误差 filtered=0.2362、true-state=0.03463。所有窗口 rank=3，但 regressor correlation p95=0.996、mean minimum singular value=0.009544、information condition-number p95=1111，说明局部 full rank 不等于可靠可辨识。low-excitation fraction=0.05467。

2. **Dominant parameter for alpha prediction.** 单参数替换为真值的 offline ablation 显示 `m` 带来最大平均 alpha-RMSE 降幅 1.583；各参数降幅={'m': 1.5833697871903154, 'k': 0.03387924262601885, 'b_r': 0.005641732751692959}。

3. **Robust loss in stronger-noise/mass-mismatch.** Huber checks={'parameter_error_improved': False, 'one_step_improved': False, 'multi_step_improved': False, 'alpha_improved': False, 'jitter_acceptable': True, 'bounds_acceptable': True, 'uncertainty_directional': False}；Cauchy checks={'parameter_error_improved': False, 'one_step_improved': False, 'multi_step_improved': False, 'alpha_improved': False, 'jitter_acceptable': True, 'bounds_acceptable': True, 'uncertainty_directional': False}。因此 robust loss does not materially improve all required metrics。

4. **Smoothing and jumps.** Current stress update TV=426，Huber=475.7，Cauchy=474.1。固定 alpha=0.5 并未降低总更新变化，且 robust variants 的参数误差更高；本次 smoothing 表现为额外 lag，而非有效抑制 harmful jumps。

5. **Identifiability.** 数值 rank 在所有 current 窗口为 3，宽松 local criterion fraction=1，但 p95 regressor correlation=0.996 且存在很小 singular values，因此 m/k/b_r 不能在所有窗口被可靠、独立地估计。轨迹并非普遍低激励（fraction=0.05467），主要限制是相关 regressor 加上 noisy estimated-state input。

6. **Uncertainty calibration.** 整体 90% empirical coverage：{'windowed_nls_current': 0.20365110757218716, 'windowed_nls_huber': 0.32424843427243055, 'windowed_nls_cauchy': 0.3177221049475617}；current 分参数 coverage={'m': 0.42143055429559717, 'k': 0.028951719576719576, 'b_r': 0.16057104884424472}。远低于 nominal 90%，尤其 k 明显过度自信，因此不能支持后续 uncertainty tightening。

7. **Accuracy after samples.** Current mean relative error：t0=0.2715，first valid=0.2256，fixed 2 s=0.2232。有小幅改善，但 2 s 相对 t0 只降低约 0.178，且远差于 true-state replay，未达到可靠 long-horizon planning 的证据标准。

8. **Delayed/confidence-gated planning.** 20% relative-std trigger 可用比例=1，平均在 t=0.2625 s 触发，但当时 mean relative error=0.2476，且 coverage 显示严重 overconfidence。故当前 confidence gate 不可信；固定 2 s 也没有足够大的误差改善来支持 primary delayed plan。

9. **Closed-loop alpha/crossing.** Offline gate 未通过，因此按规则未运行 closed-loop comparison，不能声称 robust identifier 降低了 true closed-loop alpha。

10. **Next step.** improved identifier。true-state replay 明显优于 UKF-input replay（0.0346 vs 0.236），下一步应是 estimator-aware errors-in-variables 或 joint state-parameter identifier。 本阶段未实现下一方向。

## Reproducibility

- Replay source: `results/stage9j_gap_decomposition/stage9j_replay.csv`; all identifiers consume identical UKF-state/control sequences.
- Optional true-state replay is diagnostic only and never changes recorded actions or states.
- Huber f_scale=1.345; Cauchy f_scale=2.3849; both use per-window frozen MAD scale and fixed parameter smoothing alpha=0.5. No sweep was run.
- Optional augmented-parameter UKF was not implemented because adding a coupled 11-state process/measurement model was not straightforward enough to justify blocking the required NLS comparison.
- Confidence trigger diagnostic: max relative parameter std <= 0.2; fixed later diagnostic time=2.0 s.
- Low-excitation thresholds: {'F_tan_std': 0.25, 'F_rad_std': 0.02, 'omega_std': 0.02, 'r_dot_std': 0.002}.
- No dynamics, UKF, planner/tracker, MPC weight, rho_alpha, horizon, constraint, solver, crossing, or schedule changes were made.
