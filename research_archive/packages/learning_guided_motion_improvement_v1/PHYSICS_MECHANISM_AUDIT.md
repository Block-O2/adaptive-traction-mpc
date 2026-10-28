# 物理机制与信息边界审计

零新增物理。见PROXY_MODEL_RESULTS.json的独立allocator重算与实际完整积分。事后使用estimated q/requested torque；事前重建只用已完成B的causal reference、commissioned估计与提议参数。没有使用目标H150未来真值/torque/receipt。历史36.53/37.92来自另一开发条件，本轮不移用作预测准确率。

名义Human inverse_dynamics与allocator存在；legacy Predictor采用人为指数tracking衰减、12点segment积分和settling allowance，没有robot/cuff/contact闭环。该闭包可算负荷近似，不能保证真实motion/task。残差学习是否有用需真实预序验证。

## 锁定新candidate的事后机制核算

只在候选/模型冻结和物理队列结束后运行，不回流任何新proposal。estimated posture与generalized action输入交换只是allocator代数归因，不是合法可执行物理反事实，也不将它解释成已识别因果中介比例。真实robot六轴torque另由native/receipt独立闭合。

|臂|实际ΔJF|事后allocator ΔJF|geometry输入贡献|请求action输入贡献|实际ΔJM|
|---|---:|---:|---:|---:|---:|
|A|-2.531636168|-2.377871556|1.501025173|-3.878896729|0.648777057|
|B|-2.553483226|-2.405137056|1.382111375|-3.787248430|0.632415944|
|C|-2.553483226|-2.405137056|1.382111375|-3.787248430|0.632415944|

完整posture/reference/action差、分phase受力、瞬时正负差与积分见NEW_CANDIDATE_MECHANISM.json。降力可能伴随moment增量，净完整积分下降不等于每一瞬间都更低。源自已执行状态的好闭合也不能替代事前预测。
