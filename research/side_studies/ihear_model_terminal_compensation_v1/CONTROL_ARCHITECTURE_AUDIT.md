# 控制架构审计

本审计基于独立包的实际执行闭包；原B及所有原安全、plant源码仅作路径重定位。完整文件SHA和定位见 `audit/CONTROL_SOURCE_INDEX.json`，原启用选项见 `audit/ACTIVE_OPTIONS.json`。本轮新增控制合同见 `CONTROL_EXTENSION_CONTRACT.json`。此文件描述实际能力，不将历史类名中的“shadow”或“MPC”作为当前执行权限的证据。

## 1. Human模型与真实plant

真实plant为MuJoCo耦合CR12—柔顺cuff—被动2DOF Human，`cr12_plant.py:272`继承SpringDamperCoupledUR10eHumanV2；实际模型换成CR12，不能因父类旧名误称UR10e实验。人体状态由物理步进形成；control只读取因果测量与估计。物理步长0.25ms。

在线控制模型是 `StateResidualHumanModel`：在线识别的有效几何、11个动力学基参数以及有界2×5状态残差。`BaseParameterHumanModel.mass_matrix`具有非零髋膝耦合项，逆动力学由regressor、被动/重力/科氏项、软ROM项及有界残差组成。模型参数是因果估计，并非已知plant真值。完整小腿长度与cuff比例不能由有效膝—cuff距离自动分别辨识。

模型可以计算 `continuous_dynamics` 和固定广义输入下的RK4推进；这不等于已经拥有闭环robot–cuff–Human动态预测器。robot惯量、柔顺界面的瞬态和实际力矩保持响应没有被该2DOF模型闭合。

## 2. 原B已有的反馈

1. 外层Human waypoint规划器用新鲜估计q/dq形成下一目标，并用已发出的reference状态作为新曲线边界；不是盲目开环轨迹播放。目标选择、当前状态准入、几何及mechanics检查、执行后的活态重规划构成反馈。
2. Human跟踪器 `human_waypoint_shadow.py:403`：`a_PD = [180,140]*(q_ref-q_est) + [28,22]*(dq_ref-dq_est)`。原B已经有PD，没有在此路径发现积分项。
3. Human逆动力学把该加速度请求转换成关节广义作用。已有重力、惯性、科氏、被动刚度/阻尼、软ROM和状态残差补偿，不能把再加同一重力项叫新增前馈。
4. 原启用的增量加速度/clearance反馈：因果测得加速度加上 `M^-1 Δtau_command`，必要时投影到原加速度/clearance界限。窗口平均命令为基准，源状态必须与测量对齐。源码明确它不预测robot惯量和界面瞬态，也不是物理安全证明。
5. robot笛卡尔位置/速度、姿态/角速度反馈，及机器人关节零空间姿态/阻尼反馈。冻结默认值：3000 N/m、140 Ns/m、120 Nm/rad、12 Nms/rad；姿态关节项12 Nm/rad、3 Nms/rad。

## 3. 已有前馈、allocator与实际输出

`loaded_execution.py:372`从测得robot q/dq的刚体模型计算bias torque，配合原零空间反馈。allocator以Human广义作用为等式约束，将其映射为cuff wrench，并兼顾合力与表面载荷代理。robot总命令为bias/零空间项加Jacobian转置作用的allocator及笛卡尔反馈wrench，随后保留原force/torque限制与最终执行检查。

实际cuff力由柔顺位移/相对速度以及robot–Human耦合物理产生；allocator期望wrench不是已传入Human的实测wrench。`applied_generalized_action_nm`是软件层广义请求，不能当作Human真实输入。已用源代码确认trace中的 `physical_cuff_force_world_n` 和moment来自 `interface.measured_*`，可用于因果预测；Human qpos/qvel evaluation字段只能用于离线评价。

## 4. reference q/dq/ddq及预测范围

原scheduler用quintic边界状态生成q/dq/ddq，限制参考速度/加速度，检查连续几何和mechanics。40ms bridge负责实际reference的未来拼接；receipt governor把进度与已应用命令绑定。原任务注册RETURN目标[5°,10°]，历史合法robust terminal内部reference为[5.5°,9.5°]；本轮二者都保留。报告overshoot按issued膝9.5°定义，另明确相对注册10°会得到不同数值。

`HumanWaypointFeedbackMPCV1`是receding one-waypoint search，源码明确没有robot/interface动态预测器。mechanics screen使用参考q/dq/ddq的逆动力学估算负担；控制跟踪律本身没有直接的 `+ddq_ref` 项。未来reference在planning/certificate中可见，但原活跃控制链没有未来Human实际停止距离的完整闭环预测。

## 5. 时钟、延迟与资格

控制周期5ms（200Hz），自适应更新名义20ms，native物理0.25ms。W1 ER的RETURN5 request=16.900s、activation=16.905s、splice=16.945s。40ms桥接是实际参考交接的一部分；100ms是source/lifecycle最大年龄，不能直接相加当作每次固定延迟。科学模拟冻结epoch，只由native step推进plant；host耗时仍为profile，不能替代host实时LEVEL3。

最终actual write继续核验source age；过期、失配、未通过当前状态准入的提议不得执行。receipt需绑定真正positive native steps，单个“ACTIVATED”标记不代表实际完整执行。

## 6. 可以复用、缺失与需重新证明的部分

|事项|判断|本轮处理|
|---|---|---|
|估计q/dq、因果加速度、有效模型|已有|可用于新预测与辅助，不使用Human truth|
|合法定时quintic接口|已有|H150重新建证书、mechanics、escape、bridge与current admission|
|Human PD、robot PD、逆动力学|已有|禁止将B叙述为无反馈；KD120单独身份|
|直接reference加速度前馈|活跃Human跟踪律缺失|FF只加入有界半幅参考ddq对应的`M delta_a`，不重复重力|
|闭环robot/cuff动态停止预测|活跃规划链缺失|本轮滚动评估局部模型，不把后验拟合或固定wrench预测当作闭环证明|
|新的轻量辅助控制|新隔离合同|原输出过滤器在新增作用之后重新运行；不宣称旧reference证书证明新控制律|
|更快控制入口|未新增|保持5ms；bridge/lifecycle/source age不改|
|全局闭环稳定性、跨Human/hardware|未证明|仅PHYSICAL_LEVEL1/SCIENTIFIC_SIMULATION；资格与代价依实际验证|

现有mechanics/reference证书本来就只描述参考路径与模型负担，不是任何反馈输出的无条件物理安全证书。新辅助不能改变这些输入语义：它保留原reference；改动的广义请求必须再经过原action transforms、allocator、executable filter、supervisor、当前write及native安全监测。每个新候选版本、修正和receipt单独绑定，不能称为原B同一控制律。

## 7. 已核验的终末控制事实

历史ER 16.895s时，膝估计q≈8.33051°、reference=9.5°；未投影PD请求≈+168.174°/s²，真实native加速度≈+5.753°/s²。实测wrench输入当前Human模型给出≈+16.049°/s²；广义请求作为模型输入则给出≈+168.174°/s²。三者定义不同。

15.3–18.0s的540个历史执行窗口中，增量加速度投影active=0；robot torque clipping=0，shank–bed接触=0。它们否定了“该段完全没有制动请求”及“已观测饱和就是唯一解释”，不排除未建模耦合/传递响应，也不能单凭相关性认定allocator或惯性为唯一根因。
