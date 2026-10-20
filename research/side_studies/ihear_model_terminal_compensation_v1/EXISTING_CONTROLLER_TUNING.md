# 原反馈的小幅优化

结论：在本轮冻结的终末门控和幅度内，增加原膝速度反馈20%的KD120没有修复价值。膝下冲从1.275378484°变为1.275741590°，excursion差仍为+0.548959573°，保持motion FAIL。不能据此否定所有阻尼优化，只能否定本次参数与接口组合。

原Human PD为Kp=[180,140]、Kd=[28,22]，原robot笛卡尔/姿态及零空间反馈保留。KD120新增项为near×0.20×22×(dq_ref,k−dq_est,k)，仅RETURN临近终点有效；总新增加速度±0.2rad/s²、变化率1rad/s³。因限幅存在，它不是全程将Kd精确改为26.4。没有积分项或更快执行入口。

新增意图经M(q_est)映射为广义作用，位于原action transforms与最终executable filter之前，保持原allocator/supervisor/write。候选是新控制律，不能称为B原能力；原reference证书只保留其原路径范围。每个变化后的输出均重做原检查并绑定positive-step receipt，见[audit/CONTROL_EXECUTION_VERIFICATION.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/audit/CONTROL_EXECUTION_VERIFICATION.json)。

理想2DOF局部PD极点仅是设计参考，不能证明robot–cuff–Human的全局稳定性。本轮完整native轨迹、原全部运动/安全门和力矩/振荡诊断才是实证范围。

|辅助|Δ下冲相对ER (°)|ΔJ_F (N·s)|有效修正receipt|最大广义修正 [hip,knee] (Nm)|结论|
|---|---:|---:|---:|---|---|
|KD120|+0.00036311|+0.00002153|603|[0.107476, 0.040323]|motion FAIL|
|PD|+0.00275000|-0.00349334|385|[0.107566, 0.040323]|motion FAIL|
|FF|+0.01261148|+0.02233690|594|[0.423335, 0.107478]|motion FAIL|
|PDFF|+0.01532879|+0.02027724|603|[0.423336, 0.107478]|motion FAIL|


一次接口修复：v1在主进程查询了只存在于planner worker的terminal属性。Dev_KD120在新增native step=0时失败；父partial与原STOP保留。v2只改为读取已接受的deployable terminal缓存；缺失缓存时禁用辅助。科学参数完全未变。修复前后代码、hash、纯接口检查均保存，没有用失败partial积分排名。其他新控制方向使用同一已修复接口。

停止KD120方向，不扩大增益。最小侵入的H150已有更明确的受控物理收益。
