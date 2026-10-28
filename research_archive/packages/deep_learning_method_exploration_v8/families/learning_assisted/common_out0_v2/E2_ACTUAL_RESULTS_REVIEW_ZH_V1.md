# E2 完整48条冻结训练与结果解释

一次完整运行 PASS，0 physics，无重试或范围缩减。冻结 bundle SHA `56b32083ae55ff1cd5e8dc1f3c4e87c08cf4a7948f21fd4a19f9a12b3922f40e`；actual artifact manifest SHA `082c9e75de8d7542379e2155e3be2b7ec247dec6564d991df2f91d2cba422983`；原fit/model/source/data SHA复核不变。此报告只聚合已保存结果，未调用任何新模型或预测。

数据为同父真实common OUT0因果39、完整五recipe语义的48个已完成原任务，10个case SHA/parent context，31原qualified、17原完整motionfail；两缺失recipe不补。不是10个独立患者。全部3807原5ms TASK节点覆盖19.03秒，源标签与原JF/JM左积分闭合。未来estimated/reference/measured只作label；新参数验证物理结果尚未产生，不参与fit。

同一8训练点数量、同架构/初始权重/200步比较 D4 与 DFull；每域4ridge+3MLP，11fold（全开发与10整case LOCO）完整保留，无CV挑优。paired预测delta14及独立deltaJF/JM；其轨迹误差目标与absolute不同，禁止直接比较为绝对状态精度，积分N/A。

以下为10case LOCO、19.03秒，ΔJF/ΔJM MAE单位Ns/Nms；sign分母38个非B非tie，rank分母93个非tie action pairs。qual为greedy选择后的原fullqualification回顾，未用于选择或mask。

## directJF/独立cost头 · D4

| 方法 | ΔJF MAE | JF sign | JF rank | ΔJM MAE | JM sign | regret | qual/10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| KINEMATIC | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| MLP_ACTION_ONLY | 28.454 | 38/38 | 46/93 | 16.375 | 0/38 | 6.327 | 6 |
| MLP_CONTEXT_ACTION | 35.142 | 18/38 | 50/93 | 5.217 | 18/38 | 10.376 | 7 |
| MLP_PAIRED | 27.988 | 38/38 | 75/93 | 4.403 | 38/38 | 1.464 | 5 |
| PERSISTENCE | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_BLIND39 | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_ONLY | 13.572 | 38/38 | 65/93 | 5.431 | 20/38 | 1.663 | 5 |
| RIDGE_CONTEXT_ACTION | 29.735 | 33/38 | 68/93 | 6.108 | 26/38 | 1.374 | 6 |
| RIDGE_PAIRED | 22.467 | 36/38 | 81/93 | 4.938 | 32/38 | 0.289 | 6 |

## directJF/独立cost头 · DFull

| 方法 | ΔJF MAE | JF sign | JF rank | ΔJM MAE | JM sign | regret | qual/10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| KINEMATIC | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| MLP_ACTION_ONLY | 22.444 | 28/38 | 37/93 | 6.931 | 18/38 | 4.589 | 6 |
| MLP_CONTEXT_ACTION | 25.626 | 32/38 | 68/93 | 5.741 | 20/38 | 2.617 | 6 |
| MLP_PAIRED | 19.458 | 38/38 | 89/93 | 3.808 | 38/38 | 0.000 | 6 |
| PERSISTENCE | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_BLIND39 | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_ONLY | 12.925 | 38/38 | 65/93 | 3.197 | 38/38 | 1.663 | 5 |
| RIDGE_CONTEXT_ACTION | 26.265 | 35/38 | 68/93 | 3.712 | 32/38 | 1.572 | 6 |
| RIDGE_PAIRED | 22.566 | 36/38 | 77/93 | 3.381 | 34/38 | 0.493 | 5 |

## 绝对预测wrench原左积分 · D4

| 方法 | ΔJF MAE | JF sign | JF rank | ΔJM MAE | JM sign | regret | qual/10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| KINEMATIC | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| MLP_ACTION_ONLY | 139.152 | 25/38 | 36/93 | 60.993 | 28/38 | 10.034 | 6 |
| MLP_CONTEXT_ACTION | 182.350 | 37/38 | 73/93 | 16.329 | 18/38 | 1.611 | 5 |
| PERSISTENCE | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_BLIND39 | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_ONLY | 273.987 | 38/38 | 65/93 | 60.097 | 0/38 | 1.663 | 5 |
| RIDGE_CONTEXT_ACTION | 253.906 | 38/38 | 59/93 | 59.003 | 0/38 | 3.588 | 6 |

## 绝对预测wrench原左积分 · DFull

| 方法 | ΔJF MAE | JF sign | JF rank | ΔJM MAE | JM sign | regret | qual/10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| KINEMATIC | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| MLP_ACTION_ONLY | 260.743 | 18/38 | 38/93 | 7.875 | 37/38 | 5.839 | 6 |
| MLP_CONTEXT_ACTION | 84.950 | 30/38 | 65/93 | 9.966 | 22/38 | 1.612 | 4 |
| PERSISTENCE | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_BLIND39 | 35.534 | 0/38 | 0/93 | 5.307 | 0/38 | 38.870 | 10 |
| RIDGE_ACTION_ONLY | 22.687 | 38/38 | 65/93 | 2.310 | 38/38 | 1.663 | 5 |
| RIDGE_CONTEXT_ACTION | 33.470 | 32/38 | 65/93 | 2.994 | 36/38 | 1.889 | 6 |

## 结论层级与机制

DFull MLP_PAIRED 的排序89/93、regret0对应10/10全部选择同一个 EARLY_H150；这10个case中该动作无资格mask的窗口JF最低，但仅6/10原完整任务合格。它复现固定动作偏好，不能称个体化控制获益。DFull action-only ridge的ΔJF MAE12.925优于MLP_PAIRED19.458，ΔJM MAE3.197亦优于3.808。paired相对zero-effect基线有有限信息，但不足以超过强action-only幅值误差或固定H的资格结果。

DFull修正了D4长时绝对查询的失配：ridge context的0→19.03s estimated-q区间MAE（两关节平均）99.840°→4.362°，action-only为99.753°→4.348°；这支持时间域对齐机制，未显示该项context优于action-only。DFull绝对MLP context仍44.364°、action-only30.058°。paired MLP的1.770°是delta轨迹目标，不可冒充更优的absolute轨迹。查询来自同一初始状态与public time，并非Markov逐步rollout。

原0.5/1秒各38个非B对照中19个true tie、19个nontie；不能把全部短窗一概称无动作效应。2秒起38个均nontie。JF获益与JM代价须分别保留，16头标准化loss不是政策物理加权reward。

独立direct cost头与绝对预测wrench积分不能互换。例如DFull ridge action-only的ΔJF MAE12.925对22.687，context26.265对33.470；DFull MLP context25.626对84.950，MLP action-only22.444对260.743。paired无合法绝对B预测，不提供wrench积分selector。任何低cost都不授予原任务资格；绝对轨迹/积分误差说明仍有明显未解决的surrogate一致性问题，不否证整个world-model方法家族。

## 实际工作与资源

704 multihead solve /11264 scalarheads，66 neural init、13200 Adam updates；training forward/backward各17600API/2252800vectors（sharedB各4400）；inference2240 backendAPI/5853696vectors，logical learned trajectory1344，fixed baseline1461888vectors单列。与冻结EXPECTED完全一致。外wall20.38s、user9.86s+system1.71s、RSS198292KiB；内部wall20.322197s、CPU11.507787s。单CPU affinity、threads1、AS1GiB、外240s/killafter2，原全局钟不重置。

三次已观察PID/startticks均闭合。time1179953→timeout1179954→唯一leaf1179955，startticks61732096。原monitor在zombie时以空cmdline覆盖leaf文本，故不能伪称原receipt有最终Python executable文本；命令树/唯一child/返回code和proc消失证实该owned计算已结束，原receipt保留不改。

只读摘要另计wall0.57s、user0.51s+system0.06s、RSS68052KiB，0新prediction/fit/physics。全开发冻结模型与所有LOCO结果保留。未经审批不部署或运行新parameter物理。
