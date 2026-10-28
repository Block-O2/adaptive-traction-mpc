# 传统上层优化与真实预算

| 方法 | 真实attempt检查点 | 合格数 | 新增native | 最佳身份 | S | JF | JM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PATTERN | 4 | 4 | 277040 | OPT01_PATTERN001 | 0.964078 | 1401.756380 | 107.779354 |
| PATTERN | 8 | 8 | 554080 | OPT01_PATTERN006 | 0.957100 | 1402.464352 | 106.735303 |
| PATTERN | 12 | 12 | 831120 | OPT01_PATTERN011 | 0.953545 | 1402.725729 | 106.179593 |
| BO | 4 | 4 | 277040 | OPT01_BO001 | 0.964078 | 1401.756380 | 107.779354 |
| BO | 8 | 7 | 554080 | OPT01_BO001 | 0.964078 | 1401.756380 | 107.779354 |
| BO | 12 | 11 | 831120 | OPT01_BO001 | 0.964078 | 1401.756380 | 107.779354 |


PATTERN/BO在同一四维固定计划子族[O_pass,R_pass,O_time,R_time]∈[-1,1]比较，每臂12次真实尝试，失败和partial照计。共享初始强固定与HANDOFF历史起点选择另账；两臂仅消费自身优化反馈。代理查询、拟合与既有历史不是免费物理尝试，也不替代native计数。S=.65组合raw jerk RMS比+.35实测200Hz force-norm变化率RMS比+.004ΔJF+.004ΔJM；原门与同权限先通过。分量与Pareto取舍仍单列，不用S宣称所有指标同时改善。动态参考策略与固定计划的策略族不同，不把它们当相同搜索空间效率对照。两种新优化均从历史强固定与本轮Handoff证据出发，12次是增量预算，不能与历史scratchPPO64直接比较总样本效率；历史v2共285 START/20,093,240 native含PPO72 START，是背景总量，不能全部归因所选baseline或与PPO子集相加。


## 池化历史的相位组合：独立适应性分支

模型使用29条已完成合格modal历史；源Handoff7 START和OPT27 START共34次已花物理尝试，不能说新组合从零只花一次。两臂固定12次结论保持。HOLD后近似重置使RETURN代价/jerk对OUTBOUND历史变化很小；这只是当前nominal Human与原HOLD下的经验结构，非普遍安全或动力学分离定理。

COMPOSE01_PAIR01：来源OUTBOUND/HOLD=OPT01_PATTERN004，RETURN=OPT01_BO007；目标=QUALITY_Q_PARETO_FRONT，预测JF=1406.093248979、JM=106.066136614。实际原门=PASS，JF=1406.093248766、JM=106.066136610；预测差(actual−pred)为-2.13e-07 N·s／-4.3e-09 Nm·s。

质量前沿Q移除S中的JF/JM标量惩罚，按预先登记的归一Q增益>=0.005、预测JF/JM相对强固定增幅<=1%筛选，原资格一律不改。这一候选可改善实际jerk/wrench而提高JF，不能替代S最优结论；模型源hash、完整parts与预报见analysis/PHASE_COMPOSITION_MODEL.json。
