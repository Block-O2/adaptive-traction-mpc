# P1 Patient-Aware Model Matching：仅协议，未执行

状态：`PROTOCOL_ONLY_NOT_RUN`。本文件不授权工作包 B、不启动物理、不训练 Learning，也不宣称当前已有 P1 结果。P0 始终是本轮主要实验；P1 将来另立计划、预算、源代码 manifest 和结果表，不替代 P0。

## 研究问题

在相同患者 plant、相同任务及相同 B/H150 控制算法下，向两臂提供同等合法患者参数先验，是否改善原冻结 population prior 的模型失配边界？分别报告 P0→P1 对 B 与 H150 的影响，以及各实验内部 H150 相对其匹配 B 的结果。

P0 的原传感器驱动 commissioning 与在线估计不是 P1：这些机制仍只接收原本合法观测。P1 的区别是额外提供患者已知参数，必须显式记录来源、可用时刻和误差假设。

## 允许的信息来源

每个参数条目必须包含 `name`、`value`、`unit`、`known_at`、`provenance`、`uncertainty`、`provided_to_B`、`provided_to_H150`。

- 合法可测的几何量，例如经过明确标定程序得到的段长、cuff 位置和安装几何。
- 明确记录的模型标定参数，例如通过独立已完成的 commissioning 数据辨识得到的质量/动力学系数、被动刚度或阻尼。
- 如果未来为机制上界诊断直接采用生成器精确参数，必须命名为 `P1_ORACLE_PARAMETER_MATCHING`，标记这是仿真假设，不是实际完成的患者标定，不宣称传感器可获得。

不得让控制器读取运行中的 native Human q/dq、future outcomes 或患者 truth 对象。即使使用 oracle 参数，参数注入也应是初始化时冻结的显式输入，不是运行时直接 plant introspection。已知生成参数、已知标定参数和在线估计参数必须分列。

## 两臂公平与算法边界

同一患者的 B/H150 收到逐字节一致的已知参数先验及其有效时刻，初始估计器、准入、certificate 和 allocator 获得完全相同的信息。不可只向 H150 提供几何或更准确动力学。

B/H150 正式算法、H150 协调参数、目标与剂量、phase/完整时长合同、ROM、力/力矩/机器人 torque 阈值、床面与 cuff 机制不变。不能因为先验更精确而扩大原安全阈值或修改动作。若系统没有合法接收某个参数的接口，该字段记 `UNSUPPORTED_INPUT`；先解决接口协议并独立核验，不能通过真值全局变量替换悄悄注入。

P1 不应对不支持的软限位项重新辨识后改变原软限位规则。现有动力学模型中不包含的项应记模型族限制，不伪装成已知参数即可完全匹配。

## 物理初始化和配对

每个 P1 患者仍从自己的合法 cold initialization 和完整 commissioning 出发。不能把 P0 的完整 native state 复制到另一个参数或另一实验标签来省略初始化。原算法必要的 physical commissioning 不因已知先验而自动删除；若未来研究希望单独评价缩短 commissioning，那是另一个任务合同。

P1 内 B/H150 从同一完整合法 live parent 串行 fork，记录相同 parent full/native hash、case hash、model XML hash、seed 与冻结信息先验 hash。每次 physics START/END、失败 partial 和新增 native 步数独立计入。

P0 与 P1 的全状态通常不同，因为不同先验可改变 commissioning 及估计历史。跨实验比较因此是同患者、同任务、同 seed 的独立 cold-start 模式对比，不能声称两者共享同一执行初态。报告 commissioning 后状态与模型差异，以免将启动差异误归为 H150 机制。

## 执行和审核规则

先做无物理的输入通道审计，确认参数只到达声明的先验接口；再用 reference patient 检验 matched prior 与原先验相同时行为一致。该验证如果运行物理，必须计 START，不能叫静态检查。

先验文件在任何 P1 结果前固定；不根据 H150 通过情况选择患者或参数误差。所有预注册患者都保留，即使几何、commissioning、observer 或任务失败。

沿用 P0 原资格、完整积分、native truth 导数和 receipt 归属审计。B 无效时相对运动记不可评价。不能用 P1 的 B 替代 P0 的 B，或用 P0 reference Human B 比较其他患者。

## 结果表（当前没有任何数值）

每行键为 `(patient_id, experiment, prior_source, arm)`，至少包含：

- patient/case/XML、控制器、先验与源 manifest hash；
- 参数先验值、来源、误差假设，以及 commissioning 后实际估计；
- cold initialization、commissioning 和 admission 资格；
- task、absolute safety、causal execution、integral 与 motion 资格；
- 完整 J_F、moment、tracking、overshoot、excursion 与实际干预；
- P0/P1 各自的匹配 B/H150 gain，并标明可解释性；
- 所有失败、partial、预算未运行与缺失原因。

当前结论必须为 `INSUFFICIENT_EVIDENCE_FOR_P1`。此协议的存在不能被计作患者已知模型实验完成，也不能被写成已经证明模型失配是主要障碍。
