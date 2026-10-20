# Force—motion机制诊断

先对复制保存的完整raw独立核算；新复现另列BASELINE_REPRODUCTION。不把历史值伪装成新rollout。每个native步均对实际receipt区间、完全一致applied torque与receipt steps核验。TRACE_VERIFIED。

原I_F口径：TASK 5ms边界上cuff force范数左积分；force单位N、moment单位N·m、积分N·s/N·m·s。TV_v与TV_a按0.25ms native true dq微分后作梯形累计，单位rad/s、rad/s²。reference使用解析ddq与5ms采样ddq的梯度诊断。口径分开，均非临床标准。

|阶段|B J_F|18D J_F|收益N·s|时长s|
|---|---:|---:|---:|---:|
|OUTBOUND|725.825779278|707.100519988|18.725259290|9.005000|
|HOLD|54.394338793|54.394332783|0.000006010|1.020000|
|RETURN|658.393380396|639.202368382|19.191012014|9.005000|

完整B=1438.613498467486、18D=1400.697221153149N·s；总收益37.916277314N·s / 2.635613%，分母为一个已暴露Human的同条件B。全程19.03s，phase积分闭合误差<1e-8N·s。

A. 收益在OUT/RETURN形成18.725259/19.191012N·s，HOLD几乎不变。15–16s单秒收益9.996502N·s；4–5s与5–6s分别4.907485与5.192261。TRACE_VERIFIED。

B. 峰谷与高力只部分重合。0.25s分箱，B的OUT force与speed-L1/acceleration-L1相关为.717/.371，RETURN为−.178/−.048；18D为.665/.195、−.384/−.268。序列自相关、姿态和阶段混杂未分解。CORRELATIONAL，不作显著性或物理因果结论。

C. reference本身有宽尺度速度峰谷。按0.5°/s prominence、峰间≥100ms定义的时刻保存于DIAGNOSTIC_RESULTS；正常分段加减速不自动等于抖动。原C2不消除段内极值。SOURCE_CONFIRMED / TRACE_VERIFIED。

D. 终末tracking偏差突出：18D膝约9.542°/s在TASK7.000s，髋约4.963°/s在16.900s，分别在最近suffix后230/360ms。TRACE_VERIFIED。

E. ±150ms移位相关中，18D OUT hip/knee最佳相关滞后40/65ms、RETURN50/60ms。这是整phase相关，并非激励辨识的因果响应延迟；也不等同于D的峰值距splice时间。CORRELATIONAL。

F. 分段固定通过速度、duration、端点零加速度与终末制动提供反复加减速的结构线索。没有消融证明哪些“不必要”，也不能单归cuff或估计器。具体因果份额UNRESOLVED。

G. 高力不必伴随大速度变化：18D1.0–1.25s平均104.094N而acceleration-L1均值12.995°/s²；1.25–1.5s平均106.454N、TV_a仅.6180rad/s²。高力/较低acceleration阈值分别为全运动分箱force75%分位与acceleration中位数，完整值见audit/FORCE_MOTION_WINDOWS。它们仍在运动，不称静止。force与moment分箱相关更高（18D OUT/RETURN .775/.744），支持下一轮同时查姿态/支撑、moment和tracking；gravity是否主因仍UNRESOLVED。

H. 5–6s收益5.192261N·s，但TV_v从.560375升至.579751rad/s、TV_a从7.557340升至8.015063rad/s²。15–16s收益9.996502N·s而TV_a从8.681795升至10.622485。不能用“jerk更低”解释所有局部收益。TRACE_VERIFIED。

完整actual TV_v：9.690794510/8.660500761rad/s，下降10.632%；TV_a：125.159334262/124.743509035rad/s²，仅下降0.332%。真实J_F不能用平顺性代理替代。

建议五个局部开发区间：0.75–2.50s（持续高力/较低加速度）；4–6s（约10.099746N·s收益且TV方向不一致）；6.60–7.40s（去程终末tracking）；15–16s（最大单秒收益而TV_a增加）；16.50–17.50s（回程终末髋tracking）。这些已用作开发诊断，未来不得称未见时段。

数值微分：np.gradient(raw native dq,t,axis=0,edge_order=2)，再微分求jerk。端点保留二阶单侧差分，未删除峰值。绝对时间平移引入微小浮点舍入差，已量化，未改历史口径。SG5/21三阶窗口敏感性另存，raw仍主诊断。reference jerk是5ms解析ddq序列的梯度，跨段样本不等于严格连续时间jerk积分，与0.25ms actual raw不混用。

每5ms都有receipt，尖峰邻近receipt不是因果识别；不能将峰值直接归因新suffix。三张对齐图见figures/。不修改原历史PASS/FAIL。
