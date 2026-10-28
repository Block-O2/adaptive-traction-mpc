# 决策相关公开研究

四项原论文/官方实现深入记录见[详细审查](literature/DECISION_RELEVANT_LITERATURE.md)，逐项含作者、问题、算法/假设、数据/计算和评价条件、项目联系、可借鉴/不可迁移部分与最小验证建议；固定链接/代码commit见[来源登记](literature/SOURCE_REGISTER.json)。均为READ_NOT_REPRODUCED，不把论文性能计成本项目结果。

|原论文及主来源|论文事实范围|本轮具体启发和边界|
|---|---|---|
|Mandi、Bucarey、Mulamba、Guns，Decision-Focused Learning: Through the Lens of Learning to Rank，[ICML2022](https://proceedings.mlr.press/v162/mandi22a/mandi22a.pdf)、[作者仓库](https://github.com/JayMan91/ltr-predopt)|候选排序服务下游优化，有原可行解集合假设|SUPPORTED（应用解释）：先找强规则外排序缺口。本轮历史身份去重、相对完整响应拟合及真实执行；非论文算法复现，不用未来qualification mask|
|Rosolia、Borrelli，Learning Model Predictive Control for Iterative Tasks，[原文](https://arxiv.org/html/1609.01387v7)、[作者实现入口](https://urosolia.github.io/jekyll/update/2021/08/06/MPC-Part-II.html)|已成功迭代轨迹构造终端集/成本，保证依赖原假设|SUPPORTED：完整可执行后缀/continuation须绑定身份，partial不作成功排名；LMPC本轮NOT_RUN，原safe-set论证不授予本混合非线性任务安全资格|
|Kim、Ding、Malcolm、Speeckaert、Siviy、Walsh、Kuindersma，Human-in-the-loop Bayesian optimization of wearable device parameters，[PLOS2017](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0184054)、[官方数据](https://biodesign.seas.harvard.edu/data/kimPLOSone2017)|健康行走条件下人体闭环参数优化，有真实测量费用|SUPPORTED：标签不免费；本轮冷父/失败/partial/开发/验证全计，不能回放全菜单称省试。新连续BO NOT_RUN，原人群不迁移为患者证据|
|Liao、Shao、Long、Zakka、Horowitz、Abbeel、Sreenath，SuperMimic，[原论文](https://arxiv.org/pdf/2610.28480)、[官方项目](https://supermimic.github.io/)|动作条件WM、短期展开与匹配策略Critic；本轮未核验到可运行官方训练仓库|SUPPORTED：短模型与tail价值须绑定实际后续policy，cost regressor不改名Bellman Value。WM/BPTT本轮NOT_RUN，机器人结果不是iHEAR/硬件/患者结果|

**CONFIRMED（项目）：** GP/二次面同选、前瞻JM符号错；传统组合更好但SS迁移反转。因果stump相关性未超常数B。这些实验支持强调真实决策价值和强简单对照，不为文献清单扩大复现。

**HYPOTHESIS：** 未来若有强固定/解析规则未覆盖、因果可辨的跨状态合格排序，再考虑相对benefit模型或匹配continuation的value。建议不自动产生下一轮、训练或物理队列。原论文事实、Agent解释与本项目证据保持分层。
