# iHEAR Lab — Motion-Constrained Counterfactual Dataset & Ranking Feasibility v1

终态：历史证据及dense运动审计完成；新增状态/分支阶段 **STOPPED_AT_RESTORATION_GATE**；真实host-replanning价值差 **NOT_EVALUABLE**。本轮完成研究交付，未训练或新增物理运行。

**唯一主要方向：D. 先解决监督目标或原生执行合同问题。** 已有数据能描述有限SCI committed后缀的force/运动权衡；完整state恢复、真实host continuation标签与合同转移尚未成立。不能直接开训v2，也不能只通过扩大网络容量解决。

## 三个核心问题

Q1：在原安全/任务资格下，已有13state的有限候选均有force获益；完整研究motion/fairness三档都只剩zero候选，获益0。仅运动负担与剂量诊断下还有有限机会，所以不能断言当前K3空间无解。三档profile不是临床阈值，阶段轨迹形状约束需进一步解释。

Q2：相同phase/mask/carry、精确相同三个共有计划的三个层均未出现ranking inversion，fixed regret0。含历史G-head扩展的cohort池里仅一snapshot有3.241335N·s固定排序损失；ordinary池13state损失均0；不同pool/phase best索引变化不证明真实state-conditioned preference。此为有限状态覆盖下有效负结果，不证明所有人体状态排序不变。

Q3：原remaining label按native integral可严格闭合，dense motion也已恢复；作为 **V_commit有限表排序** 标签可用。它不是已证明的V_replan host policy value，真实host同完整state数值差/排序差不可测；旧scientific rolling诊断的两处差值20.646403/0N·s已核验，见下节。没有可靠可恢复父状态或匹配host因果时钟，本轮停止该比较。

## 最新状态核验与新发现

先读取并核验b_fast_jitter_m2_host_v1、m2_host_generalization_attribution_v1和m2_neural_q_motion_v1 REPORT与相关原始source/DATA/trace/BRANCH_GATE。原6%–7%force收益、RETURN主贡献、固定mask线性Q公共state项相消、新MLP test9.9306 vslinear1.6207负结果保持原报告范围；旧R2/strict55 FAIL未改。

新发现：原80合法branch的runtime_artifacts gzip仍有约0.25ms native qpos/qvel，上一包只导出5ms auxiliary label。本轮从这些原证据恢复全部80条dense真实运动，无任何physics rollout。每条验证人体列映射与sensor共同节点、严格递增native时间及同snapshot fork前q/dq完全一致。原13个snapshot仍只有4个source group，公共causal context round4为12个，不增加统计独立性。

原snapshot JSON是process-scoped fork摘要，数组/MuJoCo integration/长历史只有hash，opaque handles只能活进程fork复制。15个保存snapshot文件（13个cohort使用state及原排除）没有durable可恢复checkpoint，也无原父进程。阶段C不满足门限，新增branch attempts **0/30**；没有重建plant或persistent Human，也没有近似replay/拼接状态。

积分闭合使用fork时TASK logger区间 **包含边界** 的原始成本记录；不能用运动导数去重索引对区间cost求和。原终值减prefix与首value_row一致，重算最大误差 4.372623152e-09N·s。先前exclusive-boundary诊断差完整保留，并明确不是标签uncertainty；未修改原标签或历史trace。

## 当前ordinary池与历史G-head扩展必须分开

原80行cohort包含 **74条ordinary K3候选＋6条历史离线G-head候选**。后者是原诊断留下的K3表标签，本轮没有生成G计划或训练G/P。当前Frozen M2 ordinary池的13snapshot全部 **fixed selection regret=0**，均值/最大均0，mean zero−best=73.897398N·s。包含G扩展后的0.249333均值、1.620668历史test均值和3.241335最大值均保留，但唯一新增机会来自OUTBOUND的historical G_head_0（candidate6），属于候选覆盖扩展；不能将它说成相同ordinary池已经存在需state-conditioned排序才能获得的收益。

相同计划/mask/carry的三个共同池没有包含G-head，均保持fixed最优。完整motion筛查的结果对ordinary与G联合池都只剩13条zero；普通池是74→13、完整历史cohort是80→13。先前表格统一使用80行历史cohort，不能混淆分母。

来源独立性进一步受限：三个注册父轨迹为初始OUTBOUND slot零、+0.12、−0.12三种prefix；第四个来源是已暴露nominal M2的精确动作replay。所有80条model_hash与model_beta各只有 **1种**，所以没有跨model estimate排序证据。公共context round4有12种并非12独立人体；RETURN近乎相同的成本亦不能放大覆盖。

## 已存在的scientific rolling诊断：有限数值差可测

| phase | issued index | commit remaining N·s | archived rolling remaining N·s | commit−rolling N·s |
| --- | --- | --- | --- | --- |
| OUTBOUND | 2 | 989.427237 | 968.780834 | 20.646403 |
| RETURN | 1 | 511.657835 | 511.657835 | 0.000000 |

来自原DIAGNOSTIC_ANALYSIS_v1和060_v1...REPLAY_GATE；本轮重新核验原initial applied table与selected branch表完全相同、remaining=原终值−同prefix integral，原replay gate记录所有trace字段精确相等和causal context相等。OUTBOUND固定后缀高20.646403N·s，RETURN为0，已支持continuation差别不能忽略。全部为 **SCIENTIFIC_SIMULATION** 的已暴露历史诊断，不是本轮新增实验。

这个gate未证明replay接口/对象、完整RNG、lifecycle及host时钟等与原rolling进程的完整可执行state相同；它证明物理trace和可见causal context匹配。每个state只存在原selected action的一个rolling结果，没有其他candidate的rolling反事实，因此不能计算V_replan候选排序或用20.646403作为host偏差界。真实host同完整状态下的价值差仍NOT_EVALUABLE。本包没有重新运行replay；hash和重新计算在HISTORICAL_ROLLING_CONTINUATION_AUDIT.json。

## 运动剂量与排序

| 候选筛查 | snapshot | 有效候选行 | 有force降低机会的state | snapshot均值fixed regret N·s | 按父来源等权均值 N·s |
| --- | --- | --- | --- | --- | --- |
| unconstrained | 13 | 80 | 13 | 0.249333 | 0.405167 |
| original_physical_task | 13 | 80 | 13 | 0.249333 | 0.405167 |
| strict | 13 | 13 | 0 | 0.000000 | 0.000000 |
| moderate | 13 | 13 | 0 | 0.000000 | 0.000000 |
| wide | 13 | 13 | 0 | 0.000000 | 0.000000 |

八组历史host配对knee excursion增加1.109–2.834°，累计knee角位移另外增加 2.191321–6.706682°；最大最终knee位置差 0.687065°。这说明原目标与完成虽相同，中途实际运动剂量和轨迹并非完全相同。Moment integral不等于momentum，没有临床推断。

不加新motion约束的全cohort fixed mean selection regret0.249333N·s；按4个父来源等权0.405167；历史test2state1.620668；最大3.241335。state oracle额外机会限定于该有限pool且全cohort含旧训练/开发暴露；不能当作独立泛化估计。完整三档profile的67个非zero候选均被排除，13zero保留；0 regret仅来自单一可行选择。

负担单独≤10%/25%仍有5/6state获益；负担加幅度/累计量/端点/时间、去掉phase形状的诊断有4/5state获益（平均zero−best4.351452/6.210357N·s）。所有67非zero计划不满足完整profile的phase形状界。报告这一敏感性，不按测试结果扩大轨迹形状容差，不把该结果说成普遍空间无解。

## 最终八项判断

1. 满足本轮完整研究motion条件且降低J_F：**本有限cohort未发现**；较弱拆分条件存在小幅获益，普遍可行性UNRESOLVED。
2. 不同状态出现有实际收益的固定计划最佳变化：**匹配共同池未观察到**；原全池变化受candidate/mask不同影响，不能归因state preference。
3. 固定排序损失：当前ordinary池13state均为0；含历史G-head扩展的80行cohort中全13state均值0.249333N·s，父来源等权0.405167，原test1.620668，最大3.241335；匹配共同池及完整motion筛查损失0。
4. 状态条件化额外可获收益：ordinary池没有观测到；历史G扩展池的唯一3.241335机会首先属于candidate coverage，有限全池回顾差值等于上述regret；不等于可部署收益。相同候选共同池未见额外机会，host transport未测。
5. 平顺性与剂量要求会显著收缩候选空间；strict负担无force机会，10%/25%诊断仍有小机会，但完整profile均无收益。临床可接受性NOT_EVALUABLE。
6. 神经网络数据充分性：**不足**。80rows≠80独立状态，13snapshot/12公共context/4来源group/同一Human，且RETURN状态多样性有限，没有新独立父状态。
7. Commit/replan合同一致性：**未成立且不能默认相同**；历史SCI滚动诊断OUTBOUND高20.646403、RETURN相同，真实host差值NOT_EVALUABLE；fixed residual suffix仍由B规划物理segments，host持续candidate替换、carry/expiry/admission与时钟机会不同；数值差NOT_EVALUABLE。
8. 首要补充：可恢复完整state及明确continuation/执行合同，随后才是独立来源数据与受运动约束的合法候选；没有证据要求扩大模型结构。

唯一建议D：先建立可验证完整状态fork与明确定义的监督/原生执行合同；保留V_commit作为有边界的参考，未来同state比较V_replan后再决定是否收集v2训练数据。本轮不启动后续工作。

## 预算、保护与验证

保守start=2026-10-08 23:51:00 Asia/Shanghai，硬截止=2026-10-09 02:21:00 Asia/Shanghai。新增离线branch0/30、正式host-clock配对0、新Q训练0、G/P/online adaptation0。只做单线程、串行历史数据分析，无重型物理并行。未改变Windows/WSL RAM、swap、电源或调度，未终止无关进程。

所有新增代码/报告/派生只在独立包目录及其Windows副本。Git branch/HEAD/index/status/staged diff与历史8074文件保护清单在最终PACKAGE_VERIFICATION核验；没有stage/commit/push/reset/stash/branch切换。冻结旧linear/NeuralQ权重、B/controller/commissioning及所有历史source/data/report不覆盖。完成退出后过程与时间见PACKAGE_CLOSED.json。

命令依次为指定Python -B执行code/prepare.py、state_audit.py、analyze.py、ranking.py、decompose_gates.py、enrich_analysis.py、build_reports.py、refine_reports.py、verify.py；所有是新目录内数据审计代码，不导入plant执行模块。read-only probe脚本/日志也保留。没有独立子agent（默认单agent；没有另行指派审计者），报告生成后做分开的保护/证据校验；无科学参数修复，积分重算边界口径澄清保留初诊；初次机械校验的phase-count猜测错误（55/25，实际54/26）已按冻结原DATA核对修正，原FAIL及日志保留于derived_history，不改变样本或阈值。

核心文件REPORT.md、EXPERIMENT_PROTOCOL.json、MOTION_QUALITY_PROTOCOL.md/json、STATE_RESTORATION_AUDIT.md/json、COUNTERFACTUAL_DATASET_MANIFEST.json、COUNTERFACTUAL_BRANCH_RESULTS.json、RANKING_FEASIBILITY.md/json、COMMITTED_VS_REPLANNING_VALUE.md/json、PACKAGE_VERIFICATION.json；另有dense series/receipt索引、所有branch审计与字段说明。文件存在或机械校验PASS不能替代上述有限科学结论。

Canonical：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_motion_counterfactual_ranking_v1/REPORT.md。Windows review copy：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_motion_counterfactual_ranking_v1/REPORT.md。

STOP。无自动host实验、Neural Q训练、online personalization、跨Human泛化、实时/硬件或临床资格声明。
