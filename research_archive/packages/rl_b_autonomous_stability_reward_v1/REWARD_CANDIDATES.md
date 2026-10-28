# Reward 候选与晋级门

全部候选保持gamma=1、原41D actor因果输入、原2D动作和原物理/执行/任务合同。训练外层从已执行转移的合法传感器累计量计算Reward；原环境的R0仍独立保存和重算。奖励不读native truth、未来Human轨迹或隐藏测试结果。

令p为原任务连续potential（OUTBOUND 0–1、HOLD 1–2、RETURN 2–3），JF/JM为真实执行时间上已观测的force/moment左积分，V为原online Human状态估计的归一化加速度平方积分。V是可部署估计代理，不能宣称它等于真实Human平顺性；晋级必须另外读取实际native Human运动。

|版本|进度项|终末成功|终末失败|执行代价增量|机制|
|---|---|---|---|---|---|
|R0|5 Δp|+20|−10并补齐失败总代价下界1.5|0.0002 ΔJF +0.01 ΔV|原pilot_v3，严格对照|
|R1|2 Δp|+20|−15并补齐失败总代价下界15|0.0005 ΔJF +0.005 ΔJM +0.02 ΔV|减少暂态进度信用，相对强调完整成功，同时明确moment代价|
|R2|2 Δ(p²/3)|+20|与R1相同|0.0005 ΔJF +0.005 ΔJM +0.10 ΔV|更集中地奖励接近整链完成的进度，并加重online Human加速度代理代价|

失败终末potential置0；成功终末p=3。成功终末固定potential贡献是显式成功bonus，不声称不同终末身份之间严格policy invariance。R1/R2对标量p的映射分别为连续线性/二次函数；p沿用原phase估计定义，实际切换可因容差和估计值出现跳变，不假定数值严格连续。转移只计真实前后potential之差，不额外加重复phase切换奖励；gamma=1时闭环回到同一完整phase状态的Δpotential总和为0。所有项基于转移结束时已发生的结果，无未来信息。

失败终末补偿为 `−max(0, floor−已观测总代价)`，使失败总回报为`−15−max(15, C)−2P(initial)`。所有失败保留身份与partial积分；绝不把低partial JF视为任务改进。在30秒、force≤200N、moment≤60Nm且归一化估计加速度积分≤30时，R2总代价界为3+9+3=15，R1≤12.6。该估计代理界若超出只增加惩罚，仍不产生失败正收益。

R1/R2数学审查见`audit/RESEARCH_REWARD_MATH_TESTS.json`：重复推进/退回不刷potential；成功/失败与零/最大代价的12个算例通过。真实每次运行还按保存的因果measurement独立重算本候选总Reward；原R0、native/receipt、真实运动和force积分另外审计。

每版本先2seed×10训练集并各执行deterministic/sample冻结评价；若四次均无完成，不追加40集，而保存失败并做reflection。存在至少一次完成才按原seed共同延续至30集。此门仅决定开发计算分配，不是泛化或稳定性通过门。所有Reward使用相同不可变外部指标，不能比较不同Reward总数值来选优。

本轮新增三个主要候选R1/R2/R3。R2检验potential形状与更强online代理，R3检验实际单位耦合；均在对应反思后单独记录源码与审计，再运行有界训练。没有R4或无界尺度网格。

## 聚合PPO筛选段的共同更新合同

若稳定性选择采用H2，R1/R2的10+20分段只用于冻结/调度，不在10集额外强制更新。全局至少64完整transitions更新，29集留住终末余量，30集统一更新。完整pending数据连同policy/Adam/RNG按独立SHA保存并在下一段恢复；EFFECTIVE_CONFIG及不可变configs/REWARD_ROLLOUT_PROTOCOL_v1.json记录实际参数。无物理跨段测试证明连续30与10+20最终policy/Adam/RNG和全部计数相同。早期筛选被拒绝时，若有未更新pending，将明确保留并报告；它们是实际采样成本，不冒称已训练优化暴露。该修复不改变Reward公式或live H2语义。

## R1、R2共同三十集结果

R1/R2都从两个相同原050完整policy/Adam/RNG恢复，采用H2的LR3e-4、aggregate64配置；没有接在H2已训练030权重之后。各自10/30两父mean/sample共8次开发评价均完整，支持明确窗口内的名义保持。R1两父训练完成13/30、14/30，sampled=optimized为431/424、实际Adam各116；R2为15/30、14/30，450/424 transitions、120/116 Adam。末端pending0、0singleton、原4epochs。

|三十集mean对同父050|149 JF%|149 JM%|163 JF%|163 JM%|
|---|---|---|---|---|
|H2/R0|-0.454636|+1.079758|-0.199720|+0.351936|
|R1|-0.534922|+1.343022|-0.349395|+0.640773|
|R2|-0.471300|+1.189251|-0.354002|+0.690710|

以上都是完整19.03秒mean；随机轨迹时长不同，不计算直接剂量收益。163的R1/R2 knee tracking RMS为0.627587°/0.630518°，高于父0.580361°；R2两个关节、两个父的jerk RMS都高于R1。R2同时改变potential和V权重，不能把差异唯一归因于某一项。有限长保持优先R1的较简单linear potential与当前运动证据；R2保留为完整短窗口备选，没有被证明全面较差，也没有60集保持证据。详细七问反思为R1_REWARD_REFLECTION.md、R2_REWARD_REFLECTION.md。

R1/163的真实十集pending59条/4完整episode已连同fullstate恢复，与第11集新增24条严格按序构成83-transition实际更新。中间完整pending不是丢失数据，也不冒称已进入梯度。R1和R2两次真实恢复均有逐项核验。

## R3：R1所有项与floor统一除30，实际十集消融完成

30只来自abs(failure15)+floor15，尺度在打开最终动作流前固定。progress=2/30、success=20/30、failure=−15/30、force=0.0005/30、moment=0.005/30、V=0.02/30、failure_floor=15/30；全部项同除，不改变完整轨迹偏好。保留原050 critic与Adam单位，不重标定；PPO、gamma、任务、安全和std不变。它不是仅缩小returns的事后分析。

两父各实际10集，mean/sample四次开发评价均完成。149训练5/10、sampled172/optimized152、完整pending20、40Adam；163训练4/10、160/160、pending0、44Adam。各2次PPO.train/8epochs。十集没有额外终末flush；163第10集按原>=64阈值自然更新。149的pending20完整保存在010 generation，不能作已优化样本。

149 mean完整JF对父−0.279504%、JM+1.368140%；163为JF+0.325382%、JM−1.241229%。没有一致force收益或明确Pareto优势。真实运动亦有取舍，不延长到30/60，不把短筛选替代长保持，也不按较低value loss或约−1的失败回报晋级。全部真实结果见R3_REWARD_RESULTS.json，七问反思见R3_REWARD_REFLECTION.md。

四Reward的首80/77条物理输入、完整prestate、PPO超参和update AST逐项相同，每父各20实际Adam。R3的actor参数L2变化为R1的1.887/1.953倍，Gaussian KL却为2.576/0.230倍。单位会改变实际优化，参数距离不能代替函数漂移，单点joint-clip梯度也不能预测长期任务表现。没有分别隔离旧critic、GAE、joint clipping和Adam状态。证据见R3_CONTROLLED_UNIT_EFFECT.json及两个实际first-update审计。

R0–R2原定义和旧完整模块SHA4107426f…保留；加入R3后的完整模块SHAcd612934…对旧三版本输出逐项相同，见audit/R3_REWARD_ACTIVATED_AUDIT.json。每次job使用独立内容地址源码包，准确module SHA、配置、父checkpoint和恢复身份保存在各job与checkpoint metadata；不能只用当前磁盘源码代替历史导入身份。

## 继续保持与最终动作流的解释规则

H2/R0与R1的30→60是从各自真实030终末flush后的完整状态延长30集，不等同从050不作030 flush连续60。完整结果、样本/Adam成本及所有模式分别见RETENTION_H2_RESULTS.json、RETENTION_R1_RESULTS.json；文件未产生前不能推断结果。晚期mean失败会撤回该家族的一致保持支持，旧030成功不能覆盖。

最终只允许一对预锁checkpoint、四个未用动作RNG×两父。选择遵循在任何60结果前记录的FINAL_SELECTION_PROTOCOL.md，准确SHA在FINAL_FROZEN_SELECTION.json，全部八条结果在FINAL_ACTION_STREAM_RESULTS.json。它们是同一nominal物理初态的动作流holdout；打开之后不再调Reward/PPO/std或换候选。不是独立初态/患者泛化，也不是原B/H150 live matched资格。完整JF、JM、native Human motion和失败partial都按原不变口径保存；G4、Stage2和最终Campaign资格另列。
