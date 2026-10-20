# 未来Q-learning合同依据（本轮不训练）

本包提供有限的同Human PHYSICAL_LEVEL1反事实证据、执行合同和负结果，不提供成熟Q策略。原线性Q的`a(s)+b(p)`公共state项在候选比较中相消；本轮没有通过增加几个样本就解决这一表示限制。

## 状态：记录动作真正发生前的因果上下文

保留原测量/commissioned belief、estimated Human q/dq、issued reference q/dq/ddq、phase及进度/remaining time、原生目标与通过速度、已经执行的残差历史、模型/几何版本、current-state admission、source age、carry/escape状态和命令版本。参考结束而实际仍在运动、HOLD后的状态收敛、相邻目标经闭环重规划累积，都是不能只用phase或目标位置替代的上下文。

native Human真值、contact真值和其数值导数只能用于离线评价/监督标签，不能进入在线Q观测、准入或控制。完整父hash用于配对和数据划分，不是可部署状态特征。未来状态表示需要能表达state–action交互，不能继续以公共state常数冒称状态条件排序。

## 动作：意图、认证对象与实际应用分开

本轮动作是原18D-T已选择目标之后的有界内部髋膝目标偏移，或保持外端q/dq/ddq和duration的认证分段形状。原18参数、RETURN1/2 plateau、T=1.5及其5ms取整仍是控制合同的一部分，不能在学习器里悄悄改为可调动作。

request、worker所选意图、certificate、activation、40ms bridge、splice、reference progress、实际command receipt和positive native steps都必须有可核对关联。拒绝/过期/未应用的提议不能标成已执行动作；原carry/braking/fallback的实际结果要保留。Q只能在原准入与安全机制允许的动作集合内排序，不能赋予执行权限。

## 反馈：完整物理结果优先于数学评分

完整TASK J_F与各phase积分、force peak/RMS、actual velocity TV、acceleration variation、raw jerk及其敏感性、tracking、moment、ROM/dose、clearance、task/safety/motion/causal资格都应保留为独立字段。局部与完整窗口分开，不能用局部收益掩盖后续补偿。

本轮去程局部形状的reference velocity TV变小，但该段reference积分平方jerk增加约30%，实际完整acceleration variation增加约0.217%。这直接反对把“更平滑”命名或reference目标分数当成实际Human奖励。回程双目标姿态方案进一步降力，但完整velocity TV和acceleration variation略增，髋raw加速度峰相对T约+5.61%，也不能标成全面motion改善样本。原motion资格参照匹配B，不等于所有motion条目相对T都非劣；这些反馈必须分别保存。

只有完整task、原安全、motion/fairness与receipt归属均通过的结果可进入合格force ranking。更低force而motion失败的样本保留其失败轴，不给予“合格降力”的正标签；partial不能按观察到的低累计成本排名。工程motion门不是临床舒适阈值。

## 标签与划分：保持反事实含义

同完整live父状态的B/T/候选配对才能提供本条件的差值标签；完整积分保留共同prefix，动作后的remaining-cost及完整delta另列。不能把不同prefix的绝对J_F相互排序。每行需要父状态来源、seed、合法prefix、request时钟、策略/源码版本、实际执行receipt与结束原因。

本轮后续MPC继续因果重规划，因此标签是该冻结后续策略下的结果；`V_commit`与`V_replan`不自动相同。确定性重复用于复现和数值审计，不充作新state或新Human，也不能跨训练/验证划分泄漏。

既有四个T条件在HOLD后RETURN几乎收敛，说明“多个早期prefix”不等于覆盖回程动作发生前的状态。新验证协议因此另外登记RETURN0背景prefix，通过原物理和准入链改变干预前历史；这种背景变化必须写入数据合同，不能归因于新患者。完整适用域仍以VALIDATION_RESULTS为准。

## 下一阶段门槛

先扩大合法状态与近干预状态的覆盖，确认冻结候选在原门内的收益/失败范围；同时明确采集schema、执行标签和prefix分组划分。之后才决定是否建立学习数据包和带交互的排序器。本轮不生成下一研究包，不训练RL、Q或Neural Q，完成保护核验后STOP。
