# Critic、Value与长时域学习结果

**CONFIRMED（历史封存证据）：成本Critic能纠正部分短窗排序，却没有超过最强固定phase规则。** v6四个主prefix测试中，Critic相对1秒short改变真实选择4/4、原门4/4；相对强固定phase的实际轨迹改变0/4，平均额外JF收益0，全部菜单已物理执行，实际尝试节省0。本轮没有新鲜数据训练并部署独立long-horizon Critic、Bellman Q/Value、world model或BPTT分支；这些新分支 **NOT_RUN**。历史PPO自己的value网络确实训练过，本轮8个私有Adam诊断也实际改变它的参数，均在RL报告另账，不能写成零神经更新。本轮真实训练的二维GP/quad属于固定父状态的监督动作响应，不应改名Value。

本文件整合独立封存的历史/方法审计与主Agent最终核验；原独立审查的outcome cutoff保存在各自子包，后来结果不追认为当时已知。CONFIRMED/SUPPORTED/HYPOTHESIS/NOT_TESTED按证据深度区分；NOT_RUN不等于方法普遍无效。

**已真正训练或验证过什么**

|方法/证据|目标与信息|实际决策及完整门|强传统外增量与效率|
|---|---|---|---|
|v5成本Critic：CONFIRMED|RBF ensemble，主每phase16真实tail标签、两个父，另有冻结8标签版；预测指定B后续的remaining JF/JM/time/motion|RETURN完整tail排序较0.5s short好，约1.56 N·s收益；1s short和固定训练动作同选。OUTBOUND两版仍选失败SPEEDP|相对强固定选择增量0；没有物理节省。|
|v6修订成本Critic：CONFIRMED|126字段、物理尺度floor、已发生累计历史、分开的风险信息，匹配COMPOSE上游/后续|四主prefix原门4/4，相对1s short真实改变4/4|相对强phase轨迹变化0/4、平均额外JF=0；未展示复杂模型独立决策价值。|
|v6已发生风险头：CONFIRMED|1281窗口、12父族、3族有失败；24维causal guard/observer/wrench等历史|按整父族CV，TP18/FN32/FP14/TN1217；OUTBOUND12与HOLD6失败窗口全漏检|不是1281独立状态；不能替代原guard或完整motion门。|
|历史state ridge Q/early-value：机制CONFIRMED，性能SUPPORTED|单nominal Human六开发parent×四动作，七causal特征、rank5；不是神经TD|Q三测试状态都选H150；early-value三状态都退B|Q未超固定H150；early-value约34 N·s regret。部分权重/raw缺档，不能升格本轮独立复算。|
|历史History Value：机制CONFIRMED，性能SUPPORTED|17维ridge特征，四history量×action交互；三开发模拟Human×五动作=15标签|V12/U14/U15合格收益约0.636836/0.580099/0.639314 N·s，三次都选RETURN slot3 −0.3°；U16退B|未证明超过固定−0.3°或H150；不是患者级增量已完成。|
|v7二维GP/quad：CONFIRMED|一真实父、9动作，监督ΔJF/ΔJM与三个运动/力变化指标；15 kernel solves、10 least-squares fits，0Adam|确实fit并提出共享冻结动作；不是只读旧模型|同fork action-LOO不等于独立状态；本文件不将它计作长Critic或Bellman Value。|
|v7新long Critic/WM/深度Q/BPTT|NOT_RUN|没有新增该类训练checkpoint或闭环策略|有效性、强传统外增量、效率与独立泛化均NOT_TESTED。|

历史Critic/risk与raw复核依据：[历史总审计](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/history/HISTORY_AUDIT.md)、[机器摘要](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/history/HISTORY_SUMMARY.json)、[12条历史原积分复算](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/history/RAW_INTEGRAL_RECHECK.json)。历史Q/History Value：[专门历史审计](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/HISTORY_VALUE_ILC_BO_AUDIT.md)。v7GP真实训练身份：[冻结MODEL](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/models/LOCAL_RESPONSE_2D_V1/MODEL.json)、[TRAINING_ACCOUNTING](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/models/LOCAL_RESPONSE_2D_V1/TRAINING_ACCOUNTING.json)。

**为什么“预测较好”仍可能没有决策价值**

CONFIRMED：v5/v6已经做过合理修订，不是第一版失败就停止。v5常量时钟0.001缩放放大约15ms变化；均值查询干预虽降低误差仍选同一失败动作。v6加入物理floor、累计历史和负例后改善部分排序，仍没有超强phase；风险整父族CV仍有上述漏检。旧Critic“有用地纠正短视”成立，“具有独立增量”不成立，二者不能混写。

CONFIRMED：固定phase采用当前OUT1 HANDOFF、之后共同COMPOSE，并不是全程HANDOFF。Critic与这个强规则轨迹相同，因而把规则解释成模型特有行为不成立。全部候选完整tail已真实执行后再读Critic，不能重放候选顺序宣称省下未运行尝试。数据获取、原安全/任务判定和模型训练均有实际费用。[v6结果的封存核验与scope](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/history/HISTORY_AUDIT.md)。

CONFIRMED：O3微扰配置没有改变实际pre-fork物理、参考、observer、torque/belief历史，别名已用TAILOT/TAILRESCUE父；不能算新的独立失败修复。OUTBOUND PATTERN/HANDOFF也有实际动作别名。窗口、不同H、不同tag或配置hash均不能自动增加独立样本。这里只继承该历史审计确认，不把v7新prefix测试重分类成同一结果。

**Value标签必须包含后续策略与全任务历史**

CONFIRMED：v5标签绑定B后续，v6采用共同COMPOSE；两者不是无条件通用cost-to-go。B上游接COMPOSE后续时，v6 TRAIN_R1–R3的15个完整候选全部excursion失败，匹配COMPOSE上游后才恢复资格。原Human/robot/cuff动力学没变，任务历史与完整motion路径依赖却不能被一个短tail成本替代。

SUPPORTED：每条价值/响应数据应绑定真实父状态、截断时刻、截至H的累计成本/峰值/ROM、执行动作、continuation代码/参数/guard记忆和完整结果。只读q/dq不证明状态充分；H前已经违反的门不会因低tail JF而恢复。未来qualification可作监督label，不能进入部署时已知的可行mask。未观测动作不得从一次已执行trial凭空得到反事实label。

HYPOTHESIS：对同一父状态预测`G(s,π_a)−G(s,π_ref)`可能比拟合含共同prefix偏置的绝对成本更直接；若后续策略固定，这是指定整策略响应，不是最优Bellman Q。需要重新决策的闭环Q，必须定义并验证随后的实际policy，不能只给旧regressor改名。

**历史条件学习没有被全项目遗漏，也没有完成强增量证明**

CONFIRMED：另有实际History Value/ILC/BO源码与冻结决策，不能把v1–v6某系列的“未实施患者history”扩大成全项目NOT_RUN。History Value的四history特征来自过去已完成5ms causal observer/reference/wrench；在线换context，不更新权重。ILC是误差驱动传统修正，BO有cost/motion/task独立估计；两者也不能包装成新深度Q。

SUPPORTED：H系列报告79 START/END、5,500,360 native，O系列83 START、6,038,480 native；当前H权重、训练labels、主要raw与完整ledger缺失，O也缺主要U/repetition raw。源码freeze hash可实核，历史性能与独立测试声明只能保留SUPPORTED，原raw复算为 **NOT_TESTED / PAYLOAD_NOT_AVAILABLE_IN_THIS_ARCHIVE**。缺档不能改写成当年没运行，更不能补造模型数据。[缺档逐项清单](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/SELECTED_EVIDENCE_AND_AVAILABILITY.json)。

SUPPORTED：History Value三次非零选择全是固定RETURN−0.3°，不能证明患者特定非零动作排序。ILC有正有负；BO在V12/U14/U15同选B，U16改变动作后JF增加0.330361、JM降低0.096051，是取舍。连续repetition反馈确实更新一项kernel coefficient，却仍选H150，相对同父固定H150动作改变False、收益0。只有一次H150完整cost residual，不能识别其他动作的反事实收益；共同prefix偏置与置信clip也可能限制翻转，后者是有源码支持但未完全独立识别的机制解释。

**本轮GP、独立prefix和state learning的界限**

CONFIRMED：v7二维模型输入只有已知动作x3/x7，没有多Human state、TD、Bellman backup或可微world model。五个独立物理target不是新加权reward；数据来自一个已暴露父状态，action-LOO仅为该格上的诊断。模型有训练事实，不等于新long Value有训练事实。

SUPPORTED：把nominal拟合后冻结的同一动作在独立合法prefix上执行，可检验该固定动作的迁移；它不是使用新state信息学到不同选择。即使固定动作保持原门，也不能自动宣称state-conditioned learning、患者泛化或Critic独立增量。实际两prefix均显示共享提案JF微降/JM微升；SS也未获得双成本收益。传统组合两prefix双降、SS反转，见主报告与配对表，不能重定义暴露状态。

CONFIRMED（封存方向审查的有限反例）：三种开发Human有可用且不同的OUT1因果估计，但三点在估计刚度均值轴上严格排序，两个阈值可复制任意三种菜单标签。三Human×动作不是更多患者，77维分类准确不排除简单记忆。现有77D helper只承认OUT1，不能拿OUT1/tail回填更早OUT0学习决策；固定early菜单不依赖该无效OUT0向量，所以不能据此称它是泄漏模型成功。[方向审查及cutoff修订](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/next_learning_target/REPORT.md)、[机器scope](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/next_learning_target/DECISION_SUMMARY.json)。

该审查的“当前新增模型NOT_RUN”绑定它未读取EARLY/独立结果的证据cutoff，不是全轮封死Learning；其中8context只是候选分组筛查设计启发，不是统计充分或泛化保证。main可依据后来另登记的真实开发证据重新评估，不能因结果已暴露重置测试身份。

**文献具体带来的研究限制**

SUPPORTED（Agent应用解释）：[Mandi等的原ranking论文](https://proceedings.mlr.press/v162/mandi22a/mandi22a.pdf)支持把候选相对差与决策regret作为目标，但原已知可行解集合不能变成iHEAR的未来qualification mask；[Rosolia/Borrelli LMPC原论文](https://arxiv.org/html/1609.01387v7)使“可执行后缀+其成本身份”成为必要设计提示，其确定性safe-set保证不授予当前混合非线性任务安全资格；[SuperMimic原论文](https://arxiv.org/pdf/2610.28480)的动作条件WM与匹配同策略tail训练并未在iHEAR实施，不能把读论文或局部成本回归称作复现。完整原方法、假设、资源和不可迁移部分见[已封存文献审查](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/literature/DECISION_RELEVANT_LITERATURE.md)；检索来源身份与原文阅读范围保存在来源登记，不把该子审查未新增检索误写成全轮未检索。

**有限停止与结论边界**

SUPPORTED：停止把同一已暴露父、同一phase同选和更低RMSE反复包装成独立Learning进展。若再推进，应先存在强固定/阈值/1-NN/局部响应/解析guard无法覆盖、且有因果输入可辨的真实合格动作排序变化；另登记完整状态/动作/continuation、预算与停止条件，再在未暴露合法状态冻结验证。只修复已知误差、与简单法同选、或不超过强传统，就停止该实现。这里没有创建新模型/队列或授权新状态。

四项结论保持独立：旧Critic在部分排序任务**有效（CONFIRMED，限定scope）**；相对强phase的**独立增量为0（CONFIRMED，四主测试）**；**计算效率优势NOT_TESTED**，其中**实际尝试节省为0（CONFIRMED，已全菜单执行）**；新long Critic/WM与患者级泛化**NOT_TESTED / NOT_RUN**。预测/学习信息、真实动作变化、完整门、最强传统、计算效率和泛化分别核验。任何仿真结论均不升级为硬件、舒适度或患者安全结论。


**CONFIRMED（后来注册的v7条件分类）：** 两个一维stump确实拟合三个OUT0 commissioning context，不是Bellman Q/Value。两CF的原benefit均0，模型各1/2不及常数B 2/2；CFL prospective metadata拒绝保持NOT_TESTED，V2开发gate关闭，实际条件选择NOT_RUN。K对CF“原资格”2/2只作信息诊断，不能代替完整benefit。详见[方法审计](LEARNING_METHODS_AUDIT.md)及[冻结门](freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json)。
