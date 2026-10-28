# v8 方法家族矩阵（持续更新，尚未封包）

每个家族独立矩阵/变体账本见 families；当前所有整体范围均 NOT_FULLY_EXPLORED，不由一个模型、seed或菜单失败否定家族。

|家族|已执行机制|当前物理/独立证据|正在推进/未完成|
|---|---|---|---|
|A Critic/Value|完整JF/JM、相对B/固定、pairwise、风险；25/33/39D；原45margin；新增2partial只作操作资格标签|A1四状态3/4；A3开发10/10；A4开发9/10/假可行2但假失败17；A5风险50整case留出与A3主法完全同选|A5局部已见修补不算泛化；新参数冻结验证、校准、TD仍待覆盖|
|B PPO/Reward|三动作离线RF/PPO/BC与五动作真正32新rollout分开；raw/gain20；parent/first/last；新连续Beta标量密度|categorical24合格8完整失败/16更新；Beta第一批16完整excursion失败，8更新调用但advantage/梯度/权重变化均零；第二批8完整失败1partial、0更新、9pending隔离UNKNOWN|失败floor塌缩已确认；同旧4行margin奖励恢复梯度；global/条件LOO各4私有步；GateK确认负跨条件核压过Light局部方向；核去耦合实际同4私有步/同当前梯度范数，旧两条件均值转正；六固定mean新参数物理待部署|
|C ILC/BO/History|action-only/additive/interaction/disabled/commissioned；真正T1-T2-T3；两增益ILC/固定±.25/异质prior/分量BO|连续14任务全原合格、1106000新增native；history改变动作，未超过固定−.25；BO按原门弃权|冻结C4程序的新参数持续Trial验证待运行；更广history表示/增益NOT_FULLY_EXPLORED|
|D IL/DAgger/SAC|BC覆盖三模型/720SGD与6规则；SAC64/1650SGD；同目标精确Q；matched linear/tanh/ridge独立RETURN/RISK/物理头|BC树/nearest同10/10；SACactor11/1；精确Q7/3/2；NeuralQ468init93600更新完成，三seed主6/4/2、8/2/2、8/2/2；known12 API parity通过|实际新参数冻结选择待运行；真正多阶段DAgger/SAC仍NOT_FULLY_EXPLORED|
|E 学习辅助/动力学|共同OUT0 legal39与48完整trace；actionblind/actiononly/context/paired；short direct/curve；matched8knots D4/DFull/ridge/MLP|全任务E2已704solve11264RHS、66init13200Adam；时间域修正显著降误差，DFull paired十case固定同选EARLY_H150、6/10合格|synthetic parity曾漏真实外层schema；ENG01前缀失败保留，E2V2真实权重25API/85query/320scalar/9selector parity通过，ENG02实际OUT0已返回；新参数控制与省试未建立，不称WorldModel/PETS复现|

统一层级：实现→学到目标信息→实际选择→完整原资格与目标→强基线增量→独立合法状态→总成本效率。低预测误差、训练reward、共享轨迹和离线表优化不越级。主动作目标和JM/运动代价分列，双成本原负结果不覆盖。

新增状态只逐字段验证：原77D整体仍INVALID；KIN33额外使用当前估计q/dq和请求参考q/dq，WRENCH39再加入当前实测F/M。OUT0尚无TASK累计量，不补零；guard43软件计数不进入拟合。10/10属于开发LOCO，未打开两项新参数验证结果。
