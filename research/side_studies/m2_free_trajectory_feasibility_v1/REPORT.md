# iHEAR Lab — Free Trajectory Optimization & Physical Feasibility v1

本轮完成原完整机器人—人体动力学下的隔离自由参考研究。最好完整运动 `development_resume_main_NATIVE_SCALAR_18_029` 的 J_F=1403.259730 N·s，相对同条件 B 的 1438.613498 N·s降低 **2.457489%**，全部冻结主条件 **PASS**。≥2%：达到；≥5%：未达到。唯一主方向 **A**，不是全局最优结论。

|完整方案|J_F N·s|降低%|冻结任务/运动资格|最严重约束比|
|---|---:|---:|---|---|
|development_resume_B0_original|1438.613498|0.000000|PASS|moment_peak 0.952381|
|development_resume_NATIVE_SCALAR_18|1421.845454|1.165570|PASS|excursion 0.993501|
|development_resume_main_NATIVE_SCALAR_18_029|1403.259730|2.457489|PASS|excursion 0.995090|
|development_resume_repair_C2_pair_1_2_067|1214.916378|15.549494|FAIL|excursion 3.307825|

## 本轮新自由度与真实执行

OUTBOUND/RETURN独立优化共同进度、差分进度的常数与倾斜，以及hip/knee独立通过速度，共10维。请求时产生位姿/dq意图，原quintic、governor、40ms bridge、100ms lifecycle、current-state admission和机器人六轴力矩闭环执行。数学参考、实际reference receipt、真实人体q/dq分开记录；没有qpos/qvel回放、人体主动力矩、模型变化或接触绕过。该族是连续函数定义的分段quintic参考，不能冒称任意时间样条或原生PWL逐步连续执行。详细权限见 PHYSICAL_ACTION_SPACE.md。

扩展零调整的完整trace、76,121个TASK人体原生样本、全receipt/torque复现PASS；重新生成父与之前B完整数值一致。所有历史同条件复现范围和字节证据见 BASELINE_REPRODUCTION.json；旧E指标仅作设计起点来源，不混入排序。

## 最好运动、收益分解与资格

最好参数：`[0.008630673088403396, 0.01298796570381815, -0.0029315763894719876, 0.17120373620069818, 0.2, 0.0010035577490444428, -0.00024110789350839562, 0.009921163710896835, 0.05305821705508584, 0.08279506533678752]`；native种子 `NATIVE_SCALAR_18`。新增自由参数是否非零：True。通过所有真实hip/knee速度max/p95/RMS、加速度max/p95/RMS、jerk p95/RMS、excursion±0.5°、累计角位移±5%、端点/phase boundary±0.5°、总及阶段时间±0.1s、moment integral≤25%、tracking增量≤0.5°、force/moment peak补偿与原absolute安全。jerk max和phase shape仅诊断；这些是研究规则，不是临床舒适阈值。每项绝对值与比值完整保留，不用过滤显示曲线作为验收。

OUTBOUND减少 17.273197 N·s；HOLD减少 0.000006 N·s；RETURN减少 18.080565 N·s。按完整TASK原左积分、实际phase边界分配，闭合误差门限1e-8。不同条件分母不直接拼接。

本轮最佳主要声明为 LEVEL1（完整原动力学、安全与运动条件）。它具有非零扩展参数，不能声称原生 B 已实现该收益。LEVEL3和真机均未开展。两个未用于选参的合法RETURN前缀条件，冻结remaining suffix资格 1/2；实际状态差和完整配对收益见 PHYSICAL_FEASIBILITY_VALIDATION.json。它们是同一Human，且前缀消耗R0，不冒称原完整策略跨患者或全串独立验证。参数冻结后未再修复或重新选择。

## 力与运动权衡

最低力代表 `development_resume_repair_C2_pair_1_2_067`，下降 15.549494%，运动失败条件 `['velocity_deg_s/max_abs', 'velocity_deg_s/p95_abs', 'velocity_deg_s/rms', 'acceleration_deg_s2/max_abs', 'acceleration_deg_s2/p95_abs', 'acceleration_deg_s2/rms', 'jerk_deg_s3/rms', 'RETURN_duration', 'excursion', 'task_duration', 'moment_integral_Nm_s', 'tracking']`。低力参考的实际暴露持续时间、phase负担、接触与控制输入见 FORCE_MOTION_TRADEOFFS.json。常见限制 `{'acceleration_deg_s2/max_abs': 47, 'excursion': 36, 'acceleration_deg_s2/p95_abs': 18, 'velocity_deg_s/p95_abs': 17, 'acceleration_deg_s2/rms': 16, 'velocity_deg_s/max_abs': 15, 'jerk_deg_s3/p95_abs': 7, 'jerk_deg_s3/rms': 9, 'velocity_deg_s/rms': 14, 'endpoint_phase_boundary': 3, 'moment_integral_Nm_s': 14, 'tracking': 13, 'OUTBOUND_duration': 1, 'task_duration': 8, 'RETURN_duration': 7, 'cumulative_dose': 3}`。优化器同时接收完整力目标与实测各项约束，strong seed修复不能把超标方案升级为teacher。

新自由运动合格数 10，实际positive-step自由运动候选数 64。有限预算下COBYLA status和实际评估次数原样保存；不能把maxiter/budget终止说成收敛。未覆盖的更高维连续参考和底层输入优化仍是局限，不能判断真实物理最优只有1%–2%。

## Teacher与下一决定

本轮找到明显更好的原动力学可行参考，可作为有限条件离线teacher；最小接口变化需进一步以冻结验证范围约束，不直接合并正式B。下一主方向仅为 A，理由见 NEXT_RESEARCH_DECISION.md；没有训练Q、Neural Q、G/P或在线个体化。

## 预算、失败与保护

新增attempt启动 84/96，所有冷父、完整fork、partial、optimizer真实评估、重复及失败均在START分母。首次归档因自有结果列表覆盖原参考rows导致KeyError，物理零调整完整且父未污染；保留错误和partial父，用原live snapshot与完整trace恢复记录，修正命名后新父精确复现。没有重置计数或墙钟。

轻量归档只删除本新包已完成全receipt/安全/积分审计的普通生成raw；完整trace、dense运动、参数、指标和关键原始receipt保留，COMPACTION.jsonl记录每次原SHA/bytes。没有复制全历史或Windows镜像。原源码/权重、Linux两处Git状态、退出和空间见 PACKAGE_VERIFICATION.json；保护范围不是全部历史字节扫描。

完成报告和核验后 STOP，不自动启动后续。

## 完整原生运动数值

|原生实际运动统计|Hip最好|Hip B|Knee最好|Knee B|最差比值|冻结规则|
|---|---:|---:|---:|---:|---:|---|
|velocity_deg_s/max_abs|23.475668|23.784934|23.168077|26.048980|0.986997|≤1.1|
|velocity_deg_s/p95_abs|22.824497|22.857473|22.279416|20.512000|1.086165|≤1.1|
|velocity_deg_s/rms|14.987928|14.775722|14.512063|14.039894|1.033631|≤1.1|
|acceleration_deg_s2/max_abs|81.250256|85.115055|122.680061|112.526790|1.090230|≤1.1|
|acceleration_deg_s2/p95_abs|40.175449|39.907239|31.071065|29.744453|1.044600|≤1.1|
|acceleration_deg_s2/rms|20.415460|21.892447|16.746104|17.787939|0.941430|≤1.1|
|jerk_deg_s3/p95_abs|389.919377|400.702143|907.387475|895.495178|1.013280|≤1.1|
|jerk_deg_s3/rms|328.992674|308.665820|689.285433|703.137158|1.065854|≤1.1|
|jerk_deg_s3/max_abs|6558.491097|5548.470080|17103.069102|18188.903758|1.182036|仅诊断|

速度单位deg/s，加速度deg/s²，jerk deg/s³。以上用全部native true dq，原生0.25ms间隔、raw梯度，不删除端点或以滤波显示替代。

行程差 Hip/Knee=[0.23905976650813443, 0.49754477278101206]°；累计角位移比=[1.002008767440939, 1.0045217455765485]；phase/endpoint最大偏差=0.000807784°；阶段形状最大差=14.238075°（不宣称治疗等效）。tracking RMS最好=[0.46861198547860605, 0.5121651365623453]°，B=[0.4776353633264532, 0.45574342031770343]°。

完整及各phase时长：最好 {'HOLD': 1.0200000000048703, 'OUTBOUND': 9.005000000000718, 'RETURN': 9.005000000042997}，B {'HOLD': 1.0200000000048703, 'OUTBOUND': 9.005000000000718, 'RETURN': 9.005000000042997}；完整native运动时长 19.030000s。moment integral最好/B=106.797982/100.417251 N·m·s；force peak=114.118932/115.479119N；moment peak=15.642424/15.711377 N·m。原absolute原生安全轴全部通过。

## 冻结独立条件结果

|新合法条件|配对方案|J_F N·s|相对本条件B降低%|完整任务/运动条件|失败项|
|---|---|---:|---:|---|---|
|W1|B0_match|1440.640816|0.000000|PASS|无|
|W1|frozen_best|1405.715543|2.424287|FAIL|excursion|
|W2|B0_match|1436.598447|0.000000|PASS|无|
|W2|frozen_best|1402.411644|2.379705|PASS|无|

两条件均从合法完整OUTBOUND入口fork，实际执行冻结的完整OUTBOUND，再执行共享native-only RETURN0条件前缀，后续R1+继续冻结参数。初始完整状态同条件配对一致；不同实际RETURN1状态由真实前向运动产生，没有qpos/qvel设置。原R0动作被条件消费，不能冒称全串原动作未见测试。

真实RETURN1跨条件最大状态差：{'q_max_abs_difference_rad': 0.014372063352484421, 'dq_max_abs_difference_rad_s': 0.0005364206885526968}。这是同一Human的状态扰动，非不同患者。参数冻结时刻 1791896504.6086435，没有验证反馈选参。扩展验证覆盖的修订早于参数冻结和任何W输出，原协议版本保留，主运动规则/任务/动力学/预算未改变。

## 接口字段消融

|冻结消融|完整J_F N·s|相对B降低%|运动资格|相对冻结最好增加J_F N·s|
|---|---:|---:|---|---:|
|no_free_velocity|1414.263094|1.692630|FAIL|11.003363|
|no_free_common_progress|1402.089674|2.538821|FAIL|-1.170057|

候选最小后续接口：已有请求上的有界 common-progress scalar（与反对称delta分开）；已有内部路点上的独立 hip/knee pass-through velocity scale/skew 或等价dq pair。消融不重新选参，完整阴性结果也保留。

优化器子进程从COBYLA回调返回继承的物理runtime时，会打印预期的callback unwind文本；父优化器等待完整物理子进程后继续。这不是MuJoCo数值失败。实际优化终态及未收敛记录保留在OPTIMIZER_STATUS.jsonl，不能将有限可行观察称为全局最优或优化收敛。

![Force and motion](figures/FORCE_MOTION_SEARCH.png)


最终包核验 **PASS**：84/96次物理attempt，墙钟约154.16分钟；新包约1.960GiB，D可用约101.06GiB。1373个复用原源码/依赖/原生构建/权重文件哈希未变，两处Linux Git快照一致，79次父fork检查未污染；完整保护范围见PACKAGE_VERIFICATION。84次START中包括首次归档异常和partial父，未隐藏失败。所有自有物理进程已退出。

三张静态科学图已视觉核验：标签、原始运动、累计力和通过/失败分类一致。图中采样只用于显示。最终状态 **STOP**。

图表标签和收尾完成后，总墙钟约163.39分钟，仍在4小时硬限内；该阶段仅更新报告/图表/清单，没有新增物理任务。STOP。
