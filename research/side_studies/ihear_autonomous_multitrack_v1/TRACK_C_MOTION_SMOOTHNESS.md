# Track C — 实际Human平顺性与轨迹质量

## 发现与研究分配
native true dq按原0.25ms时间轴两次gradient得到acceleration/jerk，edge_order=2、不删端点。SG5/SG21、order3只作敏感性，不替代raw验收。TV_v是双joint速度向量相邻差范数之和，TV_a同理；combined jerk RMS是sqrt(mean(sum(j²)))，各joint门另算。

|候选|Δ真实膝下冲°|ΔJ_F对ER N·s|完整TV_v Δ%|完整TV_a Δ%|完整jerk RMS Δ%|
|---|---:|---:|---:|---:|---:|
|Adev_AV090|-0.003153622|+0.450487445|-0.638868|+0.031001|-0.705427|
|Adev_AV080|-0.006344743|+0.897391372|-0.890976|+0.505604|-1.248944|

|运行|raw/SG5/SG21膝jerk RMS °/s³|raw/SG5/SG21膝jerk max °/s³|
|---|---|---|
|Adev_ER|679.781446/676.279621/604.654887|17842.989139/17424.063928/12496.852534|
|Adev_AV090|674.304867/670.802043/599.104576|17842.989139/17424.063928/12496.852534|
|Adev_AV080|670.131913/666.615268/594.575552|17842.989139/17424.063928/12496.852534|
|Bmap_ER|679.030080/675.521045/603.744359|17842.989139/17424.063928/12496.852534|

新速度候选真实降低完整velocity TV和combined jerk RMS，却轻微增加完整acceleration TV，且未修复excursion、J_F也上升。这是实际运动的有界改善与代价并存，不是数学reference更光滑即可晋级。
还有一个直接反例：×0.80的R3参考膝速度峰从19.832669降至19.488670°/s，真实Human同窗峰却由19.866159增至20.243157°/s。参考峰下降不能替代实际峰验证；后续R4真实速度峰虽然下降，完整force仍增加。完整窗口划分及积分闭合见derived/TRACK_A_WINDOW_RESPONSE.json。

## 时间分布与历史负结果
derived/TERMINAL_ESTIMATE_AND_COMPENSATION.json逐joint保存raw峰时刻/phase、高值样本分布和平方能量份额。历史D膝267.010807°/s²窄峰、raw jerk RMS1920.131547°/s³已经由ER显著降低，但余下终末下冲并未随峰值消失。全程p95、extrema、局部峰不能互相替代。
既有18D+Waypoint：去程平滑完整J_F只降低0.016413030 N·s，回程平滑反而增加0.016430641 N·s；后者局部省0.051324而下游增加0.067755。第二轮T去/回程微小shape收益仅0.004602/0.000682 N·s，未达冻结晋级。已有完整物理证据足以停止同一0.05°边界密集搜索。
固定外端q/dq/ddq与duration的quintic具有reference积分平方jerk最小结构；这个数学结论不约束闭环实际Human一定最平滑。历史改shape的reference jerk能上升而局部速度TV下降，指标目标本就不同。

## 停止与未解决
本Track完成诊断，没有额外Waypoint物理优化；使用A的真实干预作为平顺性反例。更广合法时序/协调空间未被否定，但重新研究需要一个能解释完整下游响应的新窗口和可证伪机制，不能仅重复更小q点搜索。

![Adev_full_motion_force.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/Adev_full_motion_force.png)
