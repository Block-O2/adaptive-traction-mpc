# Phase 3A：冻结 1 ms 契约下的 compliant 40/40 数值资格 Spec

**状态：DRAFT，供用户审核；尚未批准按这些新增容差执行。**
本轮授权是起草 Spec。本文件及同名 JSON 都不是活动运行配置；本轮不移植代码、不运行仿真、不提交。

## 1. 问题、证据范围与成功含义

问题：同一个注册软接口、同一套 de23ea3 闭环实验，在 1 ms 下是否具有可重复性、可解释的力学/能量行为，并在本文件拟议误差预算内与匹配的 0.25 ms 结果一致？

- 实验母线：`de23ea3cdf9f0fb078496ba5ba4abb6a205ad955`。
- 当前分支：`codex/interface-phase3a-de23ea3`；当前 HEAD：`99169491ea1336d6af74e3b63318afba18c1e881`。
- 仅接口 donor：`3ce0129587bae3b9d13c0f581e0e4d8af5779e3a`。
- 刚性 40/40 gate 已有证据：66 个非主机耗时数组相对两次历史运行均完全一致；本 Spec 不再运行刚性轨迹。
- Phase 2 的 0.3 s / 1 mm / 床接触诊断只作历史背景，不能作为本次 MPC 40/40 的收敛参考。
- 新增的 0.25 ms 运行是同工况的**有限步长数值参考**，不是精确解，也不因旧短诊断通过就自动在本工况合格。

PASS 只表示本次 40/40 全参考历程通过拟议有限参考一致性门槛。它不是严格连续时间收敛证明、长期稳定性证明、材料参数有效性、临床安全或 ROM 扩大证据。由于闭环重新计算控制与测量，本比较衡量整个离散闭环的 timestep 敏感性，不能把差异全部归因于接口积分误差。

## 2. 最多三次运行，严格顺序

| 顺序 | ID | 接口 | physics dt | 用途 |
|---|---|---|---:|---|
| 1 | soft_40_40_1ms_repeat1 | 注册软接口 | 1 ms | 待资格运行 |
| 2 | soft_40_40_1ms_repeat2 | 完全相同 | 1 ms | 确定性重复 |
| 3 | soft_40_40_025ms_reference | 完全相同 | 0.25 ms | 匹配细步长参考 |

每次 fresh process、fresh plant/controller/estimator/RNG，以同一注册初始状态开始。不增加加载后静置、预热、预变形或平衡轨迹，不重新登记 rest。

先检查第 1 次的警告、有限性、机制一致性、既有终止事件及参考覆盖；通过后才运行第 2 次。第 2 次与第 1 次的确定性检查通过后才运行第 3 次。第 3 次必须同样满足有限性、机制和能量检查；不能因为它更细就假定其有效。

任何阶段不满足已批准门槛立即停在当前运行完成/既有安全终止之后；保留原始输出。数值警告或非有限值发生时可立即中止，禁止继续使用失效状态。没有自动重试、补跑、额外 timestep、局部 replay、其它目标或第四次轨迹预算。普通任务跟踪误差较大本身不是停止条件。

## 3. 冻结契约和唯一拟议例外

沿用已验证 commissioning spec、完整模型锁和源文件指纹。配套 JSON 保存来源 hash、61 个 source/config/model 文件的原始 hash、MPC 配置和轨迹参数。

- 场景 `suspended_high_rom`，实现 `suspended_seated_like_high_rom`；保持其床接触设置。
- Human V2、nominal High-ROM 几何、population-prior beta、allocator/cuff geometry、UR10e、140 mm adapter 不变。
- `freeze_control_geometry=True`，control model 不接受在线更新；原有 shadow estimator 仅诊断。
- 原有 Executable Command、Safety Filter、BRAKE、Unified/force-related Reference Manager 和 command/physical-force contract 原样保留。
- 无 Adaptive MPC、gamma、额外 pacing/governor、恢复/HOLD、新预测器、重力补偿或旧 compliant/soft-weld 实现。
- integrator=`implicitfast`，solver enum=2，iterations=100，solver tolerance=1e-8；其余 MuJoCo options 也保持原始模型值，不只检查这四项。
- low-level 5 ms、MPC 20 ms、测量 5 ms；measurement seed=44104、MPC seed=20260824。
- 初始 Human q=[5°,10°]；目标=[40°,40°]。
- 初始 hold=1 s；outbound=5.303030303030302 s；target hold=1.5 s；return=5.303030303030302 s；final hold=1 s。
- nominal reference phase duration=14.106060606060604 s；既有 maximum simulation duration=28.215 s。Reference Manager 仍根据各自测量运行，不能回放某次 alpha 曲线强行同步。
- 既有 task completion tolerance=0.06896926724078867°；不以本文件的数值误差容差替换它。

**拟议例外仅用于第 3 次参考：physics dt=0.25 ms。** 为保持物理单位和控制频率，同一 5 ms control tick 内的 physics substeps 从 5 改为 20；时间积分、采样窗口和离线导数使用真实时间戳。控制/测量/估计器/Reference Manager 的执行周期、调用顺序、RNG 抽样规则及物理窗口长度不能随 substeps 改变。不会把 1 ms 离散闭环命令直接回放给参考。

这是一项显式的数值参考例外，不会修改 1 ms 生产比较契约，也不会修改刚性历史结果。如需改变算法、solver、gains、物理阈值或模型才能支持该例外，停止，不扩张本 Spec。

## 4. 接口和测量边界

精确采用 donor 保存值：Kt=500 I N/m，Dt=35.63902676526988 I Ns/m，Kr=20 Nm/rad，Dr=1 Nms/rad。不得使用显示精度 35.639 重新构造参数，不重新计算有效质量或阻尼。

- R=`adapter_cuff_site`，H=`sleeve_attach_site`；rest translation=0，rest rotation=I，原始名义 [5°,10°] 登记不变。
- 保持显式 spring-damper 本构、两端施力、坐标系和作用点传输；禁用刚性连接仅属于接口替换。
- 对 Human 的实际载荷为 `W_H=[F,T+(p_R-p_H)×F]`，对机器人为 `W_R=[-F,-T]`；机器人测量端的正向 transmitted wrench 是关于 R 的 `W_s=-W_R=[F,T]`。
- 控制器只接收机器人侧 pose/twist、关于 R 的 transmitted wrench，以及冻结几何重建所得 proxy。
- Human q/dq、H pose/twist、真实变形只写诊断；不能反馈、校正 proxy 或补偿控制器。

最小实现限于 donor 接口及新的 plant/measurement adapter、runner 和日志器。不能在旧 controller 中拼装或替换算法。全部允许代码差异、导入来源和 hash 必须在运行前登记；既有控制文件 hash 应保持一致。

## 5. 前置实现检查（不属于额外轨迹）

执行有针对性的单元/代数检查：rest 力、作用点平移、同一点 action/reaction、瞬时功率恒等式、阻尼非负、测量对象不携带 Human truth、冻结模型锁及 1 ms/0.25 ms 的固定控制调度。golden 1 ms trace 和历史 hash 只读核对，不重跑刚性。

验证器需用合成数据检查：误差恰在容差内/外、shape/key 不匹配、非有限值、离散 mode 差异、零参考信号、时间覆盖不足和主机耗时排除。模型/控制/诊断中发现必须修复的明确代码错误，要保留失败记录并停下报告；不自动消耗新运行预算。

## 6. 拟议验收容差——需要审核

以下是为新实验提出的**工程误差预算**，不是生理阈值、理论误差界或 Phase 2 既有结论。5%/2% 用于分别限制局部最大偏差和全程 RMS 偏差；1% 能量预算限制离散功率记账缺陷。选择这些数值属于待审核科学范围；不声称它们是唯一合理阈值，也不依据新结果调整它们。

旧短诊断中已有的约 7.42% force Linf 不满足拟议 5% 门槛；这既不能预判新工况 FAIL，也不能成为事后放宽门槛的理由。

### 6.1 确定性（两次 1 ms）

所有必需非主机耗时数组：同 key、shape、dtype、有限值；数值 `rtol=0, atol=1e-12`，离散状态/事件标签精确相同。包含完整 state、proxy、命令、transmitted wrench、变形、能量、reference progress、Safety Filter/BRAKE、模型锁和终止标签。只排除显式列出的 host compute duration，不排除物理时间戳或不利事件。主机耗时仍保存报告。

### 6.2 波形及标量（1 ms repeat1 vs 0.25 ms）

按**相同物理时间**对齐，将粗网格数据分量线性插值到细网格；不得平移事件、按 phase 重新定时、截去初始瞬态或平滑信号。每种信号同时报告原生网格 peak/RMS/final，防止插值掩盖尖峰。1 ms repeat2 若已通过确定性，不作为新的独立样本。

令 `e(t)=y_1ms_interp(t)-y_fine(t)`，`B∞=max ||y_fine||`，`B2=sqrt(mean_time ||y_fine||²)`，`E∞=max ||e||`，`E2=sqrt(mean_time ||e||²)`。向量使用 Euclidean norm，积分用各自实际时间戳的梯形法。

必须同时满足 `E∞ <= max(a, 0.05 B∞)` 和 `E2 <= max(a, 0.02 B2)`。
原生 peak、RMS、final 标量差分别满足 `|s_coarse-s_fine| <= max(a,0.05 |s_fine|)`；向量 final 使用向量差的 norm 和 fine final norm。

| 信号 | 绝对误差预算 a | 相对 L∞ | 相对 L2 | peak/RMS/final |
|---|---:|---:|---:|---:|
| R 点 transmitted force，world | 0.1 N | 5% | 2% | 5% |
| R 点 transmitted moment，world | 0.01 Nm | 5% | 2% | 5% |
| H 点实际 moment，world | 0.01 Nm | 5% | 2% | 5% |
| H frame translation deformation | 0.01 mm | 5% | 2% | 5% |
| H frame rotation vector | 0.0001 rad | 5% | 2% | 5% |
| H frame relative linear velocity | 0.001 m/s | 5% | 2% | 5% |
| H frame relative angular velocity | 0.001 rad/s | 5% | 2% | 5% |
| Spring stored energy | 0.00001 J | 5% | 2% | 5% |
| Cumulative damping loss | 0.00001 J | 5% | 2% | 5% |
| Executable command force，world | 0.1 N | 5% | 2% | 5% |

绝对预算是对近零信号的数值比较容差，不是物理允许载荷。相对分母为零时标记 relative metric=N/A，并按绝对门槛判断；不得静默更换分母或任意 floor。

另外逐关节检查：true/proxy q 最大跨步长差 ≤0.1°；true/proxy dq ≤1°/s；各关节 tracking RMSE、endpoint/return error 的跨步长绝对差 ≤0.1°。这些不改变任务完成容差。

Reference phase 最大跨步长差 ≤5 ms；BRAKE/Filter 的有序事件身份及次数一致、对应发生时间差 ≤5 ms。状态序列只在已匹配事件两侧允许这个时间量化差，不能删除不匹配事件。物理力事件发生时间及终止时间差 ≤1.25 ms（两个 physics dt 之和）。所有终止原因、task classification 和现有 runtime physical-force classification 必须一致；处在阈值附近且无法判定的情况记为未解决，不能猜测通过。

### 6.3 能量、passivity 及接口一致性（每次运行各自满足）

用 donor 的定义记录 `U`、非负 damping power `D`、两端对各自物体的功率 `P_R,P_H`；各自原生网格积分得到 `W_R,W_H,E_D`。

`R(t)=U(t)-U(0)+W_R(t)+W_H(t)+E_D(t)`。
`S=max(max_t U(t), E_D(T), max_t |W_R(t)+W_H(t)|)`，不加随意 floor。

- `max |R| / S <=1%`；`max positive R / S <=0.5%`。
- 若 S=0，仅按 `max |R| <=1e-10 J` 判断，并报告相对值 N/A。
- `U >= -1e-12 J`；`D >= -1e-10 W`；负值不得裁剪后再评估。
- 瞬时 `|P_R+P_H+dU/dt+D| <=1e-9 × max(1 W,|P_R|+|P_H|+|dU/dt|+|D|)`，这里的 dU/dt 使用本构解析恒等式；独立离散残差 R 仍必须满足上述要求。
- 同一点 action/reaction：力残差 ≤`1e-9 N +1e-12×sum(force norms)`，力矩残差 ≤`1e-9 Nm +1e-12×sum(transported moment norms)`。

两端功率不能混用不同作用点的 moment/twist。阻尼可消耗能量、servo/gravity 可输入能量，因此不要求 U 单调下降。不把数值能量预算称为组织安全界限。

### 6.4 “变形有界”的可验证含义

不新增允许变形 mm/deg 的物理阈值。本次仅检查全记录历程中变形与速度有限、无 MuJoCo 警告、能量记账通过，以及 coarse/fine 变形与速度通过上述波形/peak/RMS/final 门槛。报告各分量、target arrival/hold end/final 变形、漂移趋势、增长区间及其与参考和功率的关系。

这是有限历程内没有观察到不受数值参考支持的发散，不能证明任意时间有界。若旋转对数分支切换或诊断映射失效导致波形/能量不可比，标记 unresolved 并停止，不通过改算法或重置变形消除问题。很大的但跨步长一致的变形仍是需要报告的物理/性能结果，不因没有临床阈值而称其可接受。

## 7. 完整性、失败类型和停止

拟议全轨迹资格需要两种 timestep 都覆盖既有 Reference Manager 的 registered reference completion；最终采样差仅允许上述 1.25 ms 量化差。common interval 用于波形计算，未重叠末尾必须单独列出；不把早停公共前缀冒充全 40/40。

既有 safety termination、BRAKE 和 timeout 全部原样执行。若因此未覆盖全参考历程，则本次全轨迹资格为 `FAIL_EVIDENCE_INCOMPLETE`，同时保留真实 task/force 标签；不声称它证明数值不稳定。端点误差大但参考完整、所有数值检查通过时，允许 numerical PASS / task SAFE_INCOMPLETE 并列。

| 数值资格原因码 | 含义 |
|---|---|
| PASS | 三次规定运行、完整性和全部拟议门槛都满足 |
| FAIL_DETERMINISM | 两次 1 ms 不满足确定性容差 |
| FAIL_NUMERICAL_STATE | 非有限值或 MuJoCo 数值警告 |
| FAIL_INTERFACE_CONSISTENCY | 作用点、符号、边界、功率恒等式等不一致 |
| FAIL_ENERGY | 能量预算不满足 |
| FAIL_REFERENCE_AGREEMENT | 跨步长波形、标量、状态或事件门槛不满足 |
| FAIL_EVIDENCE_INCOMPLETE | 参考无效、覆盖不足、缺少数据、未解决事件或需要额外细化 |
| NOT_RUN_PREFLIGHT_BLOCKED | 指纹/配置/实现审计不满足，尚未开始资格运行 |

FAIL 表示未通过本 Spec 的工程资格门槛；原因码必须说明是观测失败还是证据不足，不能全部写成 instability。

保留现有 runtime force policy 并报告 peak、>200 N duration、contiguous duration、excess impulse 和 trailing-window 指标。若既有物理力审查需要本预算之外的 replay/refinement，标记 unresolved / FAIL_EVIDENCE_INCOMPLETE 并停下，不新增运行，不修改阈值，也不把 runtime 标签冒充完成了所需数值确认。

无论 PASS/FAIL，完成这次资格任务后停止。PASS 时只报告下一阶段 rigid-vs-compliant A/B 的数值前置条件已满足，不自动运行 A/B、40/80、90/120、120/120、调参或重新设计。

## 8. 日志、产物和审核

每次保留实际命令、环境/package 版本、源码/配置 hash、完整注册 JSON、模型 options、初态、所有 held commands、控制/物理时间戳、R/H pose/twist、W_R/W_H/W_s、q_true/q_proxy、dq_true/dq_proxy、变形、功率/能量、模型锁、Safety Filter/BRAKE、Reference Manager、warnings 和终止事件。真值列显式 diagnostic-only。

产物保存到新的唯一命名 engineering_validation 目录，不能覆盖原结果，也不提升为 authoritative/formal 证据。输出：逐门槛 PASS/FAIL 表、1 ms 两次重复表、1 ms vs 0.25 ms 表、同步曲线、原生 peak/事件窗口、能量残差和变形分析、40/40 task/force classification、完整 git diff/status。结果和代码保持未提交。

批准后实施前，将审核后的 MD/JSON 固定为 approved spec 并记录 hash；若两者有冲突，先更正并重新审核，不能由 runner 自选。运行入口当前尚未实现，因此不提供伪造的可执行命令。本轮只能审核此 Spec，不应把草案 JSON 交给任何自动运行器。

**本次审核重点：** 是否接受最多三次运行及匹配参考例外；是否接受第 6 节提出的所有数值误差预算；是否接受参考覆盖不足或需要额外确认时按“资格证据不足”停止。不得等看到新结果后再选门槛。
