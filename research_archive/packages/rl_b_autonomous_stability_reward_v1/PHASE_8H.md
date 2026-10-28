# PHASE_8H 内部阶段报告

生成UTC：2026-10-21T02:52:10.296824+00:00；实际elapsed 8.002小时。此报告不是STOP信号。

累计训练attempt 360，冻结评价attempt 40，native steps 38567580，RL decisions 6223，Adam steps 1640。未结算attempt仍保留硬预留。

|分支|训练完成/attempt|确定性冻结完成|随机冻结完成|
|---|---|---|---|
|CONTROL_IDENTITY|3/10|0/0|0/0|
|H1|29/60|3/6|2/6|
|H2_AGG64|26/60|2/2|1/2|
|REWARD_R1|27/60|4/4|4/4|
|REWARD_R2|29/60|4/4|4/4|
|RETENTION_H2|30/60|2/2|2/2|
|REWARD_R3|9/20|2/2|2/2|
|RETENTION_R1|8/30|0/0|0/0|

以上跨checkpoint累计只描述已执行事实，不能当作单策略稳定完成率。当前候选和具体选择以STABILITY_SELECTION.json及RESEARCH_DECISION_LOG.jsonl为准。

剩余硬预算：训练90、评价20、native 11432420；距硬截止2.00小时。

下一阶段：继续有限队列或按Agent反思分配跨seed保持、必要消融及未见动作流复核；到9h15m停止新训练。独立物理初态接口BLOCKED，G4_STRICT_PASS=FAIL，新live matched不完整，Stage2及正式Campaign均NOT_READY。普通任务失败只停止分支，不停止研究包。

## 八小时证据审阅补充

补充UTC：2026-10-21T02:55:53.732359+00:00；数据截止仍为原自动快照2026-10-21T02:52:10.296824+00:00。原快照完整保存在audit/phase_reports/PHASE_8H_AUTO_77d17b1e3d00e482fe7d64d30821826f862d6c81d02f9b8572dc5e3f4df82915.md，没有把后续冻结结果倒填到8小时。

已完成H1、H2共同30窗口、R1/R2各两父30、H2两父30→60，以及R3两父10的单位消融。H1只保留163 mean，149全部mean失败，最终sample两父失败；H2两父mean在30/60均完整，最新60两父sample也完整，但163/30 sample失败仍保留。R1/R2两父10/30 mean/sample全部已测完成，R3两父10 mean/sample完成。不同checkpoint/模式不合并为一个冻结策略成功率。

当前最长窗口候选是R0/H2两父060，原050永久保留；R1是已登记的同60窗口Reward保持候选，仍未完成最终判断。R3仅是短窗口数值机制消融，不因未测更长而占据最长保持支持。

|H2六十mean对同父050|JF%|JM%|tracking RMS hip/knee °|jerk RMS hip/knee °/s³|
|---|---|---|---|---|
|1495656323|-0.749477|+1.931898|0.485968/0.472444|381.026/881.508|
|1630784693|-0.314121|+0.848430|0.500847/0.629999|379.253/797.378|

两mean TASK均19.03秒。H2的163 knee tracking仍差于父0.580361°，RETURN knee overshoot2.653867°；moment上升，不能称全面运动改善。R3/10的mean同为19.03秒，149 JF−0.279504%而JM+1.368140%，163 JF+0.325382%而JM−1.241229%；没有一致force改善。不同sample时长与失败partial不计算同父剂量收益，不能宣称优于原B/H150。

受控R3首更新：每父四Reward的首80/77物理样本、policy/Adam/RNG/计数、PPO参数及update AST一致，实际各20Adam。R3把R1全部项/floor除30后，actor参数L2分别为R1的1.887/1.953倍，Gaussian KL却为2.576/0.230倍。单位缩放改变优化，但参数范数不直接决定函数漂移、native命令或任务保持；GAE/joint clip/旧critic/Adam未单独因果隔离。R3首父采样172而优化152，完整pending20已保存；第二父160全部优化，实际Adam40/44，无十集额外flush。

截止时R1首父31–60训练已经全部结算，本段8/30完成，sampled=optimized=462、124实际Adam、6次PPO.train/24epochs，0singleton和终末pending0。两父原R1/030完整policy/Adam/RNG恢复合同不变，新模块只添加R3，R1输出语义逐项等价。截止没有任何R1六十冻结记录，第二父尚未开始延长；不得用训练sample比例代替mean保持结论。

账目为360/450训练、40/60评价、38567580/50000000 native、真实Adam1640、RL decisions6223，所有400个已准入物理attempt在该瞬间均已结算，无在途预留。剩余硬预算90训练、20评价、11432420 native，距停止新训练约75分钟、硬停约120分钟。尚未启动的R1第二父30训练/两父共4冻结，加最终8评价共42次，最坏预留6930000 native，连已结算总量为45497580，低于50M；预计最终390训练/52评价，仍需每次真实准入检查。预算是上限，不会为耗满而额外重复。

下一步仅完成当前R1保持及反思，按FINAL_SELECTION_PROTOCOL.md冻结一个checkpoint对，然后运行2191–2194四未见动作流×两父8次。当前最终流未打开；看到其结果后不再训练、修改Reward/PPO/std或换候选。若R1长窗口失败，保留失败并按预锁规则使用已有H2长窗口证据，不回避退化或继续无界搜索。

最终审计已准备：独立进程用原审计器重读gzip native/receipt，在完整与失败partial样本均重算通过，约6秒/例，无新物理/Adam；关闭后覆盖全部冻结评价，要求ledger不变。最近模型/RNG检查覆盖133个发布generation及110个pre-Adam generation均通过；最终还会再次核对新增generation及全部69384份保护文件内容。更新前输入/ZIP/RNG hash、真实Human运动、完整及partial剂量均保留。

补充路径检查发现固定GitHub的FETCH_HEAD在本轮时间段更新，属于启动清单明确排除的.git元数据；已查启动至19:31工具调用无fetch，来源未确定。当前固定HEAD仍1adb1de177d6f5f32de6d01c4e629cbfae9ce121，工作树干净，没有为隐藏元数据观察而删除/回退文件。Git元数据与科学源码/原checkpoint保护范围分别报告，最终仍完整核验。

阻碍保持独立：合法独立物理初态BLOCKED、G4严格自然极端/全矩阵未闭合、新PPO原同父prefix/B/H150 live matched缺链。它们不阻止当前受控nominal开发，但Stage2/最终Campaign仍NOT_READY。UTC04:07:04后不启动训练，04:52:04停止全部owned计算；最终9–10小时完成二十问、原始证据复核、进程退出和manifest封存。不自动启动下一包或正式Campaign。
