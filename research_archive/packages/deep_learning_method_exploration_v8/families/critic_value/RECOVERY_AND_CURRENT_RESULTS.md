# Critic / Value恢复与当前结果

本轮恢复的真实权重和关键证据逐文件SHA保存在 analysis/HISTORICAL_MODEL_RECOVERY_V1.json。长期日志v5开始/转折/结束、v6上游匹配及父状态别名纠正、v7结束记录已只读核对；未重复追加根日志。

v5出程/回程主模型分别16条真实分支标签、两个父状态，8标签模型各一个父状态。100维合法H状态，小型三lengthscale RBF ensemble，gamma=1，预测tail JF/JM、remaining time、motion worst ratio。冻结模型没有失败训练例。标签后续是当前一次候选后恢复原B rolling/replan，不是强平顺性整段方案。

真实0.5秒短窗与完整合格tail排序曾不同：出程约0.042779 N·s、回程约1.553816 N·s。冻结回程Critic使JF约1429.726061→1428.170545，同时JM约103.487906→103.819659；固定RELATIVEM与1秒窗口也选相同。出程仍选SPEEDP并原motion FAIL，失败在H前约0.18秒发生。未来资格mask不能修复该结果；15ms时钟缩放敏感性存在，但修正查询也没有改变失败选择。

v6真实COMMON_COMPOSE模型出程15训练行/3父、回程30训练行/6父，126维；只删除history_前缀的成本消融108维，不能称完整历史禁用。score_index=3是菜单中心化tail JF。新增累计测量JF/JM、observer极值及guard/context历史，时间scale设物理下限，B与COMPOSE成本标签分库。B上游接COMPOSE后续15动作原excursion失败保留，匹配COMPOSE上游后才恢复资格。

v6风险最终1281相关窗口、12实际父族、3含失败族，整父留出混淆为TP18/FN32/FP14/TN1217；出程12个失败窗口全漏。它不是1281独立样本或安全证书。4个主冻结新prefix的Critic均原门通过，相对1秒改变4/4，相对强phase改变0/4，平均JF增量0。O3与TAILOT实际同父已降格训练重放；本轮没有恢复其独立称谓。

v7新长Critic/Bellman Q/WM本来明确NOT_RUN，GP/quad/stump不能改名成价值家族已穷尽。v8先提取EARLYN/L/H、CFACTORH/L和HOLDSS03六个已暴露开发context，45动作结果中26原合格，1工程partial保留null。每组所有候选真实fork hash与pre-fork observer/wrench前缀一致；跨组六个真实parent hash与六个观测前缀指纹均互异。它们仍是六个开发context，非45患者样本。

发现一对双方原资格都通过的真实排序翻转：EARLY_PHASE减LATE_H150在CFACTORL01的ΔJF=+0.124775646 N·s、ΔJM=+0.165479311 Nm·s；在HOLDSS03为ΔJF=−2.505434942、ΔJM=−0.650334440。此证据支持重新研究state-conditioned值，不能自动说明25D输入能学出翻转。

统一5动作以CFACTORH01精确recipe为锚：B、LATE_H150、EARLY_H150、LATE_PHASE、EARLY_PHASE。同tag异recipe不混；EARLYH01缺部分精确动作反事实。共6种模型：ABS_25、DELTA_25、PAIR_25、DELTA_15、DELTA_0、STRONG_DELTA_25。48次模型fit调用包含开发LOO与最终冻结，各3个ridge解析求解、1个risk和2个pair优化；优化迭代数/梯度次数未持久化，记UNKNOWN而非0。数值fit wall0.219949s、userCPU0.201887s、systemCPU0.016650s、RSS89124KiB，0新物理。首次import/I/O的工具总墙钟约0.475s，不与数值fit混淆。

| 开发整context LOO策略 | 原合格/6 | 未知反事实 | 与B不同 | 合格选择平均ΔJF | 合格选择平均ΔJM |
|---|---:|---:|---:|---:|---:|
| ABS_25 / JF主目标 | 6 | 0 | 3 | −18.132053 | +2.613814 |
| DELTA_25 | 5 | 0 | 4 | −23.332344 | +3.219016 |
| PAIR_25 | 4 | 1 | 4 | −18.677841 | +2.414155 |
| DELTA_15 | 5 | 0 | 4 | −23.332344 | +3.219016 |
| DELTA_0 | 2 | 1 | 4 | 0 | 0 |
| STRONG_DELTA_25 | 5 | 0 | 4 | −23.332344 | +3.219016 |
| 固定B / 开发best-fixed | 6 | 0 | 0 | 0 | 0 |
| 开发if stump | 4 | 1 | 3 | −9.419302 | +1.266656 |
| nearest-context | 3 | 0 | 5 | −24.903788 | +3.218874 |

合格子集均值不能掩盖失败/未知，也不能用于跨不同子集排列“最好模型”。主模型按事前开发准则：失败/未知最少，再看合格JF，选定ABS_25。其开发STRICT_JM仍在CFACTORL01误放真实JM+4.654424；其它delta/pair STRICT_JM均退B。此处的JF主目标是显式新取舍，绝不覆盖历史双成本benefit失败。

ABS总体JF RMSE74.089679优于同动作常数190.854676，但菜单中心化JF RMSE42.872863，合格JF pair正确20/26。delta25 RMSE6.895870不及常数2.204839；PAIR实际排序18/26。risk Brier约0.216670未校准。这些表明“成本信息”“相对排序”“资格正确”“控制增量”必须分开。

0.5/1/2秒真实直接成本在所有6context同选，4秒只在CFACTORH01改选另一个完整失败动作。CFL四窗口都选EARLY_PHASE而非完整最优EARLY_H150，JF regret3.841564；SS相应1.686167。窗口加长没有普遍解决当前菜单问题。短窗成本来自已付费完整trace，不能称廉价预测或独立部署。

冻结bundle SHA为5642ff8e36199e85e734daa81af24f039827b5f3f4369e5e3d268b742122c905；强对照bundle SHA为ee237d3897e55226a09d780e7697fc2d9f0b57cf1615752c958755cc060ef995。6context×6method×2objective共72项原payload/25D预测完全一致，未来case/成本/PASS扰动不影响结果，含结果标签整行被拒；三个简单对照18项一致。此审计只证明输入通路，不证明状态充分性或资格。

主Agent已冻结4个stock条件及相同5recipe，所有A/B选择在B结果前落盘，C在B真实完成后作为COLD_REPLAY；本Agent静态审查四个config SHA、完整动作/基础recipe/依赖逐值全通过，worker原资格bool AST与v7相同。通用selector源码缺显式config动作等于bundle动作的assert，本次4实例以独立精确配置存证闭合，局限保留。静态核验不代替运行时raw/receipt/时间顺序；本报告没有打开新4case结果。

家族继续保持NOT_FULLY_EXPLORED。已执行的变体没有证明所有价值学习无效，也没有证明独立泛化、双成本优势或实际净省试；实际Critic省试仍为0。
