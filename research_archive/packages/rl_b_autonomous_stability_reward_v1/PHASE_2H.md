# PHASE_2H 内部阶段报告

生成UTC：2026-10-20T20:52:06.041977+00:00；实际elapsed 2.001小时。此报告不是STOP信号。

累计训练attempt 86，冻结评价attempt 12，native steps 9375440，RL decisions 1528，Adam steps 532。未结算attempt仍保留硬预留。

|分支|训练完成/attempt|确定性冻结完成|随机冻结完成|
|---|---|---|---|
|CONTROL_IDENTITY|3/10|0/0|0/0|
|H1|29/60|3/6|2/6|
|H2_AGG64|7/15|0/0|0/0|

以上跨checkpoint累计只描述已执行事实，不能当作单策略稳定完成率。当前候选和具体选择以STABILITY_SELECTION.json及RESEARCH_DECISION_LOG.jsonl为准。

剩余硬预算：训练364、评价48、native 40624560；距硬截止8.00小时。

下一阶段：继续有限队列或按Agent反思分配跨seed保持、必要消融及未见动作流复核；到9h15m停止新训练。独立物理初态接口BLOCKED，G4_STRICT_PASS=FAIL，新live matched不完整，Stage2及正式Campaign均NOT_READY。普通任务失败只停止分支，不停止研究包。

## Agent阶段复核（UTC 2026-10-20T20:56:16.931856+00:00）

自动报告的2.001小时快照和计数保留在上文，后续训练继续进行。

H1已完成60次延续训练和12次冻结评价。149在10/20/30 mean均失败，sample成功/成功/失败；163在三端点mean均完成19.03s，sample均失败。严格配对原Control080 mean两seed均失败，所以只支持163这一父策略的nominal mean保持，不是统一稳定性。163最终完整同19.03s的JF增加0.353088%、JM减少1.220504%；tracking与jerk RMS下降，但force未改善。原050两seed仍作为共同保留参考，新跨seed可信方案尚未形成。

H2已启动，当前首seed在原050、R0、LR3e-4下真实运行；首个聚合4完整episode/80 transitions/20 Adam，无singleton。必须等两seed30集后冻结结果，不能凭训练成功或机制测试晋级。具体counter、样本/优化代价在LEDGER和UPDATE_LOG。

下一阶段：完成H2两seed30集及mean/sample冻结，再在选定PPO配置上执行R1/R2各seed10集筛选，存在冻结完成信号才共同延续到30。Reward公式不变；若采用H2，筛选段10+20必须沿用连续30的全局聚合节奏，完整待更新数据随模型/Adam/RNG checkpoint保存和恢复。该修复已通过无物理的policy/Adam/RNG/计数器逐项完全一致测试。工程合成Adam总数为80（初批组织16+跨段一致性64），与MuJoCo训练账本分开。若筛选10集拒绝且仍有pending数据，则明确保留并报告未进入梯度更新的transition，不静默丢弃。

阻碍与替代：合法独立物理初态接口仍BLOCKED，G4_STRICT_PASS=FAIL，新live matched/Stage2/最终Campaign仍NOT_READY；继续允许的nominal开发。后续若主要Reward均失败，必须分析共同机制，再决定最多一个独立R3或有证据的探索尺度分支；不因局部失败停止研究，也不无依据搜索。最终未见动作RNG仍未运行、不得用于Reward调参。

剩余硬预算以2h快照364训练/48评价/40,624,560已结算native余量为参考；当前实时预留和计数以LEDGER为准。UTC04:07:04后不新训练，UTC04:52:04硬停止。阶段报告不是STOP。
