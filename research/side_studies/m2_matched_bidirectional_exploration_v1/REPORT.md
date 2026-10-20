# iHEAR Lab — 匹配状态与双阶段协调探索 v1

终态：**NEGATIVE_RESULT**。科学层完整活状态fork及同动作复现 **PASS**；本包 **HOST_CLOCK_CAUSAL_QUALIFICATION=NOT_EVALUABLE**。

O/R/OR均满足冻结的运动、任务公平及原生安全检查，均有小幅真实科学层force收益；总收益分别0.1197%/0.3305%/0.4502%，都低于预注册0.5%发现门限。因此没有主条件PASS方案，保留验证NOT_RUN，不声称VALIDATED，也不按本次结果调低收益或运动门限。

实际attempt **16/18**，完整导出 **12**。失败和首次零物理启动均计入保守attempt预算；没有并行重型物理、Q/Neural Q训练、G/P、online adaptation、新Human或硬件试验。

## 完整同初态发现结果

以下B0/O/R/OR及Frozen M2均来自本包最终活进程同一完整native OUTBOUND请求状态。B0为未受child写入影响的原父续跑；每个child后原父完整hash不变。无法完成B0的前一父运行及其O/R/OR记录保留为复现证据，不用于本表的主要配对分母。

| 配置 | 总J_F N·s | OUTBOUND | HOLD | RETURN | B0相对收益 | motion/force接受 | 发现主门限 |
|---|---:|---:|---:|---:|---:|---|---|
| B0 | 1438.613498 | 725.825779 | 54.394339 | 658.393380 | baseline | baseline | reference |
| O | 1436.892184 | 724.104465 | 54.394338 | 658.393380 | 0.1197% | PASS | FAIL |
| R | 1433.858423 | 725.825779 | 54.394339 | 653.638305 | 0.3305% | PASS | FAIL |
| OR | 1432.137109 | 724.104465 | 54.394338 | 653.638305 | 0.4502% | PASS | FAIL |
| Frozen_M2 | 1312.019870 | 682.602004 | 54.404260 | 575.013606 | 8.7997% | velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion, moment_integral_Nm_s, tracking | reference |

收益百分比为100×(B0−配置)/B0，配置ΔJ为配置−B0；正收益表示降低force。积分使用原TASK完整left-endpoint quadrature，所有阶段精确分区闭合原完整J_F。没有按phase删点、截短HOLD或换B0。实际phase-clock与积分trace duration均另存。

R从同一RETURN入口的独立分叉：ΔRETURN J_F=-4.755075310 N·s，总收益=4.755075310 N·s，motion/force接受=PASS。

2×2交互收益近似为0，本固定组合呈数值上的近似加性。G_OR−G_O−G_R=-2.14699866774e-08 N·s。OR相对O/R的额外收益分别为4.755075289/1.721314652 N·s。这是从完整共同初态得到的总轨迹交互，不自动将全部RETURN差解释为独立阶段因果。

## 最终十问

1. **旧RETURN-only为什么出现OUTBOUND改善？** 三个RETURN-only的proposal→native accepted metadata→activated segment→positive-step receipts审计均没有RETURN前非零执行。发现005的OUTBOUND减少53.240123769 N·s属于pre-intervention imbalance。最早可见force/运动/command差在commissioning物理t=0.010s，reference差在0.035s；两个旧验证pair的force差分别从0.005/0.015s开始。不能归功于尚未执行的RETURN residual。

2. **B冷启动差异关联哪些因素？** 在commissioning早期已经出现command、force及真实q/dq差，随后commissioning beta/residual/geometry、TASK入口与native activation/等待机会均不同。五个candidate/B-zero对照的早期force差都早于首个aligned estimator更新，初始population beta/residual相同；后续模型拟合差不能作为已证实的最早外生原因。三次B-zero范围26.067509 N·s；其11维beta分量range见JSON，最大0.162644026。n=3不足以区分独立原因、估计误差界或进行显著性推断；‘主要关联’只能定位早期执行/观测时间线，不能独断beta或某个OS原因。

3. **合法匹配初态是否建立？** 是，限定SCIENTIFIC_SIMULATION。两次same-control所有归档trace及116320 native行、5817 receipts一致，有限观察误差0；新四个完整入口hash相同=True，RETURN入口完整hash相同=True。MuJoCo integration、全部Human/commissioning对象、controller/estimator、reference/phase、planner/scheduler、carry/slots/lifecycle、RNG、native handles在活进程中fork继承。JSON未用于恢复。未复制OS调度或证明host-clock同状态反事实。

4. **OUTBOUND能否独立产生真实force收益？** 本注册O配置的OUTBOUND ΔJ_F=-1.721313899 N·s，总gain=0.1197%。执行计数与motion接受见下文。该数值由合法同初态干预比较得到，作用范围为一个既有Human/配置的科学仿真；不是人口或host验证。

5. **RETURN能否独立产生真实force收益？** R的OUTBOUND/HOLD无非零执行且介入前完整归档字段一致=True；其RETURN ΔJ_F=-4.755075310 N·s，同RETURN入口的独立zero/R差为-4.755075310 N·s。完整入口及RETURN入口两种对照区分了R作用与先前运动。

6. **OR是否优于单独协调？** 该固定组合的完整J_F低于O/R分别4.755075289/1.721314652 N·s；交互项-2.14699866774e-08 N·s，应按其实际量级解释。O/OR进入RETURN的q/dq并不被假定相同，真实状态及与B0差已保存。

7. **能否同时满足运动平顺性和任务公平？** 原native physical/safety审计与新研究接受条件分开。以下逐方案失败项和各速度/加速度/jerk比值保留；force下降不是整体PASS。研究规则保持10%非劣、excursion≤0.5°、累计量±5%、端点/phase-boundary≤0.5°、完整/每阶段时长差≤0.1s、moment≤25%、tracking≤0.5°增量、peak≤5%补偿且原absolute安全/clearance PASS。Phase-shape独立诊断，0/5/10/25%和SG5/21敏感性保留，均非临床阈值。

   - O: motion/force PASS; knee p95 speed/acceleration/jerk ratio = 1.000000/0.985672/1.001901。
   - R: motion/force PASS; knee p95 speed/acceleration/jerk ratio = 1.005293/0.975910/0.966144。
   - OR: motion/force PASS; knee p95 speed/acceleration/jerk ratio = 1.005293/0.966103/0.969190。
   - Frozen_M2: motion/force FAIL — velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion, moment_integral_Nm_s, tracking; knee p95 speed/acceleration/jerk ratio = 1.693083/2.271232/1.147729。

8. **哪些收益可重复、哪些仅发现？** SCI零动作exact gate通过；O/R/OR在两次fresh科学父进程的全部归档trace精确复现结果为[{'tag': 'O', 'exact': True}, {'tag': 'R', 'exact': True}, {'tag': 'OR', 'exact': True}, {'tag': 'R_RETURN_fork', 'exact': True}, {'tag': 'B0_RETURN_fork', 'exact': True}]。这些仍是相同已暴露setup的数值复现，不增加独立Human/条件分母。选中方案=None；保留条件验证0/0，状态NOT_RUN_DISCOVERY_GATE_FAILED。本轮没有host冷启动新验证，旧host0/2 FAIL仍保留，不能把科学层收益升级为host VALIDATED。

9. **主要瓶颈是什么？** 旧大幅表面收益的可归因性瓶颈为启动混杂；本轮合法SCI匹配后可直接测小幅force作用和运动权衡。有限O/R/OR覆盖与当前执行时钟差异仍未穷尽。Frozen M2的较大力收益必须与knee burden/剂量同时评估，不能宣称原生协调空间无解或把候选不足归因于网络容量。科学R的实际非零次数与旧host0.10三次执行不同，属于跨执行合同可观察差异，未进行跨时钟性能相减。

10. **下一步扩大搜索还是先解决复现？** 主要方向：**先解决host实验可比性及执行复现**。本包已建立科学层的同状态参照和介入前negative control；下一研究应先使host cold commissioning/native时序差异可测、以固定规则检验效果转移，再扩大受运动约束的协调覆盖。这里仅给方向，不启动下一包、不训练Q、不修改B。

## Native执行与数值来源

| 配置 | 实际非零native计划 | 关联native steps | 首次物理执行s | OUT/HOLD/RETURN实际clock s |
|---|---:|---:|---:|---|
| B0 | 0 | 0 | none | 9.005000/1.020000/9.005000 |
| O | 5 | 28740 | 10.055000 | 9.005000/1.020000/9.005000 |
| R | 5 | 27260 | 20.080000 | 9.005000/1.020000/9.005000 |
| OR | 10 | 56000 | 10.055000 | 9.005000/1.020000/9.005000 |
| Frozen_M2 | 8 | 43640 | 10.055000 | 9.005000/1.020000/9.005000 |

每个请求保留proposal的固定K3/decision表、原admission/lifecycle/source timestamp、selected accepted native differential、实际positive-step receipt及对应native物理区间。科学日志不含host版command_id；原wall_physics._step按active_receipt_index增计native_steps并记录真实torque，依照唯一连续区间、torque逐字段和steps闭合重建所有native步归属。初次host schema假设失败记录保留；原执行逻辑没有修改。ACTIVATED、proposal或Q分数不单独作为执行证明。

真实hip/knee dense速度以及对native时间的gradient acceleration/jerk、excursion/累计travel/终点、所有phase shape/边界、force/moment积分/peak、tracking和clearance见MOTION_FORCE_TRADEOFFS.json与motion_series。FAST_RUNTIME_OBSERVATIONS仅报告科学epoch中的实际native-step wall profiles及原wall plan-age，原host FAST服务间隔NOT_EVALUABLE。原raw scorer wall-age FAIL、mode-aware realtime N/A均不改。

## 无效尝试、预算与保护

初次logger命名冲突发生在物理run前，保守记1 attempt。第一父运行因gate报告对bool减法报错而退出；两个完整零branch保留并只读核验PASS。第二父运行的Frozen M2缺少已冻结历史K3数据文件，child和parent退出；O/R/OR完整记录保留，但无完成B0，故不作为主要同初态pair。复制缺失的原文件并静态检查候选/Q后，只有一次有界固定重跑。参数、运动阈值、主0.5%发现增益门限和选择规则均不改。分析缺失json导入和command_id schema错误也保留旧日志/派生，不消耗新物理。

预算分配：复现/首次失败4；B0/O/R/OR完整attempt（含未完成父）8；Frozen M2参考2（含失败）；合法RETURN入口分支2，共16。若发现PASS仅剩一组独立保留条件的2次空间；若发现不PASS则0次验证，不为耗尽预算新增实验。初始未完成父没有自行伪造完整trace；部分native计算、errors/logs以及完整兄弟分支内继承的前缀原证据全部保留，见ATTEMPT_EVIDENCE_INDEX.json。

保护前后核验覆盖主Linux Git branch/HEAD/status/index/staged diff、31154个历史文件集合/字节hash以及旧B/M2/Q/E相关源码/权重/数据、复制路径迁移、完整新包清单、gzip EOF/CRC、积分重算、parent恢复hash与进程退出。Git stage/commit/push/reset/stash/branch切换0。未改变RAM/swap/power/affinity，不终止无关进程。保护结果最终以PACKAGE_VERIFICATION.json为准；文件完整性PASS不等于科学/实时资格。

Canonical Linux目录：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1/`。Windows完整review副本：`C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_matched_bidirectional_exploration_v1/`。执行Python为用户指定路径，源码版本、具体commands、clock/denominator、哈希和所有raw trace均保留。

![Matched scientific force and motion](MATCHED_FORCE_MOTION.png)

STOP。保护核验及进程退出后停止；无自动后续工作。
