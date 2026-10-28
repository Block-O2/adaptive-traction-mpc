# B/D离散recipe离线研究结果

CONFIRMED：本轮完成真实的参数优化和冻结argmax接口验证；数据均为v7已执行历史表，没有新增物理、环境构造、fresh on-policy rollout或患者泛化证据。模型是**线性softmax**及常数策略，并非深MLP；PPO使用离散clipped surrogate，不能把这些表优化称旧41D PPO续训。

## 数据、训练与身份

使用critic_value的`HISTORICAL_RECIPE_DATASET_V2.json`。它有6个已暴露OUT0 commissioning context、45原轨迹；本试验只用跨全部6context真实存在的3个完整recipe，合计18个独特context×action标签。两H150候选在3context原合格、3context不合格；失败与partial仍在总库，未按低成本剔除。本试验的18条都完整，但6条未过原运动等资格。actor只用原commissioned25，QA33与完整77D INVALID保持；case/父/未来结果仅为分组和评价metadata。

原始JF单目标、同目标gain20尺度、JF且JM不增、JM单目标，分别训练BC/RF/PPO、常数/linear25、全开发及6个leave-one-parent-context-out，共168个小fit。一次schema-only预检0拟合失败已保留；producer的V2文件名保留v1 schema字符串，修复后逐字段核验完整底层recipe，输出新目录，不覆盖旧失败。

已完成训练耗时14.466秒，CPU14.465秒：599,328个policy forward、391,680个手工梯度样本等效backward、31,360次手工参数更新，**Adam=0**。这些不是168个独立数据集或168个新物理实验。之后冻结API复核24模型×6context再144 forward，0backward/update。总计forward599,472；真实新物理/新on-policy均0。全部checkpoint、RNG、每update梯度norm、输入SHA、PID/start ticks及START/END存于`offline_fit_v2/`，两家族ledger按模型归属只计一次。

## 六context开发交叉验证

|训练目标/方法|原合格context|合格轨迹ΔJF总和 N·s|合格轨迹ΔJM总和 N·m·s|说明|
|---|---:|---:|---:|---|
|qualified-JF raw，linear BC|6/6|−79.6276|+11.5051|两context选择early H150；不是双成本改善|
|qualified-JF raw，linear RF|6/6|−71.0275|+11.0890|两context选择late H150|
|qualified-JF raw，linear PPO|6/6|−71.0275|+11.0890|与RF同选择，不证明PPO增量|
|qualified-JF gain20，linear PPO|4/6|−79.6276|+11.5051|两个不合格结果保留；本栏成本仅合格子集，不能直接与6/6组排名|
|最佳训练常数B|6/6|0|0|在当前失败floor下是最优常数|
|训练选单层if|5/6|−37.6772|+5.0666|一个原不合格，表明all-dev拟合不能代替冻结迁移|
|25D nearest teacher|3/6|−37.6772|+5.0666|三个原不合格，不能拿其弱结果代替全部强传统|

六个context全部在v7已暴露，LOCO只是开发交叉验证；各合格子集成本总和是描述性合计，不是总体效果、统计稳健率或独立患者数量。控制层收益须由主Agent在新冻结context通过原完整物理与motion评价后另授予。

JF+JM不增及JM单目标的最优teacher都是6/6恒B。BC和多数constant模型复现B；部分linear RF/PPO仍输出H150、付出JM代价，这是当前有限优化/表示反例。没有“学不到任何目标信息”的证据，也没有额外JM改善可供当前菜单学习。不得因这一菜单缺收益就否定其他动作表示、连续合法协调、旧41D分组clip或整个方法家族。

## Reward机制与未识别原因

qualified-JF raw的合格reward在[0,.0267095]，不合格floor=-1。初始均匀策略在18历史标签上的解析梯度分解：原不合格floor norm=.314339，原合格reward norm=.007333，倍率42.87；gain20后后者=.146659，倍率2.14。它确认尺度差异会影响初始优化权重；scaled PPO开发资格反而4/6，故不能把floor主导当成所有部署失败的唯一根因，也不能认为放大奖励必改善。

每条不合格结果仍原样保留。独立JM门、原motion、task时长与强传统参照没有改。`force_with_JM_nonincrease`的输出字段`feasible_reward_range`包含原合格但额外JM约束失败的−1；应按其独立原因读取，不能将它们当完整可行奖励。

## 冻结部署与下一步

`offline_fit_v2/DEPLOYMENT_API_FREEZE.json`冻结24个全开发模型、简单规则及API源码。checkpoint为封套，部署仅用`document['policy']`；其余RNG/trace/evaluation不是actor输入。`select_out0(policy, feature_names, commissioned_values, qa_validated=True)`只做argmax并返回完整recipe SHA、proposal_action和底层candidate；原资格授予始终False。144次回放逐项复现，QA=false、错序、NaN均拒绝，模型/输入字节不变。

最佳常数为B；all-dev if使用feature24的训练阈值−.00052548563639965，左B、右early H150；这是拟合结果，尚无因果解释。nearest按训练context归一化25D距离选teacher，tie固定训练顺序。三者与模型规则在新结果前统一冻结。

主Agent计划把同一完整recipe的selector预测先锁定，再只执行一次物理供各selector共享评价。这能验证冻结选择与完整控制效果，但不是多个独立rollout，也没有实际省试的证据。fresh on-policy需要另外批准、真正按当前policy采样完整物理任务、保存old logprob/原资格/实际动作，并冻结新验证；本报告没有借旧表更名。

家族结论：**NOT_FULLY_EXPLORED / 独立控制收益尚未授予**。保留线性资格条件选择的开发信号、scale反例与JM恒B负诊断，等待新冻结物理验证；不把168个fit数量冒充机制充分覆盖。
