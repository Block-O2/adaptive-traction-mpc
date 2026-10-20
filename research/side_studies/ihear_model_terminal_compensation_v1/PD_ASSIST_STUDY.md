# 轻量终末PD辅助

结论：本次轻量PD没有独立改善价值，真实下冲比ER增加0.00275000°，仍未通过原excursion门。其物理输出确实生效，不是零作用或未执行。

辅助意图采用Kp=14、Kd=4.4：max(0,14×(q_goal−q_est)−4.4×dq_est)，只沿膝终末制动方向作用。目标来自当前任务已接受的terminal reference缓存；当前issued终点为9.5°，不是偷偷改动注册10°任务目标。

near门由当前reference距终点6°以内逐渐开启，2°以内达到1；速度方向门在−0.2至+0.2°/s平滑变化；停止距离使用当前估计负向速度的平方/(2×0.35)，配合2°位置裕量。三者都是当前因果状态/参考函数，不以“17秒”触发。幅度±0.2rad/s²、变化率1rad/s³；stale、非有限值或无合法目标时辅助归零，并保留原安全机制的最终决定权。

新增广义作用=M(q_est)×delta_a，不直接附加到电机力矩。原reference输入定义、40ms bridge、100ms lifecycle/source age、5ms控制周期不变。reference证书不声称覆盖新控制律；变化后的作用由原输出过滤器、allocator、supervisor和actual-write检查重新验证。

|辅助|Δ下冲相对ER (°)|ΔJ_F (N·s)|有效修正receipt|最大广义修正 [hip,knee] (Nm)|结论|
|---|---:|---:|---:|---|---|
|KD120|+0.00036311|+0.00002153|603|[0.107476, 0.040323]|motion FAIL|
|PD|+0.00275000|-0.00349334|385|[0.107566, 0.040323]|motion FAIL|
|FF|+0.01261148|+0.02233690|594|[0.423335, 0.107478]|motion FAIL|
|PDFF|+0.01532879|+0.02027724|603|[0.423336, 0.107478]|motion FAIL|


正向制动意图未必降低耦合系统的最终下冲；这里的结果表明该微小附加作用没有足够收益，不足以唯一归因于allocator、髋膝惯性或cuff柔顺。没有继续试更大Kp/Kd，也不把有界、局部稳定极点或“无安全失败”误称为全局稳定证明。

![有界辅助意图](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/figures/09_controller_intents.png)
