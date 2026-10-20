# 研究时间线：问题怎样推动结构变化

日期来自可读Git checkpoint、报告时间或t0；checkpoint不是功能首次发生的精确日期，也不是实际教授会议日期。不能以seed或目录名替代日期证据。上次教授汇报边界：LAST_PROFESSOR_UPDATE_UNCONFIRMED。

## 从起点到可审核执行底座


| 可核实时间 | checkpoint/工作 | 推动问题与结构变化 | 证据边界 |
|---|---|---|---|
| 2026-06至07 | Spring2D → 2026-07-30 closeout `82e4822` | 在简化elastic rod上研究MPC/辨识/安全/信息可辨识性 | 非Human V2、非机器人执行 |
| 2026-07-30 | MATLAB intake `c3957e8` | 示意双臂脚本需区分model/controller/endpoint，并审计符号/重力一致性 | 教授原参考，非教授最近汇报证明 |
| 2026-07-30至08-16 | physical linked Human、Human V2、single-arm/load-transfer | 直接关节力矩示意转向合法endpoint force与真实物理可行性 | 早期force分支非当前active plant |
| 2026-08-23至24 | sleeve MuJoCo → rigid cuff → Stage3 UR10e | 将cuff force/moment、robot torque与coupled plant写清，固定15sreference | engineering smoke，surrogate |
| 2026-08-24至29 | Stage4 adaptive tracking、robustness | 不确定患者模型影响tracking；有效模型+causal trust+shared gates | 正式有限Human family，不等于当前B |
| 2026-09-01至08 | executable contract、High-ROM与control velocity修正 | command-safe与physical-safe不等；feedback latency是重要结构瓶颈 | 老FAIL保留；corrected仍有SAFE_INCOMPLETE |
| 2026-09-14 checkpoint `e6ea54b` | Stage5 goal torque MPC | 从whole time-reference转phase目标，暴露interface prediction/hold/handoff/motion问题 | 首complete历史motion-envelope disabled |
| 2026-09-23 checkpoint `bd7952f` | recovery V2.2+Human-waypoint V3 | directΔq有限候选、quintic、adaptive screen、causal records | Phase3接口smoke，不是fullrobot闭环 |
| 2026-09-25至29 | full3D、100ms lifecycle、40ms escape、source/ownership | planner迟到与handoff需可验证准入与合法旧command延续 | host/scientific gates各自记录 |
| 2026-10-07至08 | multi-rate、native FAST、qualification decoupling/jitter | compute与task完成/因果/FAST/R2分开；有限host执行 | 无正式deployment资格 |



# 阶段6–9研究时间线（问题驱动版）

时间全部Asia/Shanghai。未知日期不依据名称、seed或文件mtime推断。上次教授汇报边界由总稿另核，本表不是“教授已知/未知”的划分。

|时间（证据）|问题与结构转变|成果和负结果|范围|
|---|---|---|---|
|精确日期待核；early RL原报告|从scratch absolute-target SAC到teacher/DAgger与anchored训练：先获取完整任务，再保住能力|scratch300k 22evaluation全OUT失败；DAgger学生会完成但HOLD约10s；SAC20k能力丢失；anchored50k最好主要减少过长HOLD，MATCHED仍无合格|非当前native residual Q；同Human，不能跨任务时长横排J_F|
|2026-10-01 05:34:31报告生成；源LEARNING_RESEARCH_V1_REPORT.md:3|96D cost-to-go，区分NATIVE与MATCHED时长，FULL/SHORT监督|FULL ridge有限dev较好，test排名弱；连续pilot各4/8valid来自新片段，native continuity blocker|历史科学计算/拟合，非少rep成功|
|2026-10-05 17:46:24登记起点（原E报告unix1791193584.3798375）|E残差K2高预算CEM代替被用户取消的50k SAC任务|搜索92/92valid，强E5.422631%包内gain，但moment+22.18%|E_SEARCH科学benchmark，非成熟RL专家|
|精确t0待核；expert_strength原报告|K2重启与K3差分挑战；四state多步prefix|K3比旧E+.898957%；一个state一步负、full正；common-mode未跑|多步依赖诊断，未证明数学最优或K2不可表达|
|精确t0待核；native matrix源|移除P/truth、直接接冻结B；120D Q决定remaining合法K3计划|40methodSCI全valid，M2八pair平均7.177%gain，G不稳定；七host无资格|Q/M2原native接口执行，但不是formalhost|
|2026-10-08 20:59:12 t0；host attribution REPORT|真实host有限prefix复验并剥离learned排序机制|4/4gain合并6.828%；131decision固定池排序唯一；moment/knee burden变差|causalhost research，formalruntime未资格化|
|Neural报告精确t0待核；counterfactual保守t0 2026-10-08 23:51|joint32×32 challenger与dense motion审计；V_commit/恢复门|test2state regret9.9306>linear1.6207；80rows仅13snapshot/4来源；旧snapshot不可durable恢复|离线负结果；新增branch0/30，不训练v2|
|coordination_space精确t0待核|十二可执行表候选与frozenmotion验证，发现cold-start混杂|3/12发现motion接受，选4.1077%；heldseed0/2；RETURN-only OUT-53.240N·s早于介入|host研究，旧R2/strict55fail，无法归因大表面gain|
|matched bidirectional精确t0待核|活地址空间fork同完整父/RETURN入口，positive-step ownership与negative control|exact复现；O/R/OR .1197/.3305/.4502%，motionPASS但发现门FAIL|SCIENTIFIC_SIMULATION限定，OS调度没复制|
|2026-10-12 21:16:15 t0；comprehensive RUN_PLAN|扩大phase/sign/amplitude/slot/onset/support/PWL覆盖|128完整search comparison；29motion接受、4发现合格；C4 .738762%、H1/H2PASS；C2 15.090469%FAIL|SCI_VALIDATED同Human有限prefix；PWL每native请求仅采一个delta|
|2026-10-13 02:58:22 t0；lowforce REPORT|保强低力repair与原native标量reexploration|268attempt；native18 1.165570%、3/3PASS；强收益未修成motion合格；RETURN state却收敛到~4e-9rad|有限扰动验证，非多种RETURN state；整体广域31.17%未达40%|
|2026-10-13 14:17:42 t0；sequential RUN_PLAN|多次合法连续slot调整、prefix真实推进后fork|best O0+.006 1.350269%；79attempt；V1FAIL，V2best未跑|SCI_DISCOVERY_ONLY，不将suffix拼成未知全策略验证|
|2026-10-13 18:58:37 t0；free RUN_PLAN|相对delta→共同/差分进度+独立路点pass速度10D|84attempt；开发2.457489%PASS；OUT/R都降力；W1excursionFAIL/W2PASS，1/2；低力15.55%仍motionFAIL|LEVEL1扩展参考teacher，非原BLEVEL2/hostLEVEL3|

最后三项t0从已读RUN_PLAN原字段独立转换；转换和数值复核见reports/COMPACT_EVIDENCE_VERIFICATION.json。日期晚于旧索引覆盖的新包按自身REPORT/合同核查，索引不代替原证据。


## 本轮

2026-10-14约01:40读取真实时钟；01:44建立新side-study及冻结协议；随后先恢复历史与源保护，再执行串行预检查/离线探索。新增attempt、包装失败与修复均计入本轮分母，不能把历史原84次attempt加入本轮分母，也不能漏掉冷父commissioning。绝对09:30结束，07:30停止新物理派发、08:00前结束自有物理进程。精确事件时间见RUN_PLAN.json、ATTEMPTS.jsonl及PACKAGE_VERIFICATION.json。


<!-- OVERNIGHT_FINAL_START -->
## 本轮夜间探索的最终补充（2026-10-14）

本轮未训练学习器。保留原机器人、被动Human、接触和执行约束，在隔离研究中将原10维意图扩为18维：两方向的共同进度倾斜/曲率、差分进度曲率、髋膝速度倾斜。参数仍经原quintic与原筛选/准入，再由六轴robot实际执行。

同完整开发父状态，冻结最好`development_repair2_quality_NATIVE_SCALAR_18_063`下降2.635613%，全部冻结motion规则PASS；相对旧2.457489%增加0.178124个百分点。这是一项有限开发改进，不是全局最优。16个±0.4新轴probe和后续三个区域的有限COBYLA结果保留；joint optimum不能把增益简单分摊为某一自由度的贡献，详见MECHANISM_ANALYSIS.json。

冻结primary在四个预注册合法prefix条件中合格0/4、完整任务4/4。四条件都来自同一已暴露Human；仅未消费suffix被测试，共享prefix不属于未见完整原策略。失败保留且不从分母移除，secondary事先冻结而没有用测试改选primary。VALIDATION_RESULTS.json记录完整candidate身份、冻结文件hash和先后时间、配对初态及干预前物理/控制相等。

最低force代表下降16.816751%，motion FAIL，失败项['velocity_deg_s/max_abs', 'velocity_deg_s/p95_abs', 'velocity_deg_s/rms', 'acceleration_deg_s2/p95_abs', 'acceleration_deg_s2/rms', 'jerk_deg_s3/rms', 'RETURN_duration', 'excursion', 'cumulative_dose', 'task_duration', 'moment_integral_Nm_s', 'tracking']。它保留为负结果，不能称优质teacher。实际START/END=148/148，包含两次包装失败和真实commissioning，不把数学拒绝当physics。全部科学结论最多LEVEL1，未新增原B接口、host、硬件或临床资格。

与教授的关键问题仍是：允许多少中间姿态变化、怎样评价平顺与治疗剂量、何时迁移最小参考接口，以及何时才具备few-repetition学习值得使用的state/action/label证据。

<!-- OVERNIGHT_FINAL_END -->
