# 跨虚拟患者参数变化合同（独立审计草案）

本文件仅定义工作包 A 的 P0 参数实验与审核规则；不声称任何物理实验已经完成。原始患者、任务、控制器及安全门以最终执行 manifest 和生成 XML 为准。实际预注册需将本文件、队列、冻结控制器身份、实验顺序及失败规则一起哈希封存，并且早于首个完整 B/H150 对照结果。

## 研究对象与证据范围

本队列是 12 个确定性工程敏感性配置，不是随机临床样本，不代表康复患者参数的概率分布。长度、质量、质心、惯性半径、关节刚度和阻尼的变化均为探索性工程假设。代码中已有参数化接口支持这些变化，但“代码可以表示”不等于“临床范围已验证”，也不等于“物理任务已通过”。

所有结果的最高证据等级为 `PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION`，前提是对应患者确实执行并通过原始证据审计。编译、静态几何、理论分析和历史结果分别标为 `MODEL_STATIC_CHECK`、`ENGINEERING_HYPOTHESIS`、`HISTORICAL_REFERENCE_ONLY`；不可代替本轮物理结论。

## 真实参数来源与有效继承链

- `source/stages/stage3_full3d/src/traction_mpc_stage3/human.py`：Human V2 基础力学公式，身高 1.72 m、总质量参数 75 kg、被动刚度每关节 10 N·m/rad、阻尼每关节 5 N·m·s/rad；基础大腿/小腿长度分别是身高的 0.254/0.233，段质量分别是体重参数的 0.099/0.060。
- `source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/human.py`：Stage5 cuff 位置覆盖基础 Human 的 0.90 比例。必须读取实际配置；不得将 Stage3 的 0.90 当成任务 cuff 真值。
- `.../traction_mpc_stage5/high_rom_v1.py` 与 `.../fresh_qualification_v1/scenario.py`：`research_model=high_rom_v1` 覆盖基础 ROM，两个关节硬限位均为 0–125°，软限位边缘 5°。不得误用基础类的 80°/100° 上限评价高 ROM 任务，也不得借患者变化再次扩宽 125°。
- `.../fresh_qualification_v1/scenario.py::HiddenHumanV2`：现有物理生成接口支持独立段长度/质量倍率、质心比例及惯性半径比例；`hidden_plant` 只构建物理 truth、几何及原任务。
- `.../traction_mpc_stage3/coupled.py::build_coupled_model_xml` → `.../traction_mpc_stage5/plant.py` → `.../traction_mpc_stage5/cr12_plant.py`：核对真实合成 MJCF，而非孤立 Python 参数。Stage5/CR12 会改变基础装配和机器人子树，基础 UR10e 代码中的位置不能直接作为实际 CR12 实验配置。
- `.../full3d_adaptive_integration_v1/runtime.py`：`physical_human` 与 `control_human` 是分开的输入；高 ROM 控制先验来自 `high_rom_deployable_prior`。这一分离必须保留。

以上相对路径均相对于已核验的冻结 source 快照；最终包应另存每个文件的绝对来源与 SHA-256。

## 队列：固定参数而非成功筛选

以下倍率相对于最终冻结 reference，未列参数保持 reference。两个数字按大腿/小腿或 hip/knee 排列。`COM/L` 是段质心位置比例，`r/L` 是段转动惯性半径比例，均不是额外倍率。P09–P11 的设置必须在结果产生前固定，不能因 H150 失败改回温和配置。

|患者|长度倍率|段质量倍率|刚度倍率|阻尼倍率|COM/L|r/L|预留用途|
|---|---|---|---|---|---|---|---|
|P00|1 / 1|1 / 1|1 / 1|1 / 1|0.433 / 0.430|0.30 / 0.30|reference，未来开发|
|P01|1 / 1|0.8 / 0.8|1 / 1|1 / 1|0.433 / 0.430|0.30 / 0.30|质量低，未来开发|
|P02|1 / 1|1.2 / 1.2|1 / 1|1 / 1|0.433 / 0.430|0.30 / 0.30|质量高，未来开发|
|P03|0.95 / 0.95|1 / 1|1 / 1|1 / 1|0.433 / 0.430|0.30 / 0.30|短腿，未来开发|
|P04|1.05 / 1.05|1 / 1|1 / 1|1 / 1|0.433 / 0.430|0.30 / 0.30|长腿，未来开发|
|P05|1 / 1|1 / 1|0.7 / 0.7|1 / 1|0.433 / 0.430|0.30 / 0.30|低刚度，未来开发|
|P06|1 / 1|1 / 1|1.3 / 1.3|1 / 1|0.433 / 0.430|0.30 / 0.30|高刚度，未来开发|
|P07|1 / 1|1 / 1|1 / 1|0.7 / 0.7|0.433 / 0.430|0.30 / 0.30|低阻尼，未来开发|
|P08|1 / 1|1 / 1|1 / 1|1.3 / 1.3|0.433 / 0.430|0.30 / 0.30|高阻尼，未来开发|
|P09|0.95 / 0.95|0.8 / 0.8|1.3 / 1.3|0.7 / 0.7|0.40 / 0.40|0.28 / 0.28|复合，未来保留患者|
|P10|1.05 / 1.05|1.2 / 1.2|0.7 / 0.7|1.3 / 1.3|0.46 / 0.46|0.32 / 0.32|复合，未来保留患者|
|P11|1.03 / 0.97|1.1 / 0.9|1.3 / 1.3|1.3 / 1.3|0.45 / 0.41|0.31 / 0.29|不对称复合，未来保留患者|

P01/P02 等质量倍率可通过统一体重参数或两个段质量倍率实现，但不可重复乘两次。P11 必须使用独立段质量倍率。最终表需保存实际段质量和惯量，不能只保存倍率。

`I_i = m_i (r_i L_i)^2`；若质量乘 `s_m`、长度乘 `s_L`、惯性半径比例由 `r_0` 改为 `r`，则 `I_i/I_i0 = s_m s_L² (r/r_0)²`。COM 的变化只移动显式 inertial 中心，不把平行轴项再次加入 COM 转动惯量；动力学质量矩阵本身负责对应平行轴项。原 MJCF 三个主惯量为 `[0.51 I, I, 0.51 I]`，保持原形式并逐一验证正数和三角不等式。

统一长度变化并不等于独立识别“长度效应”：COM 绝对位置、cuff 位置和惯量会随长度一致变化。报告应称为“形态一致的长度变化总效应”。P11 的质量分布、段长比例与被动力学同时变化，不能据单个复合结果分离各自因果贡献。

## P0：冻结算法转移的边界

P0 固定 B/H150 正式控制算法、初始 deployable prior、估计器、准入、certificate、allocator、参数冻结、目标、ROM、安全阈值、cuff 机制、机器人模型和执行时序规则。只能在物理 plant 生成端应用上述患者参数。

原 B 体系允许的在线估计和每患者物理 commissioning 保留，这是算法冻结后的正常行为。不同患者通过合法传感器产生不同估计值，并不自动把 P0 变成 P1。需要同时报告初始先验与 commissioning 后实际估计值。不得将真实段长、真实质量、真实刚度或离线 truth 直接替换控制器模型或 observer。

生成、静态审计、离线评价允许读取 truth。runtime 只允许原合法观测接口和原安全监测体系。禁止把新增 truth 字段放进接口、动作选择、证书模型或特征状态，禁止通过全局 `HUMAN` 重绑定让控制与 plant 同时静默变更。

P1 若未运行，仅保留协议：在新独立实验标签下，向 B/H150 同时提供同一组已知患者参数，明确标注 `known_calibrated_parameter`；不得替代或混合 P0，不得将 truth 自动视为已知标定，不得只帮助 H150。

## 模型一致性与准入

每患者先独立检查有限值、正段长/质量/惯量、COM 在段内、cuff 在小腿内、三维主惯量有效性，以及全 ROM 网格的 2×2 Human 质量矩阵正定性。再核对生成 MJCF：大腿 capsule 终点、膝 body 起点、小腿 capsule 终点、两个 inertial 位置/质量/惯量、cuff site/geom 位置、关节 stiffness/damping/springref、limit 和所有 contact 位掩码。

几何变化必须同时改变膝位置、段端点、COM、惯量和 cuff。不能仅改长度常数或可视 geom；不能设置编译器自动平衡惯量来掩盖非法模型。所有机器人 inertial、关节、actuator、torque 限制、bed/contact law、cuff 参数保持一致。MuJoCo 的显式惯性在通常 `inertiafromgeom=auto` 下不会由 geom 自动重算；因此质量/长度变更需明确更新它们。[MuJoCo MJCF inertial 文档](https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-inertial)

患者自己的初始装配应通过原合法 cold initialization，检查真实 cuff site 与机器人末端的连接、IK 可达性、bed clearance 和原稳态判据。仅为装配而使用既有初始化 IK、初始姿态及患者几何是正常安装步骤；它不能向在线控制器泄露患者模型。任何安装偏移必须预声明、记录并对两臂相同。本方案默认不改变机器人 base、cuff adapter 或床面来挽救失败患者。

原 observer 的几何边界、certificate、工作空间或任务预检如果拒绝 P03/P04/P11，保留原始错误及参数，不扩边界。需区分“物理几何非法”与“P0 原执行合同不接纳”：后者可能是系统适用性障碍，不代表人体惯性模型本身非法。

物理 commissioning、初始稳定性和完整原任务可执行性需要实际证据。静态通过只记 `STATIC_ADMISSIBLE_PENDING_COMMISSIONING`。完整任务预检若本身积分推进物理，必须计入 START 和 native 步数。

## 初始化、配对和顺序

建议患者顺序 P00→P01→P02→P05→P06→P07→P08→P03→P04→P09→P10→P11；先完成各患者自己的 cold parent，再在同一 live parent 上串行 fork B、H150。若实用顺序因预先几何检查改变，需记录原因与时间，不能因结果收益而选患者。实际顺序以最终预注册为准。

患者之间不得复制 native state、`qpos/qvel`、observer、估计历史或 `os.fork`。同一患者的 B/H150 应共享完整父状态哈希、任务目标、测量 seed、合法历史及 frozen manifest；两子运行必须 join，父状态回查不变。每个患者都重新 commission。

不得因为 B 失败便跳过原本合法的 H150 分支；两臂仍应在相同合格父状态上独立运行，除非公共父状态或模型本身不合法，或统一时间/START 预算已达上限。不得继续使用不安全的物理末态产生后续对照；配对状态应是分叉前合法父态。

每次物理启动（父、commissioning 独立运行、子臂、失败、partial、重复）都有 START/END；异常退出也闭合并保存已产生的 raw evidence。最多 80 次，硬停 T0+8 h，末 45 min 不开新物理。运行截止预测不足时不派发，已不可能完成的任务保留 `NOT_RUN_BUDGET`，不得记成失败。

## 指标和完整积分

完整 J_F 只用原 5 ms 左积分：`sum(||F_k||*(t[k+1]-t[k]))`，时间区间覆盖任务开始到 COMPLETE。phase 积分以真实 phase 转移时间裁剪每个左积分区间，三个 phase 之和必须等于完整积分。不可用梯形、native 力积分或 commissioning 段替换主指标；允许单独列辅助统计并明确口径。

必须保留完整任务边界、最后一个 5 ms 区间、重复时间戳处理规则和 prefix 拼接归属。父 prefix 若包含在子原始记录中，只计一次；分叉后新增 native steps 与完整任务评价步数分别统计。不能用短提前退出路径的低累计力计算完整降力。

Human 真实运动使用原 0.25 ms native q/dq，按原协议求加速度和 jerk，保留端点，原 raw 指标为主；滤波只能作为既定敏感性。真实轨迹不以 reference 代替；tracking 使用同时间实际 reference。task duration 和 native 样本跨度可能相差一个采样间隔，应分别标明，不能把 0.25 ms 的偏差错判成或遮盖完整时钟缺口。

## 资格、对照解释性和缺失结果

每臂记录多轴状态，允许多个失败同时存在：`TASK_FAIL`、`ABSOLUTE_SAFETY_FAIL`、`MOTION_RELATIVE_FAIL`、`CAUSAL_EXECUTION_FAIL`。患者模型/初始化另记 `MODEL_NOT_ADMISSIBLE` 或明确的 P0 commissioning/admission failure。`COMPLETE_QUALIFIED_PASS` 需要任务、安全、执行、完整积分以及有效 B 参照下的原运动合同全部通过。

B 自身相对 B 的运动表只提供数值参考，不能证明绝对安全。若 B task、绝对安全或执行无效，H150/B 相对运动资格置为 `NOT_EVALUABLE_INVALID_BASELINE`；可保留原始数值差但不可解释为合格运动非劣。H150 自己的任务/安全/执行轴仍照常报告。

当两臂完整任务和完整积分均有效且 J_F(B)>0 时才报告 `gain=(J_F(B)-J_F(H150))/J_F(B)`。即使存在运动或安全失败，完整积分差仍可作为描述性数值，但要同时标注对照无合格解释性；合格收益统计另用双臂有效且 H150 完整资格通过的分母。任务或积分缺失时 gain 为 null，不填零、不外推剩余任务。

原 `MOTION_ACCEPTANCE_PROTOCOL.json` 全部冻结：burden 1.10；excursion、终点/phase boundary 0.5°；累计 dose 比例 0.95–1.05；总时长和各 phase 差 0.1 s；moment integral 1.25；tracking RMS 增加 0.5°；force/moment peak 1.05。phase shape 仅诊断，不追加挑选用的新门，也不删除原门。阈值是工程研究合同，不是临床耐受标准。

每个患者原计划行必须出现在结果表，区分预注册数、静态通过数、commissioning 通过数、完整配对数、B 合格数、H150 合格数、正/负完整收益数及合格收益分母。结果不能只呈现 H150 PASS 子集。

## 未来 Learning 留存

P00–P08 为未来开发身份；P09–P11 的全部 prefix、重复、轨迹、结局、归一化统计和标签共同保留，不参加未来拟合、超参、动作选择或阈值校准。不能把同患者的另一条运动作为跨患者测试。

本轮为了完整描述会公开 P09–P11 的 B/H150 结果，因此它们不是对本研究者盲态的未见数据。准确名称是“未来 Learning 拟合保留患者”，不应声称是从未被观察的前瞻性临床测试。若后续控制动作或模型设计根据这些结果调整，需另造未接触的患者身份作最终确认，不能继续称本三患者为未经使用的确认集。

在线 STATE 只能包含原传感估计、reference、phase/elapsed、历史 force/moment、source age 和执行状态；ACTION 为 B/H150 身份与实际协调意图及被接受的时序；OUTCOME 保存所有原资格；TRUTH 与 PATIENT_ID 中的生成真值仅离线用途。模型参数可供监督标签和分析，但不得被错误装入在线 STATE。

## 统计与解释限制

主表逐患者给出原始 N·s、配对百分比、moment、tracking、overshoot、motion/safety/task/execution。跨患者平均应对患者 gain 等权，单列范围、有效分母及所有负收益；不可把不同患者绝对 J_F 拼排名，更不能把总 J_F 比例误称平均患者改善。

单因素对比用 P00 与对应低/高配置描述敏感性，复合配置仅为交互压力测试。样本稀少不做临床泛化、总体显著性或独立作用归因。高刚度与下冲、阻尼与制动、质量与降力的机制，只有实际时序、force/moment/torque/估计误差支持时才提升为“物理证据支持”；否则保持 `INSUFFICIENT_EVIDENCE` 或 `MECHANISTIC_HYPOTHESIS`。

## 外部模型一致性依据

1. [MuJoCo 官方 MJCF 参考：inertial、compiler、contact、weld](https://mujoco.readthedocs.io/en/stable/XMLreference.html)。显式 inertial 与几何自动推断行为、主惯量约束、contact 位掩码和 site weld 语义用于模型审计；不用于证明患者参数具有临床分布依据。
2. [MuJoCo 官方版本化 3.3.1 MJCF 参考](https://mujoco.readthedocs.io/en/3.3.1/XMLreference.html)。运行时版本若不是 3.3.1，应将最终证据绑定实际安装 MuJoCo 版本，避免 stable 文档版本漂移。

未运行 P1、未训练 Learning、未修改正式 B/H150、未修改任何原 Human 冻结文件。本草案没有把准备工作写成完成实验。
