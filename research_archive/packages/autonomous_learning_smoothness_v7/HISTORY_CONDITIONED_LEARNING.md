# 因果历史与条件学习

**CONFIRMED：历史实施过History Value、ILC、BO与连续trial memory；本轮新增小型commissioning条件分类，没有连续患者trial更新或患者级验证。** 不能把某轮NOT_RUN写成全项目未实施，也不能把fork菜单当多个患者重复运动。

|历史方法|证据|增量限制|
|---|---|---|
|History Value ridge|源码、冻结hash、17维history×action特征CONFIRMED|V12/U14/U15报告收益.636836/.580099/.639314 N·s仅SUPPORTED，均选固定RETURN slot3−.3°，未超固定动作/H150；主要模型/labels/raw缺档|
|误差驱动ILC|实现CONFIRMED|有限正负性能SUPPORTED；U15/U16及T3有反向结果，无单调保证|
|约束BO|cost/motion/task独立估计及概率门源码CONFIRMED|三状态同选B，U16唯一改变后JF+.330361/JM−.096051，属取舍；关键raw缺档|
|连续kernel memory|过去反馈更新、后续admission代码CONFIRMED|报告仍同选H150、动作与收益增量0为SUPPORTED，不能补反事实标签|

[历史审计](agent_reviews/rl_history/HISTORY_VALUE_ILC_BO_AUDIT.md)和[可用性表](agent_reviews/rl_history/SELECTED_EVIDENCE_AND_AVAILABILITY.json)逐项列出缺档。既不抹去历史运行，也不升格成本轮独立raw重算。

**CONFIRMED（输入）：** OUT1 77D包含已发生observer/reference/wrench、commissioned有效模型、公开任务和过去历史；完整有效只限对应payload。原nominal有351 dynamics样本、11接受beta更新、351 residual更新，非纯默认先验。beta受先验、ridge、边界、平滑和限幅影响；accepted/rank不是无偏人体参数识别。geometry也不能拆分真实shank与cuff fraction。[因果接口](agent_reviews/causal_human_interface/CAUSAL_HUMAN_INTERFACE_GUIDE_DRAFT.md)。

**CONFIRMED（OUT0）：** 整体77D保持INVALID；beta11、有效geometry4、residual10与33项质量在commissioning已存在。与OUT1逐值相同来自commissioning_only在TASK冻结参数，非未来回填；observer/wrench仍更新。bound、rho1条件冻结、样本排除警告保留，未捕获参数更新时间仍UNKNOWN。[独立审查](agent_reviews/out0_context_scope/REPORT.md)。

本轮stump只取三个scalar：估计K1/K2均值和有效thigh length，沿用hash/来源/OUT0时点/accepted commissioning及QA，不读true case、隐藏物理或未来结果。三context不是三个真实患者，也不是完整77D新状态模型。

**CONFIRMED（实际拟合）：** 两stump在EARLYN/L/H三context真实训练、均3/3。原benefit定义为EARLY_H150完整原合格、JF<B、两关节native jerk各<B、力模长变化率<B，JM另列。数据提取与拟合CPU约.335秒；完整标签尝试全计费。[训练成本](agent_reviews/causal_stumps_v1/ACCOUNTING.json)。

**CONFIRMED（负结果）：** 交换K/D的两CF属于开发扩展；两B均合格。重型软K/D的H150原门失败，轻型硬K/D的H150虽原合格但髋jerk变差，两benefit均0；K/geometry各1/2，常数B为2/2。开发门关闭，未部署。[证书](freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json)。CFH真正前瞻仅K 1/1、geometry 0/1，K同常数B；CFL时间戳拒绝保持NOT_TESTED，回溯不能补成prospective。训练资格/benefit混淆由CF打破；K对资格2/2仅作解释。[诊断](analysis/STUMP_TARGET_IDENTIFIABILITY_DIAGNOSTIC_V2.json)。

**NOT_RUN：** CVNHS01/CVHNM01实际条件选择、连续trial更新、新History Value/ILC/BO。两future case与driver静态候选保留，case未安装，物理未启动，不因gate失败换状态或标签。单阈值有完全等效if规则，不能凭3/3训练准确率声称Learning增量。

**SUPPORTED：** context与激活时点确实影响资格，但现小模型未学到强固定/简单规则外完整benefit排序。后续须先证明跨状态排序缺口，保留B、H150、phase、同权限优化及等效阈值/近邻，再冻结独立合法状态。少次真实trial学习、累计尝试效率、患者泛化及临床结论均NOT_TESTED。
