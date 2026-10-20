# iHEAR Lab — 18D Baseline Qualification v1

开发复现资格成立，但冻结18D尚不具备跨合法状态的可靠motion资格。固定参数直接迁移不能被称为通用优化基线。 本轮复现门PASS；新合法状态完整配对4，正降力4/4，motion PASS=3/4，绝对安全PASS=4/4，receipt/causal PASS=4/4。历史motion 0/4另列并保留。

## 七个问题的明确答案

1. **真实方法与参数**：原B上方的固定参考意图扩展。18个无量纲系数分去程/回程，控制common/differential进度常数、一次/二次形状与终端速度common/differential/tilt；完整历史方案还含RETURN槽1/2的-0.020/-0.022 native差分plateau。算法公式、逐项数值及源码定位见METHOD_DEFINITION与PARAMETER_MAP；不能仅由“18D”名称解释算法。
2. **是否学习策略**：否。历史使用有限离线约束COBYLA/probe/候选筛选；本轮固定参数执行，没有Q-learning、Neural Q或在线RL。原B仍负责因果估计、在线waypoint选择、认证quintic、40ms bridge、100ms lifecycle、current admission、governor、FAST/allocator、torque与fallback。
3. **是否精确复现历史**：是；本轮新物理B/18D完整trace、native身体/contact/torque和receipt字段与历史精确一致，完整积分和phase独立重算通过。 历史报告值、本轮新物理与独立raw计算在BASELINE_REPRODUCTION和REPRODUCTION_AUDIT中区分。
4. **新合法状态能否保留降力**：本轮4/4个完整配对正降力，数值如下。每种来自同一Human实际native prefix，fork发生在prefix执行后的下一原生请求，B/18D完整活状态匹配。完整J_F包括共同prefix；被冻结策略的OUTBOUND0已消费，因此结论是剩余策略的迁移，不宣称整串策略在不同患者上的泛化。
5. **motion/safety是否通过**：motion 3/4，绝对安全4/4，receipt/causal 4/4；降力不能掩盖运动失败，阈值未放宽。
6. **是否足以成为第二轮可靠基线**：开发条件下的完整可复现比较基线已成立；跨合法状态的可靠直接迁移资格仍受本轮及历史失败限制，不能称通用最优/临床策略。固定参数直接迁移和为新状态重新优化必须分别评价。
7. **下一步优先级**：优先开展独立版本、事前冻结的保守状态条件准入/有界校准研究；本轮仅提出合同，不实现、不调参。先确认能用因果状态/模型特征预测风险，再用新未见prefix验证；状态重优化须独立标识，不能冒充原18D泛化。

## 本轮完整结果

|合法prefix条件|B完整J_F N·s|冻结18D完整J_F N·s|降力%|motion|失败项|
|---|---:|---:|---:|---|---|
|N1|1433.243733131|1400.836420943|2.261117|PASS|无|
|N2|1444.351653542|1409.561609567|2.408696|FAIL|acceleration_deg_s2/max_abs|
|N3|1431.180251244|1399.075582816|2.243230|PASS|无|
|N4|1436.916546550|1403.953045882|2.294044|PASS|无|

各臂完整OUTBOUND/HOLD/RETURN积分、phase/task时长、tracking、moment、clearance、ROM/torque/contact与绝对安全细项、source/receipt/native ownership、完整父状态来源及hash都保存在VALIDATION_RESULTS、reports、derived与原raw。partial不排名。B自比motion PASS只证明比较基准；绝对task/safety另由原评价审查。不同条件的绝对J_F不用于重选最优；本轮通过率与历史0/4的prefix集合不同，不能解释为未改参策略的性能改善。

## 失败定位与解释

- N2：knee acceleration_deg_s2/max_abs完整比值1.249192 > 1.10；主要诊断贡献位于OUTBOUND（该phase指标比1.249192），绝对峰时刻task 7.072250s。p95按超过完整B指标限的样本数、RMS按全程归一化均方增量定位，不以近零HOLD比值当主因；phase定位不等于证明单一因果。

新条件各失败约束计数：{"acceleration_deg_s2/max_abs": 1}。所有逐joint/full/phase原生raw统计以及超全程基准限的样本时长在derived/*FAILURE_DIAGNOSIS.json。motion是冻结工程非劣等/剂量规则，不是临床舒适标准；phase-shape和raw jerk最大值仅作诊断。源码描述了状态依赖的B目标、可行性与闭环响应，观察结果不足以证明特定非线性因果或一个有效筛选器。若各条件均降力而motion仍失败，应将其理解为本有限集合的力收益方向一致、运动可行域依赖状态的开发解，不能推成稳定通用协调规律。不得以重新优化后较好的结果冒称冻结18D的泛化。冻结可复现基线的适用边界见BASELINE_CONTRACT.json；没有现成自动准入筛选器。

## 历史失败原样保留

retrospective primary：V1–V4 motion 0/4，四者都有正降力；历史完整记录在provenance原VALIDATION_RESULTS。本轮另从历史trace和保存的native motion_series独立重算四对完整/phase J_F及所有raw burden统计，再确认每个条件都有原burden失败，见audit/HISTORICAL_FAILURE_RECOMPUTATION。它是历史raw重算，不是本轮新物理；其他历史fairness失败标签保留、不重新分类。V1 velocity p95；V2 acceleration p95/phase-boundary；V3 velocity p95/acceleration p95/excursion；V4 acceleration max/p95、jerk RMS/excursion。secondary 1/4不用于改选primary。历史更低力1196.685445候选motion失败及原host/strict/R2/FAST未获资格均保留。

## 证据层级与保护

**本轮新PHYSICAL_LEVEL1**：原MuJoCo native执行的父运行与完整live fork、issued reference、实际commands、native receipts和真实Human响应。**历史报告**：隔离provenance完整原文及hash。**数学/计算证据**：无physics的参数公式检查、SHA/源码闭包、独立raw积分/导数/ownership重算。**未解决**：跨患者、模型不确定性、整串策略未见初态、正式Native LEVEL2、host-clock LEVEL3/硬实时、硬件与临床；不将这些层级混称PASS。

环境：真实WSL Ubuntu-Research-Verify；指定Python 3.10.21；主仓库与Side Studies路径已确认，未安装/更换环境。canonical包：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1`。Windows目录只作审阅镜像，不含全部source/raw。主分支/HEAD及既有Git暂存/未暂存状态见audit/GIT_BEFORE与FINAL_PROTECTION；无commit/push/merge/reset/stash/clean或branch切换。

物理START=15/40，END=15，实际新增native步1290040（继承prefix不重复算新增）。完成本有限预注册集合后提前停止，不为耗尽4–6小时追加实验；报告生成距注册约0.555小时，六小时与最后一小时无新START规则在RUN_PLAN中冻结。START/END、returncode、partial及错误见ATTEMPT_ACCOUNTING。一次START前缺共享合同的包装错误保留，未新增物理attempt；分析脚本还曾将TASK-only两字段误用整session时间mask，已改为它们实际TASK时间轴，原始数据/物理不变。最终完整归档审计首次失败，发现4份native支持归档未复制；按历史SHA补齐并保留初始审计失败，没有改变执行manifest或新增physics。三项工程/审计事件均保留，不隐瞒失败。

所有新文件只在本版本化包及其Windows审阅镜像。历史保护包括全主仓库内容SHA、既有Side Studies元数据和受保护源码/权重/报告/关键raw SHA；精确范围与最终复核见PACKAGE_VERIFICATION。源码路径迁移、参数身份、原1376项manifest原件核对，以及最终完整归档逐项核对均有证据；4项支持文件为物理结束后补齐，不能与物理前执行manifest混淆。执行源不叠加Waypoint或训练；无科学阈值、模型、task、HOLD或控制底座改变。

完成后owned物理进程全部退出，最终进程/保护核验和文件清单见PACKAGE_VERIFICATION与EVIDENCE_MANIFEST。STOP；不自动启动下一研究包。
