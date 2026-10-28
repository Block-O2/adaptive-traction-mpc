# 下一轮 Reward 研究提案

本文件是尚未训练的假设。R0–R3定义保持历史身份；不按不同Reward总数值排序。成功身份、planner/certificate/admission、ROM/torque/clearance、真实任务目标和正式B/H150 scorer均固定。新Reward只读取已发生转移的causal observation和传感器积分；失败partial永不以低累计剂量晋级。

令p为原OUTBOUND/HOLD/RETURN potential，失败终末强制0；JF/JM为原5ms执行区间观测左积分，V为原online估计加速度代理。R1为2Δp + 20·success −15·failure −.0005ΔJF −.005ΔJM −.02ΔV；失败再补齐总代价floor15。

## 候选一：R4，先检验moment价格不足

公式保持R1，唯一目标变化为moment权重从`.005`增至`.020 / (Nm·s)`。失败floor仍15，但补偿成本必须用新moment权重重算。任意失败总回报为`−15−max(15,C_R4)−2p_initial`，不能因短失败成为高回报。Reward成功差距不构成未见路径保证。

动机：两父R1/60完整mean相对原050均JF略降/JM上升；独立phase复算定位为RETURN force下降伴随RETURN moment增加。R1相对H2的额外收益跨父不一致。四倍moment价格是一个预声明假设，绝不随结果做权重网格。

预期：完整等时任务JM降低，保持force与成功，不恶化knee tracking/RETURN overshoot。副作用：可能以更大force、较慢任务、更多拒绝或优势尺度/critic耦合换取moment下降；已有R3提醒总单位变化影响优化，必须报告KL、ratio、value/gradient及actor/critic漂移。

最小实验：先确定本轮STD支持的训练配置；从该配置下每父相同checkpoint分叉R1对照10集与R4 10集，2父×2Reward×10=40集。两分支使用相同初始完整policy/critic/Adam/RNG，无旧pending跨Reward混用；分叉前pending必须为空。之后采样轨迹允许分歧并逐份记录。若要延长至30集，另作有界批准计划，本轮不启动。

独立评价：每个分叉端点mean和stochastic开发各一次；候选锁定后两父各6条独立保留动作流（共12次）与开发分开。先看完整任务与原安全；再列时长、完整JF/JM、native q/dq/a/jerk、knee tracking、overshoot。仅同父同任务完整等时轨迹计算直接剂量差。开发筛选规则：两父mean均保留；R4须开发随机完成数不低于R1、两父JM均下降且各完整等时JF不增加超过1%，才优先于R1；1%是开发计算分配容差，不是科学/临床阈值。否则保留R1并保留R4反例。

失败/停止：普通任务FAIL保留证据后进入下一独立假设；R4两父mean均失败时不延长。任何实际安全、身份、receipt/未来truth泄漏、checkpoint损坏或不可控资源则全局停止。单个合法几何拒绝不等于实际碰撞。

## 候选二：R5，合法状态进度与停止误差的potential

设计：保持R1成本和终末项，将potential改为`Phi(s)=p(s)−0.10 E(s)`；`E=mean((dq_hat/[45,75]°/s)^2)+I_RETURN mean(((q_hat−q_start)/span)^2)`，所有量来自转移终点已经取得的online Human估计。p和目标定义仍是原合同。失败终末Phi=0，成功终末Phi=3（固定终末项归入显式成功奖励），gamma=1，奖励仅`2[Phi_after−Phi_before]`。新potential量纲归一化且系数预声明；不把phase switch重复计分。

动机：原min-progress potential给协调/停稳的信用有限，163 RETURN knee overshoot仍2.36°。希望在真实接近RETURN目标且减速时提供合法信用。拒绝本身不会虚构p或E改善；拒绝期间若旧已应用控制实际产生运动，其真实状态变化照实计入。绝不能用“提议将成功”“planner预测进度”替代已观测状态。

预期：RETURN overshoot、末端dq和knee tracking改善；副作用：可能鼓励等待、减速或让critic更难拟合；phase切换对E造成跳变，必须独立测试相同状态闭环potential总和为0、终末收益与失败floor正确。若改gamma，须重新证明shaping语义，不能直接沿用。

最小实验：在稳定探索/PPO配置上，2父×R1/R5×10集=40集，必要时共同延长至30；独立开发/保留动作流分离。尚未实现的E累计与独立Reward复算器必须先通过causal与闭环算例，才允许训练，不列入默认夜间自动执行队列。

失败/停止：成功保持下降或仅靠延长任务降低motion则不晋级；保留实际时长。普通分支失败继续其他假设，全局安全/完整性条件同R4。

## 候选三：R6，RETURN跟踪与causal平顺性增量成本

设计：R1加非负`ΔC = .02 Σ[(ddq_hat/[300,600])²平均 + .05(j_hat/[6000,12000])²平均 + .5 I_RETURN ((q_hat−q_start)_−/span)²平均]Δt`。q_hat/dq_hat仅来自已经发生的5ms online tick；ddq_hat用历史差分，j_hat用因果一阶低通后的ddq_hat历史差分（20ms时间常数）。首帧须从真实pre-TASK历史初始化，不填未来值或插值。分母为开发归一化常数，不引入新的硬安全/jerk合格阈值。成本加入失败floor计算。

动机：R1的online V不是native jerk；R2增加V权重没有一致改善实际jerk。需要区分估计噪声、实际平顺性与RETURN超调，避免只堆高加速度权重。

预期：native jerk和RETURN膝超调下降；副作用：差分噪声放大、估计器偏差、force/moment增加、任务变慢。必须用保存online tick离线先测代理与native jerk的偏差、方向一致性及对拒绝partial的行为，不能以代理变好替代native结论。

最小实验：causal代理单元验证通过后，2父×R1/R6×10集；固定所有滤波/权重，禁止网格。独立评价与R4一致，另报各父代理与native指标相关/分歧；跨父方向不一致不延长。由于实现与因果审计工作较大，列为第三优先，默认夜间队列只执行R4。

动作准入附近的协调参数化是另一个机制方向，不偷渡为Reward修改。若STD=.2仍有拒绝，应先保存状态/mean/clip/候选geometry反例，再提出保持原安全合同的参数化研究；不得放宽准入或把拒绝当作已完成进度。本轮不改变动作映射。

R4公式工程检查已完成：在52条历史保存的causal measurement上逐转移重放，与独立终末总式一致；失败均为负、potential闭环不能刷分、无已执行进度的早期失败为−30。见 `audit/R4_PROPOSAL_MATH_TESTS.json`。这仅证明算术与已有接口可用，零训练/新物理，不是R4控制性能证据。
