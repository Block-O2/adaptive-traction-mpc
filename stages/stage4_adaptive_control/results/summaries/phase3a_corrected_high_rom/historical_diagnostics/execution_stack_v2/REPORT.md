# Phase 3A 执行栈力分解审计

证据类别：**offline deterministic reconstruction**。只读取冻结 Rigid evidence，并重放冻结 measurement preprocessing；没有运行 trajectory、MPC 或 plant dynamics。

## 事件总览

| case | t (s) | Safety Filter | Human total | position | velocity | nominal executable | filter correction | filtered candidate | physical |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 40/80 | 11.935 | FILTER_INFEASIBLE | 143.23 | 26.72 | 83.14 | 213.38 | 0.00 | 213.38 | 195.74 |
| 120/120 | 10.410 | FILTER_INFEASIBLE | 119.91 | 33.70 | 135.49 | 237.79 | 0.00 | 237.79 | 208.87 |
| 90/120 | 22.185 | SAFE_UNCHANGED | 133.10 | 27.30 | 65.48 | 199.79 | 0.00 | 199.79 | 157.99 |

力均在共同 world frame。表中分量 norm 不可按标量相加；逐分量闭合见 CSV/NPZ。投影方向定义为各事件 final filtered candidate 的平移力方向。

## 逐阶段表

### Rigid 40/80

| stage | incremental [Fx,Fy,Fz,Mx,My,Mz] | |delta F| | cumulative |F| | projection |
|---|---|---:|---:|---:|
| static_human | -87.01, -0.03, +58.93, +0.00, +2.49, +0.00 | 105.09 | 105.09 | +87.71 |
| reference_dynamics | -0.02, -0.00, +0.01, +0.00, +0.00, +0.00 | 0.03 | 105.12 | +0.02 |
| human_tracking_feedback | -23.41, -0.02, +32.25, -0.00, -0.06, -0.00 | 39.85 | 143.23 | +38.75 |
| registered_human_total | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 143.23 | +0.00 |
| allocator_objective_offset_vs_min_force | -26.40, +0.01, -19.96, -0.00, -11.58, -0.01 | 33.10 | 143.23 | -8.36 |
| robot_position_feedback | +6.96, +0.03, +25.80, +0.00, +0.00, +0.00 | 26.72 | 156.19 | +21.18 |
| robot_velocity_feedback | +21.93, -0.01, +80.19, +0.00, +0.00, +0.00 | 83.14 | 213.38 | +65.72 |
| other_low_level_orientation_and_angular_velocity | +0.00, +0.00, +0.00, +0.41, -18.34, +0.36 | 0.00 | 213.38 | +0.00 |
| nominal_executable | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 213.38 | +0.00 |
| safety_filter_correction | -0.00, -0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 213.38 | +0.00 |
| final_filtered_candidate | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 213.38 | +0.00 |
| causal_prior_applied_command | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 200.00 | +0.00 |
| physical_minus_causal_prior_command | -78.03, +8.19, -123.63, +10.23, -5.95, -8.44 | 146.42 | 195.74 | -84.42 |
### Rigid 120/120

| stage | incremental [Fx,Fy,Fz,Mx,My,Mz] | |delta F| | cumulative |F| | projection |
|---|---|---:|---:|---:|
| static_human | -81.61, +0.00, +0.65, +0.00, +2.00, +0.00 | 81.61 | 81.61 | +57.27 |
| reference_dynamics | +0.62, +0.00, -0.15, -0.00, -0.00, -0.00 | 0.64 | 80.99 | -0.54 |
| human_tracking_feedback | -38.60, -0.00, +8.18, +0.00, +0.40, +0.00 | 39.46 | 119.91 | +32.74 |
| registered_human_total | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 119.91 | +0.00 |
| allocator_objective_offset_vs_min_force | -10.86, +0.02, -30.30, -0.00, -11.14, -0.01 | 32.19 | 119.91 | -14.20 |
| robot_position_feedback | -15.05, -0.83, +30.14, +0.00, +0.00, +0.00 | 33.70 | 140.13 | +32.12 |
| robot_velocity_feedback | -30.84, +0.08, +131.93, +0.00, +0.00, +0.00 | 135.49 | 237.79 | +116.20 |
| other_low_level_orientation_and_angular_velocity | +0.00, +0.00, +0.00, -0.11, -30.96, +0.27 | 0.00 | 237.79 | +0.00 |
| nominal_executable | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 237.79 | +0.00 |
| safety_filter_correction | -0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 237.79 | +0.00 |
| final_filtered_candidate | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 237.79 | +0.00 |
| causal_prior_applied_command | +0.00, +0.00, +0.00, +0.00, +0.00, +0.00 | 0.00 | 200.00 | +0.00 |
| physical_minus_causal_prior_command | -28.31, +57.66, -184.37, +21.49, -4.79, -4.32 | 195.24 | 208.87 | -112.87 |

`allocator_objective_offset_vs_min_force` 是注册 1:1 allocator 相对同一 Human torque 下 minimum-translational-force 解的 torque-preserving nullspace 偏移，属于反事实诊断，不是运行时新增模块。Safety Filter correction 是之后的独立 nullspace 投影。`physical_minus_causal_prior_command` 使用物理采样前最近一次实际施加的 ZOH command；同周期被拒绝的候选命令不被误当作 plant input。

## 状态与误差

- 40/80：位置误差 norm **8.91 mm**，线速度误差 norm **0.594 m/s**；q error **[-0.48222177  0.63262353] deg**，dq error **[-32.03076306  44.43184034] deg/s**。
- 120/120：位置误差 norm **11.23 mm**，线速度误差 norm **0.968 m/s**；q error **[-0.7587903   0.51132754] deg**，dq error **[-37.60616124  97.4726058 ] deg/s**。
- 90/120 对照：选择保存记录中 nominal executable force 最大的 SAFE_UNCHANGED 时刻 **22.185 s**，其 nominal force 为 **199.79 N**。
- 三个事件的 physical sample 均发生在当周期 command 计算/施加之前，因此 execution residual 对齐到 **5.0 ms / 5.0 ms / 5.0 ms** 前实际施加的命令（分别对应 40/80、120/120、90/120）。
- 事件距最近一次 high-level MPC solve 分别为 **15.0 ms / 10.0 ms / 5.0 ms**；Safety Filter 与 supervisor transition 均在所列事件的 low-level 5 ms 边界执行。

## DIRECTLY DERIVED

- 40/80 的 Human allocator force 是 **143.23 N**；position 与 velocity 增量分别为 **26.72 N** 和 **83.14 N**，组合后 nominal executable 为 **213.38 N**。Safety Filter 已无可行 nullspace 修正，rejected candidate 为 **213.38 N**。
- 120/120 的 Human allocator force是 **119.91 N**；position 与 velocity 增量分别为 **33.70 N** 和 **135.49 N**，nominal executable 为 **237.79 N**。该事件同样没有可行 Safety Filter 修正。
- 两个 failure event 的平移 feedback 未触发 200 N component clipping；`other low-level` 对平移力严格为零，只贡献 orientation/angular-velocity moment。robot bias 与 posture-nullspace 项只进入 joint-torque command，不改变所报告的 Cartesian wrench。
- 40/80 在 11.935 s 由 `TRACK` 进入 `BRAKE`，同周期 rejected TRACK candidate 没有施加，而是施加 BRAKE command；120/120 在 10.410 s 由 `TRACK` 进入 `BRAKE`，BRAKE candidate 也不可行并终止，当周期没有新命令。物理力只能与上一周期实际命令作因果比较。

## SUPPORTED BY CURRENT EVIDENCE

- 两个事件中，从约 120–143 N Human demand 到 200 N 以上 executable command 的主导额外项是 **robot velocity feedback**，position feedback 次之。注册 allocator 的 1:1 objective offset 和 Safety Filter correction 都不是主要增量。
- 40/80 与 120/120 共享同一直接执行机制：线速度 tracking error 通过冻结 140 Ns/m 增益形成大的 +z 或组合方向 force，叠加 Human allocator wrench后越过 200 N。两者并非完全相同状态，但 mechanism family 一致。
- 20–50 ms 窗口内 velocity term 快速增长，而 posture-only static force 和 reference-dynamic increment变化很小，支持此前的 history/velocity dependence；这仍是关联证据，不把根因归给某个 estimator 或 MPC cost。
- 90/120 在高 nominal-force 时仍是 SAFE_UNCHANGED，说明 200 N gate 与路径相关 feedback vector 的方向叠加共同决定 crossing；更大 ROM 本身不足以预测 BRAKE。
- 所见增量来自已注册 executable-command law 的 robot Cartesian velocity feedback，属于 low-level execution-layer 与 200 N engineering budget 的交互；当前证据不足以把它定性为 controller design defect 或数值异常。

## UNRESOLVED

- 保存 evidence 不能把 velocity error进一步因果分成 robot inertia、tracking lag、measurement preprocessing、MPC action history或某一个 joint 的来源。
- 尚不能判定冻结的 140 Ns/m velocity feedback 本身设计不当；这需要先核对 twist target/measurement 语义和方向，再用另行预注册的敏感性实验判断。
- physical wrench 与 command 的瞬态差不能仅靠这些 algebraic command terms解释；它还包含 rigid constraint dynamics、robot/Human acceleration和离散执行响应。
- 90/120 窗口有 3 个 high-level 更新边界样本无法用保存的降采样 action/reference 通道把 command 分量唯一重建（最大 component mismatch 22.14 N/Nm）；图中将这些点留空。所选 22.185 s 对照事件的 component mismatch 仅 0.052 N/Nm。
- 本审计不能说明放宽 force budget 后的完整 120/120 轨迹结果，也不建立 hardware 或 clinical limit。

## 建议

建议 **investigate one specific execution term：robot Cartesian velocity feedback**。先保持 controller 和 200 N target 不变，对现有保存窗口继续检查 target/measurement twist、140 Ns/m 映射及其与 position term/allocator vector 的方向关系。当前证据不支持立即改 gain；若该检查确认实现与预期一致，再预注册 relaxed-force-budget sensitivity，用于区分工程 gate interaction 与底层 plant/controller capability。
