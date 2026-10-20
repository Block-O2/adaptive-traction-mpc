# Learning问题与冻结合同

本轮主要学习问题是：在同一被动Human、合法prefix形成的可观测状态下，学习四个合法协调动作的完整任务价值及适用条件。使用实际完整物理回报训练有限动作价值模型，不运行COBYLA，不把参数搜索重命名为Q-learning。

**本轮主模型的精确定义为contextual Monte Carlo action-value regression**。一个动作定义RETURN2/3两个中间姿态修正及其冻结的后续执行规则；完整任务终止后得到回报。它有显式state×action交互，但没有多步Bellman bootstrap，不宣称学到Q*或长期患者适应。此前的18D仍是传统约束优化。

在线决策时点为RETURN slot 2、第一项姿态干预之前。七个输入为估计髋/膝q相对当前reference的误差、估计dq相对reference dq的误差、当时测得cuff force/moment范数、当前phase elapsed。request原source time、age、model hash、phase/slot同时保存。只使用已经获得的估计/测量；native Human truth、未来matched B统计、整个任务结束后的最小角度都不进入这次选择。

动作H150/HIP/KNEE/ZERO分别在RETURN2与RETURN3使用[+0.3,-0.3]、[+0.3,0]、[0,-0.3]、[0,0]度姿态修正。四者都保留18D、T、RETURN1×1.10、RETURN4×1.20及RETURN5 hip×1.5；全部由原5ms量化、规划、证书、current-state admission与allocator执行。ZERO只表示这两个姿态增量为零，不等于正式B。B只作为同父完整资格和force对照。

任务仍含OUTBOUND/HOLD/RETURN；不得截短HOLD或以partial force积分获益。奖励采用分层合同：提议合法、实际接纳/应用、完整task、原绝对安全、causal ownership、原motion/fairness全部满足后，才比较完整J_F。失败的完整积分仅为诊断标签，不作为成功奖励；拒绝动作的实际fallback与提议身份分开保存。overshoot、velocity TV、acceleration variation、jerk、moment、tracking、峰值与剂量同时保留。

训练单位是完整cold parent/prefix family。D01/D02为已暴露W1/W2；D03–D06为前瞻开发状态；V01/V02仅用于模型选择；U01–U03必须在权重与选择规则冻结后才消费。同父的所有动作、重复和时间节点不得跨split。只有一个Human，不将多条轨迹计为多个独立Human。

模型比较全局固定动作均值与具有每动作独立状态斜率的ridge。训练只使用D组，alpha候选0.1/1/10/100由V组选择；最终不把V再并入训练。学习完整J_F相对本状态H150的差及每个原资格归一化余量，匹配H150/B仅构成离线标签。保守选择要求预测余量超过leave-one-parent-out最大残差、预测force优势超过开发误差，并处于开发状态支持范围。证据不足保留H150；这不意味着H150在任何新状态都motion合格。

必须报告直接Q排序和保守选择两种结果，避免把资格屏蔽导致的动作变化当作Q学习出状态偏好。最终与固定H150及训练集选出的全局最佳固定动作对照。只有未见状态真实完整合格获益且确实优于全局固定动作，才考虑Q_GENERALIZATION_PASS。

跨重复是单独资格：必须先执行一整次运动，用其真实已获得反馈实际更新模型/记忆，再在下一次重新准入并执行。冷启动fork数据、离线重放选择和确定性重复均不等于FEW_REPETITION_LEARNING_PASS。连续plant接口若有失败，不修改门槛或重置Human状态使其通过。

参考方法来源：[Sutton与Barto，《Reinforcement Learning: An Introduction》第二版](https://mitpress.ublish.com/book/reinforcement-learning-an-introduction-2)；[Ernst等，Tree-Based Batch Mode Reinforcement Learning，JMLR 2005](https://jmlr.org/papers/volume6/ernst05a/ernst05a.pdf)。前者用于区分contextual action-value与完整MDP；后者用于区分回归拟合与真正的迭代Bellman目标。本轮不因引用后者就声称已实施fitted Q iteration。

## 开发阶段的资格优先澄清

D03完成后、训练与全部U测试之前，明确：若H150预测余量下界不为正而其他候选有正下界，可选择预测成本最低的合格候选，即使其力积分高于不合格H150。若没有可信候选仍保持H150研究参考，但不宣称实际资格。若H150本身预测合格，则保持原force优势误差门。资格恢复与对合格H150的降力收益分开报告。详见audit/SELECTION_RULE_DEVELOPMENT_CLARIFICATION.json。
