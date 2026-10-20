# iHEAR Lab — Comprehensive Executable Coordination Search v1

终态：**SCI_VALIDATED**。唯一推荐方向：**A**。完整性核验：**PASS**。

已找到合格且可重复的协调方案，下一阶段建立正确编码的 Neural Q 训练数据；本轮不训练。

新增实际 attempt **151/160**，完整任务 trace **147**，导出 trace（含中止）**150**，搜索候选 attempt **131**，完整搜索比较 **128**，实际非零执行 attempt **143**，非零 native 计划 **534**，新增物理步 **11355960**。所有重型物理串行；原 B、commissioning、estimator、scheduler/governor、40ms bridge、100ms lifecycle、current-state admission、causal ownership、安全与 fallback 保持原合同。本轮没有 Q/Neural Q 训练、online adaptation、host-clock 资格试验或新 Human。

| 代表 | 候选 | 完整 J_F 收益 | motion | 最大 raw 负担比 |
|---|---|---:|---|---:|
| lowest_J_F | C2_pair_1_2 | 15.090469% | FAIL | 2.270844 |
| smoothest | C4_2_0 | -0.080765% | FAIL | 0.999575 |
| best_eligible | C4_1_5 | 0.738762% | PASS | 1.080182 |

主方案 `C4_1_5`：只在 RETURN 的第3个既有 issued interior slot（index=2）提案，其余 slot 为原 B 零残差，HOLD/terminal 仍由 B 拥有。设当前因果参考公共进度为 s、r=1−s，PWL 结点为 `(0,0)、(s+0.1r,0)、(s+0.145r,−0.035)、(s+0.55r,−0.021)、(s+0.955r,−0.007)、(1,0)`。值的单位是归一化阶段进度，不是角度或 torque。native 在原 B nominal target 的公共进度 m 处采样，并执行反对称 `[delta,−delta]` 分配；RETURN 的负 delta 对应 knee 在阶段方向领先、hip 延后。

发现 trace 的实际 delta 为 `-0.029054927948`；唯一非零 native 计划关联 `4520` 个物理步，首次实际执行 physics t=`23.005000s`。完整任务收益包含其后全部原生续跑、carry/fallback，而非仅此窗口。完整参数与执行证据见 MAIN_COORDINATION_SOLUTION.json。

主发现门限固定为 ≥0.5% J_F 改善。沿用 10% 速度/加速度 max、p95、RMS 及 jerk p95/RMS 非劣、0.5° excursion/endpoint/phase boundary、累计角位移±5%、全任务及每阶段时长±0.1s、moment integral≤25%、tracking RMS 增量≤0.5°及 peak≤5%补偿；原绝对安全与 clearance 必须 PASS。jerk max 仍测量，但按原冻结协议仅作诊断。0/5/10/25%敏感性仅作诊断，未替代主资格。phase-shape 单独保留；moment 是力矩。

匹配冻结 M2 的 J_F 收益为 7.716337%，motion=FAIL；失败项：velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion, moment_integral_Nm_s, tracking。其 knee p95 velocity/acceleration/jerk 比为 1.650069/2.133304/1.191462。

当前主要代表 C4_1_5 的最大 phase-shape 差为 7.565056°。该指标不自动作为安全/运动失败，但表明任务运动的时间分布改变；研究接受 PASS 不等于临床舒适或治疗轨迹等效。

| 代表 / 阶段 | J_F 减少 N·s（负数表示变差） |
|---|---:|
| lowest_J_F / OUTBOUND | 39.624318034 |
| lowest_J_F / HOLD | 0.000120357 |
| lowest_J_F / RETURN | 177.469082030 |
| smoothest / OUTBOUND | -1.956866708 |
| smoothest / HOLD | 0.000017950 |
| smoothest / RETURN | 0.794954769 |
| best_eligible / OUTBOUND | -0.000000000 |
| best_eligible / HOLD | -0.000000000 |
| best_eligible / RETURN | 10.627925502 |

| 保留条件 / 冻结候选 | J_F 收益 | motion | 失败项 |
|---|---:|---|---|
| H1_C4_1_5 | 0.746213% | PASS | none |
| H2_C4_1_5 | 0.737962% | PASS | none |
| H1_C4_1_4 | 0.577948% | PASS | none |
| H2_C4_1_4 | 0.571558% | PASS | none |
| H1_C4_0_5 | 0.684513% | PASS | none |
| H2_C4_0_5 | 0.676945% | PASS | none |

## 搜索覆盖与资格

实际阶段计数：{"C1": 48, "REFERENCE": 3, "C2": 32, "C3": 24, "C4": 24}。运动接受候选 29，同时达到发现资格 4。全部候选参数、实际分母、未执行/失败及 motion 失败项见 CANDIDATE_CATALOG.json、ATTEMPTS.jsonl、RESULTS.jsonl 和 SEARCH_SUMMARY.json。每个维度的不同参数值及测试候选数量见 SEARCH_SUMMARY.json 的 coverage；所有数值来自实际原生物理，而非 Q 预测。

| 搜索维度 | 已测候选数 | 不同参数值/组合数 |
|---|---:|---:|
| phase | 128 | 2 |
| sign | 128 | 2 |
| amplitude | 128 | 26 |
| slot_mask | 128 | 10 |
| remaining_progress_onset | 128 | 3 |
| remaining_progress_support | 128 | 5 |
| PWL_knot_locations | 128 | 7 |
| PWL_shape | 128 | 5 |
| joint_phase_independent_parameters | 40 | 40 |
| within_phase_slot_combination | 128 | 16 |

接口审计区分固定 K3 库、连续 K3、raw v2、admission 与实际执行。raw v2 在每次原生目标请求处采样 PWL 图的一个值；改变图形并不授予持续时间或速度/加速度控制。非零执行通过 accepted metadata、activation、positive-step receipt 与逐 native torque/step ownership 核验。PROPOSED/ADMITTED/ACTIVATED 不代替 EXECUTED。raw 新图经相同原生接口，未直接施加隐藏 torque。

## 十二项研究判断

1. 本轮探索阶段、符号、幅度、slot mask、起始/持续进度、PWL结点/形状、独立双阶段参数及阶段内多slot组合。详见 ACTION_SPACE_MAP 和 coverage。
2. 每个维度测试数量在 SEARCH_SUMMARY.json 单独列出；重复 fork 是相同父条件的候选比较，不视作多个 Human。
3. 未覆盖任意 PWL 图、完整连续30维空间、额外 Human 和 host-clock；本轮有限采样不构成全局穷尽或数学最优。
4. 合格发现数为 4；代表方案及实际 J_F、运动失败或接受见上表与 FORCE_MOTION_PARETO.json。
5. OUTBOUND/HOLD/RETURN 各自收益按完整积分精确分区，见 PHASE_ATTRIBUTION.json。RETURN-only 介入前 exact negative controls 保留，不能把早于残差的差异归因于 RETURN。
6. 双阶段与原单阶段来源的交互项按 G_OR−G_O−G_R 逐组合计算；完整父状态 hash 是否同一逐项标记。机械恢复前后的父状态命名/时钟上下文不同，即使零动作物理复现精确一致，跨父项仍只记描述性 contrast；不宣称同完整状态的 factorial 因果效应。O 改变 RETURN入口时不冒充 RETURN独立效应。独立 RETURN入口诊断另存。
7. 振幅与 force/加速度的 profile 内描述性关系见 parameter_diagnostics；形状、slot和幅度作用混合，相关性不升级为独立因果效应。
8. 两个保留 prefix 条件结果见 VALIDATION_RESULTS.json；不按验证表现重选参数，不声称已识别状态最优策略。
9. 独立验证状态为 SCI_VALIDATED。保留条件属于既有 Human 的有限合法扰动，不是人口泛化。若发现失败则正式成功验证不运行。
10. 固定候选库稀疏是覆盖限制；是否构成主要性能瓶颈由本轮实际结果限定，不能凭有限未成功搜索证明现接口无解。
11. 完整参数、原生执行链、真实密集 motion与force标签及Pareto区域可作未来数据来源；失败、未执行和零残差必须带资格标签，不能伪造成功训练标签。raw_v2 日志的旧 K3 action/previous=[0,0,0] 是记录占位符，实际动作必须从 graph/registered_spec 和 native metadata读取；未来需重新编码 raw PWL plan/history，不可直接把占位符送入旧120D Neural Q。TRAINING_SOURCE_INDEX.json 列出来源与限制。本轮不训练。
12. 唯一建议方向 A，依据当前发现/验证状态；本轮停止后不扩大空间、不修改接口、不自动启动下一包。

## 复现、隔离、资源与退出

复现证据见 OUTBOUND_FORK_GATE.json、RETURN_FORK_GATE.json、PARENT_VS_CHILD_GATE.json 和每次完整 state manifest/parent check。Linux 完整地址空间 fork 保留 MuJoCo integration、控制器、commissioning、reference、lifecycle、RNG和 native handles；hash仅核验，不用于状态恢复。发现父条件与 H1/H2 验证条件隔离，候选冻结文件有时间和SHA256。SCIENTIFIC_MATCHED_EXECUTION 不等同 HOST_CLOCK_EXECUTION；后者 NOT_EVALUABLE。

本轮有一次搜索包装缺陷：原 fork 对 TASK_VALID=false 抛断言，父包装未区分任务失败与绝对安全/实际写入 ownership 失败，导致第一父进程退出。C1_020 的 +0.12 OUTBOUND flat 发生 NO_FEASIBLE_WAYPOINT；完整任务失败，原绝对安全条件与实际 receipt/native ownership 均 PASS。原失败、首父 partial compute 和代码版本保留。新增恢复注册只修正包装层的失败分类，并在同 case/seed/物理条件的新父进程上要求双零 child 精确复现及旧/新零动作全 trace/native/receipt/积分精确相等；未修改科学 fork、候选边界、阈值或测试条件，未重跑失败候选。每个原生任务失败保留未完成指标并排除完整 J_F 排名；安全/ownership FAIL 或连续3个候选任务失败仍按协议停止。额外恢复 attempt 全部计入160总预算。详见 IMPLEMENTATION_RECOVERY_REGISTRATION.json、FRESH_PARENT_COMPARABILITY_GATE.json、TASK_FAILURES.json 和 code_history。

验证前还修正了两项包装记账：冻结 M2 继承已执行共享 prefix 的 count/history，不重复 prefix；实际新残差计数排除 fork 前继承计划。代表选择的多样性项按原协议绑定实际 slot mask、shape、knots/support，而非 C4 缺失的 phase 简写。修正发生在任何保留条件运行前，未修改候选参数或资格阈值；初始选择与最终冻结均保留，见 SELECTION_BOOKKEEPING_REPAIR.json、FROZEN_SELECTION_INITIAL_IMPLEMENTATION.json、FROZEN_SELECTION.json。

截至汇总 wall 4.415 h；保留原始证据 5.814 GiB，包总量 7.130 GiB；监测 D 最少空闲 117.86 GiB，Linux available 最少 5.99 GiB。每5次 dispatch 及父退出采样，非持续系统峰值监测。joined child CPU 与RSS计数见 RESOURCE_AND_STORAGE_AUDIT.json。没有新建Windows全量副本、没有删除历史文件或本轮证据。

主 Git branch/HEAD/status/index/staged diff 精确保护；历史 file size/mtime 全清单及源码、权重、报告、关键证据字节hash保护，覆盖范围与差异完整列于 PACKAGE_VERIFICATION.json。未将全历史 metadata 检查误称为全部大trace字节重hash。复制B源码/fork仅路径迁移核验。完整任务和阶段 J_F/moment积分闭合、所有 fork child JOIN、研究 worker退出见核验文件。

Canonical：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1`。STOP。


实际工作量计数从每次 fork 后的 DATA 记录核验，排除归档 trace 中继承的完整前缀：11355960 个新增 native steps（2838.9900000000002 s 新增模拟物理时间）。早期 ID.json 保存先于 finish 的前缀扣除，已修正汇总；原 J_F、motion、任务与验证结果未改变。逐attempt完整/继承/新计算步数见 ACTUAL_PHYSICAL_WORK_ACCOUNTING.json。

![Force–motion search](FORCE_MOTION_SEARCH.png)
