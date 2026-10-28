# 少次重复运动接口提案 v1

本轮仅验证单周期局部优化；几十次同父仿真优化不能写成新患者两三次即可改善。C模型目前只在相同Human、相同合法父状态下使用二维候选参数，不具备患者状态泛化资格。

## 数据与因果输入

Trial1从合法完整任务产生causal history：commissioned beta/geometry及其估计来源、estimated q/dq、issued reference q/dq/ddq、实际测量cuff force/moment、原source timestamp、applied torque receipt、原执行拒绝/任务结局。保存每个时刻是决策前可用还是执行后反馈；不把native true Human q/dq、物理患者生成参数或下一trial receipt放入预测特征。

当前患者信息只能来自其已完成trial和当前因果观测。离线群体prior必须单列训练患者/轨迹数量、估计与生成侧物理参数边界及计算成本。本轮历史模板是同一nominal Human的已完成D01R causal reference与commissioned belief，不是群体先验；状态特征在本轮恒定，不能宣称学到跨患者条件关系。

本轮优化使用完整反馈JF/JM和原motion evaluator余量作为离线监督标签。原motion余量依赖evaluation-only native Human运动，尚非真实装置可直接获得的患者历史输入。下一阶段需先建立经传感器/observer误差验证的可部署运动测量与保守余量，否则此分支只保留仿真研究身份。

## Trial协议

Trial1执行固定强baseline，公开该患者真实因果历史。Trial2只用Trial1更新残差或局部协调参数；冻结candidate和模型SHA后才执行Trial2。Trial3/4按同样边界逐次更新，各trial保留原安全准入最终权限，不能用未来真值重选先前动作。

同一患者的公平对照从真实连续父状态分支，比较固定强baseline、history-disabled（冻结群体均值或无个体更新）、传统ILC、直接局部BO和物理+残差；动作权限、trial数、预算及原资格门一致。history-disabled不得偷看个体历史，强baseline若在该状态motion失败须单列并改用真实合格固定父。

新患者验证按患者与完整轨迹分组；不能随机分割相邻时间步。模型和超参数在未见患者前冻结，在线只允许预先指定的少次局部更新。每次真实尝试均记探索成本，包括partial/拒绝；报告每trial完整合格JF、JM/motion、累积实际负担ΣJF、失败partial负担与到达同等收益的真实尝试数。不同repetition的自然状态漂移须与同父固定对照区分。

## 本轮可复用接口

`source/nominal_proxy.py`定义causal template/belief输入与显式UNKNOWN输出；`source/optimizers.py`定义每臂独立模型、训练ID及参数提议；`predictions/`在START前冻结预测；`attempts/`和`history/`绑定实际结果及causal轨迹。后续应增加患者context与逐trial数据合同，并独立验证传感器motion余量，不直接复用本轮恒定父状态模型给新患者决策。

CROSS_CYCLE_READY=NOT_READY：本轮未实施Trial1→Trial2→Trial3/4的真实连续患者自适应，也未验证跨患者不确定性。

真实患者不能作完整物理状态fork。未来硬件比较还需预注册的随机交叉/顺序与carryover设计、可测状态匹配和伦理/安全审查；本轮仅给出仿真接口，不能直接迁移为人体试验协议。

本包还交付每个完整attempt的FULL_TASK_CAUSAL_HISTORY.npz，只导出已完成trace中的estimated state、issued reference、cuff wrench和boundary time，包含共享物理prefix。直接live采样的原CAUSAL_HISTORY.json只覆盖fork suffix；其request source timestamp仍单列保留。完整导出不伪造缺失的传感器source时间，不含native true Human状态，详见audit/FULL_TASK_CAUSAL_HISTORY_EXPORT.json。
