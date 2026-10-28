# Reward credit assignment 与执行机制诊断

本项只读保存轨迹，不启动物理或 Adam。完整与失败 partial 分开；同轨迹重评分不是 R4 训练效果。

R1/R4 对任意完整 episode 的总式为 `2(phi_terminal−phi_initial)+20−C`；失败为 `−2phi_initial−15−max(15,C)`。R4−R1 在成功轨迹上等于 `−.015*JM`。失败且两种成本均低于15时，终末 floor 补偿会抵消此前增加的 moment 成本，总回报不变。

实际保存训练轨迹 120 条，失败 19 条，其中两版本失败 floor 同时激活 19 条；完整 101 条。

这说明当前 moment 价格主要改变成功轨迹的总代价排序；不能只凭失败 partial moment 小就期待更高总回报。单步 GAE/critic/优势归一化仍可能因成本的时间分布变化而改变，总代价相同不等于梯度相同。gamma=1 的 potential 总和 telescoping；lambda=.95 的近似优势与继承 critic 仍影响有限样本学习。

已审计实际 PPO 更新 29 次；逐批保存 finite advantage、value/return 范围、旧密度误差、KL/ratio、mean 漂移和 log_std。此项不把 critic 数值变化误写为真实任务收益。

几何与 emitted-reference 拒绝采用原 summary.decisions 中所有非 ACTIVATED disposition，包含 FAILED 和 REJECTED，逐相位计数并与 runtime rejections 对齐。原始失败最后一步的 mean/std/raw/clip 保留；内部 raw 的失败不能归咎于边界 clip。

降低 STD 会改变 clip 后的一阶矩和边界点质量，尤其 network mean 已越界的维度；这不是 bounded action 上仅改变方差。解析 clipped Gaussian 均值/方差只描述提议分布，不是已应用 torque 分布。原 native/receipt 审计另行证明实际执行归属。

结论限制：没有固定失败状态的 planner/mean 物理反事实，不能唯一归因；没有把动作 RNG 当作独立患者或物理初态。
