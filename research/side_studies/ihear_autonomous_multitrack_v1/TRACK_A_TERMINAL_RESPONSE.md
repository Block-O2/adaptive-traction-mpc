# Track A — 终末停止响应与真实overshoot

## 假设、合同与结论
在ER110_R4_120父规则冻结下，仅将RETURN3膝通过速度乘0.90或0.80，保留该槽原选目标、髋通过速度与duration，通过原fixed-duration certificate/mechanics/escape/current admission检验。两个候选均数学可行、真实激活，完整task/safety/receipt通过，但原motion均因excursion失败。停止该因素搜索；不通过放宽门或增加第三个更小倍率取得通过。

## 真实下冲定义与时间
本包将回程真实下冲定义为max(0,最终issued reference q−RETURN真实最小q)，另报“参考稳定停止后继续位移”。native极值分辨率0.25ms，参考稳定停止时间来自5ms记录。它们与全程excursion−matched B不同。
ER膝参考终点9.5°；实际最低8.224621516°，下冲1.275378484°。参考16.895s稳定停止时actual=8.330104289°、dq=−0.191408179°/s；271ms后达到最低点，期间继续下降0.105482772°。首次穿过9.5°在16.5085s，因此大部分下冲形成于参考停稳之前。
原B真实下冲0.577911072°；其最低点17.09825s早于参考稳定停止17.175s。不能使用同一个“停稳后位移”代替各方法完整下冲。
ER全程膝max相对B低0.148870945°、min相对B低0.697467411°；相减才得到excursion差0.548596467°。这个恒等式说明0.548596°不是overshoot幅度。

## 配对物理结果
|完整运行|J_F N·s|对本组B降力%|膝真实下冲°|膝excursion−B°|原motion|
|---|---:|---:|---:|---:|---|
|Adev_B|1436.456498145|0.000000|0.577911072|+0.000000000|PASS|
|Adev_T|1403.456709761|2.297305|1.261666035|+0.534884018|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/p95_abs, excursion|
|Adev_D|1402.234611439|2.382382|1.270504839|+0.543722823|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, jerk_deg_s3/rms, excursion|
|Adev_ER|1402.644192729|2.353869|1.275378484|+0.548596467|FAIL: excursion|
|Adev_AV090|1403.094680174|2.322508|1.272224862|+0.545442845|FAIL: excursion|
|Adev_AV080|1403.541584101|2.291397|1.269033740|+0.542251724|FAIL: excursion|

|候选|Δ真实膝下冲°|ΔJ_F对ER N·s|完整TV_v Δ%|完整TV_a Δ%|完整jerk RMS Δ%|
|---|---:|---:|---:|---:|---:|
|Adev_AV090|-0.003153622|+0.450487445|-0.638868|+0.031001|-0.705427|
|Adev_AV080|-0.006344743|+0.897391372|-0.890976|+0.505604|-1.248944|

所有积分为完整19.030s，phase仍9.005/1.020/9.005s。B/T/D/ER与历史全trace/native/receipt物理字段逐项复现。候选在新splice前与ER全body qpos/qvel、command/contact及step归属一致，之后真实运动改变；细节见derived/CAUSAL_RESPONSE_AUDIT.json。干预不是Human真值回放。

×0.80曾使真实膝角最大变化1.270993°、膝速度最大变化3.755052°/s，但RETURN5及最终等待窗口的最大膝角差已缩到0.020987°，最终下冲差仅0.006345°。RETURN3/4/5的原选时长1.245/1.515/0.440s及请求时刻均保持，不能归因于后续duration重新选择；RETURN4髋目标因果变化−0.018624°，其余冻结规则保持。窗口账本见derived/TRACK_A_WINDOW_RESPONSE.json。
×0.80在R3及其桥接窗口节省force积分0.435311 N·s，R4及其桥接却增加1.329535，最后增加0.003167，精确闭合完整+0.897391。局部收益确实存在，却被下游代价超过；这些partial窗口只用于机制诊断，不进入排名。

## 机制证据与限制
R3/R4请求、膝首次过目标、参考停稳、实际最低点的因果估计与真值角度差均约0.001°以内；在参考停稳处估计跟踪偏差−1.169492°，真值−1.169896°。现有证据不支持“估计器完全看不到误差”。RETURN4膝速度落零后RETURN5仍在完成髋运动；参考/allocator/position/velocity torque与恢复峰同步，但本轮未单独干预中介，因此不能宣布allocator或某一模型项是唯一根因。已采样停止窗口没有clipping或shank-bed接触事件；这不等于没有cuff耦合力。

## 失败边界与再次研究要求
×0.90/×0.80只把下冲分别减少约0.003154/0.006345°，相对于原0.048596° excursion缺口不足，且J_F增加。数学速度边界变小不保证真实终末误差等比例降低。此因素信息增益已低，停止继续缩小速度。
下一项有价值证据应来自一个新的、前瞻注册的髋终末时序受控干预：膝终点/停止参考不变，仅改变原合法RETURN5髋终末时间形状，检验膝继续运动是否随之改变；先重做原证书，不更改控制gain、模型或阈值。本轮不执行第三个A候选。

![Adev_terminal_response.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/Adev_terminal_response.png)

![terminal_estimate_tracking.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/terminal_estimate_tracking.png)

![Track_A_local_and_downstream.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/Track_A_local_and_downstream.png)
