# v8 统一实验合同

唯一时钟见 ACTIVATION.json：北京时间2026-10-27 11:25:40开始，23:25:40硬截止，不因恢复、任务或子Agent重置。预留至少30分钟封包；每个实验局部有限超时，不设全局episode或物理尝试数额度。单物理owner，RAM可用≥6GiB，磁盘余量≥20GiB；原源码、raw、checkpoint及历史报告只读。正式Stage2、Campaign、硬件、扩容及自动Git写操作均不运行。

完整原合同保持Human/robot/cuff方程、guard、安全阈值、HOLD、端点、ROM、torque、clearance、scheduler、admission及原scorer/motion门。原任务实际phase约9.005/1.020/9.005秒。JF/JM为TASK含HOLD的5ms实测wrench模长左积分；原native未滤波运动门完整保留。完整失败与partial单列、保存原积分且不得排名。新算法只改变独立研究包内已登记的协调选择、学习目标及训练配置。

每个变体分别检查 IMPLEMENTATION_VALID、LEARNING_VALID、DECISION_VALID、TASK_VALID、BASELINE_INCREMENT、GENERALIZATION、EFFICIENCY；不得从低RMSE、训练reward或proposal改变推定更高层。模型输入只含决策时真实可得的observer/reference/wrench、commissioned有效参数、公开task状态与已完成trial历史。true case、hidden Human、未来receipt/motion/成本/完整资格仅作评价或过去已结束trial标签。OUT0完整77D仍无效。最初仅用25D commissioning子集；后续A3逐字段源与时刻审计批准KIN33（当前估计q/dq、请求参考q/dq）及WRENCH39（再加当前实测F/M），并要求实际job/source/checksum/age/QA。尚不存在的TASK积分/峰值不补零，guard43不进入拟合，无效QA必须停止相关推理。

统一离散动作是完整冻结recipe JSON，包括18D/T底层、early/late激活、timing、posture、legacy及slot覆盖；动作库哈希、后续policy、时点和case身份共同绑定。同动作权限的强固定/传统优化、历史禁用、简单规则与学习模型公平对比；跨权限方法另列。不同后续策略标签不混库。JF、JM、motion与wrench各列；新目标需预登记，不能改旧benefit或借加权总分掩盖代价。

权限核对补充：早期离线RF/PPO/BC、C3B实际上只覆盖三recipe，五recipe是审计菜单而非这些actor的权限证明。真实PG已单独显式lift至五recipe，BC聚合也为五recipe；后续同权限主比较用这些新冻结checkpoint，旧三动作结果保留但不与五动作策略混合排名。

历史v5/v6/v7与更早研究是已暴露开发资料，不冒充独立test。同父多候选、seed差异、配置hash或fork时钟不自动增加独立状态；训练按真实父/context分组。冻结验证的case、合法prefix、模型与菜单须在结果前固定，已打开的失败不能替换。真实父native/causal/physical身份须核对。新物理执行先通过原B资格；相同父串行完整fork，父前后不变并与B raw核对。

首项V8ENGH01仅作已暴露heavy条件的工程复现，菜单B/LATE_H150/EARLY_H150，1冷parent+3child，局部3600秒、每物理600秒。其结果与原v7相应raw逐值核对，不当泛化证据。复现通过后才登记新科学菜单。历史资产缺失如实标记，不补造旧凭据。

所有分支在METHOD_EXPLORATION_MATRIX与METHOD_VARIANT_LEDGER登记动机、机制、数据、权限、强对照、实际结果、修正和剩余变体。科学家族停止须限定本轮覆盖范围，未充分覆盖写NOT_FULLY_EXPLORED。实际START/END、native新增、训练更新、拟合、scorer与资源分账，共享fork前缀只计parent一次。物理尝试全菜单已跑不能声称实际省试。
