# iHEAR Lab 长期研究决策日志

# 2026-10-21 — Learning研究方向反思：从算法试错到物理机制驱动的学习优化

记录UTC：2026-10-21T14:26:25.990267+00:00。研究身份：learning_guided_motion_improvement_v1；固定源码起点：`1adb1de177d6f5f32de6d01c4e629cbfae9ce121`。本条为事前追加记录；后续结果只可增补注释，不回写本条假设。新包：`/home/hank/ihear-lab/learning_guided_motion_improvement_v1`。

## 背景与始终不变的目标

最初目标不是证明某种Learning算法能训练，而是在机器人辅助被动康复运动中，保证安全、完整任务和运动质量，进一步降低患者交互负担，并希望通过少数重复运动实现患者自适应改善。研究先后涉及传统MPC与协调优化，E/CEM/COBYLA及10D/18D/H150，Q与Neural Q，IL/DAgger/SAC，ILC/BO/History-conditioned Value，以及scratch PPO、H2、Reward迭代和STD探索。各阶段的患者、初态、动作权限、执行链、目标和评价合同不同，百分比不能直接横向排序。

## CONFIRMED — 可定位的直接证据

- 正式B保留估计Human状态、有限候选MPC、quintic scheduler/governor、current-state admission、FAST反馈及allocator、robot torque与真实cuff/Human动力学的因果执行链。5ms服务、0.25ms native、40ms bridge、100ms lifecycle是不同合同。
- 历史18D开发条件完整JF为1400.697221，相对该条件B的1438.613498 N·s降低2.635613%；新合法prefix原motion为0/4。后续T/H150另有有限合法状态资格与失败，不能覆盖此负结果。D01R历史H150/B为1402.643211/1436.456498 N·s，不能与前一分母混用。
- force_mechanism_waypoint_v3对已执行estimated q/requested torque进行allocator重算，得到−36.527540 N·s，对应实测−37.916277 N·s；这是事后代数机制核算，不是新轨迹事前预测准确率。不可将36.53/37.92写成96%预测准确率或已识别因果中介比例。
- 原Q结构Q(s,p)=a(s)+b(p)的公共state项在候选比较中相消；Neural Q的两个历史测试state未优于linear。动作覆盖、条件交互、V_commit/V_replan标签与数据量仍有缺口。
- History-to-next-trial报告包含有限患者上的history-enabled优于固定B和history-disabled的正证据，也明确未证明超过冻结H150、广泛患者泛化或临床收益；BO/Value只有B首轮到第二轮条件优化，不能称多轮收敛。
- 最新PPO真实完成训练120集、冻结开发24次和最终流12次。选定R1/STD_INIT_0p2在两个既有成功父、相同nominal物理初态各观察6/6；PPO稳定改善、force/moment改善均NOT_ESTABLISHED。R4未获得两父mean共同的JF/JM改善。G4、live matched、Stage2及最终Campaign仍未就绪。

## SUPPORTED — 有限实验支持

- Learning能获得任务能力，某些历史决策产生有限额外改善，传统搜索也能找到低force运动；这些是不同合同内的证据，不是统一算法排行榜。
- 姿态相关gravity与elastic需求是18D降力的重要解释；仅优化smoothness不是主要降力机制的充分解释。局部shape干预有可重复小收益，同时存在motion、moment与离散时序响应的取舍。
- 原执行门与运动资格、动作表达、数据覆盖、优化稳定性和Reward都会影响学习表现。执行成功、低force和完整合格是独立问题。

## HYPOTHESIS — 待检验解释

- 过去偏向更换算法、训练、观察结果；不同算法往往同时改变动作权限、目标与评价合同，使收益难归因。
- Learning潜力大不证明当前可行集合必有大收益；已有小收益也不证明学习存在天然上限。尚不能判断限制主要来自算法、数据、动作表示还是当前物理与约束。
- Q/Value困难可能来自动作覆盖、状态条件排序、价值目标和数据不足。PPO另涉及任务获取、策略退化、探索分布、奖励目标与真实执行不一致。
- 名义物理模型或能解释部分姿态负荷，但闭环tracking、allocator/contact响应、离散准入与motion余量可能需要学习残差。必须用执行前合法输入的验证检验，不能预设。

## DECISION — 本轮研究决策

1. 不继续单纯增加PPO episode或Reward候选。先明确物理能解释什么、接口能改变什么、哪些剩余响应值得学习，以及预测能否帮助实际优化。
2. 保留物理与受约束控制框架，以Learning补充闭环预测误差和约束余量，优化产生新的协调方案，再交给原真实物理与原安全/motion/task门验证。
3. 先做零新物理的机制/事前预测闭包诊断；分清事后重算、准静态预测与完整闭环预测。缺口按实际证据报告。
4. 在相同合法父状态、参数权限和新增物理预算下比较DIRECT_NATIVE、PHYSICS_GUIDED和LEARNING_RESIDUAL_GUIDED；逐臂隔离未公开反馈，登记历史数据优势与代理计算成本。
5. 仅完整合格运动进入正式JF收益。保留所有拒绝、partial、失败及其预算；不放宽原motion门，不按结果更换分母或强父baseline资格。
6. 学习辅助优化若没有超过传统搜索，保留负结果并分析原因；本轮不能预先宣布新方向必然成功。
7. 坚持教授的两个最终问题：单周期能否降低完整合格受力；同一患者少数重复周期能否利用历史进一步改善。几十次仿真试错不能写成新患者两三次即能学会。
8. 这次改变的是研究问题与实验设计，不是宣布PPO、Q或ILC失败或放弃学习。没有自动启动Stage2、长程PPO、最终Campaign或Git推送。

## OPEN_QUESTIONS — 尚未解决

- 新参考执行前，能否准确预测phase/full JF、JM、tracking及原motion门余量？完整闭环预测输入是否可获得，是否存在合法full-state live fork？
- 相同权限、相同新增真实物理预算下，学习残差是否比直接搜索和纯物理代理带来额外完整合格收益？
- 小样本下如何校准不确定性、防止优化器利用模型误差，如何区分新动作收益与学习贡献？
- 不同合法初态、患者和重复周期是否一致，累积探索负担如何计入，论文和真实硬件还缺何种验证？

## 研究时间线与引用

2026-10-14的canonical总结冻结B及18D证据边界；2026-10-17机制研究将重点从单一smoothness移向姿态需求—allocation/feedback—contact；2026-10-19历史到下一trial研究给出有限history因果收益；近期PPO恢复、稳定性、STD/R4开发则区分任务能力与科学收益。以上时间来自现有报告而非推测实际运行时长；本轮不重写旧结论。

- [CURRENT_RESEARCH_BASELINE.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/CURRENT_RESEARCH_BASELINE.md)；SHA256 `ff2547a069c1c8fc5a700746881f5731841b99b019589c69c931820594d1f1d7`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/force_mechanism_waypoint_v3/REPORT.md)；SHA256 `a40867807e70f6319343df5e5166e4e81f6d111bc04931ef70ea53f29e2ccee1`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_overnight_research_retrospective_v1/REPORT.md)；SHA256 `8bf1a534230e71ff6fd910f07d905b5fb64d1a6e807b270ba486d74812c64948`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_history_to_next_trial_learning_v1/REPORT.md)；SHA256 `e3f589633a582f3014530e442454a0022f59eb13c9180485542c8fd65c2328bf`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_training_stability_reward_v1/REPORT.md)；SHA256 `f5a9cfbab6ebcb77cd6c4844143bba5523dc30df8d367776795e850dc0fae6be`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_autonomous_stability_reward_v1/REPORT.md)；SHA256 `976bdd6526786f410252d8689f37ca32c78cb0d4e812855571452deac1c67690`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/REPORT.md)；SHA256 `ddfa19b4c7cf7c2117af04af64d4355aa34ba36275d82461f9972213f500a479`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_autonomous_replication_v1/REPORT.md)；SHA256 `7e2646dab938168397b89eac674fe50052b98c4c600ebc6715b0379e23a77735`。

本条引用的是已定位报告，具体raw与源码闭包将在本轮恢复审计中另行核验；报告存在不自动等于所有原始轨迹已在云端恢复。


---

## 2026-10-21T17:11:18.141990+00:00 UTC — Learning-Guided v1 结果注释（不改写先前反思）

CONFIRMED：三臂实际优化attempt {'A': 20, 'B': 20, 'C': 20}；同链合格H150 JF 1402.643211，最佳完整合格新candidate收益 2.553483 N·s。固定12次C严格超过A/B=False；全分配=False。预算/native、原scorer与旧包保护见本轮审计。

CONFIRMED补充：本轮完整但原motion失败ID=['OPTIMIZATION_B_013', 'OPTIMIZATION_C_015']；C事前预测motion可过而实际原门失败ID=['OPTIMIZATION_C_015']。同参数跨臂重复按一个动作/状态组理解；失败不入正式收益排名，未放宽原raw门。学习motion余量可靠性NOT_ESTABLISHED。

SUPPORTED：当前受限二维参数可用于局部协调改进；Learning残差是否增加优化价值按真实预算结果保留，不由训练或拟合精度推断。

HYPOTHESIS：跨状态闭环响应、可测motion余量、失败域与少次重复运动仍待独立检验。

DECISION：本轮STOP；下一步优先闭环响应/余量和合法状态覆盖，未启动新研究、Stage2或最终Campaign。

OPEN_QUESTIONS：学习额外价值的一致性、患者覆盖、累计探索成本、临床motion依据和host/硬件资格仍未建立。

研究包：/home/hank/ihear-lab/learning_guided_motion_improvement_v1；REPORT SHA256 `399bba58e6a5151dc58d0da5d2afa752219b606f34d0572fa58fa6f4169095d0`；固定源码commit `1adb1de177d6f5f32de6d01c4e629cbfae9ce121`；原反思保持原文。


---

## 2026-10-21T18:08:55.399309+00:00 UTC — Autonomous Coordination & Learning v2 开始（ACTIVATION）

状态：RUNNING；研究包：`/home/hank/ihear-lab/autonomous_coordination_learning_v2`。上一轮二维局部优化中，名义物理与GP残差均达到约1400.09 N·s，残差数值预测更准却未形成额外优化收益。本轮首先检验：限制是否来自协调表示及其真实执行权限，而非预先归咎Learning。主假设是分离髋膝联合路径、局部时间安排与通过速度，可增加原安全链能够执行的有效运动；同时用同运动族的坐标变换区分表示效率与新增权限。随后按实测吞吐比较直接搜索、物理引导、Learning辅助及新语义scratch PPO，保留完整任务、原motion门、失败样本和等物理预算；冻结后再打开独立合法prefix验证。硬截止为原T0+10小时，最终独立重算并STOP。


---

## 2026-10-21T21:07:34.334889+00:00 UTC — Autonomous Coordination & Learning v2 机制转向

状态：RUNNING；研究包：`/home/hank/ihear-lab/autonomous_coordination_learning_v2`。新表示八方向已真实执行，三臂共同设计得到小幅额外降力；首个Learning改变选点的完整任务却未通过原motion门。峰值定位到髋膝近等角时原clearance包络最低端点切换，中心差分曲率触发瞬时控制修正；以已记录因果充分输入重放，曲率和修正量均复现。此发现提示部分运动质量失败来自既有反馈计算的非光滑性，不能笼统归于患者物理或学习能力。原物理、安全与scorer保持，安排四个有界时序干预检验敏感性；尚不据事后诊断宣称前瞻预测或少次患者适应。详细证据留在独立包。


---

## 2026-10-22T03:02:29.176365+00:00 UTC — Autonomous Coordination & Learning v2 结束

状态：STOP；研究包：`/home/hank/ihear-lab/autonomous_coordination_learning_v2`。本轮累计8.893小时、物理START=285。完成同运动族坐标核验、八方向实签参考核验与等预算A/B/C优化；PPO及冻结合法prefix只按实际结果报告。最佳新增modal完整合格JF=1398.034615 N·s、JM=107.971017 Nm·s，动作身份MOTION_MARGIN_BACKOFF_RPASS_020。A/B/C最佳JF分别为{'A': 1398.5491214314125, 'B': 1399.33552280347, 'C': 1399.1883230336996}，PPO已评价mean最佳JF为1399.9182718110073。初版固定时长certificate拒绝与逐关节终点缺锁已定位并修复；粗名义代理的实签参考映射是关键缺口；另定位原clearance包络差分跨分支触发jerk冲击，原guard保持，时序干预按实际结果报告。事后重建不能冒充前瞻预测。补充参考响应模型与同数据传统成本模型的实测状态为EXECUTED。保留JF/JM/原生motion取舍及失败partial，未建立少次患者适应或一般Learning优势。下一步先在独立协议检验非光滑clearance反馈处理且不放宽原阈值，再考察因果历史对实际参考与可部署motion余量预测的额外价值。独立raw/scorer重算、历史保护审计与STOP封包见REPORT；无Git、硬件或自动下一轮。


---

## 2026-10-22T04:21:34+00:00 UTC — Representation & Execution v3 开始

本轮以完整旧18D能否复现当前最佳运动为首要问题，先恢复实际参数域、waypoint、通过速度与scheduler权限，分层核对参考、执行和物理结果；只有同权限同预算才比较搜索效率。第二优先复用C19与PPO第9次raw，区分clearance包络不可微、差分尖峰和真实控制响应，必要时做有界配对干预。硬上限3小时，保留原物理、安全、motion与scorer及全部失败，所有新实现和证据存入独立包，不启动长程训练或自主队列。


---

## 2026-10-22T05:12:29.605093+00:00 UTC — Representation & Execution v3 结束

本轮完成完整旧18D恢复、零物理构造核验及20次有界物理任务。新表示在逐关节终点锁和时长编译上确有旧合同无法逐参考复现的能力，但旧18D加固定H150已得到JF1398.137075的合格近似，仅距新最佳0.102459N·s，JM较高，性能及搜索效率优势仍未建立。C19微参数配对在时长和请求不变时改变差分跨分支、实际扭矩与Human运动，三个motion失败完整保留；guard物理中介受支持但未做单独替换。原scorer和receipt全量重算通过，旧包与规则保持。下一步先对齐编译权限、推导端点分支保护，再决定Learning；本轮STOP，无自动下一轮。


---

## 2026-10-22T05:32:58.707100+00:00 UTC — Constraint Geometry & Learning v4 开始

本轮优先研究clearance最低袖套端点切换：已有证据说明跨分支差分会触发实际扭矩和motion资格变化，必须先区分几何不可微、估计误差、控制投影、饱和与Human瞬态。目标是在原物理、任务和保护阈值不变的条件下，检验双端点光滑约束是否有可核验的保守关系；若不能成立，保留原guard并转向分支感知的预测与优化。随后用同权限、同真实物理预算检查完整合格运动与低force收益，只有出现明确决策缺口才开展Learning。所有修改隔离、失败完整计账，冻结后独立验证，十小时硬截止不因恢复重置，最终STOP。


---

## 2026-10-22T06:58:51.426817+00:00 UTC — Constraint Geometry & Learning v4 结束 [constraint_geometry_learning_v4_20261022T053258Z]

本轮完成双端点解析导数与采样间条件推导、原guard精确重放、六个未见局部点预测、终点锁/时长编译2×2物理消融及三个冻结合法prefix复核。点态等价成立，但observer/actuator误差界和可行backup尚未闭包，故未物理替换guard。局部分支模型6/6吻合，未证明独立Learning或优化效率收益。保留终点锁而恢复旧H150时长的开发候选JF1397.383797、JM108.639143，力矩代价上升，跨状态资格按冻结结果限定。全部38次物理尝试和失败partial计账，原门不变；raw/scorer、历史SHA和owned退出均已核验。下一步先补保护界与同权限状态相关运动余量，再决定Learning。本轮STOP，无硬件、Stage2或自动下一轮。


---

## 2026-10-22T16:21:13.763847+00:00 UTC — Constraint Geometry & Learning v4 流程回顾

上一轮开始、结束和技术缺口已记录，但未明确说明提前结束的流程问题。日志结束条目距ACTIVATION约1.43小时，最终END封包约1.50小时，并非授权的10小时。双端点仅点态等价，采样间和最终actuator保护未闭合；替代guard物理、同权限优化收益、独立Learning及PPO增量均未运行或未建立。六个局部点吻合与force/moment取舍不能替代这些分支。后续采用动态队列，某分支受阻或一次实验结束后继续评估其它有信息价值的方向；也不为耗时重复计算。


---

## 2026-10-22T16:21:13.763847+00:00 UTC — Smoothness-Aware Control & Long-Horizon Critic v5 开始 [smoothness_critic_research_v5_20261022T162113Z]

本轮优先验证实际Human运动和cuff施力平顺性：比较强固定、参考平顺化及原guard完整生效下的提前协调，保留完整任务、原motion门和所有失败。随后以相同决策及剩余完整任务费用检验短视；仅在有真实排序或决策缺口时开展长期Critic及Learning增量。动态队列按吞吐、证据与剩余预算调整；T0起最多10小时，截止不重置。所有新源码和raw隔离，历史只读，最终核验并STOP。


---

## 2026-10-22T16:42:34.520115+00:00 UTC — v5 转折：rolling交接参考与实际瞬态

强固定方案的TASK内原guard未激活，但十处rolling交接出现连续参考q样本保持、dq仍非零；原receipt核对与固定时间窗重算显示，大部分未滤波jerk能量集中在邻近窗口。这与C19端点跨支冲击是不同机制，窗口重合不等于已识别中介比例。本轮保留执行链，追加合法通过速度的去程/回程配对干预，检验提前减小交接失配能否改善真实Human与wrench；同时继续已登记真实tail诊断，不从参考曲线更平滑推定实际收益。


---

## 2026-10-22T17:58:14.637548+00:00 UTC — v5 转折：真实rolling续跑触发成本Critic

两个合法中间父状态各八个候选均通过原门，单次决策后恢复同一B滚动后续策略，真实续跑确认0.5秒与完整tail选择不同：去程JF差约0.043N·s，回程约1.554N·s，并伴随JM取舍。回程延长到1秒已选对，故不能直接推断复杂Critic必要。本轮已登记小型分量成本模型、训练固定动作及1秒lookahead对照，先冻结权重再打开新prefix测试；实际物理节省仍未建立。原安全、原积分与历史保持，另一主线继续优化已观察到的交接平顺性收益。


### v5 转折：Critic尾部费用与已发生motion失败 — 2026-10-22T20:56:48.766031+00:00

v5成本Critic在首个冻结去程测试中未改变short选择，并选到原motion失败轨迹。复核显示guard冲击在决策后0.18秒、H=0.5秒前已令加速度峰值门失败；当前状态未显式记录累计运动极值与guard历史，且训练只有合格样本，不能把尾部force成本预测等同失败价值。输入还出现15ms相位时间域外偏移。保留负结果与冻结模型，继续回程和独立物理验证，暂不扩大模型；后续优先补足因果执行状态、失败标签和显式风险处理，不能靠未来资格mask或更大PPO掩盖问题。

研究包：`smoothness_critic_research_v5/`；ACTIVATION：`smoothness_critic_research_v5_20261022T162113Z`。


---

## 2026-10-22T23:33:04.898456+00:00 UTC — Smoothness-Aware Control & Long-Horizon Critic v5 结束 [smoothness_critic_research_v5_20261022T162113Z]

本轮封包前实际约7.20小时，完成189次MuJoCo物理执行并计账，保留全部失败。交接降速、pattern与相位组合在四个冻结prefix均通过原门；组合相对强固定降低实际jerk和施力波动，JF小升、JM下降。真实B策略续跑确认局部短视；Critic回程选对，但固定动作和1秒窗口相同，去程仍失败，常量字段诊断也未改变选择，真实尝试节省为零。分支模型独立信息收益未建立，PPO仅作冻结与显式接口修复。原guard、阈值及历史未改；原scorer、raw、source、日志和owned退出已核验，详细边界见独立研究包。最终封包STOP，无自动下一轮。


---

## 2026-10-26T09:55:17+00:00 UTC — Smoothness Critic Integration v6 开始

已知：v5提前协调改善实际平顺性，但组合方案增加累计JF；回程Critic尚未超过固定动作或1秒短窗，出程还选择了已发生motion失败的动作。本轮假设是因果累计风险状态、合理时间尺度和一致后续策略能改善候选决策。先只读核验旧包与raw，再以独立模型、固定菜单和原资格门作未见状态冻结评价；保留强平顺性及1秒基线，不预设Learning收益。未完成：截断的主线D后续要求待补充，节省物理尝试须另立有限协议。唯一T0为09:55:17 UTC，硬截止15:55:17 UTC；全部新结果存入独立v6包，旧包不改写。


---

## 2026-10-26T10:55:46.035078+00:00 UTC — v6 转折：失败父状态去重与验证边界

已确认：共同COMPOSE后续的两个出程菜单，0.5秒与1秒选择均比完整菜单多约1.31N·s；固定规则可能已足够。风险数据再审计发现TAILRESCUE与TAILOT是同一父状态，先前按job分组的5/5检出不能作独立验证，已封存并纠正；五个失败实际上仅覆盖一个状态族。当前假设是因果风险头能识别新状态中已发生的峰值失败，但尚无独立正例支持。继续冻结新出程风险检验与平顺性候选复核；不因单项模型受限停止其它研究，也不把旧状态重复称作未见测试。


---

## 2026-10-26T12:03:44.660342+00:00 UTC — v6 转折：平顺性后续策略必须匹配真实上游

已确认：三个B上游回程开发菜单的平顺性候选均因excursion不合格，不能由低尾部成本补偿。首个实际执行COMPOSE上游的新回程菜单则全部过原门；其完整原B与COMPOSE轨迹均与已有整策略逐字段一致，资格恢复并非修改阈值。研究因此保留全部旧失败，加入已执行上游身份和累计历史，再从策略一致的合法状态冻结验证；原B完整参照独立计费，父采样prefix不冒充完整成功。累计风险库已覆盖12个状态族、其中3族有失败，但留族检验仍有明显漏检，可靠性尚未建立。


## 2026-10-26T13:18:58.160772+00:00 UTC — v6 转折：完整尾部排序仍被强阶段规则覆盖

已知主模型、菜单和选择规则已在测试前冻结。实际四个新合法prefix中，Critic全部通过原门并恢复比1秒短窗更低的剩余JF，但四组真实轨迹均与训练时固定的阶段规则一致；名称别名不算决策增量。这支持考虑完整尾部，却未支持复杂学习不可替代。本轮暂停该成本模型扩张，不换Q或PPO名称继续训练；继续检验旧B出程风险、真实事前筛选和单一有界传统交接组合。精确在线native资格与跨Human有效性仍未完成，后续选择以完整motion、JF/JM和平顺性共同证据为准。


## 2026-10-26T15:00:54.106866+00:00 UTC — v6 转折：配置微扰不构成独立状态

实际raw核验发现，最后一次声明为局部微扰的新配置并未改变真实决策prefix，重放了已暴露TAILOT父状态。该分支的独立验证声明立即封存并降为训练父状态重放，不用配置差异冒充状态差异，也不重训覆盖结果。风险头在重放中避开了已发生运动失败，但固定动作和直接guard规则相同，独立出程修复仍未验证。主四个冻结新状态的身份核验有效、选择仍无强规则之外的增量；固定阶段组合已有真实JF/JM收益。所有物理派发停止，继续独立重算与保护封包。


## 2026-10-26T15:21:06.237602+00:00 UTC — v6 结束 [smoothness_critic_integration_v6_20261026T095517Z]

已知v5平顺性收益已由原raw和匹配完整执行复核。本轮实际完成149次MuJoCo尝试，9353000个新增native步；主Critic在4个冻结新prefix中4个通过原门，超越1秒与强固定阶段规则的独立收益状态为0。修正了缩放、因果历史和后续标签，保留旧上游不匹配的完整失败；风险模型仍漏检，不能替代原门。传统事前筛选实际省略7个唯一候选续跑，尚无整体摊销净节省证明。固定阶段组合在两组配对中通过原门并同时降低JF/JM。最后配置微扰实际为训练父状态重放，已剔除独立证据。未完成精确在线native资格、独立出程修复与患者泛化。下一步先核验真实新状态及强规则外排序变化，再决定学习投入。owned已归零，本轮STOP。


---

## 2026-10-26T15:56:51.846771+00:00 UTC — Autonomous Learning & Smoothness v7 开始（ACTIVATION）

本轮延续v5/v6平顺性与Critic证据，先以原guard、完整任务和原motion门开展RETURN交接时间的同权限配对优化，建立最强传统参照。Learning仅针对真实排序或历史适应缺口登记后实验，比较固定规则、短期成本与完整续跑，区分预测、决策增量、计算效率和独立泛化。保留负结果、失败及partial，主Agent统一登记分支和预算；唯一T0起12小时硬截止不因恢复重置，历史只读，不启动硬件、Stage2或自动下一轮。


---

## 2026-10-26T16:40:25.978079+00:00 UTC — v7 转折：时间轴只有负担取舍，转向协调交互

首组RETURN局部时间扫描已完整执行：四个扰动均通过原门并保留冻结平顺性界，实际参考与物理轨迹均改变，但JF下降伴JM增加，反向扰动亦相反，未得双成本改善。强固定、参考平滑及提前协调的excursion失败均保留，所有分支仍属同一已暴露开发父状态。下一项已登记相对姿态与通过速度的小型配对矩阵，检验不同协调机制；同时准备原有不同Human场景的冷启动接口及身份链，保留条件未打开，不以换状态或同结果重用制造Learning增量。


---

## 2026-10-26T17:20:12.714157+00:00 UTC — v7 转折：同分叉响应模型与简单方法等价

第二组RETURN相对姿态/通过速度八个新点均通过原门，仍无JF/JM双降。九点二维数据的完整分叉快照文件严格相同，才允许合并；跨组主机日志等价未完成，时间轴没有强行加入训练。真实训练的小GP与同数据二次响应面提出同一动作，二次面诊断误差更低，预测收益仅约0.001N·s，尚无Learning独立增量。现冻结共同动作前瞻执行及另一个传统时间/速度组合；随后检查固定菜单在真实不同Human下的排序，不把同父重放当独立验证。


---

## 2026-10-26T18:15:01.856474+00:00 UTC — v7 转折：真实Human暴露两类资格失败

预登记的不同Human冷启动已产生真实模型与因果估计差异。light_soft原B通过，七个非B方案全部因excursion失格；native分解确认主要来自RETURN膝下沿，phase差0.511°超过原0.5°门。heavy_stiff原B通过，七个非B方案在RETURN5因原膝reference恒定前提不满足而中止，partial全保留且不排名。名义双降不具跨Human资格。下一步先补原H150强参照，再检验合法内部路径与可选timing适用规则；原源码、断言、任务及安全门不改，规则修复不记Learning成果。


### v7 转折：强对照与优化器机制（2026-10-26 UTC）

三个已暴露 Human 的原 H150 对照已补齐：名义及轻型均完整但膝 excursion 超界，重型完整合格；因此不能继承其历史资格，也不能把重型 modal 失败说成原任务无传统解。现分别检验合法 RETURN 内部路径与可选末端 timing，原断言及 motion 门不变。两轮 PPO 离线诊断确认联合裁剪影响私有副本 Adam 步长，但一组整批 actor 目标反而变差；仅有八次诊断更新，无新 rollout 或部署收益。后续先检查简单规则等效性与冻结独立状态，不以更多拟合掩盖负结果。


### v7 转折：已发生负担与更早传统介入（2026-10-26 UTC）

重型晚启策略的髋膝jerk平方和约95%/97%已在OUT1前发生，推动单独登记OUT0更早介入。三个旧raw对照逐值复现后，早启原H150保留完整资格，jerk从1392/3865降至319/663，力变化率从65.71降至21.65；JF降4.883，JM增0.205。这属于既有传统控制器部署时机改变，不能记Learning增量或旧OUT1修复。名义早启H150仍失格，早启phase有额外质量代价；轻型与冻结独立验证继续，失败不换状态，guard中介原因尚未确认。


### v7 转折：冻结状态结果与参数共变（2026-10-26 UTC）

两个预承诺名义prefix已实际执行，native、因果状态及真实前缀均不互为别名。传统时间/速度组合在原任务及额外质量界内保留JF/JM微小双降；GP与二次面同选动作仍为JM微升，无独立增量。原动作留一验证未检验speed水平间曲率，不能拿低误差作控制成功。PPO原NATIVE可复算，完整motion桥接却缺真实RL接口证据，未补造报告。现补最强早启phase与简单T方案，再按事前固定K/D交叉条件分辨anthropometry和被动参数包；所有原失败保留，不换测试状态。


### 2026-10-26T23:28:18.583983+00:00 — v7 最终结果与负结果（封包核验）

本轮170次物理尝试全部闭合，新增12,997,720 native独立复算，历史全量哈希通过。传统组合两冻结前缀微双降，几何变体反转；重型早启H150改善平顺性但增加JM。GP与二次面同选且JM失败；两stump交叉状态benefit均零、不及常数B，未部署。八私有Adam仅为诊断，fresh PPO公平桥接未闭合。轻型路径与四合法时间因子全失格。失败、partial和存证缺口保留；下一步先查完整动作排序和RL接口，封包后STOP，无自动下一轮。
