# 终末下冲诊断

本文件使用历史W1 ER的完整原始native与5ms记录重新对齐。细节见 `derived/DETAILED_TERMINAL_DIAGNOSIS.json`、`derived/TERMINAL_EXECUTION_ATTEMPTS.json` 和 `derived/HISTORICAL_TERMINAL.json`。新干预的因果结论与结果另见REPORT，不用本节相关性代替干预证据。

## 五个定义

|概念|本轮定义|
|---|---|
|A reference相对目标|当前issued reference q减最终issued目标q；最终膝目标9.5°|
|B 跟踪误差|实际或估计Human q减当前有效reference q；两者分别记录|
|C overshoot|RETURN中 `max(0,最终issued目标q−实际最小q)`|
|D excursion|完整TASK实际q的max−min|
|E excursion difference|新方法D减同合法父状态matched B的D|

注册任务RETURN目标仍为[5°,10°]。原robust terminal合法选出的内部issued reference为[5.5°,9.5°]，本轮没有改目标。若用注册10°定义膝下冲，ER为1.775378°；若用实际issued9.5°则为1.275378°。本文主口径为后者，并明确分母。

## 时间对齐与误差形成

- 第一次低于9.5°：16.508500s；此时参考仍在减速。
- 膝reference稳定停止：16.895000s；实际膝8.330104289°、速度−0.191408179°/s。
- 实际最低膝角：8.224621516°，发生于17.166000s。
- 完整真实下冲：1.275378484°；参考停稳时已形成1.169895711°；停稳后另走0.105482772°。
- RETURN5 request/activation/splice约为16.900/16.905/16.945s。膝参考已恒定，髋参考与实际仍在运动。

约91.7%的最大下冲幅度在膝reference停稳时已形成，因此仅停止后的补偿无法解释整段误差来源。轨迹支持偏差在减速阶段累积，并有后续耦合瞬态；不支持把它描述成最后一瞬间才出现的全部误差。

ER膝全程最大角比matched B低约0.148870945°，最小角比B低约0.697467411°，两者相减才得到excursion差+0.548596467°。不能把1.275378°直接填入excursion门。

## 原控制器在做什么

16.895s时膝估计q≈8.330508°，估计误差与真值误差相近；未投影PD请求约+168.174°/s²，实际native加速度约+5.753°/s²。模型输入实测wrench时约+16.049°/s²，输入软件广义请求时约+168.174°/s²。这是三种不同量；广义请求不是已实现的人体动力学输入。

15.3–18.0s共540个执行窗口，原增量加速度投影active=0，robot torque clipping=0、shank–bed接触样本=0。已有反馈确实看到了误差并尝试制动。不存在该段新增积分饱和证据；也不能把allocator、时延或惯性单独认定为唯一根因。

当前Human模型的非对角质量矩阵显著非零。例如16.895s `M_knee,hip≈−0.537736`，髋实际加速度会进入膝广义惯性平衡。该计算证明模型有耦合项，不能证明真实下冲只由髋运动造成；本轮另用H150单因素物理对照核验时序效应。

## 新增控制变量证据：H150

在保持膝reference一致、干预前全body native状态与控制输出完全一致的条件下，仅延长RETURN5髋时长0.22s，使膝最低角从8.224622°提升到8.298971°，最低点从17.166000s提前到16.988500s。膝reference停稳时的实际状态完全相同；停稳后继续下行从0.105483°减至0.031133°。因此本次改善集中于后续下探，不能修复干预前已形成的约1.17°误差。

同一干预使髋下冲从0.688142°减至0.328992°，最大robot命令从160.540732Nm减至150.329845Nm，并降低终末膝/髋加速度响应幅度。它证明“髋终末时序通过耦合系统影响膝停止响应”，不把中间路径唯一归因于人体质量矩阵、robot反馈或cuff柔顺中的任一项。精确native分叉核验见 `audit/Dev_FULL_NATIVE_CAUSAL_PROOF.json`；完整配对资格和新状态结果见REPORT。

## 延迟和加速度预测的实际局限

每个5ms控制区间包含20个0.25ms native步。原增量响应模型以因果加速度和命令wrench增量为中心，源码明确未包含robot惯量及interface瞬态。其终末下一5ms平均膝加速度预测误差RMSE约36.707°/s²；仅保持因果测得加速度的对照约2.217°/s²。该局部预测目前是限制/clearance控制的一部分，不应直接用作已验证的停止预测器。

100ms source age是准入上限，40ms bridge是参考交接；不能把它们相加宣布固定140ms反馈延迟。科学模拟中的实际request→activation为约5ms，之后40ms bridge；host实时资格仍未取得。

![停稳前后下冲和跟踪误差](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/figures/04_overshoot_before_after.png)
