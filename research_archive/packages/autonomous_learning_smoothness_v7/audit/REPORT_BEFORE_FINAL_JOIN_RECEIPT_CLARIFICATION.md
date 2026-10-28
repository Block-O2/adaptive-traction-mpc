# iHEAR 自主学习与平顺性研究 v7

**CONFIRMED：本轮得到有限条件下的传统优化进展，没有建立 Learning 超过最强传统方法的独立收益。** 名义配对传统组合在两个冻结prefix保留微小双成本改善，在short_segments反转；既有H150更早部署显著降低重型状态的jerk和wrench波动，但增加JM，轻型条件失败。所有负结果、partial和工程失败保留，没有更换失败测试状态、放宽motion/任务合同或以重复暴露结果制造成功。

本文件的科学结论已统一；最终封包结果以[END.json](END.json)及[PACKAGE_VERIFICATION.json](PACKAGE_VERIFICATION.json)为准。截至本报告定稿，研究已运行约7小时42分；最终封包实际总耗时见END.json的elapsed_seconds。唯一T0为2026-10-26 15:56:51.846771 UTC；物理科学实验于2026-10-26 22:51:35.449649 UTC结束（T+6小时54分43.60秒），硬截止2026-10-27 03:56:51.846771 UTC未重置。剩余工作只做证据与封包核验，不自动下一轮。

## 结果与四种结论

|方法/结果|方法有效|强传统外独立增量|计算/尝试效率|独立验证|
|---|---|---|---|---|
|传统TRAD_COMBO|CONFIRMED：同nominal OUT1相对phase ΔJF−.05499342、ΔJM−.01741937，原门及额外quality过|传统局部改进，不计Learning；B仍有更低JM、BLEND仍有另一权衡|全菜单执行，实际省试0；未证总计算优势|CONFIRMED：两固定prefix双降，SS两成本反转；非患者泛化|
|传统EARLY_H150|CONFIRMED：重型完整原合格，jerk/wrench显著下降|是原方法更早动作机会，不是新学习；JF与JM仍有取舍|无实际省试，单次wall/API差异不证明效率|开发Human/CF及固定SS菜单结果混合，不能声称通用|
|局部GP/quad|CONFIRMED训练和真实执行；完整双成本目标未成立|CONFIRMED：二者同选，未胜简单传统组合|局部GP/quad拟合及提案进程CPU约.131秒，不含标签采集；实际省试0，总优势NOT_TESTED|固定动作两prefix/SS均执行，JM目标均失败；条件state泛化NOT_TESTED|
|两个因果stump|CONFIRMED训练3/3；原完整benefit迁移未成立|CF开发各1/2，不及常数B 2/2；if阈值完全等效|数据提取与拟合CPU约.335秒，标签全计；未部署/未省试|仅CFH前瞻身份合格；CFL NOT_TESTED；原V2开发门NOT_MET，未来CV NOT_RUN|
|新PPO/长Critic/WM等|本轮fresh部署NOT_RUN|NOT_TESTED，历史Critic相对强phase增量0|无本轮实际省试结论|NOT_TESTED，不能用旧raw诊断替代|

## 用户要求的二十项回答

1. **实际耗时和规模（CONFIRMED）：** 28次有限supervisor执行，其中26次产生物理START、DEVPC01/HOLDSS01两次preimport失败为零START。170唯一START/170 END=26 cold parent+144 fork candidate；新增native 12,997,720步，继承前缀不重复计。144候选中78原合格、51完整原不合格、13物理partial、2完整raw但工程失败/无有效资格，全部保留不排名。[账本](RESOURCE_AND_ATTEMPT_ACCOUNTING.json)、[三批59+104+7不相交证明](agent_reviews/integral_audit/incremental_final_lstf_v3/THREE_SNAPSHOT_170_CLOSURE.json)、[分类协调](analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V2.json)。这些不是170个独立患者或完整冷启动episode。工程完整raw另列：DEVRC01_B的原物理资格已独立恢复PASS，但原worker工程失败和不排名保留；HOLDSS01_B属于HOLDSS02，缺原motion结论。DEVRT02_B在之后作业路径检查失败前已原合格，保持原资格，不把整作业判成功。

2. **最强传统与局部优化（CONFIRMED）：** 没有跨Human/权限/所有指标的统一赢家。原B低JM、phase强平顺性、BEST/REF025/ANT和H150权衡均保留。四时间/八路径速度扰动无双降；简单时间×速度组合得到上述微小双降。LS三路径、去T5/R4及四合法终端factor仍失败；未突破原factor≤1.5或motion .5°界。[完整基线表](BASELINE_AND_PAIRED_OPTIMIZATION.md)。

3. **真正训练或验证的Learning（CONFIRMED）：** GP五独立目标15核求解、二次面10次最小二乘、两个stump八阈值/极性目标评估。另有8个私有Adam诊断步骤，确实更新参数；0 fresh RL rollout、0新可部署PPO checkpoint，不能写成新on-policy训练。[方法审计](LEARNING_METHODS_AUDIT.md)。

4. **只读/分析/小型诊断（CONFIRMED/NOT_RUN）：** 历史PPO、Q/Value、ILC/BO、Critic及公开原文均有源证据审查；120 reward重放、梯度/一步Adam、两个历史PPO raw scorer桥接为实际离线诊断。新长Critic、Bellman Q/Value、WM/BPTT、LMPC、SAC/DAgger/约束RL、连续trial learning未实施，明确NOT_RUN。

5. **是否学到目标（限定CONFIRMED/SUPPORTED）：** GP/quad同父拟合含成本/质量信息，但前瞻JM符号错，微小收益不可靠。原三训练context的资格与完整benefit标签完全重合；CF将二者区分，不能确认模型内部学到资格机制；K对CF资格2/2不能替代原benefit1/2。历史moment reward有JM信息，不能把R4失败解释为reward完全无信息；旧Critic能纠正部分短窗排序。[标签诊断](analysis/STUMP_TARGET_IDENTIFIABILITY_DIAGNOSTIC_V2.json)、[RL报告](RL_AND_REWARD_RESULTS.md)。

6. **是否改变真实选择（CONFIRMED）：** GP/quad共享动作不同于已测中心，实际reference/physics改变，但两模型之间无选择差异。风险缓冲修订后均退phase。stump只做预测，实际selector未部署。旧Critic相对1秒short改变4/4，相对强phase改变0/4；更早H150是传统动作时点改变。

7. **是否改善完整任务和motion（CONFIRMED，有限）：** 共享GP/quad通过原门而双成本失败；传统组合完整原门与额外quality通过；EARLY_H150在重型通过且改善运动，但nominal/LS和交叉格有原失败或benefit失败。不能把低partial积分或资格单独等同全部收益。[motion/force/moment](MOTION_FORCE_MOMENT_TRADEOFF.md)。

8. **是否超过最强传统（CONFIRMED负结果）：** 本轮学习方法没有。GP与更简单quad同动作，传统组合更好；stump未超常数B benefit分类，且有完全等效if规则。只赢短窗、弱B或某成本并不证明全面超越。原qualified但额外quality失败的BLEND/B/H150权衡不删。

9. **是否减少真实物理尝试（CONFIRMED/NOT_TESTED）：** 仿真菜单全部实际执行，实际减少0；冷父、commissioning、开发标签、失败/partial全计。硬件实际尝试0，硬件省试NOT_TESTED。训练快与反事实“本可少试”不作为效率成功。

10. **独立合法状态或患者验证（CONFIRMED有限、患者NOT_TESTED）：** 两事前冻结prefix的native/causal/physical前缀互异并通过已知45 native过滤，仍同Human且future RETURN0也按预承诺变化。传统组合两例双降，SS反转；GP固定动作JM目标持续失败。SS工程失败已暴露B，14菜单事前冻结，恢复不算新状态。CF是开发包交叉，不是患者/IID；CFL prospective拒绝保留。两个未来CV未运行，不补写泛化成功。

11. **合理迭代后仍无独立价值（SUPPORTED限定）：** GP经同父二维重构、真实前瞻、残差缓冲和独立失败诊断，仍无强传统外选择价值；stump两种信息假设经交叉参数与资格/benefit区分诊断，仍不及常数B，gate关闭。该有限结论不等于所有Learning无效。PPO的两轮梯度/Adam诊断仅解释优化器，不宣称策略无效。

12. **继续投入证据（SUPPORTED/HYPOTHESIS）：** 更早传统干预的重型大幅运动收益、资格随context/动作变化以及完整目标之间差异，说明真实协调问题仍存在。先证明简单动作库/规则外剩余合格排序，才有新增学习模型价值；没有依据直接扩大WM/RL训练规模。

13. **Reward、动作、状态、流程变化（CONFIRMED）：** 实际物理评价未换reward/任务/原guard；新监督目标分列JF/JM/运动/wrench，原benefit不因失败改写。仅私有诊断比较联合/分组裁剪和继承Adam，不改历史checkpoint。执行动作测试合法x3/x5/x7、RETURN recipe和OUT0更早激活；OUT0只用三scalar目的子集，完整77D仍INVALID，QA保留；版本/模型/数据均独立SHA。[合同](EXPERIMENT_CONTRACT.md)、[接口指南](LEARNING_CONTROL_INTERFACE_GUIDE.md)。

14. **文献具体启发（SUPPORTED应用解释）：** ranking推动先检查真实相对排序；LMPC提示绑定完整可执行后缀；HIL BO强调标签真实成本；SuperMimic提示WM/Critic匹配后续policy。这些影响了身份去重、相对响应、continuation审计和计费，没有论文性能导入。[原论文/作者仓库、算法假设与迁移边界](RELATED_WORK.md)。

15. **确认与假设的失败原因：** CONFIRMED：真实动作别名/非别名、GP标签单位与符号正确、前瞻JM方向错、原motion/constant-knee失败、训练资格/benefit混淆、metadata时间戳拒绝。SUPPORTED：混合时序/曲率失配解释GP微增益不可靠。HYPOTHESIS：guard唯一中介、跨关节响应的单一物理归因、更多因果信息能否学习完整排序；未唯一识别，不补写因果证明。

16. **Learning定位变化（SUPPORTED）：** 从“修正短窗预测就会产生价值”收窄为“在完整资格、强传统和简单等效规则之外验证真实决策增量”。历史与本轮均有训练事实和目标信息，但与独立增量分开；传统已经解决的部分不强行包装学习。

17. **下一阶段优先事项（SUPPORTED建议，未启动）：** 保留重型早启传统方案与有限nominal组合，先整理context×动作的完整合格benefit/力矩取舍，确认简单规则未覆盖的排序缺口；RL若继续，先完成原fullmotion/ownership及同两fraction权限强传统桥接，再另登记fresh对照。不是继续微扫已暴露二维域，也不是自动扩大模型。[下一研究决定](NEXT_RESEARCH_DECISION.md)。

18. **长期日志：** 保留原24,862字节前缀并核验，只追加v7意图、转折与最终负结果/建议；最终append证据与SHA见PACKAGE_VERIFICATION的journal项。未重复v5/v6历史记录。

19. **进程结束：** 所有物理supervisor均STOP、worker已join、END无survivors；独立审计和有界Agent计算也有退出证据。最终元数据扫描及其自身tool-return外部退出核验见PACKAGE_VERIFICATION；不把当前写封包进程预先说成已退出。没有后续自主队列。

20. **历史完整：** CONFIRMED：204,641文件/93,289,584,051字节最终全量内容及原metadata核验PASS，62,049关键源码/checkpoint核验及无增删PASS。起始全量内容哈希约T0后30分钟获取，不冒称精确T0全量hash；T0后的metadata及早期critical证据另绑定。根日志按append-only单独核验，无Git写操作/Stage2/Campaign/扩容/硬件。

## 证据限制和科学停止

科学实验的原Human/robot/cuff方程、guard、HOLD/端点/ROM/torque/clearance/admission、原积分与motion合同保持。本轮共有六个实际case，其中两例为新增CF参数组合；新实例和新动作不自动继承原安全资格；科学仿真的HOST实时资格NOT_EVALUABLE，不升级为临床舒适或患者安全。

**CONFIRMED（metadata限制）：** 两零START preimport失败没有worker SOURCE_MANIFEST；解释器binary/path及完整实际loaded-module身份未独立证明。若干前台static/metadata操作只有tool退出回执；部分早期review没有原END/标准manifest，最终只能由当前主核验receipt承接并保留原缺失。一次600秒纯deadline修复分支实际624.61秒，24.61秒metadata封包超时，未增加fit/env/physics；如实保留，不称完美预算/PID合规。源证据、失败版本和修正版本均不覆盖。

**SUPPORTED（科学停止）：** 当前窄域模型已完成有区分力迭代、传统早启/简化/跨参数门及原失败状态验证，剩余扩大训练缺少强简单对照外的可验证排序前提；fresh PPO还缺公平完整桥接。停止本轮新计算的依据是这些有限科学/工程证据，不是第一批完成、额度担忧、固定次数或要耗满12小时。后续有价值研究写入NEXT而不自动执行；封包不完整时优先修复再STOP。

完整原raw、partial、原scorer重放、native指标、训练checkpoint和来源都在本包manifest中。标准可导出图见[科研图](analysis/figures_final_v3/README_zh.md)，所有主要结论按CONFIRMED/SUPPORTED/HYPOTHESIS/NOT_TESTED标注，未实施分支为NOT_RUN。
