### 在线计算与更新（问题 15–19）

以下是 Scientific Simulation 的实际主机剖析。模型属于固定 MATCHED pacing（1.3 倍注册段时长）和明确 continuation context；native 绝对目标补充研究未混入拟合。主机时间不会推进冻结的生产者仿真 epoch，因此这些数据不能认证硬件实时行为。

**15．端到端高层决策延迟是多少？**

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 原始传感捕获 → 参考验证完成 | 13 | 41.966 | 57.172 | 69.532 | 72.622 |
| 原始传感捕获 → 实际命令激活 | 13 | 42.381 | 57.654 | 69.947 | 73.020 |
| 研究决策开始 → 参考验证完成 | 12 | 40.051 | 55.605 | 66.436 | 69.143 |
| 研究决策开始 → 实际命令激活 | 12 | 40.433 | 56.080 | 66.849 | 69.542 |
| 首个特征开始 → 参考验证完成 | 12 | 30.992 | 42.964 | 51.245 | 53.316 |
| 首个特征开始 → 实际命令激活 | 12 | 31.374 | 43.439 | 51.659 | 53.714 |
| 选定参考 → 实际命令激活 | 12 | 30.685 | 34.084 | 34.744 | 34.910 |

单位：ms。

传感捕获早于 observation ready，故捕获到验证/激活是比所需观察就绪边界更宽的实际测量；特征边界采用同源绝对单调时间戳，缺失时保留“未测量”。适用样本数见表，p99 是样本分位数而非最坏时间证明。

此剖析未标记 snapshot 捕获 IO；正常运行的安全/任务有效性及模型 SHA 仍须由相应 rollout provenance 独立确认。

独立 capture 专用运行含 immutable snapshot 文件 IO，不能替代正常运行；配置也有差别，不能把两次运行的延迟差值解释为 IO 因果开销。该运行实际捕获 → 激活：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| capture 专用运行，额外 IO | 13 | 81.387 | 126.949 | 170.577 | 181.485 |

单位：ms。

观察到的角色延迟（排除明确标记的捕获 IO 运行）：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 首个 pattern 选择：捕获 → 激活 | 1 | 73.020 | 73.020 | 73.020 | 73.020 |
| 已提交 continuation：捕获 → 激活 | 11 | 42.381 | 45.923 | 47.113 | 47.410 |
| 其中 moving handoff：捕获 → 激活 | 10 | 42.538 | 46.072 | 47.142 | 47.410 |

单位：ms。

**16．哪部分主导延迟？**

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 原始 planner 比较候选 | 12 | 0.000 | 2.716 | 5.371 | 6.035 |
| 继承 terminal/input guard 与 committed 原硬筛选 | 12 | 5.054 | 6.542 | 6.876 | 6.960 |
| 研究 proposal 枚举 | 12 | 0.170 | 0.455 | 0.701 | 0.762 |
| 研究候选调度/硬筛选 | 12 | 3.598 | 18.058 | 31.942 | 35.413 |
| 特征构建 | 12 | 0.060 | 0.157 | 0.222 | 0.238 |
| 批量 Q 推断和选择 | 12 | 0.049 | 0.065 | 0.075 | 0.078 |
| worker 完成到主线程收集 | 13 | 11.803 | 14.873 | 15.409 | 15.543 |
| 当前状态参考验证及命令构建 | 13 | 10.972 | 11.818 | 11.856 | 11.865 |

单位：ms。

adapter decision_total 的结束点是参考选择；它未覆盖 escape preparation、worker 主线程收集、当前状态参考验证和实际激活，不能称为端到端决策延迟。候选 feasibility/scheduling 的准入也不等于之后 activation validator 的许可。

按已测中位数，最大的上述组成项为 **worker 完成到主线程收集**。组件可能属于不同层级；不将各项 p95/p99 相加并冒充实际端到端分位数。

下面使用科学部署解释器的独立 CPU profile：Python 3.10.21，NumPy 2.2.6，线程设置 {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}。较早 abs_env/NumPy 1.23.5 profile 原样保留，未混合两种环境的分位数。

实际模型 SHA256：{"ridge_full": "39ebae5caeba2e433b8e01896aee37a03d7e51f7240977a3b486a338a0116c76", "mlp_full": "fc9450f5ed968b382da373cd7a05861e66e089bcc7b710cc9d9735cdee130863"}；冻结真实 X 文件 SHA256：4860a2bbe2ae9da23eadbfe6a390a77284117994bfccf031c2f30014051f2aff。

CPU ridge_full（真实冻结 96 维 X、实际已训练模型）：

| batch 候选数 | 首次调用 ms | warm 中位 ms | warm p95 ms | warm p99 ms | warm 最大 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.108 | 0.011 | 0.012 | 0.024 | 0.056 |
| 4 | 0.068 | 0.012 | 0.014 | 0.021 | 0.027 |
| 8 | 0.058 | 0.013 | 0.018 | 0.054 | 0.124 |
| 10 | 0.065 | 0.014 | 0.017 | 0.030 | 0.054 |
| 16 | 0.081 | 0.015 | 0.018 | 0.026 | 0.096 |
| 32 | 0.127 | 0.019 | 0.022 | 0.033 | 0.059 |

batch 8：CPU 输入复制 p95 0.001 ms；逐候选不批处理总推断中位 0.084 ms。首次模型加载 1.822 ms。

CPU mlp_full（真实冻结 96 维 X、实际已训练模型）：

| batch 候选数 | 首次调用 ms | warm 中位 ms | warm p95 ms | warm p99 ms | warm 最大 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.049 | 0.009 | 0.010 | 0.016 | 0.024 |
| 4 | 0.087 | 0.012 | 0.014 | 0.022 | 0.034 |
| 8 | 0.056 | 0.014 | 0.016 | 0.024 | 0.034 |
| 10 | 0.059 | 0.016 | 0.018 | 0.029 | 0.065 |
| 16 | 0.085 | 0.019 | 0.025 | 0.038 | 0.060 |
| 32 | 0.079 | 0.028 | 0.035 | 0.045 | 0.096 |

batch 8：CPU 输入复制 p95 0.001 ms；逐候选不批处理总推断中位 0.072 ms。首次模型加载 1.179 ms。

“首次调用”指加载后的该 batch 大小首次预测，不等于全进程冷启动。批处理/CPU 输入复制/逐候选开销均已分开保存。GPU 未测：本轮两类模型及训练实现均为 NumPy CPU 路径；不能推断 GPU 更快或更慢，也没有产生 GPU 传输数据。后台搜索负载可能造成离群值，原样保留。

**17．一次 repetition-boundary 更新需要多久？**

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 按模型 SHA/路径去重的实际模型生成 wall time | 0 | 未测量 | 未测量 | 未测量 | 未测量 |

单位：s。

当前尚无 pilot 更新；离线训练各候选的耗时不能替代这一项。

**18．学习/更新会阻塞连续执行吗？**

活动模型在任务内保持不变；后台生成新版本，校验后仅在明确安全 repetition boundary 切换。模型未就绪时保留既有验证版本。model readiness wait 上限为 2 s；这不是整个 inter-repetition 延迟上限。返回提取、checkpoint、文件归档，以及单列的安全边界/下一次运行初始化也有成本。最终 pool.shutdown(wait=True) 属于收尾，不能描述为部署延迟保证。

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 科学 harness 的 inter-rep processing | 0 | 未测量 | 未测量 | 未测量 | 未测量 |

单位：s。

预算来源：5 ms 是原控制/采样周期，不是 learner deadline；已选 waypoint 通常持续远长于该周期。原 moving endpoint 有 40 ms bridge，并在观察到的 35 ms 已认证 fork 前决定接入主参考或不可逆制动；原始 source age 必须严格小于 100 ms。初始静止 OUTBOUND 首决策与 moving continuation 应分别分析。

同一请求逐项计算的 moving 非 producer 跨度（capture → activation 减去该请求实际 producer compute，保留采集/收集/最终验证等开销）：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| moving 非 producer 实际配对跨度 | 10 | 27.337 | 29.103 | 29.156 | 29.170 |

单位：ms。

按其中已观察最大值，若其余开销保持现状，35 ms fork 留给 producer 的最小观察余量只有 5.830 ms。此余量不是 WCET 保证，也不是各组件分位数之和；它进一步说明仅有算法 max <35 ms 不能满足完整主机 moving 窗口。

当前计算门状态：`SCIENTIFIC_PILOT_COMPUTATION_PLAUSIBLE_WALL_BUDGET_UNDEMONSTRATED`；algorithm plausible-path=True；正常模型 rollout 验证=True；观察到的完整主机跨度均在对应机会内=False。原 epoch replay 不含实时队列、新观察 handoff 复验和实际写入，故算法预算可行不等于完整主机 deadline 达标。

所选配置为首决策实际 4 候选，captured BANK 来源索引 [0, 2, 3, 6]，后续一个已提交 continuation，legacy proposal limit=1。这是 development capture 的有界 proposal prior；原硬筛选保留，既有 baseline/fallback 仍为迟到结果的权威处理路径。

版本 v3 仅已提交 MATCHED continuation 延迟计算 legacy comparator：原 terminal/input guard 及 committed 候选 _evaluate 先执行，其结果复用于原 matched 硬筛选；候选拒绝时才调用原 legacy diagnostics 并保留原 research failure。初始/HOLD/native/branch 继续 eager。成功 continuation 的 comparator 未计算，日志 0 ms 表示未执行该阶段，不代表 baseline 的目标代价为零。原 escape 与 authority/epoch activation validator 未变。

实际移动 committed continuation 参考速度 [0.20943951023931934, 0.349065850398866] rad/s；算法原 epoch 验证重复测量如下：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 实际 moving committed continuation 算法 | 30 | 19.591 | 20.426 | 20.820 | 20.953 |

单位：ms。

实际 moving 快照算法的进一步拆分（adapter 总计包含其 proposal、硬筛选、特征和 Q 项；不相加重复计数）：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| adapter 决策到选择 | 30 | 7.972 | 8.471 | 8.522 | 8.527 |
| 选择返回 → 已认证 escape preparation | 30 | 6.183 | 6.598 | 6.736 | 6.770 |
| 原 epoch activation validator | 30 | 5.265 | 5.523 | 5.631 | 5.672 |

单位：ms。

RETURN 冻结快照参考速度为 [0,0]，属于静止已提交 continuation 代理；保留其缩放数据，但不将其用于实际移动算法门。

真实冻结快照的算法缩放（每项 30 次；原 epoch 参考验证，失败项另存原始结果；不含完整实时激活链）：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| eager 保留 OUTBOUND captured BANK requested 1 / actual [1] / legacy default | 30 | 64.910 | 69.954 | 70.032 | 70.042 |
| eager 保留 OUTBOUND captured BANK requested 3 / actual [3] / legacy default | 30 | 82.315 | 93.785 | 104.123 | 107.639 |
| eager 保留 OUTBOUND captured BANK requested 4 / actual [4] / legacy default | 30 | 91.213 | 97.819 | 98.576 | 98.862 |
| eager 保留 OUTBOUND captured BANK requested 6 / actual [6] / legacy default | 30 | 110.381 | 116.690 | 118.616 | 119.393 |
| eager 保留 OUTBOUND captured BANK requested 10 / actual [10] / legacy default | 30 | 175.607 | 203.129 | 216.660 | 222.167 |
| eager 保留 OUTBOUND captured BANK requested 1 / actual [1] / legacy 1 | 30 | 30.945 | 33.131 | 37.284 | 38.930 |
| eager 保留 OUTBOUND captured BANK requested 3 / actual [3] / legacy 1 | 30 | 46.549 | 52.283 | 54.795 | 55.623 |
| eager 保留 OUTBOUND captured BANK requested 4 / actual [4] / legacy 1 | 30 | 56.795 | 66.361 | 73.132 | 74.952 |
| eager 保留 OUTBOUND captured BANK requested 6 / actual [6] / legacy 1 | 30 | 80.876 | 95.593 | 116.684 | 124.459 |
| eager 保留 OUTBOUND captured BANK requested 10 / actual [10] / legacy 1 | 30 | 115.537 | 122.257 | 123.485 | 123.771 |
| eager 保留 OUTBOUND captured BANK requested 1 / actual [1] / legacy 3 | 30 | 34.725 | 39.348 | 43.707 | 45.176 |
| eager 保留 OUTBOUND captured BANK requested 3 / actual [3] / legacy 3 | 30 | 55.988 | 62.661 | 65.699 | 66.272 |
| eager 保留 OUTBOUND captured BANK requested 4 / actual [4] / legacy 3 | 30 | 64.916 | 70.478 | 72.315 | 73.022 |
| eager 保留 OUTBOUND captured BANK requested 6 / actual [6] / legacy 3 | 30 | 83.061 | 90.859 | 92.915 | 93.646 |
| eager 保留 OUTBOUND captured BANK requested 10 / actual [10] / legacy 3 | 30 | 130.587 | 144.742 | 147.201 | 147.348 |
| eager 保留 RETURN captured BANK requested 1 / actual [1] / legacy default | 30 | 68.033 | 72.470 | 74.891 | 75.710 |
| eager 保留 RETURN captured BANK requested 3 / actual [1] / legacy default | 30 | 62.945 | 67.052 | 67.596 | 67.816 |
| eager 保留 RETURN captured BANK requested 4 / actual [1] / legacy default | 30 | 68.982 | 74.869 | 75.922 | 76.265 |
| eager 保留 RETURN captured BANK requested 6 / actual [1] / legacy default | 30 | 63.993 | 68.101 | 69.458 | 69.921 |
| eager 保留 RETURN captured BANK requested 10 / actual [1] / legacy default | 30 | 68.345 | 72.310 | 74.054 | 74.707 |
| eager 保留 RETURN captured BANK requested 1 / actual [1] / legacy 1 | 30 | 26.877 | 27.896 | 28.425 | 28.602 |
| eager 保留 RETURN captured BANK requested 3 / actual [1] / legacy 1 | 30 | 27.668 | 29.204 | 30.364 | 30.802 |
| eager 保留 RETURN captured BANK requested 4 / actual [1] / legacy 1 | 30 | 28.988 | 30.869 | 31.206 | 31.244 |
| eager 保留 RETURN captured BANK requested 6 / actual [1] / legacy 1 | 30 | 29.817 | 31.929 | 33.202 | 33.669 |
| eager 保留 RETURN captured BANK requested 10 / actual [1] / legacy 1 | 30 | 29.444 | 36.614 | 40.001 | 40.688 |
| eager 保留 RETURN captured BANK requested 1 / actual [1] / legacy 3 | 30 | 36.237 | 39.246 | 41.684 | 42.637 |
| eager 保留 RETURN captured BANK requested 3 / actual [1] / legacy 3 | 30 | 35.776 | 36.725 | 37.025 | 37.134 |
| eager 保留 RETURN captured BANK requested 4 / actual [1] / legacy 3 | 30 | 36.804 | 39.692 | 40.885 | 40.951 |
| eager 保留 RETURN captured BANK requested 6 / actual [1] / legacy 3 | 30 | 36.161 | 39.696 | 41.195 | 41.656 |
| eager 保留 RETURN captured BANK requested 10 / actual [1] / legacy 3 | 30 | 35.729 | 37.933 | 39.294 | 39.769 |
| eager 保留 OUTBOUND captured BANK requested 1 / actual [1] / legacy 1 | 30 | 27.975 | 31.997 | 35.491 | 36.773 |
| lazy v3 OUTBOUND captured BANK requested 4 / actual [4] / legacy 1 | 30 | 52.191 | 56.069 | 56.590 | 56.614 |
| lazy v3 OUTBOUND captured BANK requested 1 / actual [1] / legacy 1 | 30 | 19.591 | 20.426 | 20.820 | 20.953 |

单位：ms。

RETURN 已提交 continuation 实际始终为一个候选；requested BANK 大小不代表该状态执行了同等候选数。首决策完整 10 个候选加 legacy1 的最大耗时超过 100 ms，因此不能用它宣称当前预算可行。所选四候选保留实际 development 已选优 descriptor，而不是未经测量地固定 prefix4。

协议偏差已保留：SCRATCH rep1 物理状态 VALID，但执行时使用后来被取代的静止 continuation proxy gate，不能追溯标为 actual-moving v3 gate PASS。该次日志在 NumPy 边界 JSON 序列化处失败，原 repetition、checkpoint 和 gate publication 保留。后续若由验证的原 checkpoint 恢复，rep2+ 的 lazy 计算修订仅在边界另行冻结；这是混合计算版本的 development pilot，物理状态不重置、不替代原 rep1 provenance。

**19．显式候选搜索 + Q 排序够快吗，是否需要 actor/distillation？**

本轮优先依据实际正常运行与候选数缩放选择有限的多样首决策 proposal，以及后续一个已提交 continuation candidate。单候选 continuation 已不能继续通过减少研究候选数解决成本。若 Q 推断很小而硬筛选、原始候选比较、escape preparation、主线程收集或最终验证占主要时间，单纯增加 actor 不能解决这些成本。只有实际完整决策证据持续超出机会、且 proposal 数缩减仍不足时，再评价轻量 proposal policy，随后仍执行原有硬筛选；当前证据更支持先剖析这些调度/验证开销，不自动启动 actor。

`RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`。以上不构成硬件安全、WCET 或实时资格。
