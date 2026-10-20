# 研究级真实运动质量与任务公平性协议 v1

此协议是已暴露历史数据上的研究敏感性设置，**没有临床容差或舒适性资格**。阈值在本包derived候选分析前冻结；完整原八组B参考分布及hash见FROZEN_B_REFERENCE_DISTRIBUTION.json。不得按结果改变容差，也不把参考分布当作患者标准。

第一层必须满足原物理安全/ROM、任务COMPLETE、原tracking资格、原目标/时间可比性及原生合法执行。原force/moment peak与clearance下限等安全条件全部复用，未猜造新原生门限。历史SCI物理/因果有效，与真实host生命周期资格分列。

第二层关注真实人体dq、加速度peak/p95/RMS、启停/反向窗口、jerk及数值敏感性、excursion和完整任务J_F。速度使用native真dq；加速度为实际time上的gradient(edge_order=2)，jerk再次gradient；跨phase计算，不删端点。导出raw与3阶Savitzky–Golay5/21节点（约1.25/5.25ms）敏感性。phase启停窗口±100ms、速度反转±20ms；0.5deg/s反转事件检测只用于排除零速抖动。参考平滑性、robot/cuff运动不能代替人体运动。

| 研究档位 | 速度/加速度分布倍率 | excursion绝对变化° | 累计角位移倍率 | 阶段/终点变化° | phase轨迹形状最大差° |
| --- | --- | --- | --- | --- | --- |
| strict | 1.0 | 0.0 | 1.01 | 0.5 | 0.5 |
| moderate | 1.1 | 0.5 | 1.05 | 0.5 | 1.0 |
| wide | 1.25 | 1.0 | 1.1 | 1.0 | 2.0 |

三档共同允许完整任务时长绝对差≤0.1s。核心运动筛查要求hip/knee速度max/p95/RMS与加速度p95/RMS在同档倍率内；加速度peak另报，不把数值尖峰自动变成新临床硬门。jerk p95/RMS同档筛查单独保存为optional，raw/filter所有值保留，未要求所有次要指标Pareto dominance。

任务运动剂量包括实际peak-to-peak excursion、累计abs Δq与积分abs dq、phase端点和最终q/dq。每phase以原transition物理边界、时间进度0–1对齐201点，比较真实q最大差。这是较严格的研究级轨迹可比性筛查；K3本来会改变协调轨迹，所以必须同时报告拆分gate诊断，不能将该形状容差天然当作临床或唯一科学公平性规则。分支筛查使用完整TASK运动/剂量，同snapshot zero-residual suffix作参考（既有prefix不撤销）；后缀窗口另行导出。完整host配对使用其成对B arm。

第三层允许有界补偿：moment integral≤1.25×B，true-reference RMS tracking每关节增加≤0.5°，但不得覆盖原硬资格失败。分支moment比较使用remaining integral，完整host比较使用full-task integral，二者另存完整数值。moment不是momentum。没有新加权reward。

所有基于未来motion标签的筛查均为离线有限候选参考，不能部署；没有预测motion admission模型。新增branch必须有可恢复完整状态、合法native执行、可信高分辨率trace才可评估。此次仅历史native约0.25ms运动已可恢复；原contact/tracking约5ms及原native scorer峰值分别标明。

## 上一轮knee excursion增加的含义

| B运行 | Δknee excursion° | Δ累计knee角位移° | Δ最终knee位置° | Δ完整任务J_F N·s |
| --- | --- | --- | --- | --- |
| 008_nominal_pair1_B | 2.833552 | 6.706682 | 0.000888 | -76.653406 |
| 011_nominal_pair2_B | 1.717069 | 4.694580 | -0.011193 | -95.234393 |
| 012_deviation_pair1_B | 1.263204 | 3.655645 | 0.016368 | -117.789392 |
| 015_deviation_pair2_B | 1.384657 | 4.002804 | 0.004051 | -88.238147 |
| 001_deviation_P1_seed1_B | 2.078828 | 4.385585 | -0.687065 | -81.566332 |
| 004_deviation_P1_seed2_B | 1.482086 | 3.944910 | 0.082586 | -130.050643 |
| 006_deviation_P2_seed1_B | 1.108985 | 2.949900 | -0.004063 | -91.435895 |
| 007_deviation_P2_seed2_B | 1.326122 | 2.191321 | 0.132921 | -96.952976 |

增加的幅度伴随更大的累计knee角位移：2.191321–6.706682°。终点偏移幅度最大0.687065°，并非等于1.109–2.834°的excursion变化。它主要是中途实际轨迹/过冲/反转和累计运动量变化；任务原目标与完成条件不变，也不意味着真实运动剂量相同。没有把J_F按excursion归一化掩盖差异，不能推断临床舒适或伤害。

完整配对均不通过本轮三档完整研究profile；这是本轮新研究筛查结果，不撤销历史安全PASS或force收益，不改历史R2/strict55失败。
