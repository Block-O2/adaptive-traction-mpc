# Pilot v1 冻结任务与奖励合同

身份：独立开发训练，单一 nominal 物理任务、单 seed；不授予科学晋级。没有 held-out 调参；4个评价仅为冻结checkpoint nominal评价，重复不称未见状态泛化。

物理、robot/cuff/Human、0.25ms native dt、5ms控制、[5°,10°]→[120°,120°]→返回、ROM [0°,125°]、原0.5s连续dwell、wrapper移动9s/HOLD1s timing floor、phase10s/TASK30s、controller/certificate/admission/100ms expiration/40ms bridge/governor/lifecycle全部继承封存源码。

动作：原native planner event上的两个有界进度比例[-1,1]；原certificate及实际执行扭矩receipt独立于提议。actor 41D只读因果传感器、公开目标/时钟及过去提议/拒绝，无未来Human truth。随机初始化32×32 MLP；不使用教师轨迹/模仿权重。

奖励：5ΔΦ+20×完整成功−10×失败−0.0002ΔJF−0.01ΔV。Φ为原分phase真实传感器任务进度，失败终点Φ=0；γ=1；V为原估计加速度归一化平方积分。失败terminal completion额外扣max(0,1.5−累计成本)，故失败完整return=-10−max(1.5,cost)−5Φ初值。1.5来自原安全上界200N×30s的力成本1.2与归一化加速度成本0.3。失败真实成本与积分仍独立保留；越界成本继续扣，硬安全绝不由奖励抵消。该修复在正式记账前完成；历史v2记录不重写、不并入曲线。

成功必须完整OUTBOUND/HOLD/RETURN、原COMPLETE及causal_return_actual_completion_commit。有限任务成功/失败/到期均terminated=True、truncated=False，终态obs为0。资源/异常/owner stop为异常partial，不能伪造任务失败或success。每个完整episode组成一次PPO rollout，所有真实transition进入PPO；不截短任务。每次4 epochs、batch16、lr3e-4、GAE .95、clip .2、标准Gaussian sample及原Box clipping，与SB3默认采样语义一致。

评价：初始确定性策略、固定合法[+1,+1]、最终确定性checkpoint两次；相同nominal初态和执行权限。独立时长必要回归仍19.030±.050s，但不将其冒充原B/H150完整scorer。任务/安全/motion/causal/host qualification分别报告。学习改善依据完整成功率、进度、阶段/失败时长、实际动作和完整物理指标，reward上升单独不构成改善。

阶段：5→20→50，阶段门核对全部reward/termination、安全、资源、梯度、ownership；stage3须环境稳定且有成功/进度学习价值。最多50训练+4评价，native≤8,000,000，RL decision≤6400，Adam≤2500。墙钟与最后45分钟限制见配置。异常立即保存、停止。跨进程恢复从新完整物理episode开始，保留optimizer/RNG/计数，不声称中途MuJoCo连续恢复。
