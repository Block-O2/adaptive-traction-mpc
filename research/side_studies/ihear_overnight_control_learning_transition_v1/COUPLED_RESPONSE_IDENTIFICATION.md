# 机器人—cuff—Human闭环响应证据

原waypoint执行层Human请求为Kp(q_ref−q_est)+Kd(dq_ref−dq_est)，Kp=[180,140]、Kd=[28,22]。来源为source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/human_waypoint_shadow.py的desired_acceleration，与stage3 human.py冻结系数一致。本接口的该请求未加入reference ddq；不能将它与另一套computed-torque实现混为一谈。图03用日志中实际reference与估计状态重构请求，native实际加速度只做离线比较。

request是进入Human逆动力学/allocator的期望量，真实Human加速度来自机器人执行、cuff wrench、被动动力学和反馈的闭环总结果。PREDICTION_VALIDATION.json的acceleration_alignment与图03显示二者幅值/形状不同；这支持“请求不是直接人体加速度”的结论，不能据此唯一归因于某个增益或延迟。

| 轨迹 | 原2DOF模型输入 | 100ms髋RMSE° | 100ms膝RMSE° |
| --- | --- | --- | --- |
| Ctrl_H150 | held_measured_wrench | 0.019032 | 0.029551 |
| Ctrl_H150 | held_requested_generalized_action | 0.253704 | 0.119891 |
| W2_H150 | held_measured_wrench | 0.016916 | 0.028739 |
| W2_H150 | held_requested_generalized_action | 0.251984 | 0.130932 |
| D03_H150 | held_measured_wrench | 0.018585 | 0.029510 |
| D03_H150 | held_requested_generalized_action | 0.254124 | 0.119612 |
| D04_H150 | held_measured_wrench | 0.016350 | 0.030034 |
| D04_H150 | held_requested_generalized_action | 0.251493 | 0.134605 |
| D05_H150 | held_measured_wrench | 0.018497 | 0.027462 |
| D05_H150 | held_requested_generalized_action | 0.251794 | 0.127502 |
| D06_H150 | held_measured_wrench | 0.016355 | 0.030039 |
| D06_H150 | held_requested_generalized_action | 0.251506 | 0.134634 |

上述模型在每个origin冻结当时的beta、residual weights、估计状态以及输入；分别保持当时已测wrench或已发广义action，向前积分原2DOF模型100/200ms。它没有预测未来机器人反馈和传力，不是完整robot–cuff–Human闭环模型。测试时未来truth仅作为评价标签，MuJoCo没有新增步进。

| 父状态 | 用途 | 方法 | 100ms膝RMSE° | 膝p95绝对误差° |
| --- | --- | --- | --- | --- |
| W1 | train | causal_constant_acceleration | 0.020593 | 0.042234 |
| W1 | train | ridge_residual | 0.018576 | 0.036033 |
| W2 | historical_trajectory_validation | causal_constant_acceleration | 0.022840 | 0.039884 |
| W2 | historical_trajectory_validation | ridge_residual | 0.019276 | 0.026801 |
| D03 | prospective_new_parent_validation | causal_constant_acceleration | 0.016741 | 0.042252 |
| D03 | prospective_new_parent_validation | ridge_residual | 0.017252 | 0.029927 |
| D04 | prospective_new_parent_validation | causal_constant_acceleration | 0.012781 | 0.032379 |
| D04 | prospective_new_parent_validation | ridge_residual | 0.015401 | 0.023761 |
| D05 | prospective_new_parent_validation | causal_constant_acceleration | 0.020976 | 0.037631 |
| D05 | prospective_new_parent_validation | ridge_residual | 0.017315 | 0.025912 |
| D06 | prospective_new_parent_validation | causal_constant_acceleration | 0.012781 | 0.032377 |
| D06 | prospective_new_parent_validation | ridge_residual | 0.015400 | 0.023753 |

残差ridge固定alpha=10，只在W1的B/ER/H150轨迹训练；W2是历史轨迹验证，D03–D06是后续新prefix验证。100/200ms滚动origin使用当时估计、tracking、因果加速度、已测wrench和广义request；未来truth只在训练目标/评价端使用。初版权重与结果先保存在audit/prediction_initial，后续不按新状态调参。相邻origin高度相关，不能把数百窗口当成独立Human样本。

同父HIP−ZERO、H150−KNEE等干预的首个reference、robot torque、cuff和Human变化时间见derived/COUPLED_FACTORIAL_CONTRASTS.json。干预前轨迹相同；后续原replanning可能同时改变另一个关节参考。因此这是改变髋/膝协调参考的闭环总效应，不是隔离出的纯机械耦合系数，也不能用5ms首次差异推断唯一物理延迟。

短时角度预测误差与狭窄excursion门余量/候选运动差异处于不可忽略的尺度；模型还缺少候选动作输入和完整任务force目标，不能用角度RMSE直接论证N·s收益排序可靠。没有将预测器升级为自动控制器。进一步的动作选择必须由实际同父完整物理结果验证。

例如D03的H150与ZERO真实膝最小角只相差0.004265°，该轨迹100ms ridge预测的膝RMSE为0.017252°，约为前者4.04倍。这是不同量的尺度对照，不是候选差值误差界或置信区间；它不足以认证如此小的运动差异，也不能代替动作条件反事实预测验证。

![请求与响应](figures/03_request_response.png)

![短时预测验证](figures/02_prediction_validation.png)
