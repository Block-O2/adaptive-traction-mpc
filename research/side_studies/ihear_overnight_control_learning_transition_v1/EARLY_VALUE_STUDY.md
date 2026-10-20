# 补充对照：更早选择完整后续方案

V01暴露了RETURN2动作集合的结构限制：共享此前H150执行历史后，仅修改两个中间姿态未必还有可行候选。为此在任何U结果出现之前登记EARLY_VALUE_PROTOCOL.json，增加三个实际QE分支，把决策放在共同OUTBOUND prefix完成、H150首次特有干预之前。该时点可以公平选择B/H150/HIP/KNEE/ZERO的完整剩余方案。原RETURN2主实验继续保留。

输入来自决策时严格此前的最后一个完整TASK测量样本（age≤10ms）：估计tracking q/dq、测得force/moment、OUTBOUND elapsed，以及当时已经处方给定的三个RETURN-prefix系数。后者是已知参考配置，不是未来实现的Human状态或未来成本。开发数据从每个动作的共同原始prefix重构，五个动作的十维向量逐位相同；实时QE输入又与同规则的raw重构核对。无Human truth进入选择器。

与主模型相同的6个D父状态训练、2个V父状态选alpha，原数据复用不增加独立样本数。模型有每动作状态斜率和资格余量头；alpha=10.0，标准化中心化状态rank=5。冻结元数据中的默认浮点rank=6受均值舍入影响；六个中心化样本最多有五个独立方向，解释修正及奇异值见derived/MODEL_CAPACITY_DIAGNOSTIC.json，权重未改。权重在全部U测试之前冻结，SHA256=`e88c477dbdd9617f8e388c0c014cbb6809f19a64467e32e70f0f471b05fa2d42`。无法确认合格力收益时保留B后续方案，仍走原安全执行链。

| 测试状态 | 实际QE选择 | 完整资格 | 对B收益 N·s | 恢复H150失败 | regret N·s |
| --- | --- | --- | --- | --- | --- |
| U01 | B | PASS | 0.000000 | False | 34.148093 |
| U02 | B | PASS | 0.000000 | False | 34.373705 |
| U03 | B | PASS | 0.000000 | False | 34.337084 |

EARLY_POLICY_ALL_TESTS_QUALIFIED=True；EARLY_CONDITIONAL_BENEFIT_PASS=NOT_DEMONSTRATED。实际选择非恒定=False，纯force排序非恒定=False。不能把始终回退B当学习成功，也不能把资格头导致的切换当作纯force Q排序反转。

开发阶段八个状态全部选择B=True，四个替代动作在这八个状态均未通过经验余量缓冲=True。这已经显示全局最大LOO误差缓冲在小数据下过于保守；即使实际通过的开发轨迹也被屏蔽。它是可执行回退接口及保守性代价的对照，不能包装成有效条件学习。未在消费U结果后缩小缓冲以制造非恒定选择。

预注册晋级要求：三次完整资格均通过，选择非恒定，至少一次恢复H150失败、至少一次对B合格降力，而且平均成本低于在三个U上都合格的最佳固定动作。该固定对照为H150，均值1402.666669 N·s；QE均值1436.952962 N·s。这个测试集最优固定对照仅用于事后评估，不进入在线选择或训练。

它是一次任务内更早的资格条件value选择，没有使用前一次运动反馈，也不是多步Bellman Q-learning。主Q_GENERALIZATION_PASS和FEW_REPETITION_LEARNING_PASS保持各自定义；补充结果不能代替这两个验收标志。机器结果见EARLY_VALUE_EVALUATION.json。
