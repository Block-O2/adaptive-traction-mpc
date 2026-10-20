# Track E — 执行资格与未来学习接口

## 当前执行链与证据
保持原commissioned belief与estimated Human state → 有界参考意图 → 新quintic/连续几何和mechanics/escape → 原40ms rolling bridge → current-state admission → feedback/allocator → receipt → 0.25ms native physics。不能用数学reference、提议或激活标记代替实际positive native步。
activation_validation.py的future handoff同时核验新估计状态、估计加速度、参考误差、ROM/motion、shifted geometry、剩余预算、版本/phase及原始source与revalidation sample年龄。原始source时间不被重试刷新。scientific_scheduler.py在实际write前拒绝达到100ms的source；模拟时钟资格和host profile分开。
trace字段actual_human_acceleration_rad_s2来自SplitAccelerationMonitor对历史dq_hat的因果差分；它不是本报告离线native真值gradient。见源码索引与手工调用链说明。字段名称不作为oracle许可。

## certificate、receipt与候选身份
audit/INTERVENTION_EXECUTION_AUDIT.json从最终schedule外端状态独立重建quintic，核对positive receipt中的q/dq；逐项核验T倍率、D姿态、ER时长、新速度因子、激活和native步数。D的outer_pass_velocity_unchanged元数据描述D父选择阶段；新AV候选随后明确改变膝通过速度，最终速度以新增意图和最终曲线核验，不将父阶段元数据误读为最终速度未改。
原部分receipt不含直接plan_request_id，不能伪造。绑定使用已记录request/source/version、半开激活时段、最终参考、逐步相同torque和唯一native step数量。每组完整live fork hash相同、父等待子且保持不变；全体raw原生归属另由分离算术实现复核。

## 尚未获得的资格
PHYSICAL_LEVEL1 SCIENTIFIC_SIMULATION不等于Native LEVEL2或host LEVEL3。历史FAST完成包的original R2失败，HOLD→RETURN包42 START、19完整host、0 complete+R2 PASS、NOT_FROZEN保持。HOLD的实际参考完成与串行交接开销有证据；本轮没有改时间戳、预执行、HOLD或任何准入门来修复。strict55/FAST单项好转也不能覆盖整体失败。

## 学习接口
FUTURE_Q_LEARNING_SCHEMA.json定义identity、causal observation、proposed/action-applied、execution feedback、offline evaluation、split与policy语义。derived/STATE_RISK_FEATURES.json提供只读历史特征示例，没有训练模型。
最值得后续学习的是原执行链可认证的有界duration/pass-velocity意图及必要内部协调姿态，而非直接torque、Human qpos或增益。当前只有有限反事实标签，无法宣称少量重复即可可靠学习。排序表示需包含state-action交互；历史a(s)+b(p)中的公共state项在比较action时相消，不能成为有效状态条件排序的证据。
奖励/资格优先级：先分非法/拒绝/过期/未应用、partial、task/safety/motion/receipt失败，再在完整合格样本中比较本状态匹配B的J_F。低力motion失败必须保留分项负标签；匹配B未来p95、true native extrema、全程真值下冲仅为离线标签。后续replan策略版本必须记录，V_commit与V_replan不可混用。

## 停止原因
执行合同审计未发现应在本轮改动的确定性缺陷；不扩大为实时系统重构。本轮无RL/Q-learning/Neural Q训练，无新增执行权限，无正式基线升级。
