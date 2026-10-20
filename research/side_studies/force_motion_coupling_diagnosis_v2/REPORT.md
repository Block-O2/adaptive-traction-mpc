# iHEAR Lab — Force–Motion Coupling Diagnosis + Bounded Continuous Coordination v2

**决定：情况 D，停止扩大 waypoint/speed 搜索；纯 temporal 接口另保留情况 E 限制。** 当前资料支持局部 force–motion 瞬态共现，未支持跨 phase、跨尺度稳定的“motion variation 提前上升 → force 上升 → 累计力增加”关系，也未证明“让运动更平滑能够降低累计 cuff force”。本轮新 physical START=0，没有新候选或新资格升级，正式 B 不变。报告日期：2026-10-17（Asia/Shanghai）。

## 直接回答八个问题

1. **力主要累积在哪里？** B 的 OUTBOUND/HOLD/RETURN 分别为 725.825779/54.394339/658.393380 N·s，约 50.45%/3.78%/45.76%。最高 0.5 s 窗是 task 1.5–2.0 s（absolute 11.55–12.05 s），56.127576 N·s，平均 112.255 N；1.0–2.5 s 都是高负荷。RETURN 的最高窗是 15.0–15.5 s，46.540062 N·s。B 的瞬时峰值为 115.479119 N，在 task 1.935 s。累计 25%/50%/75% 的时刻为 3.544/8.883/14.627 s；负荷分布在宽时间段，并非由一个导数尖峰主导。
2. **对应明显 motion variation 吗？** 部分区间对应，整体不稳定。50 ms 窗中，B 的最高四分位 velocity TV 仅承担 OUT/RETURN 的 26.27%/25.29% force 积分；18D 为 24.43%/23.93%。高 acceleration variation 的四分位窗口约承担 27–28%，存在温和富集，远非主要累计负荷的集中解释。HOLD 几乎静止仍累积 54.394 N·s。零滞后、最佳滞后及相关符号均依赖 phase、窗口和去趋势处理。
3. **+0.05° anomaly 与 force 有时间对应吗？** 有局部对应：task 5.870 s / absolute 15.920 s 的 hip acceleration=106.588°/s²，B 同时刻为 29.480°/s²；最大 force 差同在该 5 ms 采样点，为 +3.013366 N。jerk 峰在 5.8655 s，较 force 采样间隔还短的先后差不能支持可靠因果排序。5.82–5.92 s 净力差 +0.000895 N·s，但 5.8–6.0 s 为 −0.002985 N·s：局部增量与减量抵消。全程净差 −0.001446 N·s，正/负差面积为 +0.053962/−0.055408 N·s，force RMS 略升。它不是全任务主要高力窗口；motion FAIL 不能因净力稍低被接受。两次存档重复的 native-derived motion、force、reference、command 精确一致。
4. **旧18D收益来自哪里？** 总收益 37.916277314 N·s（2.635613%），OUT/RETURN 各 18.725259/19.191012，HOLD 几乎零。4–6 s 为 10.099746、15–16 s 为 9.996502 N·s；合计 20.096248，占净收益 53.00%。最大半秒窗 15.5–16.0 s 为 5.691310；前三个半秒窗占净收益 34.29%，前五个占 48.32%。收益有局部集中，也有分布式贡献。15.0–15.5 s 降力 4.305193 N·s，同时 velocity TV 增加 0.002816 rad/s、acceleration variation 增加 3.287643 rad/s²；5.5–6.0 s 也同时降力而两项 variation 上升。不能将全部收益归于平顺性。
5. **spatial 与 temporal 哪个值得继续？** 暂无证据支持继续二者的 force 搜索或确定胜者。已合法执行的 spatial shape 可作为后续 robustness 归因的受控微扰；优先问题是 tracking/allocator/replan。S_PROXY 仅保留 waypoint q 与总时长，点间 Hermite 路径会改变，不能当纯 speed 实验。旧 exact fixed-path timewarp 为 degree30，超出现有 2×6 quintic 证书表示；本轮仅复用该接口限制证据，没有绕过证书或新增 timewarp physics。
6. **已有“平滑能降低累计力”的证据吗？** 18D 同时较低 J_F 和 combined TV_v，是 **CONSISTENT-WITH-HYPOTHESIS** 的一个开发状态观察；combined TV_v 下降 10.597%、acceleration variation 下降 0.544%、combined jerk RMS 下降 0.475%，但 hip jerk RMS 上升 7.40%、hip jerk max 上升 20.69%、knee tracking RMS 变差，moment 积分上升 7.03%。历史 S_late、D1_hip_neg 的微小同向变化也保留，但不能从中推导稳定因果机制。当前“稳定、可操作的通用 force–smoothness 关系”标记 **NOT-SUPPORTED**；平滑干预的因果效果仍 **UNRESOLVED**。
7. **有没有新的完整 PASS 且优于 B 的候选？** 没有，本轮未启动新物理。已知 18D 开发 PASS 与历史合法小扰动没有重新命名为新发现。历史 D1_coupled_inverse/repeat=1438.613358554，比 B 低 0.000139914 N·s，但 velocity TV 上升；D1_hip_neg、S_late 的更小收益也不是本轮新重复或新 state 验证。旧18D的合法新 prefix motion 0/4、原 host plan_age FAIL 原样保留。
8. **下一步研究哪里？** 先对可重复异常做 tracking response、allocator wrench→robot torque 映射和 request/activation/splice 时序的归因；检查 18D 收益窗口的姿态、跟踪误差、moment 与 allocation 分配。存档 anomaly 附近 allocator/velocity/position/base 的最大差范数约 9.558/1.990/0.238/0.013 Nm，clipping=0；加和闭合，最大贡献不等于单独致因。最近 activation/splice 在峰前约 0.280/0.235 s，不是节点瞬间跳变。任何下一轮 physics 必须另立冻结配对合同，从合法完整父状态 fork，保留全部既有门；本包不自动执行。

## 时间、采样与指标合同

20 条完整存档：最新研究的19个 arm（含 B、+0.02、两次+0.05、D1/D2/D3、adaptive、S_PROXY、P+S_PROXY、selected repeat），加冻结18D。各自独立确认 TASK 起点 absolute=10.05 s，终点29.08 s。绝对时间与 task elapsed 的映射仅作坐标变换，不作 phase 归一化或峰值对齐。

| phase | duration s | B J_F N·s | 18D J_F N·s | B−18D N·s |
|---|---:|---:|---:|---:|
| OUTBOUND | 9.005 | 725.825779 | 707.100520 | 18.725259 |
| HOLD | 1.020 | 54.394339 | 54.394333 | 0.000006 |
| RETURN | 9.005 | 658.393380 | 639.202368 | 19.191012 |

| case | J_F N·s | peak N | RMS N | TV_v/B | TV_a/B | combined jerk RMS/B | motion |
|---|---:|---:|---:|---:|---:|---:|---|
| B0 | 1438.613498467 | 115.479119 | 77.684410 | 1.000000 | 1.000000 | 1.000000 | development PASS |
| 18D | 1400.697221153 | 113.876625 | 75.652656 | 0.894030 | 0.994565 | 0.995246 | development PASS |
| legacy002 | 1438.613737555 | 115.479119 | 77.684505 | 1.000069 | 0.999770 | 0.999964 | development PASS |
| legacy005 | 1438.612052286 | 115.479119 | 77.684568 | 1.000306 | 1.035347 | 1.126434 | FAIL |
| legacy005_repeat | 1438.612052286 | 115.479119 | 77.684568 | 1.000306 | 1.035347 | 1.126434 | FAIL |

force 有3807个5 ms boundary samples、3806个区间；原 J_F 为 F(t_i)·(t_(i+1)−t_i) 左积分，phase 使用真实转移时间裁剪。native motion 有76121个0.25 ms点，原始 dq 连续两次 `np.gradient(..., edge_order=2)` 得 a/jerk，未删端点。5个关键 case 全部116320 native rows、5817个正步 receipt 重新核对：Human q/dq 地址[0,1]、逐native值、唯一 receipt ownership、command torque 与步数全部一致。其余15个case复算已保存 native-derived series，并逐5 ms核对实际q/dq；没有冒称重新审核其全部native/receipt。

TV_v=Σ||Δdq||₂，acceleration variation=Σ||Δa||₂；同时保存逐关节 L1 TV，不能混作同一指标。jerk 保存逐关节和combined RMS/p95/max；不将数值导数峰称临床抖动。force RMS为按原区间加权 RMS，tracking为actual−issued reference。全部case有phase J_F、瞬时peak/RMS、trajectory deviation、tracking、torque-component差和原qualification；累计曲线在 `series/*.npz`。

## 滞后分析与科学分类

只相关 motion feature 与 instantaneous mean F、force变化，不相关单调 J_F 本身。分别在OUTBOUND/RETURN内聚合50/100/250/500/1000 ms等长窗，短尾只从相关分析中排除，完整J_F仍全部计入。motion保留raw并做21/101 native sample SG敏感性；线性去趋势、一阶差分和paired candidate−B对照分列。相关pair不跨phase。正lag表示motion领先force，范围±1 s；窗口≤1 s只允许至少8对样本，1 s结果样本很少且部分峰在范围边界，不能精确认定生理delay。

下面仅展示50 ms raw acceleration-variation rate；“peak r”取±1 s内最大绝对值，保留原正负号，未挑选最好看的正相关。

| case | phase | transform | zero-lag r | peak signed r | lag s |
|---|---|---|---:|---:|---:|
| B0 | OUTBOUND | level | +0.224 | +0.266 | +0.30 |
| B0 | OUTBOUND | linear_detrend | -0.113 | -0.283 | -0.35 |
| B0 | OUTBOUND | first_difference | -0.138 | +0.139 | -0.05 |
| B0 | RETURN | level | +0.152 | +0.219 | +1.00 |
| B0 | RETURN | linear_detrend | +0.171 | +0.256 | -0.35 |
| B0 | RETURN | first_difference | +0.119 | +0.119 | +0.00 |
| 18D | OUTBOUND | level | +0.196 | +0.228 | +0.25 |
| 18D | OUTBOUND | linear_detrend | -0.139 | -0.283 | -0.35 |
| 18D | OUTBOUND | first_difference | -0.201 | -0.201 | +0.00 |
| 18D | RETURN | level | +0.114 | +0.210 | +1.00 |
| 18D | RETURN | linear_detrend | +0.239 | +0.255 | -0.15 |
| 18D | RETURN | first_difference | +0.211 | +0.211 | +0.00 |

B/18D OUTBOUND 原水平在+0.25–0.30 s出现温和正峰，去趋势后最大峰转为负且lag变为−0.35 s；RETURN原水平峰在+1 s搜索边界，一阶差分则主要同步。velocity TV、jerk没有提供一致领先关系。部分within-phase circular-shift max-lag比较显示罕见相关，全部保留；它们有负向、force领先或同步的结果，不能选择性解释为motion领先降力机制。循环shift仅为保留序列自相关的描述性参照，短周期任务的非平稳趋势、不同指标/尺度和同一Human状态仍限制其统计含义，不提供因果p值或独立重复数。

直接以 motion level 对 force-rise（窗口均力的后向一阶差分）做lag时，也存在应保留的正证据：50 ms窗的 acceleration-variation 在B/18D OUTBOUND分别为 r=+0.417/+0.388，最大峰均在+0.10 s；RETURN为 −0.313/−0.305，同在+0.10 s。100/250 ms窗口大体保留OUT正、RETURN负的结构，但250 ms的峰lag已移到+0.25 s；500 ms结果的峰lag和18D RETURN的符号进一步变化。它提示phase-dependent时序关联，不能称“完全没有force–motion关系”，也不能作为跨phase统一降低variation即可降力的规则。paired candidate−B差值没有得到稳定同向领先关系；SG敏感性也保留在audit/SENSITIVITY_SUMMARY。这些现象优先指向phase/姿态/reference/tracking与allocator的共同驱动，独立因果机制仍UNRESOLVED。

**CORRELATIONAL：** 局部motion/force瞬态共现、宽窗acceleration variation与force的部分相关。**CONSISTENT-WITH-HYPOTHESIS：** 18D整体及部分合法微扰同时较低force与某些motion指标。**NOT-SUPPORTED：** 现有资料中的稳定同向、稳定领先、跨OUT/RETURN的通用motion→force规则；据此驱动持续waypoint/speed优化。**UNRESOLVED：** 纯temporal因果效应、allocator/tracking/replan的独立机制、跨状态可靠性。四者范围不同，不将未解决问题写成全局不可能。

## 分支与交付

Phase1不足以通过进入新物理敏感性实验的门，采用情况D。历史+0.05属于force稍低但motion明显变差的B类反例；adaptive_D2的TV_v/jerk微好而force升高，属于C类反例，acceleration variation也略升，不能称全指标motion改进。D1 inverse的微小降力伴velocity TV上升，不能作为本轮force+motion有效改进。历史D1_hip_neg/S_late的少量同向指标变化保留，force RMS及部分逐关节指标仍可能变差，也没有新的稳健Pareto区域证据。没有满足A的新候选，因此新repeat=0、新prefix验证=0。

情况E的最小缺口是：可绑定同一spatial path及独立单调clock、并对复合导数、连续geometry/offset、causal20ms约束、mechanics、stop/40ms bridge和current-state admission完整重验的reference/certificate合同。原100ms生命周期和native ownership仍须保持。已有multisegment quintic执行能力不等于已支持degree30纯timewarp；没有修改旧证书、阈值或plant。

核心图01为B/18D/+0.05，图02为B/+0.02/代表合法D1；每列相同task/absolute时间与phase边界，含actual/reference hip-knee、F、J_F、actual dq、TV_v、acceleration variation、jerk及request/activation/splice/waypoint/knot/terminal marker。planned waypoint与实际Human到达明确区分。图03为force及18D局部收益，04为anomaly，05–06为lag/trend敏感性，07为历史候选trade-off。PNG/SVG均保留。

入口：`REPRODUCTION.md`、`CANDIDATES.md`、`CANDIDATE_PARAMETERS_AND_QUALIFICATION.json`、`RAW_DERIVED_METRICS.json`、`LAG_ANALYSIS.json`、`FORCE_RISE_LAGS.json`、`PAIRED_DIFFERENCE_LAGS.json`、`ANOMALY_TIME_ALIGNMENT.json`、`SOURCE_MANIFEST.json`和`EXECUTION/ATTEMPT_ACCOUNTING.json`。原始完整trace/native/receipt保存在其原canonical包，本包以hash引用并保存关键完整receipt流和派生数组；这是显式存档依赖，Windows副本仅作审阅。

分析工程失败两次均保留：终末无command的NaN component误纳入断言；raw validator误假设Human坐标位于最后两轴。已分别按真实命令区间、存档[0,1]地址修正并逐样本验证，未改变科学参数、数值精度门或原始数据。没有训练RL/Q/MLP、Git修改命令、硬件动作或新physics。主仓库的初始Git/metadata快照与最终一致；来源SHA登记在成功恢复后重建，最终核对一致，不冒充完整T0字节快照。9个代表case有多尺度lag、7个候选有paired差值lag，20个case均有完整指标与累计曲线。主仓库的初始Git/metadata快照与最终一致；来源SHA登记在成功恢复后重建，最终核对一致，不冒充完整T0字节快照。9个代表case有多尺度lag、7个候选有paired差值lag，20个case均有完整指标与累计曲线。保护审核范围和结果见`audit/FINAL_PROTECTION.json`。**NEXT_RESEARCH_DECISION：研究tracking/allocator/replan interaction mechanism；不提出已获证据支持的bounded continuous coordination下一阶段。STOP。**

[核心共同时间轴](figures/01_core_common_timeline.png) · [force与18D局部收益](figures/03_force_and_18D_local_benefit.png) · [异常窗口](figures/04_anomaly_force_motion_torque.png) · [分phase滞后](figures/05_phase_lag_first_difference.png)
