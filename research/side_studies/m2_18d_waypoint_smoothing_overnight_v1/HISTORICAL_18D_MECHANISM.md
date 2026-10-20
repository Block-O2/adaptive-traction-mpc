# Historical 18D mechanism audit

本轮从原始 trace 独立复算：B=1438.613498467 N·s，18D=1400.697221153 N·s；两者完整任务19.030 s。开发条件既有 task/safety/motion PASS；历史合法新prefix motion仍为0/4，未获得正式Native LEVEL2、host-clock LEVEL3、真机或临床资格。

18D不是18个任意waypoint。`rich_planner.py`在原NativeResidualPlannerV2上加入18个连续参数：OUT/RETURN各相位的common/differential progress多项式，以及通过速度的common/differential tilt。先使用原生目标计算归一化进度m、e=sin²(pi*m)、u=2m−1，再改变内部目标；原scheduler选择合法duration并认证。完整方案还包含RETURN槽1/2的−0.020/−0.022 differential plateau；遗漏这两项就不再是原18D。完整参数保存于HISTORICAL_18D_PARAMETERS.json；组合必须保留它们。

4–6 s降力10.099746 N·s，TV_v下降，但TV_a与combined jerk RMS增加。15–16 s降力9.996502 N·s，TV_v与combined jerk RMS下降，TV_a增加；其中15–15.5 s甚至TV_v、TV_a与jerk同时变差。不能把18D当成单纯平滑成功案例。

既有v3存档机制核算给出：原allocator代数输入重算净变化−36.527540 N·s，实测−37.916277 N·s；去程更早抬髋与模型重力需求下降一致，回程更早降膝与弹性需求下降一致。相同commissioned参数下，geometry单独作用并不占优。command分量重构显示allocator通道差异最大，但这是代数分解，不是关闭通道后的物理反事实。上述分解作为有来源的既有证据保留，本轮不冒称重新执行其完整kinematic重构。

tracking并非全部改善，完整moment积分增加约7.03%。request/splice时序也发生变化，RETURN slot4的splice提前约0.405 s。姿态负荷、tracking、allocator和时序共同变化；尚不能唯一归因于smoothness、某一torque通道或时间调度。新干预只改变内部q点，保留每个外端q/dq/ddq与suffix duration，整任务duration与phase边界另以实际结果核验。

原始来源hash：audit/HISTORICAL_INPUTS.json。逐窗独立指标：derived/HISTORICAL_WINDOWS.json。共同时间轴：figures/18d_mechanism_timeline.png。瞬时force为5ms存档采样；native motion为0.25ms，不能混称force采样率。

历史生成算法已按原源码核对：`overnight_runner.py`在NATIVE_SCALAR_18 seed附近做18维有界COBYLA，目标为完整J_F/B_J_F，约束为原motion/task/safety比较项；quality配置maxiter=52、rhobeg=0.15、tol=0.015、catol=0，参数在[-1,1]归一化盒内再按原scales映射。它不是平滑目标优化，也不是RL/Q。冻结_063是有限开发搜索中选出的合格候选；预算终止不等于收敛或全局最优。原报告/源码与完整参数分别保存于provenance和HISTORICAL_18D_PARAMETERS.json。

本轮另运行原纯allocator需求分解的独立代数重算，结果见derived/DEMAND_TERM_DECOMPOSITION.json，未增加physics：gravity −18.137642、elastic −30.621873、velocity terms −0.035799、remainder +1.225298、allocation geometry +11.042477 N·s，合计−36.527540。该恒等分解与既有报告一致；没有重跑物理消融或把比值当因果中介份额。
