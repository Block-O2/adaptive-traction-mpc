# 两seed首个实际Reward更新的受控比较

生成UTC：2026-10-20T23:32:51.331737+00:00。每个seed内部，R0/H2、R1、R2的首批物理obs/raw actions/旧预测/episode边界、完整policy/Adam/RNG/计数、PPO超参数及update函数AST均一致；first batch分别80和77 transitions，实际各20Adam/4epochs。before/after ZIP SHA独立核对。本工具只读取已训练模型，无新physics/Adam。

|seed|实际Reward|actor参数L2变化|共享首批obs的mean绝对变化hip/knee|Gaussian KL pre→post|
|---|---|---|---|---|
|1495656323|H2_AGG64|0.03532398|0.01963477 / 0.00330105|0.000215932|
|1495656323|REWARD_R1|0.03277483|0.02081490 / 0.00387316|0.000236095|
|1495656323|REWARD_R2|0.03301433|0.02070803 / 0.00362429|0.000233133|
|1630784693|H2_AGG64|0.08724561|0.01160521 / 0.04747846|0.001311418|
|1630784693|REWARD_R1|0.08367507|0.00730692 / 0.05275046|0.001525888|
|1630784693|REWARD_R2|0.08353136|0.00726735 / 0.05228586|0.001499790|

两seed都显示：R1在未更新参数处的actor裁剪后梯度更小，却没有带来同比更小的实际首更新KL；R1的KL均略高于R0/H2，mean不同分量的变化也不同。初始梯度大小不足以预测带有既有Adam状态、多个minibatch/epochs的实际policy更新。R2与R1同量级。这里只归因受控first update的Reward目标效应，不识别后续闭环退化唯一根因，也不把Gaussian提议当真实torque、安全或泛化资格。原一seed阶段记录已按hash归档。
