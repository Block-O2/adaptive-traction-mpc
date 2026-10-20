# iHEAR Lab — Autonomous Multi-Track Control Research v1

**结论：五个Track均完成审查，A与B完成新真实MuJoCo配对实验；没有获得修复W1的完整合格新候选。** 两个减速前速度干预确实改变Human运动，却只小幅减少终末下冲，仍未通过原excursion门。已转入R0背景诊断，未用A失败阻止其他方向。没有训练Q-learning或提升正式基线。

## 1. 五个Track分别发现什么

|Track|主要证据与结论|本轮处理|
|---|---|---|
|A 终末响应|ER真实下冲1.275378°，大部分在参考停稳前形成；停稳后仍走0.105483°。因果估计能看到偏差。×0.90/×0.80改进很小且force增加|两个候选完整physics后停止该因素|
|B 状态可靠性|绝对运动与匹配B分母共同决定资格；通过状态也可有更大的绝对下冲。R0冻结ER结果为PASS|新增B/T/D/ER已暴露R0配对；保留适用域边界|
|C 平顺性|新候选降低完整TV_v/jerk，却增加TV_a并未消除excursion失败；旧微小Waypoint搜索收益低|raw/SG及局部/完整分析，不重开密集shape搜索|
|D 力矩/跟踪|ER降force约2.354%，moment仍高于B约5.792%；更低force不能代表全部交互负担更低|完整force/moment/tracking/clearance配对审计|
|E 执行/学习|原证书/准入/receipt可核验；host/R2等缺口仍在。在线因果特征与未来真值标签必须分开|交付学习schema，未训练/未改实时系统|

## 2. 哪些已有问题得到真实改善

本轮复现了历史ER对W1 v95/a95/amax/jerk RMS的修复。新增速度干预进一步小幅降低真实下冲、完整velocity TV与jerk RMS，幅度见下表。这些是PHYSICAL_LEVEL1的有界实际运动变化，不是完整合格或临床效果。

|完整运行|J_F N·s|对本组B降力%|膝真实下冲°|膝excursion−B°|原motion|
|---|---:|---:|---:|---:|---|
|Adev_B|1436.456498145|0.000000|0.577911072|+0.000000000|PASS|
|Adev_T|1403.456709761|2.297305|1.261666035|+0.534884018|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/p95_abs, excursion|
|Adev_D|1402.234611439|2.382382|1.270504839|+0.543722823|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, jerk_deg_s3/rms, excursion|
|Adev_ER|1402.644192729|2.353869|1.275378484|+0.548596467|FAIL: excursion|
|Adev_AV090|1403.094680174|2.322508|1.272224862|+0.545442845|FAIL: excursion|
|Adev_AV080|1403.541584101|2.291397|1.269033740|+0.542251724|FAIL: excursion|

|候选|Δ真实膝下冲°|ΔJ_F对ER N·s|完整TV_v Δ%|完整TV_a Δ%|完整jerk RMS Δ%|
|---|---:|---:|---:|---:|---:|
|Adev_AV090|-0.003153622|+0.450487445|-0.638868|+0.031001|-0.705427|
|Adev_AV080|-0.006344743|+0.897391372|-0.890976|+0.505604|-1.248944|

## 3. 哪些问题未解决，为什么

两个新候选仍失败于膝excursion。×0.80差+0.542252°，超0.5°门约0.042252°；减速前pass速度改变并未等比例改变最终停止误差。参考停稳前已有大部分误差，停稳后髋运动仍与膝响应交织，不能用“惯性”或“allocator”单词代替未完成的机制识别。广泛状态可靠性、host实时、跨Human/硬件/临床均未解决。

## 4. 哪些干预实际改变Human

AV090/AV080都沿原证书与native链真实应用，最终q/dq/torque receipt与新曲线相符；new splice前native历史精确一致，之后真实q/dq差异可观测。R0的冻结ER也通过真实执行比较。参数意图、数学曲线、issued reference、actual Human和完整资格分别保存。细节见audit/INTERVENTION_EXECUTION_AUDIT.json与derived/CAUSAL_RESPONSE_AUDIT.json。

## 5. 是否获得新的完整合格候选

没有。AV090/AV080原motion失败，不能进入合格force排名。R0的ER是原已冻结方法在已暴露背景的诊断，不能覆盖其W1失败或重命名为广泛新基线。

## 6. 是否完成重复和未见prefix验证

新候选没有开发合格，因此按预注册分支不启动候选重复或未见W2。B/T/D/ER跨包原轨迹复现是对照一致性证据，不是新候选重复，更不是新状态。W2只注册、未消费；R0是已暴露且共享OUTBOUND历史的背景控制。

## 7. 降force是否有moment/tracking代价

有。W1 ER moment integral由B的101.253695升至107.118048 Nm·s；tracking RMS hip/knee=0.456454/0.526051°。各门仍按原阈值评价，不将允许范围说成无代价。新AV候选相对ER的force还上升。完整指标见Track D与EXPERIMENT_RESULTS.json。

## 8. 当前状态适应性瓶颈

动作前估计状态、reference q/dq与历史/剩余预算未被slot索引充分表达；去程全程极值与累积分布又影响最终相对门。W1/O0几乎相同的RETURN可以有不同p95资格，R0更大绝对下冲仍可相对通过。既不能只用最终FAIL学准入，也不能用未来matched-B统计作在线输入。

|完整运行|J_F N·s|对本组B降力%|膝真实下冲°|膝excursion−B°|原motion|
|---|---:|---:|---:|---:|---|
|Bmap_B|1432.655804346|0.000000|0.819686067|+0.000000000|PASS|
|Bmap_T|1400.293954479|2.258871|1.293504546|+0.324947534|PASS|
|Bmap_D|1399.026179051|2.347363|1.329948278|+0.361391266|PASS|
|Bmap_ER|1399.241294833|2.332347|1.326647973|+0.358090961|PASS|

## 9. 未来学习器值得学什么

优先有界、可重新认证的时长与内部pass-velocity动作，并保留必要空间协调。学动作的状态适用范围及执行/失败反馈，不学直接torque或越过准入。所有动作必须绑定实际activation/receipt/native ownership；失败低force、partial、被拒提议不能当成功样本。完整schema已交付，本轮无训练。

## 10. 下一轮投入方向

只推荐一个优先方向：**髋终末时间形状与已停止膝参考之间的耦合响应**。以冻结ER为父，另立协议，只改变原合法RETURN5髋终末时序、保留膝参考、所有原门与完整任务，首先证伪“膝后续下冲与髋终末运动无关”。停止继续缩小R3膝速度或重做微小Waypoint扫描。获得完整合格候选后再重复并使用未见prefix，不能跳过这一步。

## 证据、尝试与保护

T0北京时间2026-10-18 15:55:26；6小时硬截止21:55:26；21:10:26后无新physics，本包实际还额外预留900s完成在途运行。物理START/END=12/12，总上限60，全部串行，包含父运行与fork。A两个候选已到停止点；B背景结果、C/D/E审计提供清晰结论后提前STOP，不为了目标4–6小时耗尽时间/预算。
全任务与各phase时长保持；独立算术复核为同一agent分离实现，不冒称第二agent或人类审计。最终完整积分、native导数、dose/ROM、receipt/torque/step归属、Git逻辑状态、122233历史文件metadata/SHA、冻结manifest及owned退出，以PACKAGE_VERIFICATION.json为准。审计PASS不等于科学候选PASS。
没有Git commit/push/merge/reset/stash/clean/branch切换、历史覆盖、plant/Human/robot/cuff/contact/gain/ROM/torque/task/HOLD/阈值改动。唯一新增控制是隔离R3通过速度wrapper；其余新工作为实验编排、诊断和报告。分析曾因TASK-only数组长度停止，已显式对齐并保留说明，未影响physics或科学参数。

完整canonical包：/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1。Windows审阅镜像：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1。raw/native/receipts保存在canonical/source/results，镜像不冒充完整raw备份。命令、源码闭包与验算入口见REPRODUCTION.md。

![Adev_terminal_response.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/Adev_terminal_response.png)

![Adev_full_motion_force.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/Adev_full_motion_force.png)

![state_qualification_differences.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/state_qualification_differences.png)

## 交付导航

[TRACK_A_TERMINAL_RESPONSE](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/TRACK_A_TERMINAL_RESPONSE.md) · [TRACK_B_STATE_ROBUSTNESS](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/TRACK_B_STATE_ROBUSTNESS.md) · [TRACK_C_MOTION_SMOOTHNESS](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/TRACK_C_MOTION_SMOOTHNESS.md) · [TRACK_D_FORCE_MOMENT_TRACKING](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/TRACK_D_FORCE_MOMENT_TRACKING.md) · [TRACK_E_EXECUTION_AND_LEARNING](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/TRACK_E_EXECUTION_AND_LEARNING.md)

[EXPERIMENT_RESULTS.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/EXPERIMENT_RESULTS.json) · [CANDIDATE_LEDGER.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/CANDIDATE_LEDGER.json) · [ATTEMPT_ACCOUNTING.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/ATTEMPT_ACCOUNTING.json) · [VALIDATION_RESULTS.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/VALIDATION_RESULTS.json) · [PACKAGE_VERIFICATION.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/PACKAGE_VERIFICATION.json) · [FUTURE_Q_LEARNING_SCHEMA.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/FUTURE_Q_LEARNING_SCHEMA.json) · [NEXT_RESEARCH_DECISION.md](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/NEXT_RESEARCH_DECISION.md)

![完整力—力矩—运动权衡](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/force_motion_moment_tradeoff.png)

**STOP。** 不自动进入下一包，不训练学习模型。

最终保护核验：PASS；START/END=12/12，实际新增native steps=925240；122233个历史文件metadata/SHA与Git逻辑状态未变，冻结manifest不变，owned physics全部退出。封存前实际耗时50.03分钟，提前STOP。完整原始数据留存canonical。
