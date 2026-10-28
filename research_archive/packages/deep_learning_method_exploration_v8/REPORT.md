# iHEAR v8：Learning 方法家族的系统探索

实验、独立重放与历史内容核验已闭合，最终封包状态以 END.json 为准。唯一 T0 为 2026-10-27 03:25:40 UTC，硬截止为 15:25:40 UTC；原时钟、物理模型、任务、guard、安全阈值和评分器未因学习结果调整。

本轮五个家族均完成了改变机制的实质探索，并完成两项原新参数条件的冻结评价。**在已测范围内，尚未建立超出强简单对照的独立 Learning 增量，也未证明净省试。所有整体方法家族仍标为 NOT_FULLY_EXPLORED。** 具体正面结果包括：合法状态可学习部分成本信息；奖励塌缩和共享更新干扰得到实际诊断；真实持续 ILC 改变参考并产生小幅力收益；完整时间域数据改善部分预测。它们均不自动通过更高证据层级。

评价保持原 19.03s TASK（OUTBOUND/HOLD/RETURN 9.005/1.020/9.005s）、measured wrench 范数的 5ms 左积分 JF/JM、未滤波 0.25ms native motion。JM 比值≤1.25的原资格门不是 JM 不增加；两个分量和全部运动失败单列。SCIENTIFIC_SIMULATION 的物理/科学资格与 host realtime、plan age、RSS/执行因果资格分开，后者未建立时不升级为实时、硬件或临床成功。partial 的11 hard已观测通过不等于完整TASK资格。

1. **哪些方法家族得到实质探索？**（CONFIRMED）

   A：Critic/Cost-to-go/Q/Value；B：PPO/Reward/Policy Gradient；C：History/ILC/BO；D：IL/BC/终末离散 SAC/Neural Q；E：学习辅助优化、直接轨迹与动力学诊断。每个家族有独立矩阵和账本，见 [总矩阵](METHOD_EXPLORATION_MATRIX.md) 及其指向的 families 文件。网络和超参数数量不代替机制覆盖。

2. **测试了哪些合理变体？**（CONFIRMED）

   A 比较完整剩余 JF/JM、相对收益、pairwise ranking、资格风险及原 45 margin，合法 25/33/39D、数据覆盖与新增 partial 风险标签。B 比较三动作离线诊断、五动作真正新采样、REINFORCE/PPO、gain1/gain20、parent/first/last、连续 Beta 缩放轴、失败奖励/余量奖励、全批 baseline/条件 LOO/上下文几何修正。C 比较 action-only、历史相加/交互/disabled、两增益 ILC、固定 ±.25 和六类分量 BO。D 比较教师与覆盖、旧/新归一化、树/nearest/神经 BC、同 Q 的 actor/greedy/soft-Q/温度/保守变体、原与精确 critic、matched linear/tanh16/ridge 及独立风险和物理成本头。E 比较动作盲/动作/上下文/paired 输入，短时直接预测、时间曲线、matched D4/DFull 与 ridge/MLP。

3. **哪些变体被修正、继续训练或独立验证？**（CONFIRMED）

   A1→A5 按目标、状态、覆盖和风险支持分别修正。真正 categorical PG 在原有限窗口内完成两轮提交，32 个 fresh policy rollout、16 次参数更新；未挑 best checkpoint。Beta 第一批完成 8 次实际更新调用但参数不变，第二批 partial 后不提交、不延长原时钟。私有余量奖励的 C/L/G 三种比较使用同四个旧行为样本，共 12 次私有步、72 次训练 forward、48 次 score，明确为离线反事实。SAC 对同一凸目标求精确解；Neural Q 完成固定三种子/目标/架构/训练长度设计。E2 在匹配时间点和初始化下更换训练时间域，修正真实部署外层 schema 前先做冻结权重 canary。所有原工程失败、实际物理成本和早/末端点保留。

   全部原模型、六个余量 mean 端点和持续程序先冻结，再打开两个原新参数条件。master 有 2042 个 artifact pins、7 个模型容器、49 个模型引用和 91 个程序引用；**这些引用不是 49 个独立训练模型或 91 次训练**。参数 payload 此前被结构校验读取，故不称字节盲测。六个验证作业复用两个条件，不能称六个独立患者。

4. **哪些失败机制得到证实？**（CONFIRMED，限对应证据）

   原 77D 缺字段，不能补零伪造；合法 commissioned25/KIN33/WRENCH39 保留各自来源。A4 的假可行从 6/48 降至 2/48，却增加假失败至 17 并降低开发主策略资格；风险头未校准。连续 Beta 首批 16 个完整样本全部运动失败、奖励均 −1，减批均值后 advantage/梯度/权重位移全为零；换成余量奖励恢复非零梯度。条件 LOO 仍会受共享特征跨条件更新干扰；旧四行核分解及范数匹配几何修正支持这一有限机制，不能推广为总体方差或泛化结论。SAC 精确目标下降约 98.17%，控制选择仍不如原 actor，说明优化不足真实存在而非全部原因。E2 matched 时间域修正改善预测，不能证明可合法闭环优化。

   工程层面，原非 B 配方在重载新条件触发 `KNEE_REFERENCE_MUST_BE_CONSTANT`；11 项已观测 hard 条件通过仍不等于完整任务。partial 不作完整 JF/JM 排名。Beta 第二批父前缀还有 commissioning 人加速度、session clearance、active sleeve gap 三个 UNKNOWN，原外部 pending/RNG 保留，不取消、不提交、不冒称安全通过。

   新条件的另一次固定算术诊断使用原保存的两组 pre-B 25D 和全部六端点，不读取新 TASK 成本：两个新输入相对旧二维训练 span 的残差平方比分别约 .58455/.71693；各 head 的实际权重位移几乎全在旧 span 内。Geometry−LOO 的已存均值差在新重载为负、轻载为正，一阶分解与原 logits/mean 对齐。该结果解释这个线性更新设计如何传递，不是风险概率、收益预测或所有新条件同向改善。实际111次26D dot、48次2D dot、14次2×2 solve及12次显式双head线性投影等价另计，0新非线性mean/learner API/fit/RNG/physics。

5. **哪些方法学到信息却没有改变决策？**（CONFIRMED / SUPPORTED）

   多个 SAC、soft-Q 和历史模型改变预测分数但仍同选；早期三动作 frozen RF/PPO/BC/history 在四 stock-case 同为 B/H/B/B，简单规则可匹配。E2 DFull paired 在十个开发 case 全选同一 EARLY_H150。新轻载中 categorical 四臂的 parent/first/last 全选 B。A4 新两条件都回到 B，2/2 合格但无增量。学习数值信息与条件化控制价值必须分开。

6. **哪些方法改变决策却没有改善完整任务？**（CONFIRMED）

   A1/A2/A3/A5 的冻结 JF 主选择在两个新条件均未合格：重载 partial，轻载 EARLY_PHASE 完整但加速度 p95 失败。BC 新归一化变体同为 0/2；**预登记 BC 主法是 OLD_NORM，实际 1/2**，轻载选固定 EARLY_H150。原滚动面板曾把 NEW_DEV_NORM 当主法，已由精确 fit manifest 和两份原 helper 的逐行回执更正，原证据不覆盖。Neural Q 最终固定 E200 主法三种子各 1/2；早期 E0/E25 的 B/B 2/2 不能在结果后替换最终主端点。E2 DFull paired raw 1/2，加入 A3 risk 的变体反而 0/2。

7. **哪些方法超过强传统基线？**（SUPPORTED：尚未建立）

   没有建立独立强基线增量。轻载原 B 为 JF 1360.417482 / JM 95.666539；固定 EARLY_H150 为 1323.213957 / 101.447711。原 Beta 全部 12 个逻辑均值均为 λ=.5，共用一个付费候选，1333.056546 / 100.645502；它们较 B 降 JF、增 JM，JF 仍弱于固定 H150。六个余量端点各自付费且全部合格，JF 1333.008642–1333.058951、JM 100.645455–100.649225；固定半轴本已合格，没有资格率提升。

   真实持续第三 Trial 的轻载 H150 为 1323.983165 / 101.781536；ILC gain .25 为 1323.902035 / 101.791027，gain .1 为 1323.950724 / 101.785330，disabled 为 1323.786407 / 101.804330，固定 −.25 为 1323.510984 / 101.836060。ILC 有小幅降力且增力矩，但未超过强固定降力；disabled 也比 enabled 更降力，不能归因于历史学习独有价值。

   BO 须单列目标：实际冻结 V2 新提案要求各模型相对 H150 的 ΔJM 上界不增加，比原资格相对 B 的 JM 比值≤1.25更严；还须在保守 JF 上超过已测最佳固定点至少 .01，并通过预测 motion 余量。两个未尝试点 ±.125 同时未通过这三项存储门，故 ABSTAIN，0新候选。JM 门并非唯一原因；未执行点不能标为实际 motion 失败，也不能把这次弃权与允许 JM 取舍的 ILC/固定臂作同目标优劣排名。详见 [原合同/存储决定澄清](families/history_conditioned/audit/CONVAL02_BO_ABSTAIN_OBJECTIVE_CLARIFICATION_V1.json)。

8. **哪些方法在独立状态保持收益？**（CONFIRMED 事实；广泛泛化 NOT_TESTED）

   对事前冻结的早期三动作 RF/PPO/BC/history，四 stock-case 为4/4合格，相对B合计 ΔJF=−42.412107、ΔJM=+6.122961；相同简单选择也能做到，未立 Learning 独有增量。这些轨迹后来参与 A2以后等方法的训练，因此不能继续当作这些后训练模型的独立测试。

   两原新参数条件提供真正冻结后的物理证据，结论如下。它们不是独立患者样本统计，也未覆盖临床或硬件。

   |预登记/固定方法|重载 heavy065|轻载 light035|两条件解释|
   |---|---|---|---|
   |B / A4 margin 主法|合格 B|合格 B|2/2，无 B 增量|
   |A1/A2/A3/A5 JF 主法|原 partial|EARLY_PHASE 运动失败|各 0/2|
   |BC OLD_NORM 主法|原 partial|EARLY_H150 合格|1/2，与固定 H 同选|
   |categorical 四臂 parent/first/last|按各原选择保留失败|全部 B 合格|各 1/2，轻载无 B 增量|
   |SAC actor / V7 gain1 greedy|未合格|B 合格|各 1/2|
   |Neural Q tanh16 RETURN+riskON E200，三 seed|原 partial|B 合格|每 seed 1/2|
   |E2 D4 paired raw / DFull paired raw|原 partial / 原 partial|失败 / H 合格|0/2 / 1/2|
   |六余量 mean 端点|六个 pre-B 推理返回，H gate 后 TASK NOT_RUN|六个各自完整合格|不是六个独立条件；不超过强 H 的 JF|
   |冻结 C4 持续程序|T2 H/zero partial，后续 NOT_RUN|14 TASK 全完整合格，2 boundary，ILC 有小幅作用，BO 弃权|程序验证已运行；历史独有收益和稳健泛化未建立|

   完整菜单、153 个 pre-B 与 5 个 after-B 选择、12 个原 Beta 均值及 5 个轴映射在实际回执中逐项保留。元数据审计 PASS 不等于这些选择全部任务成功。两个原冷条件的成本图见最终 [motion/force/moment 报告](MOTION_FORCE_MOMENT_TRADEOFF.md)。后续开发适用性与旧条件能力探针不增加此表的独立条件数，不转移旧模型选择或标签。

   **CONFIRMED：后验开发诊断单独闭合。** 这四组不增加原独立验证条件数，不更换原模型标签或主端点。

   |后验作业|实际付费child|完整/合格/partial|结果|
   |---|---:|---|---|
   |POSTAPP01 重载|5|5 / 1 / 0|只有B合格；四个新适用性配方完整但motion失败|
   |POSTAPP02 轻载|5|5 / 1 / 0|只有B合格；原三个合格非B启用新flag后变为motion失败|
   |DEVCAP01H 已曝光开发重载|7|7 / 1 / 0|H与五个固定λ完整但运动不合格；B合格|
   |DEVCAP01L 已曝光开发轻载|7|6 / 1 / 1|H/λ1/.25/.5/.75完整但不合格，λ0原断言partial；B合格|

   两个POSTAPP的B均与原同case/seed/prefix的B通过原全raw一致门。新非B每条回执实际记录一次RETURN5可选timing跳过；这仅解释本次实现路径，旧predicate未捕获处保持UNKNOWN。轻载原EARLY_H150为1323.213957/101.447711且合格，新配方为1323.251310/101.504235且excursion失败；不能将该启发式当作通用修复或替换原H。额外持续heavy程序因必要H运动资格不足保持SOURCE_ONLY/NOT_RUN。

   开发轴检查只支持“已测固定网格及旧已采样集合未提供合格非B支持”，不能证明整个连续域不可行。λ1是新付费raw重复，λ0不是B；轻载λ0实际新增68,140native步，原FAIL完整重现，完整JF/JM与motion为空，不以partial积分排名。四组原重放共28条已闭合记录均重现；详见 [原始汇总与SHA](analysis/OPTIONAL_EXPOSED_DEVELOPMENT_FINAL_V2.json)、[能力检查](families/ppo_reward/DEVELOPMENT_AXIS_CAPACITY_RESULTS.md) 和 [POSTAPP02独审](families/critic_value/analysis/postapp02_closed_metadata_review_v1/REPORT.md)。

   ![开发轴固定点的成本与资格](figures/DEVELOPMENT_FIXED_AXIS_CAPACITY_V2.png)

   红叉为完整但motion不合格；partial无完整成本坐标。独立导出 [PDF](figures/DEVELOPMENT_FIXED_AXIS_CAPACITY_V2.pdf)、[SVG](figures/DEVELOPMENT_FIXED_AXIS_CAPACITY_V2.svg) 和 [来源清单](figures/DEVELOPMENT_FIXED_AXIS_CAPACITY_V2.json)。原两参数冷条件图仍在 [motion/force/moment报告](MOTION_FORCE_MOMENT_TRADEOFF.md)，不与后验新recipe混合排名。

9. **是否减少真实物理尝试？**（NOT_TESTED / 未证明）

   最终共31个物理作业组、238个START/238个END、18,588,820新增native步，无未闭合物理条目或未知步数。覆盖清单分别为152个完整合格TASK ID、63个完整不合格TASK、14个partial TASK、6个boundary、3个无完整TASK评分的付费父前缀，0缺口；这些单位包括父任务和重复对照，不是独立policy/patient成功率。

   未建立同等控制性能下的净省试。多个模型共用同一付费菜单轨迹只避免评价重复，不能当作部署节约；训练、数据提取、推理、独立评分、失败和封包成本均需计入。最终 exact START/END、新增 native 及分项收据见 [资源账本](RESOURCE_AND_ATTEMPT_ACCOUNTING.json)。继承前缀和连续 boundary 不重复累计；全研究总 CPU/GPU 和全局峰值 RSS 缺完整遥测，保留 UNKNOWN。

10. **哪些范围有充分限定否证？**（CONFIRMED / SUPPORTED）

    已否证“失败奖励常数仍能产生本批非零 PG 梯度”“降低同一拟合目标必然改善控制”“预测误差下降必然带来个体化”“本例 ILC 比已测固定 −.25 更降力”“原门下 partial 可按积分排名”等具体命题。有限菜单、有限状态和固定端点的无增量是限定负证，不能扩展成整个家族失败。

11. **哪些方法尚未充分探索？**（NOT_FULLY_EXPLORED / NOT_TESTED）

    多决策 Bellman/TD/FQI、真正逐步 DAgger、完整连续 SAC、多方向连续策略、校准不确定性与安全探索、更多独立虚拟条件、复杂历史表示与高维 ILC、可合法滚动推理的长时模型和模型辅助闭环优化尚未完成。未实施分支为 NOT_RUN，已读论文不算复现。没有设置全局物理、episode、梯度或模型额度，也未因单变体失败终止家族。

12. **Reward、状态、动作与训练语义发生了什么变化？**（CONFIRMED）

    改动均隔离于本研究包：价值目标、合法状态子集、资格分量、奖励尺度/余量、三/五离散 recipe、标量 Beta 轴、覆盖和归一化、终末 actor/Q、风险与物理头、直接轨迹模型。原模型与任务合同不变。Beta 是标量密度，不是 18D 联合密度；λ0 不是 B。offline 旧行为、fresh on-policy、冷历史与真实连续 Trial 分账；终末 done=True 不称多步 SAC，OUT0 context 聚合不称真正 DAgger，条件轨迹模型不称已复现 PETS。

13. **文献提供了哪些具体迁移方法？**（SUPPORTED；复现范围以实际代码为准）

    [原论文和作者链接](RELATED_WORK.md) 支持检验 PPO 的采样分布/clip、多决策 DAgger 的访问状态覆盖、SAC 的同 Q/熵对照、ranking 与资格分离、ILC 的重复系统前提、约束 BO 的收益/可行性分离、PETS 的不确定性与 rollout 要求、RLOO 信用分配及共享梯度干扰诊断。GateG 是冻结两 context 核预条件的自定义有限比较，不是 PCGrad 复现；本文不继承论文的安全或泛化保证。

14. **下一轮优先什么？**（HYPOTHESIS / NOT_TESTED）

    先改善完整合格的可行动作支持及其资格预测，再检验比简单规则更有差异的决策问题。对 PG，区分原动作轴可行性、失败奖励信息和共享更新迁移；对 Value/Q，优先补全失败支持与独立风险校准，避免仅降 RMSE；对 C，保持真实持续 Trial 和强固定/disabled 对照，寻找历史能改变最优动作的条件；对 E，先证明合法长时推理和选择增量，再投入闭环规划。下一轮仍须先冻结预登记主端点和简单对照，不按本轮新结果挑 seed 或更换主法。见 [下一轮决策](NEXT_RESEARCH_DECISION.md)。

15. **长期日志和数据保护完成了吗？**

    **CONFIRMED：**最终对219,908个历史文件、105,969,234,540 bytes逐文件重算完整内容SHA并核对原元数据，0变化，保护PASS；不是仅做元数据扫描。初始journal 30,081 bytes和SHA固定，所有日志只追加，最终前缀证明另存 [日志核验](audit/JOURNAL_FINAL_PREFIX_VERIFICATION_V1.json)。31个执行组的模型/源码/config最终核验PASS，2,238个唯一文件重哈希，master及所有已执行job pins一致，0失败。见 [历史内容核验](audit/HISTORY_PROTECTION_FINAL.json)、[冻结身份核验](audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json)。原控制器、scorer、raw和checkpoint未覆盖。

16. **所有 owned 进程结束了吗？**

    **CONFIRMED：**31个物理supervisor均STOP且无survivor；最终核验415个已登记PID/starttick原身份均已结束，当前包关联研究process为0，元数据解析错误为0。另有125条旧元数据记录缺原starttick，保留UNKNOWN，不将其伪造为身份闭合证明；它们不是新增运行任务。当前有限封包工具的祖先进程单列，验证工具退出及原身份消失另由END/JOIN证明，不宣称覆盖全部OS进程。见 [最终owned审计](audit/FINAL_OWNED_PROCESS_AUDIT_V1.json)。

    Beta外部pending是封存数据状态，不是继续训练许可。未启动Stage2、硬件、正式Campaign、Git写入或下一轮。最终END在有限封包验证工具退出0并核验其原PID/starttick消失后写入，当前有限END writer由root收集退出后才回复。

证据层级需逐方法、逐范围解释。下表中的“合格”只指原完整任务/运动门；TASK_VALID 还要求预指定目标改善。没有任何层级因更低层通过而自动通过。

|家族|1 IMPLEMENTATION_VALID|2 LEARNING_VALID|3 DECISION_VALID|4 TASK_VALID|5 BASELINE_INCREMENT|6 GENERALIZATION|7 EFFICIENCY|
|---|---|---|---|---|---|---|---|
|A|CONFIRMED：合法子集/原回执；77D无效|SUPPORTED：开发排序/风险有信息，未校准|CONFIRMED：多目标改变选择|开发局部；新JF主0/2，A4为B无增量|SUPPORTED：未建立|两条件已实际测，个体化增量未建立|NOT_TESTED：净节约未证明|
|B|CONFIRMED：提交批次；外部批次UNKNOWN隔离|SUPPORTED：概率/梯度机制；零梯度批次不称学会|CONFIRMED：分布/mean变化|light mean合格；资格率与目标增量未立|SUPPORTED：未建立|两条件有结果/门控，均值仅一条件完整对照|NOT_TESTED：净节约未证明|
|C|CONFIRMED：真实连续对象与边界|SUPPORTED：历史/局部反应；force梯度未识别|CONFIRMED：非零reference|light ILC小降JF且JM增；heavy更新NOT_RUN|SUPPORTED：JF不胜disabled/固定−.25|冻结持续程序已测，稳健独有收益未立|NOT_TESTED：弃权不等于省试|
|D|CONFIRMED：BC/终末SAC/matched Q|SUPPORTED：覆盖、拟合和优化机制|CONFIRMED：部分改选，部分同选|新BC主/SAC/NQ final各1/2|SUPPORTED：未建立|两条件有限，旧开发LOCO不升级泛化|NOT_TESTED：净节约未证明|
|E|CONFIRMED：真实来源/schema路径|CONFIRMED：matched时间域预测信息|CONFIRMED：选择及risk组合改变|新DFull raw1/2，risk0/2|SUPPORTED：合格选择等于固定H|两条件有限，无个体化/模型闭环证明|NOT_TESTED：净节约未证明|

逐主法、seed、端点与准确状态见 [独立五家族审查](families/critic_value/analysis/final_scientific_consistency_review_v1/FIVE_FAMILY_SCIENTIFIC_REVIEW_V1.md)。BC 更正的原 manifest `/primary` 和 helper `/decision_alignment/choice_table/24` 等精确指针保留在其 correction sidecar 中，旧错误面板明确 superseded。

详细回执与限制见 [Critic/Value](CRITIC_VALUE_RESULTS.md)、[PPO/Reward](PPO_REWARD_RESULTS.md)、[History/ILC/BO](HISTORY_CONDITIONED_RESULTS.md)、[IL/SAC/Q](IL_DAGGER_SAC_RESULTS.md) 和 [学习辅助优化](LEARNING_ASSISTED_OPTIMIZATION.md)。
