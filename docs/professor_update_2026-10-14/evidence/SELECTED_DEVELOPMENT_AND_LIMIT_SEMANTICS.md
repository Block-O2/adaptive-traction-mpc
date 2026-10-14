# 冻结开发选择及原限值含义独立审计

只读实际原数据/源码，无physics、训练或physics修改。完整结构化证据：`SELECTED_DEVELOPMENT_INDEPENDENT_GATE.json`；冻结原字节观察副本：`FROZEN_SELECTION_OBSERVED.json`。独立脚本没有导入runner/plant/optimizer。

## 独立规则与积分核验

独立从冻结 `MOTION_ACCEPTANCE_PROTOCOL.json` 重建全部主比较规则，逐一核原native raw速度/加速度/指定jerk，excursion、剂量、phase/endpoints、完整及各phase时长、force/moment峰、moment积分与tracking；失败清单逐项与冻结选择一致。0.25ms原true dq重求acceleration/jerk与存档精确一致；完整TASK原left force/moment积分与原metrics误差均<1e-8。

|角色|完整TASK J_F N·s|相对B下降|原mode-aware A物理任务|冻结B运动比较|LEGACY_R2_MATCHED|
|---|---:|---:|---|---|---|
|B `development_repair2_B0_original`|1438.6134984675|0|PASS|PASS|PASS|
|best `development_repair2_quality_NATIVE_SCALAR_18_063`|1400.6972211531|2.6356125085%|PASS|PASS|PASS|
|secondary `development_repair2_quality_NATIVE_SCALAR_18_056`|1405.3674179231|2.3109807172%|PASS|PASS|PASS|
|diagnostic `development_repair2_repair_C2_pair_1_2_116`|1196.6854448690|16.8167512578%|PASS|FAIL|FAIL|

强低力失败项：velocity max/p95/RMS；acceleration p95/RMS；jerk RMS；RETURN duration；excursion；cumulative dose；完整task duration；moment integral；tracking。其完整OUT/HOLD/RETURN为9.005/1.020/9.155s，总19.18s；比B返回与总时长多0.15s，违反冻结±0.1s和原严格MATCHED R2。原物理任务则允许phase timeout10s，且完成真实goal dwell/return，故A PASS与这些FAIL不矛盾。此方案保留为物理研究负结果，不能称合格teacher、治疗等效或临床舒适。

## 45/75与300/600不是单一采样定义

这些数值同时出现在原task/reference和原物理评分中，不能改写成“仅参考阈值”，也不能称已经证明每个0.25ms native瞬时状态均受同样意义的硬保护。

1. 原task spec读入45/75°/s及300/600°/s²。`task.py:420–455`的task_limit_violation对传入q/dq/ddq检查；`runtime_coordination_residual_v2.py:2670–2678`传入deployable估计state和有效窗口加速度进行TASK状态转换。不是将真native dq导数直接当controller输入。
2. 原scheduler依据同task值约束参考。当前options `reference_pacing=true`、velocity fraction=.5、acceleration fraction=.25；runtime `:2382–2385`设置，`:3839–3843`报告作用范围为TASK及active recovery参考。`human_waypoint_scheduler.py:502–518`检查quintic连续最大速度、连续/causal reference加速度。对应参考约22.5/37.5°/s及75/150°/s²；该参考约束不是实际Human速度/加速度相等保证。
3. 在线人体加速度authority是**完整causal20ms deployable dq_hat history**。`split_acceleration_monitor.py:18–19`规定Human20ms、FAST5ms；`:134–149`记录authority来源且truth_used_online=false；`:179–225`只在有效完整20ms历史上判300/600限值；`:399–418`用窗口dq差求加速度。runtime `:2617`执行该authority。
4. 原A评分的速度是**已存TASK采样true dq**，加速度是trace里有效的**窗口monitor加速度**。`scripts/high_rom_v1/summarize_phase_b.py:41–48`明确这两个来源；原 `docs/high_rom_v1/PHASE_B_MATRIX.json:219–226`的阈值为45/75、300/600。`evaluate_execution_mode.py:28–57`保留common physical判据并另分scientific与host年龄资格。
5. B-relative真实运动审计另用0.25ms native true dq梯度，不删endpoint；速度/acceleration raw主统计及指定jerk、剂量等按冻结研究比较。两套采样含义须并列报告，不互相替代，不当临床标准。

## selected实际数值

|角色|raw native最大速度Hip/Knee °/s|raw native最大加速度Hip/Knee °/s²|原A窗口加速度Hip/Knee °/s²|
|---|---|---|---|
|B|23.784934 / 26.048980|85.115055 / 112.526790|84.650142 / 111.249276|
|best|23.530733 / 23.985586|77.563960 / 116.296879|77.027575 / 115.107661|
|secondary|23.576526 / 23.002710|65.181010 / 115.917752|63.126778 / 114.615952|
|strong diagnostic|24.777196 / 37.821920|64.167628 / 120.448144|64.006489 / 113.483592|

强代表这些raw峰值本身也没有超45/75或300/600，motion FAIL主要是在**相对B非劣与剂量/时间/力矩/跟踪**规则上。比如knee max速度37.822相比B26.049明显增大，而仍低于绝对75。不能说motion FAIL就是原绝对人体速度/加速度安全失败，更不能推导临床不安全。反过来A PASS也不证明所有运动质量变好。

原raw scorer中的host plan_age为FAIL在scientific模式是单独的host counterfactual字段；fork搜索会继承父host epoch及离线等待时间。原mode-aware evaluator按scientific request版本/年龄、实际activation certificate、真实ownership等评价，不把该host计时当LEVEL3通过。这解释原raw scorer pass=false与本报告A physical PASS的分轴，不是修改原阈值。

## 冻结身份

freeze unix：1791926199.3476582；selection SHA256：`e82de39da5e8cc054f763edc640c631019636ef26a47e9d38669926bb35171e6`。Auditor观察副本已保存完整原字节与三个candidate科学字段。新包开发DONE已COMPLETE；后续repeat/V不能改变这些字段或改选secondary替primary。

实际pin unix：1791926357.6821358；CODE_MANIFEST pin SHA256：`673faeca5afa5c1f9a6a448acdb50eeec019403454f2d15e272bb30bb3d3f195`；RUN_PLAN pin SHA256：`e6785f399fc8d4a388cffbb60737558c45e594d7352e507f2510d62bfe88fda7`。最终审计再核字节保持、实际首test START及固定四条件分母。当前PASS只表示开发classification/积分独立核验，不是held-out成功或最终退出证明。
