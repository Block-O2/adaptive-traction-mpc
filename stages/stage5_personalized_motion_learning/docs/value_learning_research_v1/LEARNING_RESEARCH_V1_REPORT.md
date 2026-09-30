# Learning Research v1：性能上限、学习效率与在线计算

生成时间：2026-09-30T18:41:26.391865+00:00。当前状态：`RUNNING`，科学工作状态：`研究处理中`。

累计运行 4.57 小时；9 小时上限为 2026-09-30T23:07:00+00:00。新研究已关闭记录 639 个：{"VALID": 519, "INFEASIBLE": 109, "INVALID": 3, "INTERRUPTED_HOST_RESOURCE": 8}。历史 518 次探索、63.77 GB 原始来源另行冻结验证，不计为本轮新增实验。

主指标为完成有效任务的实测袖套力模积分 J_F_task，单位 N·s。安全与任务有效性始终为硬门槛；均值/RMS/峰值力、力矩积分/峰值、时长、clearance 和 smoothness 分别保存于逐次结果，不重新加权成奖励。

**必须区分两种范围：** NATIVE_SCHEDULER 是主目标的绝对 best-known 搜索；MATCHED 是固定声明续行时长的条件化学习研究。MATCHED 取得的改善不能当作绝对性能上限。所有参考均为 best-known，未证明全局最优。

## 1. 接口是否复现已知有益协调？

是。四个 MATCHED 和四个 NATIVE 参考通过同一研究候选/执行接口复放，目标、实现 q、力轨迹和 J_F 差异均为零。来源包含同步、变起点、balanced-high 和 hip 条件；原始控制、安全、估计与几何屏障保留。见 ACTION_EXPRESSIVITY_GATE.json 与 NATIVE_ACTION_EXPRESSIVITY_GATE.json。

## 2. 更强搜索是否超过旧 best-known？

下表旧值取全部历史 VALID 路径的最小成本，包括时序存在差异的路径；另外保留旧 timing-isolated 值，避免把受限旧参考当作绝对旧最优。Q 筛选新增参考与 CEM 搜索分开标注。

|条件|MATCHED 旧 → 新 (N·s)|NATIVE 旧 → 新 (N·s)|新增实测评估 matched/native|
|---|---:|---:|---:|
|sync_120|1488.972118 → 1485.999765|1180.562198 → 1180.000018|64/24|
|variable_start_120|1482.176759 → 1473.789827|1176.574504 → 1176.574504|64/20|
|balanced_high|1196.030462 → 1191.410073|938.997031 → 937.068513|56/20|
|hip_ordinary|761.440631 → 761.440631|621.738501 → 618.374301|56/20|
|low_ordinary_early|598.414598 → 588.319268|500.513571 → 500.513571|56/20|
|low_ordinary_late|599.325808 → 587.790992|501.390874 → 500.054522|56/20|

新赢家通过独立同起点再执行确认；这是确定性复现，不是独立受试者泛化。见 BEST_KNOWN_REFERENCE_CONFIRMATION.json、NATIVE_BEST_KNOWN_REFERENCE_CONFIRMATION.json。

## 3. 更多路径自由度是否继续降低成本？

至少 variable_start_120 的 MATCHED 层级从 L0 1482.176759、L2 1481.931124 降至 L3 1473.789827 N·s，增加平滑控制点仍有益。其他条件增加自由度未必改善。L1/L2/L3 的连续系数分别为 2/5/7，另有离散 horizon/return 选择；层级包络继承旧参考，不能把不同评估数量当作公平复杂度消融。L4 未执行。

## 4. 有证据接近平台吗？

不足。部分条件的有限预算包络变平，但有效评估、重启和代数覆盖不同，尚无充分重复优化或下界。CEM 保留基线、已知有益初始化、多个重启和均匀探索；每个提议使用真实冻结科学栈评价。见各条件 level_evaluations、restart_generation_evaluations、restart_best 和完整收敛曲线。

## 5. 最佳协调有多强的条件依赖？

明显。大 ROM 条件倾向较强 hip-leading H3；普通低 ROM 的最佳 MATCHED 路径包含小幅相反方向或不同 catch-up peak，hip 普通条件保留旧 H4 参考。NATIVE 与 MATCHED 最佳策略也不同。六个代表条件不支持单一跨条件最优策略或人群结论。

## 6. Q 能否正确排列动作？

数据为 503 条 VALID MATCHED 轨迹、6162 个实际激活决策、96 个可部署特征；train/validation/test 行数为 {'test': 1174, 'train': 3811, 'validation': 1177}。27 组共同状态、共同续行规则的安全下一目标分支支持局部排序识别。训练按条件隔离，未随机拆相邻轨迹行。

选定 FULL ridge 的 validation 平均 regret 0.684 N·s，legacy 1.690，ρ=0.417。held-out test ρ=-0.333、regret 3.555，对比 legacy 4.360；只支持有限的开发门槛，不能声称稳定跨条件正确排序。

Q 的实际语义是 Q(x,a | 已声明续行规则)，不是 Q*；每个目标从真实激活/生效区间计算 FULL 剩余回报与 1.5 秒 SHORT 回报。后续控制保持闭环，但本次策略先在首次 OUTBOUND 目标选择一个平滑续行模式，后续按该模式提议单个目标，不把整个 H3/H4 收益归因于孤立首个 waypoint。

## 7. FULL 是否胜过 SHORT？

结果混合，不能作一致优势结论。FULL ridge 比 SHORT ridge 的 held-out FULL 动作 regret 更低；MLP 则 SHORT 的 FULL 动作 regret 2.195 优于 FULL 8.335。不同目标的预测误差量级不可直接比较，主要比较共同分支中的实际完整回报 regret。未用 test 重新选择模型。

## 8. 简单模型与小 MLP 的效果？

|模型/目标|test MAE / RMSE (N·s)|FULL 动作排名 ρ|所选动作 regret (N·s)|top1 / top2|
|---|---:|---:|---:|---:|
|mlp_full|131.769 / 181.295|-0.000|8.335|0.500 / 0.500|
|mlp_short|15.789 / 20.517|0.333|2.195|0.667 / 0.667|
|ridge_full|81.488 / 113.239|-0.333|3.555|0.333 / 0.333|
|ridge_short|205.693 / 238.999|-1.000|8.556|0.000 / 0.000|

MLP 为两个 32 单元 tanh 层、NumPy Adam、三种冻结种子；ridge 含标准化线性项和可解释状态×动作交互。选模使用 validation；模型及 scaler 保存为不可变 NPZ。简洁 ridge 在本次 FULL 开发集较好，但 held-out 排名仍弱。

## 9. PRIOR 比 SCRATCH 帮助多少？

两者使用相同候选库、模型族、由离线 validation 选定的超参数。SCRATCH 无跨条件预训练值权重，初始两轮用已知安全的连贯提议；PRIOR 只用其他 train 条件，并排除当前 sync 与全部 held-out test，当前在线行单独记录。它们均不是从零学习控制器、任务、安全或候选族。

|会话|有效/尝试轮数|首轮 → 末轮 J_F (N·s)|收敛候选轮|
|---|---:|---:|---:|

成本变化同时包含持续 Human/adaptation 状态演变；同一轮前检查点的 baseline/ref 对照用于消除直接跨轮比较的混淆。只有一个条件的两个会话，没有 PRIOR 优势的独立样本效应估计。具体预测误差、排名、选择和更新版本见 SCRATCH_VS_PRIOR_ANALYSIS.json。

## 10. 小试验几轮稳定？


稳定性同时检查最近三轮 baseline-adjusted 收益、精确模式、Q 排名、目标替代探针、安全和计算门槛。阈值仅在开发试验后冻结；本轮回溯，不用于提前强制停学。

## 11. 五轮收敛现实吗？

当前不能确认。Rep5 没有同轮替代探针，即使成本/模式平稳也不能声称触发完整收敛准则。八轮预算并非“5 learn + 25 exploit”；后续应预注册所需探针与阈值并按证据停学。

## 12. Rep1/3/5/8 的已知收益捕获？

|会话/轮|MATCHED baseline / learned / reference (N·s)|条件化 capture|NATIVE 主目标 capture|
|---|---:|---:|---:|

capture=(baseline−learned)/(baseline−best-known)，仅正且可辨的分母计算。保留负值或超过 1 的结果；超过参考需独立确认后更新该状态 best-known。两种调度范围各用同轮前不可变检查点，不能把 MATCHED capture 当作绝对全局最优百分比。

## 13. 本轮最佳有效成本/参考是什么？

见上方逐条件表与 ABSOLUTE_PRIMARY_REFERENCE_TABLE.json；跨条件 J_F 不直接排序性能。sync 的已确认 MATCHED 参考为 1478.873547 N·s，NATIVE 参考明显更低，说明匹配时长学习问题仍有范围限制。各参考同时保存时长、相位差、参数、可行比例与原始实验 ID。

## 14. 学习器是否发现并确认更好行为？

离线训练 Q 在延迟采集中选择 amp=0.15、peak=0.5、H3 的路径；独立重新执行得到完全相同的 1478.873547 N·s，低于 sync CEM 1485.999765。这是离线 Q 的条件化新发现，不能称为在线少样本个性化发现，更不能称为 NATIVE 主目标新最优。在线超过同状态参考的结果仅按 KNOWN_BENEFIT_CAPTURE.json 中确认记录报告。

## 15–19. 完整在线计算、瓶颈、更新与策略加速

### 在线计算与更新（问题 15–19）

以下是 Scientific Simulation 的实际主机剖析。模型属于固定 MATCHED pacing（1.3 倍注册段时长）和明确 continuation context；native 绝对目标补充研究未混入拟合。主机时间不会推进冻结的生产者仿真 epoch，因此这些数据不能认证硬件实时行为。

**15．端到端高层决策延迟是多少？**

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 原始传感捕获 → 参考验证完成 | 13 | 44.057 | 60.552 | 71.118 | 73.759 |
| 原始传感捕获 → 实际命令激活 | 13 | 44.361 | 61.027 | 71.513 | 74.134 |
| 研究决策开始 → 参考验证完成 | 12 | 42.310 | 58.184 | 67.760 | 70.153 |
| 研究决策开始 → 实际命令激活 | 12 | 42.638 | 58.650 | 68.153 | 70.529 |
| 首个特征开始 → 参考验证完成 | 12 | 29.831 | 44.205 | 52.595 | 54.692 |
| 首个特征开始 → 实际命令激活 | 12 | 30.210 | 44.671 | 52.988 | 55.067 |
| 选定参考 → 实际命令激活 | 12 | 29.599 | 35.276 | 35.871 | 36.019 |

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
| 首个 pattern 选择：捕获 → 激活 | 1 | 74.134 | 74.134 | 74.134 | 74.134 |
| 已提交 continuation：捕获 → 激活 | 11 | 44.361 | 51.578 | 52.146 | 52.288 |
| 其中 moving handoff：捕获 → 激活 | 10 | 44.945 | 51.649 | 52.161 | 52.288 |

单位：ms。

**16．哪部分主导延迟？**

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 原始 planner 比较候选 | 12 | 5.115 | 5.922 | 6.032 | 6.060 |
| 研究 proposal 枚举 | 12 | 0.185 | 0.481 | 0.711 | 0.768 |
| 研究候选调度/硬筛选 | 12 | 7.236 | 20.246 | 32.196 | 35.184 |
| 特征构建 | 12 | 0.060 | 0.153 | 0.231 | 0.250 |
| 批量 Q 推断和选择 | 12 | 0.046 | 0.066 | 0.073 | 0.074 |
| worker 完成到主线程收集 | 13 | 12.623 | 14.934 | 15.448 | 15.577 |
| 当前状态参考验证及命令构建 | 13 | 10.797 | 12.811 | 12.925 | 12.954 |

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
| moving 非 producer 实际配对跨度 | 10 | 25.849 | 31.251 | 32.132 | 32.352 |

单位：ms。

按其中已观察最大值，若其余开销保持现状，35 ms fork 留给 producer 的最小观察余量只有 2.648 ms。此余量不是 WCET 保证，也不是各组件分位数之和；它进一步说明仅有算法 max <35 ms 不能满足完整主机 moving 窗口。

当前计算门状态：`ALGORITHM_PROFILE_EXCEEDS_PRELIMINARY_OPPORTUNITY`；algorithm plausible-path=False；正常模型 rollout 验证=True；观察到的完整主机跨度均在对应机会内=False。原 epoch replay 不含实时队列、新观察 handoff 复验和实际写入，故算法预算可行不等于完整主机 deadline 达标。

所选配置为首决策实际 4 候选，captured BANK 来源索引 [0, 2, 3, 6]，后续一个已提交 continuation，legacy proposal limit=1。这是 development capture 的有界 proposal prior；原硬筛选保留，既有 baseline/fallback 仍为迟到结果的权威处理路径。

实际移动 committed continuation 参考速度 [0.20943951023931934, 0.349065850398866] rad/s；算法原 epoch 验证重复测量如下：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| 实际 moving committed continuation 算法 | 30 | 27.975 | 31.997 | 35.491 | 36.773 |

单位：ms。

实际 moving 快照算法的进一步拆分（adapter 总计包含其 proposal、硬筛选、特征和 Q 项；不相加重复计数）：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| adapter 决策到选择 | 30 | 13.446 | 15.797 | 15.944 | 15.990 |
| 选择返回 → 已认证 escape preparation | 30 | 7.603 | 9.079 | 9.345 | 9.445 |
| 原 epoch activation validator | 30 | 6.272 | 7.589 | 11.147 | 12.495 |

单位：ms。

当前计算门关闭，不能据此启动要求该门通过的在线改善 pilot；30 次 actual-moving 最大值超过严格 35 ms 机会。静止代理曾得到的 preliminary PASS 已保留并被版本化实际移动门取代；不删除离群值，也不通过重测挑选更小最大值。

RETURN 冻结快照参考速度为 [0,0]，属于静止已提交 continuation 代理；保留其缩放数据，但不将其用于实际移动算法门。

真实冻结快照的算法缩放（每项 30 次；原 epoch 参考验证，失败项另存原始结果；不含完整实时激活链）：

| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| OUTBOUND prefix requested 1 / actual [1] / legacy default | 30 | 64.910 | 69.954 | 70.032 | 70.042 |
| OUTBOUND prefix requested 3 / actual [3] / legacy default | 30 | 82.315 | 93.785 | 104.123 | 107.639 |
| OUTBOUND prefix requested 4 / actual [4] / legacy default | 30 | 91.213 | 97.819 | 98.576 | 98.862 |
| OUTBOUND prefix requested 6 / actual [6] / legacy default | 30 | 110.381 | 116.690 | 118.616 | 119.393 |
| OUTBOUND prefix requested 10 / actual [10] / legacy default | 30 | 175.607 | 203.129 | 216.660 | 222.167 |
| OUTBOUND prefix requested 1 / actual [1] / legacy 1 | 30 | 30.945 | 33.131 | 37.284 | 38.930 |
| OUTBOUND prefix requested 3 / actual [3] / legacy 1 | 30 | 46.549 | 52.283 | 54.795 | 55.623 |
| OUTBOUND prefix requested 4 / actual [4] / legacy 1 | 30 | 56.795 | 66.361 | 73.132 | 74.952 |
| OUTBOUND prefix requested 6 / actual [6] / legacy 1 | 30 | 80.876 | 95.593 | 116.684 | 124.459 |
| OUTBOUND prefix requested 10 / actual [10] / legacy 1 | 30 | 115.537 | 122.257 | 123.485 | 123.771 |
| OUTBOUND prefix requested 1 / actual [1] / legacy 3 | 30 | 34.725 | 39.348 | 43.707 | 45.176 |
| OUTBOUND prefix requested 3 / actual [3] / legacy 3 | 30 | 55.988 | 62.661 | 65.699 | 66.272 |
| OUTBOUND prefix requested 4 / actual [4] / legacy 3 | 30 | 64.916 | 70.478 | 72.315 | 73.022 |
| OUTBOUND prefix requested 6 / actual [6] / legacy 3 | 30 | 83.061 | 90.859 | 92.915 | 93.646 |
| OUTBOUND prefix requested 10 / actual [10] / legacy 3 | 30 | 130.587 | 144.742 | 147.201 | 147.348 |
| OUTBOUND subset [0, 2, 3, 6] requested 4 / actual [4] / legacy 1 | 30 | 50.637 | 55.601 | 56.094 | 56.148 |
| RETURN prefix requested 1 / actual [1] / legacy default | 30 | 68.033 | 72.470 | 74.891 | 75.710 |
| RETURN prefix requested 3 / actual [1] / legacy default | 30 | 62.945 | 67.052 | 67.596 | 67.816 |
| RETURN prefix requested 4 / actual [1] / legacy default | 30 | 68.982 | 74.869 | 75.922 | 76.265 |
| RETURN prefix requested 6 / actual [1] / legacy default | 30 | 63.993 | 68.101 | 69.458 | 69.921 |
| RETURN prefix requested 10 / actual [1] / legacy default | 30 | 68.345 | 72.310 | 74.054 | 74.707 |
| RETURN prefix requested 1 / actual [1] / legacy 1 | 30 | 26.877 | 27.896 | 28.425 | 28.602 |
| RETURN prefix requested 3 / actual [1] / legacy 1 | 30 | 27.668 | 29.204 | 30.364 | 30.802 |
| RETURN prefix requested 4 / actual [1] / legacy 1 | 30 | 28.988 | 30.869 | 31.206 | 31.244 |
| RETURN prefix requested 6 / actual [1] / legacy 1 | 30 | 29.817 | 31.929 | 33.202 | 33.669 |
| RETURN prefix requested 10 / actual [1] / legacy 1 | 30 | 29.444 | 36.614 | 40.001 | 40.688 |
| RETURN prefix requested 1 / actual [1] / legacy 3 | 30 | 36.237 | 39.246 | 41.684 | 42.637 |
| RETURN prefix requested 3 / actual [1] / legacy 3 | 30 | 35.776 | 36.725 | 37.025 | 37.134 |
| RETURN prefix requested 4 / actual [1] / legacy 3 | 30 | 36.804 | 39.692 | 40.885 | 40.951 |
| RETURN prefix requested 6 / actual [1] / legacy 3 | 30 | 36.161 | 39.696 | 41.195 | 41.656 |
| RETURN prefix requested 10 / actual [1] / legacy 3 | 30 | 35.729 | 37.933 | 39.294 | 39.769 |
| OUTBOUND prefix requested 1 / actual [1] / legacy 1 | 30 | 27.975 | 31.997 | 35.491 | 36.773 |

单位：ms。

RETURN 已提交 continuation 实际始终为一个候选；requested BANK 大小不代表该状态执行了同等候选数。首决策完整 10 个候选加 legacy1 的最大耗时超过 100 ms，因此不能用它宣称当前预算可行。所选四候选保留实际 development 已选优 descriptor，而不是未经测量地固定 prefix4。

**19．显式候选搜索 + Q 排序够快吗，是否需要 actor/distillation？**

本轮优先依据实际正常运行与候选数缩放选择有限的多样首决策 proposal，以及后续一个已提交 continuation candidate。单候选 continuation 已不能继续通过减少研究候选数解决成本。若 Q 推断很小而硬筛选、原始候选比较、escape preparation、主线程收集或最终验证占主要时间，单纯增加 actor 不能解决这些成本。只有实际完整决策证据持续超出机会、且 proposal 数缩减仍不足时，再评价轻量 proposal policy，随后仍执行原有硬筛选；当前证据更支持先剖析这些调度/验证开销，不自动启动 actor。

`RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`。以上不构成硬件安全、WCET 或实时资格。


## 20. 下一次更大实验具体用什么方法？

推荐一个版本化、原生调度条件化的轻量 ridge critic：保留 NATIVE 基线作真实 fallback/incumbent；用少量连贯安全模板提议下一 hip/knee 目标，原始安全筛选后独立 Q 排名，已承诺续行复用已验证的筛选结果。先针对原生调度构建共同状态/共同续行分支数据，验证 held-out 排名与主目标收益；把模型在明确安全轮边界切换，并在 rep1/3/5/8 预注册替代探针。完成完整提交链预算验证后，才进入更大的 learn-until-converged → exploit 研究。本轮不启动最终30轮、硬件或 realtime qualification。

这是一个下一步方法，包含必需的原生主目标与提交链验证门槛；当前 MATCHED critic 不能直接晋升为部署策略。推理已很快，优先削减重复安全计算和提交开销；只有少量候选仍无法满足预算时，才考虑轻量 proposal policy，安全筛选继续权威。

## 证据、修复与 Git 状态

起点分支 codex/coordination-pacing-exploration-v1，HEAD 8654cf0b6704fdecce3b4ccf1f00eb599aa5248c；研究分支 codex/value-learning-research-v1。原始控制/估计/Human dynamics/历史证据哈希保持冻结；hidden truth 仅评估使用，未进入选择。修复上限6，已用 5，逐项见修复与基础设施记录。

本轮改动位于新研究 scripts/value_learning_v1 与 docs/value_learning_research_v1，另新增 git-ignore 规则；大型原始轨迹忽略于 Git，lossless 压缩及 D 盘逐字节校验转存有清单/哈希。未 reset、stash、clean、merge、force push 或 git add -A。所有分阶段提交逐文件 stage。

RAW_DATA_MANIFEST.json、FINGERPRINTS.json、SOURCE_RAW_VERIFICATION.json、FINAL_EVIDENCE_VERIFICATION.json、Git checkpoint/REMOTE_VERIFICATION 记录用于复现。总时间与逐类别 launch 耗时见 REFERENCE_AND_TRAINING_WALL_TIME.json；并发工作时间求和不是经过的 wall time。

Git push 的自动审批已拒绝，理由是 GitHub 目的地/外发研究载荷授权未获确认。先完成可审查科学证据与本地提交，最后向用户请求向 https://github.com/Block-O2/adaptive-traction-mpc 的 codex/value-learning-research-v1 分支推送。未验证 local HEAD == remote HEAD 前，不宣称用户要求的整体 COMPLETE。

`RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`。科学算法耗时、冻结物理仿真和确定性复现均不构成硬件实时或临床安全资格。
