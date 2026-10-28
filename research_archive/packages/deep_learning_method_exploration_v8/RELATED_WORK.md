# 原始文献与本轮迁移边界

已读文献、合成数学校验、项目内最小实现和原作者算法复现分别记账。本轮没有把论文成绩当作iHEAR证据，没有下载并运行公开作者仓库的完整训练系统。以下链接为原论文或作者实现；具体方法证据仍以本包实际数据、源码及checkpoint为准。

|来源|本轮采用或检验的具体机制|未获得的结论/剩余前提|
|---|---|---|
|[Schulman等，PPO，2017](https://arxiv.org/abs/1707.06347)|固定采样old probability、ratio/clip surrogate、多epoch对同批样本；离线表诊断与真正新rollout更新严格分开|单次OUT0完整recipe策略不等于原多步机器人PPO；RF1/PPO3的强度不同，clip不是安全证明|
|[Ross等，DAgger，2011](https://proceedings.mlr.press/v15/ross11a.html)|检查教师质量与学习策略诱发的状态覆盖；另做合格教师BC及新context聚合|OUT0外生context聚合不是原生多决策DAgger；尚未闭合旧native动作接口与后续状态纠错|
|[Christodoulou，离散SAC，2019](https://arxiv.org/abs/1910.07207)、[作者实现](https://github.com/p-christ/Deep-Reinforcement-Learning-Algorithms-with-PyTorch/blob/master/agents/actor_critic_agents/SAC_Discrete.py)|有限菜单精确动作求和、双Q、熵目标和合法offpolicy回执；终末决策Q目标为真实完整任务reward|终末单决策没有未来bootstrap；必须和同Q greedy/softmax比较，不能将actor蒸馏增益预设为SAC独有能力|
|[Haarnoja等，SAC算法与应用，2018](https://arxiv.org/abs/1812.05905)、[官方softlearning](https://github.com/rail-berkeley/softlearning)|温度单独控制熵；自适应温度与固定温度需分列；离散正entropy target不能照抄连续域的负维数目标|本轮未复现原连续SAC系统；合法一维Beta动作上的policy gradient也不冒称连续SAC|
|[Burges等，RankNet，2005](https://www.microsoft.com/en-us/research/publication/learning-to-rank-using-gradient-descent/)|同真实父context内完整候选pairwise偏好，检验绝对成本误差与决策排序差别|相关pairs不增加独立父状态；排序模型不提供task/motion资格或净物理效率|
|[Ernst等，Fitted Q Iteration，2005](https://www.jmlr.org/papers/v6/ernst05a.html)|区分完整Monte Carlo剩余成本监督与真正(s,a,r,s') Bellman迭代；后续policy标签保持条件身份|当前有限完整recipe库不足以验证任意后续动作的TD/FQI；换网络不能补足反事实覆盖|
|[Bristow等，ILC综述，2006](https://doi.org/10.1109/MCS.2006.1636313)|上一真实完整Trial误差投影、两种增益、累计限幅及history-disabled；实际同对象boundary生成下一轮|该投影不是已识别的力梯度；人机非平稳与混合admission不满足简单LTI重复系统的收敛前提|
|[Gelbart等，未知约束BO，2014](https://arxiv.org/abs/1403.5607)|JF、JM和原motion分量分别建模；同父相对H150响应；收益与可行性分开选择|三点及模型spread不是校准安全概率；本轮拟议多模型保守一致门不是原论文完整采集函数复现|
|[Sui等，SafeOpt，2015](https://proceedings.mlr.press/v37/sui15.html)、[作者代码](https://github.com/befelix/safeopt)|明确已知安全起点、未知区域与候选收益的区别，保留原guard并计探索负担|当前没有可靠RKHS/Lipschitz界或置信区间覆盖率，不能继承安全探索理论保证|
|[Krause与Ong，Contextual GP Bandits，2011](https://papers.nips.cc/paper/2011/hash/f3f1b7fc5a8779a9e618e1f23a7b7860-Abstract.html)|history×action交互与相加history项消融，直接检查选择是否改变|context只能由合法因果历史产生；稀少虚拟条件与漂移不支持一般regret或个体化结论|
|[Chua等，PETS，2018](https://arxiv.org/abs/1805.12114)|先诊断absolute/kinematic/residual/history动力学与自由rollout、动作响应，再决定是否投入世界模型优化|本轮36次ridge诊断未实现PETS概率ensemble/trajectory sampling/CEM；低一步RMSE不构成可用planner|

完整文献核验与推荐最小可证伪实验见[A家族](families/critic_value/RELATED_WORK.md)、[C家族](families/history_conditioned/RELATED_WORK.md)、[离散SAC](families/il_dagger_sac/discrete_sac_v1/LITERATURE.md)。C家族另核对人体在环BO，但健康行走代谢任务不能直接替代被动康复JF/Human仿真。

Potential-based shaping、多决策TD/DAgger、复杂神经world model及其梯度控制仍为NOT_RUN或NOT_TESTED。SuperMimic未复现，未把其人形动作跟踪结果升级为iHEAR硬件、临床或控制资格。公开方法提供的是待检验机制，最终结论由原完整任务与强对照决定。


本轮另核对 [Ahmadian等，ACL2024](https://aclanthology.org/2024.acl-long.662/) 的 [RLOO公式，§2.3](https://arxiv.org/html/2402.14740v2)：同context下其他独立draw的reward可作当前draw的baseline。迁移的是这一信用分配机制；GateL仅对四个已付费样本做固定行为策略的离线诊断，未复现其LLM系统，也未证明机器人上的方差、效率或控制收益。全批均值与LOO的梯度期望比例为本轮另行推导，有限批方向不同不能推广成期望方向错误。


## 共享更新的跨条件干扰：相关机制与本轮差异

Yu 等 NeurIPS 2020 的 [Gradient Surgery for Multi-Task Learning 原论文](https://proceedings.neurips.cc/paper_files/paper/2020/file/3fe78a8acf5fda99de95303940a2420c-Paper.pdf) §2.2–2.3/Algorithm1 讨论共享梯度的冲突，并提出在冲突时向其它梯度的法平面投影。可迁移的是分解局部与跨条件更新、检查是否被共享更新抵消的诊断思路。本文同时指出负内积本身不足以证明优化受损。

本轮 GateK 实际证据来自旧四行的解析分解；GateG 是对已冻结两条件 feature span 的 K⁻¹D 预条件及共同范数缩放，不是 PCGrad 复现，不使用其随机任务顺序/投影规则，未验证其高曲率条件或论文经验收益。本轮新条件的运动资格、强基线增量和效率必须由原物理/scorer另行判断，不能由该文结论转移。PCGrad 的正式复现仍 NOT_RUN。
