# RL与Reward结果

**CONFIRMED：本轮验证了历史moment reward含有可区分动作流的目标信息，也确认actor/value联合裁剪实质改变梯度与继承Adam下的参数更新；没有完成新鲜on-policy PPO的部署收益试验。** 本轮实际执行8个私有诊断Adam步骤，0新rollout、0新RL物理尝试、0可部署checkpoint。fresh PPO保持 **NOT_RUN** 的直接理由是公平执行、完整motion与资格桥接未闭合，不是算法普遍无效、单次训练失败或额度担忧。


**实际做了多少，哪些不是本轮训练**

|证据层/分支|实际工作与计数|资格边界|
|---|---|---|
|历史41D native-event PPO|CONFIRMED：156次attempt=120 train+36 eval，17,504,340 native，1,885训练RL decisions，29次train call、524实际Adam minibatch steps|属于历史训练；不计作v7新增训练，也不把继承`_n_updates`的epoch计数当Adam次数。|
|本轮reward离线重放|CONFIRMED：重算120条已保存训练轨迹；192个同seed、完整等时轨迹对因R1/R4成本而排序反转|192对共享轨迹、相互相关，不是192次独立试验；无新策略、rollout或物理。|
|本轮首梯度诊断|CONFIRMED：12次policy forward API、24次backward traversal、0 Adam|精确旧buffer与冻结初始权重；不是历史整段update重演。|
|本轮Adam反事实|CONFIRMED：48次policy forward API、24次backward traversal、8次completed私有Adam step|四组对照×joint/separate各一步；副本实际更新，无新rollout、无部署checkpoint。|
|本轮优化诊断合计|CONFIRMED：60 forward、48 backward、8 Adam；0新RL decisions/env/physics|forward为policy API调用，非内部Linear/Tanh次数；确有神经模型计算，不能写成“零梯度/零模型计算”。|
|本轮原scorer桥接|CONFIRMED：4次原physical_audit、2次metric_record、1次fullmotion.analyze尝试|只读历史raw，env/模型构造及dynamics API为0；旧物理证据不是新物理attempt。|
|fresh joint/separate PPO续训|NOT_RUN|没有新policy数据、训练队列或冻结部署结果。|

计数来源：[历史训练与reward审计](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/RL_AND_REWARD_HISTORY_AUDIT.md)、[梯度机器账](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_gradient/MECHANISM_SUMMARY.json)、[Adam机器账](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/adam_counterfactual/ADAM_MECHANISM_SUMMARY.json)、[桥接资源账](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/ppo_scorer_bridge_gate/RESOURCE_ACCOUNTING.json)。汇总算术见[ACCOUNTING_RECONCILIATION.json](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/final_learning_evidence/ACCOUNTING_RECONCILIATION.json)。历史524与本轮8须分列，不能相加后称532次本轮新鲜训练。

**Reward究竟有没有目标信息**

CONFIRMED：历史native PPO的R1使用已执行causal cuff力/力矩norm积分F/M、observer差分加速度variation V和phase-chain progress φ：`r=2Δφ+terminal_bonus−.0005ΔF−.005ΔM−.02ΔV`。V不是native jerk，也不能替代完整motion门。R4只把moment系数`.005→.020`，完整同轨迹的总return差为`−.015 JM`。120条逐step算术最大误差约7.11×10⁻¹⁵，故“R4根本没有moment信号/奖励算错”不成立。[重放原结果](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/OFFLINE_REWARD_REPLAY.json)。

CONFIRMED：失败floor可抹掉R1/R4的总return价差；19条历史失败样本都落在此floor内，但它们全部来自STD分支，实际R1/R4训练40/40完整。因此该机制存在，却不能解释本次R4的部署负结果。R1/R4 actor均值越界比例为0，也不能用早期STD越界替代其原因。

CONFIRMED：历史已试过探索std、学习率、整episode聚合，R2同时改potential与variation权重、R3将整个reward包括终端/floor除30；R3仍继承原critic/Adam。这些不等于本轮分别裁剪实验，不应原样重复后称新机制验证。本轮没有新设计或闭环训练Reward；只对旧Reward、梯度与优化器机制作诊断。

**目标信息没有转化成稳定部署收益**

CONFIRMED：两个共同STD30父分别真实进行R1/R4续训，各10集，合计40集；两个seed是policy/optimizer身份，不是两位患者。冻结部署为Gaussian mean再clip，而非挑训练中最好随机sample。R4实际改变权重和行为，但两父的确定性JM均比R1更高：

|父seed|R1 JF / JM|R4 JF / JM|R4−R1 JM|
|---|---|---|---:|
|1495656323|1424.802775 / 105.581663|1425.161681 / 105.715285|+0.133621|
|1630784693|1435.924001 / 102.149296|1435.727758 / 102.160668|+0.011372|

原完整TASK的JF/JM已由trace独立复算。相对共同父，R4自身加权成本变化分别为+0.005821、−0.007030，一升一降；不能只解释为“优化了自己的reward但牺牲别的目标”。这支持有限训练没有一致实现新目标，但不独立识别失败原因。[部署目标重放](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/DEPLOYMENT_OBJECTIVE_REPLAY.json)。旧backward-difference jerk是另一诊断定义，未被重命名为当前v7完整native motion资格。

**联合裁剪与Adam：确认机械效应，保留反向结果**

CONFIRMED：四个历史首次minibatch从实际pre-update policy/Adam/RNG恢复，完整68/76条buffer的八组数组逐bit吻合；首batch16条顺序由保存RNG与已审源码重建，原档没有另存index日志。actor/value MLP参数支持不相交、梯度内积0，因此不是共享表示的方向冲突。[梯度诊断](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_gradient/GRADIENT_MECHANISM_REPORT.md)。

CONFIRMED：weighted value梯度占joint norm²约98.76%–98.96%；joint clip后actor norm仅为actor-only clip几何对照的10.20%–11.12%。随后8个真实私有Adam步骤保留原moments、单param_group、lr/epsilon等，只改变裁剪分组，得到actor参数Δnorm倍率2.184–5.168、方向cosine0.261–0.878。梯度倍率约9–10倍不能直接称Adam步长同倍；“继承Adam必然完全抵消裁剪”同样被这些对照否定。[Adam实际结果](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/adam_counterfactual/REPORT.md)。

CONFIRMED的负观察：第二个seed上两种裁剪都使固定全buffer actor loss上升，separate略更差；首minibatch下降更多或total loss下降不能掩盖这一点。R4首batch value norm反而较低、joint clip稍轻。因此 **HYPOTHESIS** 仍是“联合裁剪可能影响有限优化”，**NOT_TESTED** 的是其是否导致R4负结果、分组clip是否改善fresh部署、完整motion、强传统增量或泛化。诊断只改变保存观测上的参数与分布，没有新真实动作执行。

**旧PPO原scorer桥接完成了什么**

CONFIRMED：预选两条R1 episode010后的deterministic episode011原raw，没有按结果挑选。原physical/scientific audit均PASS，未改的metric_record以 **NATIVE** scope均valid；JF/JM分别为1424.8027750689257/105.58166327373357及1435.9240009500172/102.14929577199597。原447项source/config byte contract全部核对一致。这里447是完整manifest项，先前可行性414是source子集，不混作同一口径。[原桥接报告](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/ppo_scorer_bridge_gate/REPORT.md)、[原metric机器结果](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/ppo_scorer_bridge_gate/ORIGINAL_PHYSICAL_AND_METRIC_RESULTS.json)。

CONFIRMED：两raw的phase时长为9.005/1.020/9.005s；旧metric的 **MATCHED** 额外合同要求9/1/9、逐phase容差0.010000001s，HOLD1.020不满足。本次没有称MATCHED PASS。**这一历史scope不匹配不推出当前v7合同失效**：当前固定菜单仍按自己的冻结原task、同父B及完整motion协议评价，不能把旧固定9/1/9门无差别移植，也不能借此放松它原本约定的门。

CONFIRMED：原online_reference_records为空，outer `online_certificates_valid=True`来自空记录分支，不能证明它覆盖RL动作；内部mode evaluator对现有activation与C2等真实证据另作检查并PASS。桥接没有补造ACCEPTED行、certificate或RL-as-residual字段。

CONFIRMED：未改的fullmotion.analyze处理第一条时已保存原native运动映射及motion_series，随后强制读取缺失的`EXECUTED_RESIDUAL_RECEIPTS.json`并抛FileNotFoundError。保留partial后按合同停止，没有伪造报告、修改analyze或继续第二条motion/compare。结论是 **NOT_COMPARABLE_FULLMOTION_BRIDGE**，不是fullmotion FAIL，也不是PASS；G4未授予。[完整motion尝试](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/ppo_scorer_bridge_gate/FULLMOTION_BRIDGE_ATTEMPT.json)、[最终门决策](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/ppo_scorer_bridge_gate/GATE_DECISION.json)。

**接口、公平对照和NOT_RUN的具体理由**

CONFIRMED：历史41D actor输出两关节独立normalized progress fraction，非torque、duration、pass velocity，也非原K3反对称残差；HOLD不由actor跳过。41D包含causal observer/robot/reference、phase/时钟/目标、measured wrench与过去动作/拒绝/age；不能因runtime有belief对象就声称beta进入数值41D。latent Gaussian log probability对实际保存latent action计算，物理接口前才clip，未发现把clipped action伪作Gaussian密度的实现错误。[接口与Reward原审计](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/RL_AND_REWARD_HISTORY_AUDIT.md)。

CONFIRMED：当前v7 runtime不是旧PPO可直接替换的执行闭包；静态比较414旧source有405同、7异、2缺，callback/原native proposal路径未完整接通。旧thread owner也不能未经等价性证明就套live fork。本轮桥接推进了原scalar/NATIVE评分，但完整通用ownership-motion及同父/同prefix的B、强传统配对仍未闭合。[fresh可行性审查](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/ppo_clip_feasibility/REPORT.md)中的“原scorer桥接未实施”已由上述后续结果部分更新，不能再照抄为毫无进展。

SUPPORTED：若以后继续，应另登记原447 byte闭包隔离、真实RL request→proposal→ACTIVATED→positive native receipt与原motion数学/阈值连接，保留所有拒绝/失败和证书；不能把RL伪装legacy residual或删除causal gate。随后证明合法同父状态、41D字段/动作时点/Adam-RNG等价，建立最强同两fraction接口固定phase/slot传统对照，并另列强K3/18D/modal参照。`[+1,+1]`不是已证明最强传统。只有这些门闭合才考虑fresh joint/separate续训、冻结deterministic部署及独立合法状态评价；该后续工作 **NOT_RUN**，没有自动队列或下一轮授权。

**其他RL历史与研究定位**

CONFIRMED：modal8 scratch PPO是另一问题，64完整任务各一次全局动作、31更新epoch；按mean/std/value分组为93 parameter-group Adam步骤，不能混到native PPO的524。其部署mean JF1399.918272、JM107.492306为历史原门合格；训练最佳sample不是部署，后续TIME0/降速规则的收益要归给实际规则，未证明强传统外增量。[历史边界](/home/hank/ihear-lab/autonomous_learning_smoothness_v7/agent_reviews/rl_history/RL_AND_REWARD_HISTORY_AUDIT.md)。

SUPPORTED（历史报告而非本轮完整raw重审）：另有55D/20ms anchored SAC曾改善较差DAgger student，但不及强teacher、MATCHED仍失败，改善含duration/HOLD变化；不能直接比较当前v7等任务最优。本轮未新训练SAC、DAgger或约束RL，均 **NOT_RUN**；这不抹掉它们历史实际运行。

本轮因此改变的是证据精度：reward信息存在、优化耦合确实存在、Adam实际效应已测；尚未建立“修复优化器→更好新策略→完整合格→强传统外收益”的链条。方法执行有效、独立增量、计算/物理尝试效率、独立泛化四个结论分别报告；对fresh分组clip PPO，后四项均 **NOT_TESTED**，不能互相代替。仿真/旧raw审计不构成真实硬件、临床舒适度或患者安全结论。
