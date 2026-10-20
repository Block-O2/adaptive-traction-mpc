# 真实人体运动负担审计

结论 **SUPPORTED**：在这八组已完成的配对仿真中，M2 的真实 knee 运动速度与加速度负担相对 B 上升。并非所有关节、所有 jerk 指标都恶化；可接受性 **UNRESOLVED**，临床舒适度 **NOT_EVALUABLE**。接触 moment integral 不是 momentum，本结论来自真实 dq 的重新计算。

## 数据、信号与方法

复用两包各四组完整 B/M2 物理 trace，共16条轨迹、1,219,316个 TASK native 节点。无新增物理 rollout 或 host run。每条 native qpos/qvel 列通过共同物理时间节点与 `evaluation_only_human_state_rad_rad_s` 对应，映射误差小于1e-8 rad/rad·s⁻¹。每条审计保存列索引、节点数、间隔范围及原文件SHA256。原生步长约0.25ms。使用原 `summary.task.phase_transitions` 物理时间分 OUTBOUND/HOLD/RETURN；导数跨交接计算，不在阶段边界重置。

主要速度取真实 native dq；加速度=`numpy.gradient(dq,time,edge_order=2)`，jerk=同法再次微分。未用 q 低频差分代替真实 dq，也未把 trace 中原有因果加速度估计字段当作真值。原始峰值保留。敏感性：dq 经3阶 Savitzky–Golay、5与21节点窗口（名义1.25/5.25ms）后同法微分。端点一侧导数保留并标识 `within_1ms_edge`；没有为得到改善而删除峰值。均匀 native 节点分位数接近时间分布；保存实际时间供复查。重复 sensor trace 时间节点保留最后边界值，原文件未改，数量与最大缺口在各 quality 字段。

分别报告真实人体、参考 q/dq/ddq、机器人 torque/人体 generalized action、接触 force/moment；参考 jerk 和 force-vector/magnitude rate 是约5ms trace 导数，其间未记录的高速峰值 **NOT_EVALUABLE**。可信真 shank 代表点坐标/几何合同未恢复，shank速度/加速度 **NOT_EVALUABLE**。已有物理 cuff 速度与加速度单独标为 cuff，不能替代人体 shank。

每条 run JSON 给出 max、p95、p99、RMS、mean-abs、三个阶段；force peak、快速变化、moment peak/integral、true-reference RMS/max、clearance与原生完整 safety audit。积分权威口径为原 native scorer；去重后的 sampled interval sum 单独保留，不替代 native J_F。原 scorer保留未提供门限的条件结果，不猜造 ROM/加速度临床阈值。

## 配对完整任务结果

Δ=M2−B；速度 deg/s，加速度 deg/s²，jerk deg/s³，角幅 deg。下表 knee 列来自未滤波 native 真值。

| B运行 | ΔJ_F N·s | B max速度 | M2 max速度 | B p95加速度 | M2 p95加速度 | Δp95 jerk | Δ真实knee角幅 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 008_nominal_pair1_B | -76.6534 | 22.2877 | 37.4191 | 35.4751 | 77.9074 | 667.5981 | 2.8336 |
| 011_nominal_pair2_B | -95.2344 | 22.3118 | 38.2769 | 34.8272 | 73.7223 | 699.1484 | 1.7171 |
| 012_deviation_pair1_B | -117.7894 | 32.0482 | 38.2010 | 61.0388 | 85.0671 | 527.9969 | 1.2632 |
| 015_deviation_pair2_B | -88.2381 | 21.5826 | 38.3277 | 43.1964 | 87.6258 | 338.6777 | 1.3847 |
| 001_deviation_P1_seed1_B | -81.5663 | 32.0581 | 38.4155 | 73.6113 | 86.2527 | 263.3730 | 2.0788 |
| 004_deviation_P1_seed2_B | -130.0506 | 31.9718 | 38.0000 | 66.4106 | 84.0457 | 660.9627 | 1.4821 |
| 006_deviation_P2_seed1_B | -91.4359 | 21.0593 | 38.4571 | 65.6680 | 81.3713 | 487.0827 | 1.1090 |
| 007_deviation_P2_seed2_B | -96.9530 | 21.2113 | 38.1851 | 55.3476 | 85.2758 | -454.8304 | 1.3261 |


8/8 knee max速度、p95速度、RMS速度、p95加速度和RMS加速度上升；knee max加速度7/8上升。Knee p95 jerk 7/8上升，而 jerk max与p99有混合变化。Hip RMS速度8/8略下降，但加速度p95与RMS8/8上升。不能概括为每个指标都恶化，也不能用下降的单个 jerk peak 宣称整体平顺性改善。

任务目标、原生物理模型、安全规则、waypoints保持原配对条件。完整任务时长差范围约−0.005至+0.065s；真实 knee excursion 增加约1.109至2.834°，同时 true-reference knee RMS代价存在。故本比较是相同任务下的真实行为差异，不能声称实际运动幅度完全相同。没有缩短HOLD、裁剪RETURN或通过幅度归一化掩盖代价。

## 阶段分布

下表为 knee p95差值；完整 hip/knee p99、max、RMS见逐run JSON。

| B运行 | 阶段 | Δp95速度 | Δp95加速度 | Δp95 jerk |
| --- | --- | --- | --- | --- |
| 008_nominal_pair1_B | OUTBOUND | 4.5666 | 52.3793 | 554.2669 |
| 008_nominal_pair1_B | HOLD | 0.5781 | 21.1792 | 236.0433 |
| 008_nominal_pair1_B | RETURN | 10.6113 | 38.7841 | 854.1713 |
| 011_nominal_pair2_B | OUTBOUND | 10.0166 | 31.7901 | 393.4338 |
| 011_nominal_pair2_B | HOLD | 0.0052 | 0.0607 | 0.5613 |
| 011_nominal_pair2_B | RETURN | 15.4463 | 41.9545 | 1030.7432 |
| 012_deviation_pair1_B | OUTBOUND | 1.0449 | -9.7560 | 254.6062 |
| 012_deviation_pair1_B | HOLD | -0.0024 | -0.0068 | -0.6568 |
| 012_deviation_pair1_B | RETURN | 12.9519 | 52.0745 | 747.0473 |
| 015_deviation_pair2_B | OUTBOUND | 9.8426 | 38.4447 | 233.2382 |
| 015_deviation_pair2_B | HOLD | 0.0974 | 0.8070 | 12.2943 |
| 015_deviation_pair2_B | RETURN | 15.9423 | 45.1762 | 453.8969 |
| 001_deviation_P1_seed1_B | OUTBOUND | 0.8531 | 6.9094 | -50.4327 |
| 001_deviation_P1_seed1_B | HOLD | 0.4752 | 4.5327 | 88.6302 |
| 001_deviation_P1_seed1_B | RETURN | 15.6913 | 43.0652 | 590.7193 |
| 004_deviation_P1_seed2_B | OUTBOUND | 8.9461 | -5.5982 | 430.5895 |
| 004_deviation_P1_seed2_B | HOLD | 3.4348 | 21.9036 | 400.4934 |
| 004_deviation_P1_seed2_B | RETURN | 13.9510 | 51.8039 | 894.5078 |
| 006_deviation_P2_seed1_B | OUTBOUND | 0.0097 | -1.5883 | 143.4139 |
| 006_deviation_P2_seed1_B | HOLD | 0.0082 | 0.0218 | 8.5602 |
| 006_deviation_P2_seed1_B | RETURN | 15.7030 | 17.3110 | 866.7801 |
| 007_deviation_P2_seed2_B | OUTBOUND | 5.2418 | 39.2969 | -342.2554 |
| 007_deviation_P2_seed2_B | HOLD | 2.4146 | 26.5146 | 947.5459 |
| 007_deviation_P2_seed2_B | RETURN | 11.2346 | 18.6438 | -667.2807 |


## 滤波敏感性

| B运行 | raw Δknee p95加速度 | 5节点 Δ | 21节点 Δ |
| --- | --- | --- | --- |
| 008_nominal_pair1_B | 42.4323 | 42.4270 | 42.3789 |
| 011_nominal_pair2_B | 38.8951 | 38.8897 | 38.9090 |
| 012_deviation_pair1_B | 24.0283 | 24.0433 | 24.0548 |
| 015_deviation_pair2_B | 44.4294 | 44.4294 | 44.4176 |
| 001_deviation_P1_seed1_B | 12.6414 | 12.6396 | 12.6172 |
| 004_deviation_P1_seed2_B | 17.6351 | 17.6396 | 17.6474 |
| 006_deviation_P2_seed1_B | 15.7033 | 15.6963 | 15.7447 |
| 007_deviation_P2_seed2_B | 29.9282 | 29.9260 | 29.9570 |


Knee速度/加速度主要分布的恶化方向对轻度滤波稳定。Jerk峰值更受离散微分及窗口影响，raw与两个过滤版本均保留。该敏感性是测量分析，未进入模型调参或控制。

## 短时事件与计划交接

每条运行的原始jerk最强事件：

| 运行 | joint 0hip/1knee | 物理秒 | 阶段 | signed jerk | 端点1ms内 |
| --- | --- | --- | --- | --- | --- |
| 008_nominal_pair1_B | 1 | 26.5555 | RETURN | 24197.7152 | False |
| 009_nominal_pair1_M2 | 1 | 17.8905 | OUTBOUND | -20233.7069 | False |
| 011_nominal_pair2_B | 1 | 13.1952 | OUTBOUND | -17786.0103 | False |
| 010_nominal_pair2_M2 | 1 | 16.9807 | OUTBOUND | 19152.9921 | False |
| 012_deviation_pair1_B | 1 | 21.9478 | RETURN | 21308.4883 | False |
| 013_deviation_pair1_M2 | 1 | 13.5862 | OUTBOUND | -20432.0710 | False |
| 015_deviation_pair2_B | 1 | 17.9610 | OUTBOUND | -24923.4270 | False |
| 014_deviation_pair2_M2 | 1 | 17.3517 | OUTBOUND | -24610.6971 | False |
| 001_deviation_P1_seed1_B | 1 | 17.8452 | OUTBOUND | -23042.0068 | False |
| 002_deviation_P1_seed1_M2 | 1 | 23.3950 | RETURN | 29777.9530 | False |
| 004_deviation_P1_seed2_B | 1 | 16.7252 | OUTBOUND | -27129.8848 | False |
| 003_deviation_P1_seed2_M2 | 1 | 17.1155 | OUTBOUND | -23509.0078 | False |
| 006_deviation_P2_seed1_B | 1 | 17.7600 | OUTBOUND | -20690.3008 | False |
| 005_deviation_P2_seed1_M2 | 1 | 13.7652 | OUTBOUND | -21615.0729 | False |
| 007_deviation_P2_seed2_B | 1 | 25.8510 | RETURN | 30048.2878 | False |
| 008_deviation_P2_seed2_M2 | 1 | 21.5695 | RETURN | -49781.3369 | False |


逐run `windows` 保存阶段启停/反向±100ms、实际非零计划每个 receipt 起止±50ms，以及速度符号反转±20ms。反转事件需附近20ms内速度达到0.5deg/s，仅用于避免零速数值抖动形成无限事件，**不是舒适度或安全门限**。窗口包含真实运动、force及rate、moment、tracking与clearance，不仅看selected plan。每个 signal 另存每关节五个最强节点；未自动删去异常。

## 目标优先级判断

第0层：旧原生物理检查通过；实际幅度存在上述差异，临床含义不可推定。第1层：真实 knee 速度与加速度代价得到支持。第2层：力积分收益仍成立，最新四组−6.828%、RETURN贡献85.578%、平均力项99.962%的历史结论未被本包改写。第3层：moment、tracking、clearance代价仍保留。

因此现有M2不能凭力下降被认定为满足新优先级。需预先约定运动负担接受规则及公平幅度口径，并检验低力候选是否可同时降低这些真实运动指标。不能从“原native安全PASS”自动推出“新运动目标已满足”。

来源：两包 REPORT、PAIRED_RESULTS/PAIRED_HOST_RESULTS、EXECUTION_LINEAGE、每条native与sensor trace、原AXES；具体文件/hash在 `motion_series/*_AUDIT.json`。初始派生summary与后续物理phase-clock口径说明保留于 `derived_history`。
