# PHASE_4H 内部阶段报告

生成UTC：2026-10-20T22:52:06.030343+00:00；实际elapsed 4.001小时。此报告不是STOP信号。

累计训练attempt 182，冻结评价attempt 22，native steps 19269780，RL decisions 3087，Adam steps 892。未结算attempt仍保留硬预留。

|分支|训练完成/attempt|确定性冻结完成|随机冻结完成|
|---|---|---|---|
|CONTROL_IDENTITY|3/10|0/0|0/0|
|H1|29/60|3/6|2/6|
|H2_AGG64|26/60|2/2|1/2|
|REWARD_R1|22/51|3/3|3/3|

以上跨checkpoint累计只描述已执行事实，不能当作单策略稳定完成率。当前候选和具体选择以STABILITY_SELECTION.json及RESEARCH_DECISION_LOG.jsonl为准。

剩余硬预算：训练268、评价38、native 30730220；距硬截止6.00小时。

下一阶段：继续有限队列或按Agent反思分配跨seed保持、必要消融及未见动作流复核；到9h15m停止新训练。独立物理初态接口BLOCKED，G4_STRICT_PASS=FAIL，新live matched不完整，Stage2及正式Campaign均NOT_READY。普通任务失败只停止分支，不停止研究包。


## 四小时科学审阅补注

补注UTC：2026-10-20T22:54:10.346887+00:00。原自动快照已逐字保存到 `audit/phase_reports/PHASE_4H_AUTO_6ae37fd1855586b0b56ed8f90620d6a8ba3e2a3e1d646ad48fc6bb3918897a27.md`；以上累计计数保持不变。以下已完成结果均在原快照UTC之前获得，未把后来的结果回填成当时已知事实。

分支表的训练分母来自已完成记录；ledger累计attempt还包括在途尝试。快照当时有1个在途物理attempt，保留165,000 native steps。扣除该预留后的未占用native预算为30,565,220；最终8次未见动作流评价另预留保守1,320,000，额外研究的可分配native空间约29,245,220，后续每次启动仍须重算。

**已完成的主要判断。** 两父Control严格复演后复用，原080 mean均失败；H1只有163在10/20/30保留mean，末端sample两父均失败，不能授一致稳定性。H2两父30端点mean均COMPLETE19.03s，sample为1/2；它支持已测nominal端点保持，未测H2的10/20运行时保持，也未证明更长保持。

H2两mean等时长任务较各自父050的JF为−0.454636%/−0.199720%，JM为+1.079758%/+0.351936%。RETURN贡献主要JF下降，也贡献主要JM上升。Human部分RMS改善与某些tracking/加速度峰增加并存，不能宣称force/moment/motion全面改善。原5ms已执行区间JF/JM与0.25ms native Human运动口径分开保存。

R1共同十集mean/sample四次均完成，故按原筛选门延长双方至30。149的30集训练13/30完成、431 transitions全部优化、116实际Adam、0singleton、pending0；mean完整19.03s，JF1439.053718、JM102.896412（对父−0.534922%/+1.343022%）；sample完整19.915s，不列不同时长dose收益。163在快照前已完成21集采样，三十端点尚未评价。因此还不能把R1作为已双父三十保持的最终候选。

真实pending恢复得到执行证据：163的59个待优化transition、4完整episodes已fullstate恢复，并与第11集新增24个一起按原顺序完整组成实际83-transition更新，执行24Adam；无遗漏、重复或额外物理重放。见audit/REAL_PENDING_CONTINUATION_AUDIT.json。

**当前候选。** 已完成双父三十mean保持的共同基准仍是H2/R0/aggregate64/LR3e-4；R1有首父三十双模式的正信号，须等另一父。保留两原050和全部成功/失败后续checkpoint，不能根据某个低partial JF换掉高层任务门。

**下一阶段。** 先完成现有R1第二父及两个冻结模式，再按已封存共同方案执行R2的十集筛选和有条件三十集延长。随后用完整证据决定有限的更长保持与必要Reward消融。RETENTION_EXTENSION_PLAN.md只是一份条件方案，尚未启动；任何30→60等延长须独立明确身份和全局终末，并把父子谱系连接，不能以新branch名遮蔽退化。最终8个未见动作流不用于反复调Reward，T0+9h15m停止新训练。

**机制与替代路线。** 共享首个物理rollout的R1目标增加critic梯度占比，joint clip后actor更弱；单一R1/30离线单位消融又改变这一竞争。两项均零新physics/Adam，只提供后续尺度消融的动机，不是实际R3或任务成功证据。若候选更长保持失败，保存反例，继续有价值的机制诊断/必要消融，不将ordinary FAIL当整个研究STOP。

独立合法初态仍BLOCKED_CURRENT_FROZEN_PPO_INTERFACE；替代是诚实保持nominal和动作流范围、分析冻结策略与真实运动。G4_STRICT_PASS=FAIL，新live matched未完整，Stage2和正式Campaign均NOT_READY。没有新的GLOBAL_BLOCKER，没有启动下一研究包或最终Campaign。本阶段报告不是STOP。
