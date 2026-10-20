# iHEAR Lab — Physical Sensitivity, Adaptive Waypoint Density & Bounded Continuous Coordination v1

## 结论

新增自由度确实可以进入完整物理执行并改变实际 Human motion；它提供的是可追踪、可重复、端点与总时长不变的局部形状控制能力。本轮没有找到优于旧 18D 开发结果 1400.697221 N·s 的完整合格运动，也没有证明“更多 waypoint → 更平顺 → 更低累计 cuff force”。

本轮合格数值 force 最低为 **development_D1_coupled_inverse / 1438.613358554 N·s**，相对 B 差值为 **0.000139914 N·s**，即 **0.00000973%**。这种量级只报告为本状态下确定性数值敏感性，不能包装成新的有效降力里程碑。

合格组中最小 combined jerk RMS 是 development_adaptive_D2（B 的 0.999905）；最小 combined velocity TV 是 development_D1_knee_neg（B 的 0.999825）。这些是不同的 motion 指标，不能合并成一个未定义的“舒适度”。

**+0.05° 的远期 motion FAIL 已重复。** 两次新运行的实际 native body/torque/contact、原控制 trace 和 receipt 控制字段完全相同；它是可重复的完整闭环敏感性，内部 downstream 机制仍未被因果分解。

## 本轮做了什么

先读取 B、旧 18D、+0.02°、+0.05° 的存档 raw/native/receipt；不为诊断重跑物理。随后在全新 Side Study 复制闭包内扩展 reference 构造器，保留原 full-path/current-state certificate、原 40 ms bridge、100 ms lifecycle、FAST/native ownership 与 task/safety/motion 门。

构造器允许 D1/D2/D3 的 1/2/3 个内部位置点，每个 hip/knee 位置扰动不超过 ±0.05°。D1=2 段，D2=3 段，D3=4 段；legacy +0.02/+0.05 已有三个分割 knot，但只扰动其中一个，因此不能将其误称为三个独立调优点的实证。新增点不是新增 planner 请求，physics 仍为 0.25 ms。

**搜索范围限制：** 本轮新物理干预围绕B的一个既有OUTBOUND suffix展开；旧18D仅作存档物理对照，未在旧18D参数上叠加新waypoint优化，也没有覆盖所有phase/placement/amplitude。因而“未找到低于旧18D的结果”不是新接口的全局收益上限证明。后续若在旧18D上研究新自由度，必须先处理其历史跨状态motion失败并另设冻结预算。

测试 30 项继承合同测试和 12 项 density/C2/identity/非法输入测试通过。只有构造器发生语义改动；证书函数 AST 相同，motion protocol 字节相同；其余代码的绝对路径迁移另有清单。

物理 START 总分母 **20**：包含一个 cold parent、所有 fork、重复以及失败。候选记录 19 条，完整 19 条，其中 motion PASS 17、motion FAIL 2，异常/partial 0。完整 task 与 absolute safety、tracking、moment、force、causal receipt 均按原 evaluator 保存；motion FAIL 仍保留完整结果但不进入合格 force ranking。START/END 对账见 ATTEMPT_ACCOUNTING.json。

开发 seed=2026101303，全部 candidate 从同一完整活父状态 fork；没有直接设置 Human qpos/qvel、没有物理 replay。父状态 hash 检查和父/零分支 B 等价门单独保存。deterministic repeat 不等于新的合法 state 验证。

## Force-time 与 motion-time

B 完整 J_F=1438.613498467 N·s；旧18D=1400.697221153 N·s。原 objective 仍是 5 ms cuff-force norm 的完整 TASK 左积分。0.25 ms native logs 只有 q/dq/torque/contact 等，不能声称已经获得 0.25 ms cuff-force；本轮没有插值伪造该数据。

| phase | B J_F | 旧18D J_F | B−18D |
|---|---:|---:|---:|
| OUTBOUND | 725.825779 | 707.100520 | 18.725259 |
| HOLD | 54.394339 | 54.394333 | 0.000006 |
| RETURN | 658.393380 | 639.202368 | 19.191012 |

旧18D 最大0.5 s local benefit 位于 15.5–16.0 s，约 5.691310 N·s。它的收益分布和新小幅局部扰动的极小差异不能混同。

+0.05°相对B的局部正差积分为 0.05396186 N·s，负差积分为 -0.05540804 N·s，绝对差面积为 0.10936990 N·s，净J_F差仅 -0.00144618 N·s。新增自由度可以重新分布局部负荷；局部正负抵消说明完整累计量与瞬时负荷/运动质量都需要保存，不能从净量几乎不变推断物理运动没有改变。

所有 velocity TV、acceleration、jerk 都来自实际 Human dq 的未滤波 0.25 ms 导数。TV_v=sum ||Δdq||，speed TV=sum |Δ||dq|||；二者不等于关节空间几何 curvature。jerk p95/RMS/max、jerk energy、每个 joint 和 combined 结果在 JSON 中保留。

| B window Pearson r | 0.5 s 全任务 | 1 s 全任务 | 0.5 s OUTBOUND | 0.5 s RETURN |
|---|---:|---:|---:|---:|
| speed_variation | -0.005 | 0.013 | 0.020 | -0.137 |
| velocity_TV | 0.277 | 0.331 | 0.334 | 0.052 |
| acceleration_RMS | 0.217 | 0.249 | 0.209 | 0.056 |
| acceleration_variation | 0.465 | 0.578 | 0.456 | 0.233 |
| jerk_RMS | 0.345 | 0.506 | 0.345 | 0.112 |
| curvature_TV | -0.210 | -0.287 | -0.328 | 0.170 |

这些是同一确定性时间序列内的局部描述，不是跨 candidate 的 J_F 预测模型。0.5/1 s、phase、lag、epsilon 的敏感性均保存。HOLD 时长太短，独立完整 window 数不足，相关系数为 null 而非0。

在所列变化指标中，acceleration variation 的全任务窗口关联较高，jerk RMS 次之；在 phase 内排序、强度和符号并不稳定。speed variation 与 curvature variation 不能成为本轮 force surrogate。即便部分窗口相符，也仅 consistent with the hypothesis，不能写 smoothness causes lower force。

曲率用 hip/knee 等权 radian 平面中的 det(dq,ddq)/(||dq||²+eps²)^(3/2)，eps=1e-3 rad/s，另报1e-4/1e-2；raw curvature 只在速度>eps的相邻有效样本中统计。原地/低速对曲率诊断可有很大影响。它不是临床舒适度指标。

## 物理敏感性与 density

| Candidate | 内部点数 | family | J_F (N·s) | B−J_F (N·s) | motion | TV_v / B | jerk RMS / B |
|---|---:|---|---:|---:|---|---:|---:|
| B0 | 0 | B | 1438.613498467 | 0.000000000 | PASS | 1.000000 | 1.000000 |
| legacy002 | 3 | P | 1438.613737555 | -0.000239087 | PASS | 1.000069 | 0.999964 |
| legacy005 | 3 | P | 1438.612052286 | 0.001446181 | FAIL | 1.000306 | 1.126434 |
| legacy005_repeat | 3 | P | 1438.612052286 | 0.001446181 | FAIL | 1.000306 | 1.126434 |
| D1_knee_pos | 1 | P | 1438.613436156 | 0.000062311 | PASS | 1.000178 | 1.000000 |
| D1_knee_neg | 1 | P | 1438.613557388 | -0.000058921 | PASS | 0.999825 | 1.000002 |
| D1_hip_pos | 1 | P | 1438.613555366 | -0.000056899 | PASS | 1.000048 | 1.000005 |
| D1_hip_neg | 1 | P | 1438.613426120 | 0.000072347 | PASS | 0.999957 | 0.999997 |
| D1_coupled | 1 | P | 1438.613609029 | -0.000110561 | PASS | 0.999873 | 1.000007 |
| D1_coupled_inverse | 1 | P | 1438.613358554 | 0.000139914 | PASS | 1.000136 | 0.999997 |
| D2_knee_uniform | 2 | P | 1438.616075919 | -0.002577451 | PASS | 1.000218 | 1.000017 |
| D2_knee_alternating | 2 | P | 1438.620799334 | -0.007300866 | PASS | 1.000631 | 1.000131 |
| D3_knee_uniform | 3 | P | 1438.620598050 | -0.007099583 | PASS | 1.000183 | 1.000005 |
| D3_knee_alternating | 3 | P | 1438.620138600 | -0.006640132 | PASS | 1.000131 | 1.000133 |
| adaptive_D2 | 2 | P | 1438.618970175 | -0.005471707 | PASS | 0.999915 | 0.999905 |
| S_fixed_knots_early | 1 | S_PROXY | 1438.613541287 | -0.000042820 | PASS | 1.000125 | 1.000002 |
| S_fixed_knots_late | 1 | S_PROXY | 1438.613438256 | 0.000060211 | PASS | 0.999878 | 0.999998 |
| PS_early | 1 | P+S_PROXY | 1438.613623026 | -0.000124558 | PASS | 0.999999 | 1.000010 |
| selected_repeat | 1 | P | 1438.613358554 | 0.000139914 | PASS | 1.000136 | 0.999997 |

密度分组统计见 DENSITY_SUMMARY.json。不同 arrangement 的物理 Human response、robot torque、force/moment 和 issued reference 最大差异见 NATIVE_PROVENANCE_AUDIT.json；全任务响应向量的 SVD 仅是有限扰动输出多样性诊断，不能宣称系统形式上的 controllability rank。

多点相对单点增加了局部 q 值的独立设置与支持区间布局能力；真正的可用性还必须由当前 geometry/mechanics/ROM/v/a、task、motion 和 receipt 决定。D3 不是天然优于 D1，较密布局与不同正负点值同时改变了扰动的支持与局部曲率。当前 sparse sweep 不能识别普适的 diminishing-return 点，也不能把 density 与形状混杂的效应写成纯密度因果结论。

## Adaptive refinement 原型

从存档 B 在已打通 suffix 内的 force accumulation×actual velocity TV 选择局部区间：2.5–3.0 s，并把插入位置约束到可用 suffix 内部 fraction=0.75。adaptive_D2 保留 .5 点并新增 .75 点，做小幅 knee shape 评价。完整规则和原始窗口值见 ADAPTIVE_REFINEMENT_PLAN.json。

这是离线研究原型，使用实际运动诊断来设计下一次实验；运行时只向原 causal planner 提供注册参数，没有 native Human truth 输入。仅当 full task/safety/motion/receipt PASS、J_F降低、velocity TV无>1%恶化时，允许进入重复/进一步局部研究；本轮没有将它部署为在线 adaptive planner。

## Timing / speed

实际建立 P、S_PROXY、P+S_PROXY 三族。S_PROXY 保留全部 waypoint q 和总 suffix duration，内部时间移动 ±0.635 ms；共享内部 v/a 使 C2 保持，但点间 Hermite 几何路径可能变化。2001点 path Hausdorff 距离另存，不把有限采样距离当连续几何证书。

独立数学检查构造 exact fixed-path timewarp u+0.01u³(1−u)³，保持整个 suffix 端点 q/dq/ddq、总时长和几何路径。与原 quintic 复合后为 degree30，原 2×6 coefficient certificate 明确拒绝 INVALID_MULTISEGMENT_COEFFICIENTS。未借用旧证书、未物理执行这条未认证曲线。因此“纯 spatial 与纯 temporal 哪个更有效”仍未被完全解耦回答。

匹配 P/S_PROXY/P+S_PROXY 的 force gain interaction 为 2.8823068760175374e-05 N·s；三者 motion 全通过=True。一次状态、小幅 proxy 的交互不足以证明稳定 synergy。

## +0.05° 远期异常

- development_legacy005: hip acceleration peak 在 task 5.87000 s / absolute physics 15.92000 s，106.58802 deg/s²；最后 multisegment receipt 后 2.93500 s；附近 5 ms robot torque 最大变化范数 11.77447 N·m。
- development_legacy005_repeat: hip acceleration peak 在 task 5.87000 s / absolute physics 15.92000 s，106.58802 deg/s²；最后 multisegment receipt 后 2.93500 s；附近 5 ms robot torque 最大变化范数 11.77447 N·m。

ANOMALY_REPEAT_GATE 对比全部116320条 native 记录、5817个 receipts及原trace，结果 PASS。局部 reference 的边界 C2 和当前证书通过并不能保证远期 actual Human derivative burden 通过。torque transient 与 acceleration/jerk 峰的共现已保留；没有通过修改 controller gain/contact或 replay Human state来构造机制归因。

进一步核对了原 torque-component 定义，并验证 base+position+velocity+allocator+clipping 与实际command在异常窗口内的加和闭合。相对B的局部最大差异范数：allocator 9.557835 N·m，velocity 1.989566 N·m，position 0.237547 N·m，base 0.013214 N·m，clipping=0。allocator是最大的已观测贡献差异，但这仍不是allocator单独致因的证明；state/geometry/feedback/replan共同演化，机制尚未充分分离。最近一次plan activation提前约0.28 s，也不能把峰值直接解释成节点接续跳变。

## 冻结与验证

本轮无新方案低于1400.697221 N·s，因此未触发新的 frozen primary paired validation；VALIDATION_RESULTS.json 明确为 NOT_TRIGGERED。不能用同父状态重复代替新的合法状态或跨患者验证。旧18D 2.635613% development finding 和历史新状态 motion 0/4 保留原资格，没有按本轮数据重新选择它。

FROZEN_SELECTION 保留精确数值可行最小值，并另列仅用于呈现的0.01 N·s近似 tie-band motion对照；后者不是新primary、不是事后改变原motion门、也不进入验证重选。没有大规模COBYLA：本轮信号不足以支持把更多预算用于微小force差异追逐。

## 必须回答的11个问题

1. **density是否增加physical controllability？** 增加了可执行的内部形状配置能力，且 actual Human motion随之改变；这不等于严格控制理论意义的可控性证明。
2. **单点与多点区别？** 多点可在同一外部端点/总duration下分别设置局部位置、相位支持和相邻形状；原生physics/请求频率未增。
3. **多少点开始 diminishing return / penalty？** 当前D1–D3仅有限布局，结果和逐例motion门已给出；不足以冻结普适最优密度或临界点。
4. **force是否集中在motion variation大的区间？** 部分对应，整体与phase内均不是稳定一致；完整window积分、top-quartile force share及lag保留。
5. **哪个指标最相关？** 当前全任务窗口 acceleration variation较高；jerk、速度TV和曲率排序随phase/window改变，没有稳定胜出的force surrogate。
6. **spatial还是temporal更有效？** 物理P与timing proxy已比较；exact path/time分离受当前证书表示限制，纯效果仍unresolved。
7. **有明显synergy？** 保存了配对交互数值；未证明可重复、可泛化的明显synergy。
8. **+0.05° anomaly可重复？** 是，新的同父状态两次完整执行复现motion FAIL与相同native/control记录。
9. **有比1400.697221更好的完整合格运动？** 没有。本轮数值最小为1438.613358554 N·s。
10. **新合法state仍成立？** 没有新record触发验证，不能回答成立；当前新能力只在同一Human、同一开发父状态验证。
11. **下一步？** 优先解决 physical robustness：以+0.05°可重复远期响应为靶点，在新的合法prefix状态中辨别shape/timing/下游tracking敏感性，再决定是否构建精确speed模块。暂不进入few-repetition learning。

## 资格与边界

完整新执行属于 **PHYSICAL_LEVEL1 / development**。分段C2、identity/证书测试与exact timewarp是 mathematical/interface evidence；force-motion相关、epsilon和局部窗口统计是 correlational。没有LEVEL2、host LEVEL3、硬实时、跨患者、真机或临床结果。原host plan_age/strict资格失败仍原样保留；科学模拟使用原有mode-aware时钟，不能把它当host验收通过。

正式B、Human/robot dynamics、cuff/contact、gravity、actuator、ROM、task goal、HOLD、安全阈值、motion阈值、truth firewall、bridge/lifecycle/native ownership均未修改。未训练RL/Q/Neural Q；未推送、合并、提交或自动开始下一包。

起始主仓库分支 codex/expert-strength-value-adequacy-v1，HEAD 8bb04662b1578b72c097f546be9e836167e280e8。原有dirty/untracked状态按字节文本保存并复核，没有新建/切换分支。关键命令、环境、源码SHA、raw来源、START/END、参数及issued/applied/native证据见REPRODUCTION、EXECUTION_CODE_MANIFEST及audit。

**STOP。** 本轮预先冻结的有限敏感性组与合格重复已经结束，新增可执行shape自由度和可重复远期motion penalty已有证据；没有稳定的新force优化区域，停止扩大搜索，不宣称排除了所有合法trajectory。下一包只提出建议，不自动执行。
